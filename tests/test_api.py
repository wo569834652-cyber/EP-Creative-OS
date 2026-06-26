import os
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///./test_ep_creative_os.db"
Path("test_ep_creative_os.db").unlink(missing_ok=True)

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_health_ok(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_seed_ep_and_songs(client):
    ep = client.get("/api/ep")
    assert ep.status_code == 200
    assert ep.json()["title"] == "GROWING UP.EXE"

    songs = client.get("/api/songs")
    assert songs.status_code == 200
    assert len(songs.json()) >= 7


def test_suno_and_cubase_pack_export(client):
    song_id = client.get("/api/songs").json()[0]["id"]

    suno = client.post(f"/api/songs/{song_id}/suno")
    assert suno.status_code == 200
    assert "Primary genre" in suno.json()["style_prompt"]

    pack = client.post(f"/api/songs/{song_id}/exports/cubase-pack")
    assert pack.status_code == 200
    assert pack.headers["content-type"].startswith("application/zip")
    assert len(pack.content) > 1000


def test_chat_without_key_is_friendly(client):
    song = client.get("/api/songs").json()[0]
    ep = client.get("/api/ep").json()
    response = client.post(
        "/api/chat",
        json={
            "ep_id": ep["id"],
            "song_id": song["id"],
            "mode": "critique",
            "user_message": "看看副歌方向",
        },
    )
    assert response.status_code == 200
    assert "DEEPSEEK_API_KEY" in response.json()["assistant_message"]
