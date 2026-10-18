from __future__ import annotations

import pytest

from noecho.api.app import create_app
from noecho.config import Settings


@pytest.fixture
def thread_id(client) -> int:
    r = client.post("/threads", json={"title": "Halvern Street garage"})
    assert r.status_code == 201
    return r.json()["id"]


def _post(client, tid, body, author="sample-user"):
    return client.post(f"/threads/{tid}/comments", json={"author": author, "body": body})


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["similarity"] == "tfidf-local"


def test_thread_crud(client, thread_id):
    assert client.get(f"/threads/{thread_id}").json()["title"] == "Halvern Street garage"
    assert [t["id"] for t in client.get("/threads").json()] == [thread_id]
    assert client.get("/threads/999").status_code == 404


def test_post_and_block_shows_the_matched_comment(client, thread_id):
    first = _post(client, thread_id, "The garage is two blocks from the tram stop.")
    assert first.status_code == 201
    first_id = first.json()["comment"]["id"]

    echo = _post(client, thread_id, "the garage is 2 blocks from the tram stop!")
    assert echo.status_code == 409
    gate = echo.json()
    assert gate["blocked"] is True
    assert gate["matched"]["id"] == first_id
    assert gate["matched"]["body"] == "The garage is two blocks from the tram stop."
    assert gate["score"] >= gate["threshold"]
    assert "author" not in gate["matched"]

    assert len(client.get(f"/threads/{thread_id}/comments").json()) == 1


def test_check_does_not_post(client, thread_id):
    _post(client, thread_id, "Ground-floor shops would keep the street active.")
    r = client.post(
        f"/threads/{thread_id}/check",
        json={"body": "Ground floor shops would keep the street active"},
    )
    assert r.status_code == 200
    assert r.json()["blocked"] is True
    assert len(client.get(f"/threads/{thread_id}/comments").json()) == 1


def test_listing_hides_author_and_supports_reverse(client, thread_id):
    bodies = ["Bus lanes speed up transit.", "Bike racks are full by noon.", "Fares went up."]
    for b in bodies:
        assert _post(client, thread_id, b).status_code == 201
    chrono = client.get(f"/threads/{thread_id}/comments").json()
    assert [c["body"] for c in chrono] == bodies
    assert all("author" not in c for c in chrono)
    rev = client.get(f"/threads/{thread_id}/comments", params={"order": "reverse"}).json()
    assert [c["body"] for c in rev] == bodies[::-1]
    assert (
        client.get(f"/threads/{thread_id}/comments", params={"order": "popular"}).status_code == 422
    )


def test_attribution_is_click_through(client, thread_id):
    cid = _post(client, thread_id, "Fares went up.", author="sample-user-09").json()["comment"][
        "id"
    ]
    assert "author" not in client.get(f"/comments/{cid}").json()
    r = client.get(f"/comments/{cid}/attribution")
    assert r.json() == {"comment_id": cid, "author": "sample-user-09"}


def test_claim_and_citation_flow(client, thread_id):
    cid = _post(client, thread_id, "The bridge opened in 1931.").json()["comment"]["id"]
    r = client.post(f"/comments/{cid}/claims", json={"text": "Opened 1931", "kind": "factual"})
    assert r.status_code == 201
    claim = r.json()
    assert claim["status"] == "unverified"

    url = f"/claims/{claim['id']}/citations"
    r = client.post(url, json={"url": "https://archive.example/bridge", "stance": "supports"})
    assert r.status_code == 201
    assert r.json()["status"] == "verified"

    dup = client.post(url, json={"url": "https://www.archive.example/bridge/", "stance": "refutes"})
    assert dup.status_code == 409
    assert dup.json()["error"] == "duplicate_citation"

    r = client.post(url, json={"url": "https://records.example/b", "stance": "refutes"})
    assert r.json()["status"] == "disputed"
    assert len(r.json()["citations"]) == 2

    listed = client.get(f"/comments/{cid}/claims").json()
    assert listed[0]["status"] == "disputed"


def test_opinion_claim_rejects_citation(client, thread_id):
    cid = _post(client, thread_id, "The bridge is ugly.").json()["comment"]["id"]
    claim = client.post(f"/comments/{cid}/claims", json={"text": "Ugly", "kind": "opinion"}).json()
    assert claim["status"] == "opinion"
    r = client.post(
        f"/claims/{claim['id']}/citations",
        json={"url": "https://a.example", "stance": "supports"},
    )
    assert r.status_code == 422
    assert r.json()["error"] == "opinion_claim"


def test_validation_errors(client, thread_id):
    assert _post(client, thread_id, "").status_code == 422
    assert client.post("/threads", json={"title": ""}).status_code == 422
    assert (
        client.post("/comments/999/claims", json={"text": "x", "kind": "factual"}).status_code
        == 404
    )


def test_no_popularity_fields_anywhere(client):
    """No schema property or query parameter carries a popularity signal."""
    spec = client.get("/openapi.json").json()
    names = {
        prop.lower()
        for schema in spec["components"]["schemas"].values()
        for prop in schema.get("properties", {})
    }
    for path in spec["paths"].values():
        for op in path.values():
            names |= {p["name"].lower() for p in op.get("parameters", [])}
    banned = ("vote", "like", "karma", "popular", "count", "rank", "reaction")
    assert not [n for n in names if any(b in n for b in banned)]


def test_llm_provider_must_be_none_in_this_release():
    with pytest.raises(RuntimeError):
        create_app(Settings(db_path=":memory:", llm_provider="some-provider"))
