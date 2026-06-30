import os
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///./test_ep_creative_os.db"
os.environ["DEEPSEEK_API_KEY"] = ""
os.environ["DEEPSEEK_MODEL"] = "deepseek-v4-pro"
os.environ["DEEPSEEK_CONTEXT_WINDOW"] = "1000000"
Path("test_ep_creative_os.db").unlink(missing_ok=True)

import io
import json
import zipfile

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def access_song(client):
    songs = client.get("/api/songs").json()
    return next(song for song in songs if song["title"] == "访问失败")


def test_health_ok(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_seed_ep_and_access_failed_song(client, access_song):
    ep = client.get("/api/ep")
    assert ep.status_code == 200
    assert ep.json()["title"] == "GROWING UP.EXE"
    assert access_song["current_stage"] == "diagnosis"


def test_can_create_local_ep_project_and_filter_songs(client):
    created_ep = client.post(
        "/api/eps",
        json={
            "title": "TEST EP",
            "one_liner": "测试新建项目",
            "core_theme": "",
            "world_view": "",
            "emotional_keywords": [],
            "aesthetic_keywords": [],
            "sonic_layers": {},
            "narrative_arc": "",
            "song_list": [],
        },
    )
    assert created_ep.status_code == 200
    ep_id = created_ep.json()["id"]

    created_song = client.post(
        "/api/songs",
        json={
            "ep_id": ep_id,
            "title": "TEST SONG",
            "function_in_ep": "测试歌曲",
            "concept": "",
            "emotional_goal": "",
            "bpm": 92,
            "genre_direction": "",
            "language_plan": "",
            "lyrics": "",
            "style_prompt": "",
            "lyrics_prompt": "",
            "notes": "",
            "current_stage": "diagnosis",
            "stage_status": "not_started",
            "locked_hook": "",
            "current_structure_route": "",
            "current_prompt_pack_id": None,
        },
    )
    assert created_song.status_code == 200

    filtered = client.get(f"/api/songs?ep_id={ep_id}")
    assert filtered.status_code == 200
    titles = [song["title"] for song in filtered.json()]
    assert titles == ["TEST SONG"]

    eps = client.get("/api/eps")
    assert any(item["title"] == "TEST EP" for item in eps.json())


def test_v1_session_creates_pending_artifact(client, access_song):
    response = client.post(
        f"/api/songs/{access_song['id']}/sessions",
        json={
            "output_mode": "stage_fit",
            "user_goal": "推进访问失败",
            "user_message": "先诊断这首歌的问题",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["stage"] == "diagnosis"
    assert data["artifacts"]
    assert data["artifacts"][0]["status"] == "pending"
    assert data["stage_recommendation"]["next_stage"] == "hook_lab"
    assert data["artifacts"][0]["content"]["source"] == "local_fallback"
    client.post(f"/api/artifacts/{data['artifacts'][0]['id']}/discard")


def test_ai_lyrics_stage_creates_real_lyrics_artifact(client, access_song, monkeypatch):
    async def fake_chat(self, messages, temperature=0.7, max_tokens=1200, json_mode=False):
        return (
            True,
            """
            {
              "assistant_message": "AI 已根据 Hook 和结构写出完整歌词草稿。",
              "hook": "别关掉我",
              "lyrics": "[Verse]\\n雨声把房间调暗\\n我把旧消息读到一半\\n[Chorus]\\n别关掉我\\n别关掉我\\n让我在你心里慢慢亮着",
              "section_notes": [{"section": "Verse", "purpose": "建立雨夜画面"}],
              "singability_risks": ["副歌第二句还可以更短"],
              "revision_targets": ["下一轮压缩主歌长句"],
              "next_actions": ["保存歌词草稿", "进入 Suno Prompt 实验室"]
            }
            """,
        )

    monkeypatch.setattr("app.services.session_engine.DeepSeekClient.chat", fake_chat)
    client.put(
        f"/api/songs/{access_song['id']}",
        json={
            **access_song,
            "current_stage": "lyrics_draft",
            "locked_hook": "别关掉我",
            "current_structure_route": "classic_pop",
            "change_summary": "prepare ai lyrics test",
        },
    )

    session = client.post(f"/api/songs/{access_song['id']}/sessions", json={"user_message": "写一版更像雨夜卧室的歌词"})
    assert session.status_code == 200
    artifact = session.json()["artifacts"][0]
    assert artifact["artifact_type"] == "lyrics_draft"
    assert artifact["content"]["source"] == "ai"
    assert "别关掉我" in artifact["content"]["lyrics"]
    assert "Lyrics Prompt" not in artifact["content"]["lyrics"]

    accepted = client.post(f"/api/artifacts/{artifact['id']}/accept")
    assert accepted.status_code == 200
    song = client.get(f"/api/songs/{access_song['id']}").json()
    assert "雨声把房间调暗" in song["lyrics"]


def test_ai_lyrics_preserves_locked_hook_with_postprocess(client, access_song, monkeypatch):
    async def fake_chat(self, messages, temperature=0.7, max_tokens=1200, json_mode=False):
        return (
            True,
            json.dumps(
                {
                    "assistant_message": "AI 写出一版歌词，但忘了锁定 Hook。",
                    "hook": "别的句子",
                    "lyrics": "[Verse]\n雨停在窗边\n我把没说完的话留给房间\n[Chorus]\n我还在这里\n我还在这里",
                    "section_notes": [],
                    "singability_risks": [],
                    "revision_targets": [],
                    "next_actions": ["保存歌词草稿"],
                },
                ensure_ascii=False,
            ),
        )

    monkeypatch.setattr("app.services.session_engine.DeepSeekClient.chat", fake_chat)
    current = client.get(f"/api/songs/{access_song['id']}").json()
    client.put(
        f"/api/songs/{access_song['id']}",
        json={
            **current,
            "current_stage": "lyrics_draft",
            "locked_hook": "别关掉我",
            "current_structure_route": "classic_pop",
            "change_summary": "prepare locked hook test",
        },
    )
    session = client.post(f"/api/songs/{access_song['id']}/sessions", json={})
    artifact = session.json()["artifacts"][0]
    assert "别关掉我\n别关掉我" in artifact["content"]["lyrics"]
    assert artifact["content"]["postprocess_notes"]
    client.post(f"/api/artifacts/{artifact['id']}/discard")


def test_ai_lyrics_quality_gate_retries_weak_draft(client, monkeypatch):
    calls = {"count": 0}

    async def fake_chat(self, messages, temperature=0.7, max_tokens=1200, json_mode=False):
        calls["count"] += 1
        if calls["count"] == 1:
            return (
                True,
                json.dumps(
                    {
                        "assistant_message": "第一版太泛。",
                        "hook": "别关掉我",
                        "lyrics": "[Verse]\n世界太吵\n我落在心上\n[Chorus]\n别关掉我",
                        "quality_score": 35,
                        "section_notes": [],
                        "singability_risks": [],
                        "revision_targets": ["加入具体画面"],
                        "next_actions": ["重写"],
                    },
                    ensure_ascii=False,
                ),
            )
        return (
            True,
            json.dumps(
                {
                    "assistant_message": "已返工为更具体的歌词。",
                    "hook": "别关掉我",
                    "lyrics": (
                        "[Verse]\n旧对话在床头亮着灰光\n通勤卡还贴着昨晚的体温\n我把钥匙放回外套口袋\n像把一个旧自己重新登录\n\n"
                        "[Pre-Chorus]\n门外的风不回答\n屏幕只闪一下\n\n"
                        "[Chorus]\n别关掉我\n别关掉我\n让我在你沉默之前\n再亮一秒\n\n"
                        "[Bridge]\n如果回忆只是缓存\n我也先不清空它\n\n"
                        "[Final Chorus]\n别关掉我\n别关掉我\n这次我不解释\n只把灯留小"
                    ),
                    "quality_score": 86,
                    "section_notes": [{"section": "Chorus", "purpose": "短 Hook 重复"}],
                    "singability_risks": [],
                    "revision_targets": ["下一轮检查副歌旋律密度"],
                    "next_actions": ["保存歌词"],
                },
                ensure_ascii=False,
            ),
        )

    monkeypatch.setattr("app.services.session_engine.DeepSeekClient.chat", fake_chat)
    ep = client.post(
        "/api/eps",
        json={
            "title": "QUALITY GATE EP",
            "one_liner": "测试歌词质检",
            "core_theme": "",
            "world_view": "",
            "emotional_keywords": [],
            "aesthetic_keywords": [],
            "sonic_layers": {},
            "narrative_arc": "",
            "song_list": [],
        },
    ).json()
    song = client.post(
        "/api/songs",
        json={
            "ep_id": ep["id"],
            "title": "别关掉我",
            "function_in_ep": "旧关系无法访问后的卧室独白",
            "concept": "旧对话无法重新打开，像登录失败一样卡在卧室灯光里",
            "emotional_goal": "低电量、克制、仍然舍不得退出",
            "bpm": 92,
            "genre_direction": "bedroom pop / lo-fi electronic",
            "language_plan": "",
            "lyrics": "",
            "style_prompt": "",
            "lyrics_prompt": "",
            "notes": "",
            "current_stage": "lyrics_draft",
            "stage_status": "not_started",
            "locked_hook": "别关掉我",
            "current_structure_route": "classic_pop",
            "current_prompt_pack_id": None,
        },
    ).json()
    session = client.post(f"/api/songs/{song['id']}/sessions", json={"user_message": "写一版不要套话的歌词"})
    assert session.status_code == 200
    artifact = session.json()["artifacts"][0]
    assert calls["count"] == 2
    assert artifact["content"]["ai_retry_count"] == 1
    assert artifact["content"]["quality_score"] >= 70
    assert "旧对话在床头亮着灰光" in artifact["content"]["lyrics"]
    client.post(f"/api/artifacts/{artifact['id']}/discard")


def test_stage_confirm_blocks_when_artifacts_are_pending(client, access_song):
    session = client.post(f"/api/songs/{access_song['id']}/sessions", json={}).json()
    artifact_id = session["artifacts"][0]["id"]

    blocked = client.post(f"/api/songs/{access_song['id']}/stage/confirm", json={"next_stage": "hook_lab"})
    assert blocked.status_code == 409
    assert "待确认" in blocked.json()["detail"]

    client.post(f"/api/artifacts/{artifact_id}/discard")


def test_stage_confirm_requires_current_stage_artifact(client):
    ep = client.post(
        "/api/eps",
        json={
            "title": "STAGE GUARD EP",
            "one_liner": "测试阶段门禁",
            "core_theme": "",
            "world_view": "",
            "emotional_keywords": [],
            "aesthetic_keywords": [],
            "sonic_layers": {},
            "narrative_arc": "",
            "song_list": [],
        },
    ).json()
    song = client.post(
        "/api/songs",
        json={
            "ep_id": ep["id"],
            "title": "STAGE GUARD SONG",
            "function_in_ep": "",
            "concept": "",
            "emotional_goal": "",
            "bpm": 92,
            "genre_direction": "",
            "language_plan": "",
            "lyrics": "",
            "style_prompt": "",
            "lyrics_prompt": "",
            "notes": "",
            "current_stage": "hook_lab",
            "stage_status": "not_started",
            "locked_hook": "",
            "current_structure_route": "",
            "current_prompt_pack_id": None,
        },
    ).json()

    blocked = client.post(f"/api/songs/{song['id']}/stage/confirm", json={"next_stage": "structure_lab"})
    assert blocked.status_code == 409
    assert "还没有已保存" in blocked.json()["detail"]


def test_artifact_accept_lock_and_stage_confirm(client, access_song):
    session = client.post(f"/api/songs/{access_song['id']}/sessions", json={}).json()
    artifact_id = session["artifacts"][0]["id"]

    accepted = client.post(f"/api/artifacts/{artifact_id}/accept")
    assert accepted.status_code == 200
    assert accepted.json()["artifact"]["status"] == "accepted"
    assert accepted.json()["version_id"] is not None

    locked = client.post(f"/api/artifacts/{artifact_id}/lock")
    assert locked.status_code == 200
    assert locked.json()["artifact"]["locked"] is True

    advanced = client.post(f"/api/songs/{access_song['id']}/stage/confirm", json={"next_stage": "hook_lab"})
    assert advanced.status_code == 200
    assert advanced.json()["current_stage"] == "hook_lab"


def test_suno_prompt_packs_are_limited_and_recommended(client, access_song):
    response = client.post(f"/api/songs/{access_song['id']}/suno-prompt-packs")
    assert response.status_code == 200
    data = response.json()
    assert len(data["packs"]) <= 3
    assert data["recommended_variant"] == "primary"
    assert sum(1 for pack in data["packs"] if pack["recommended"]) == 1
    style = data["packs"][0]["style_prompt"]
    assert "BPM" in style
    assert "sonic identity" in style
    assert "arrangement movement" in style
    assert data["packs"][0]["style_specificity_score"] >= 70
    assert "Mandarin" not in style
    assert "Chinese" not in style
    assert "普通话" not in style
    assert "中文" not in style


def test_restore_version_reverts_song_snapshot_and_creates_new_version(client):
    ep = client.post(
        "/api/eps",
        json={
            "title": "RESTORE EP",
            "one_liner": "测试回溯",
            "core_theme": "",
            "world_view": "",
            "emotional_keywords": [],
            "aesthetic_keywords": [],
            "sonic_layers": {},
            "narrative_arc": "",
            "song_list": [],
        },
    ).json()
    song = client.post(
        "/api/songs",
        json={
            "ep_id": ep["id"],
            "title": "RESTORE SONG",
            "function_in_ep": "初始功能",
            "concept": "初始概念",
            "emotional_goal": "",
            "bpm": 92,
            "genre_direction": "",
            "language_plan": "",
            "lyrics": "old lyric",
            "style_prompt": "",
            "lyrics_prompt": "",
            "notes": "",
            "current_stage": "lyrics_draft",
            "stage_status": "not_started",
            "locked_hook": "old hook",
            "current_structure_route": "classic_pop",
            "current_prompt_pack_id": None,
        },
    ).json()
    first_version = client.get(f"/api/songs/{song['id']}/versions").json()[-1]
    updated = client.put(
        f"/api/songs/{song['id']}",
        json={
            **song,
            "lyrics": "new lyric",
            "locked_hook": "new hook",
            "current_stage": "suno_prompt_lab",
            "change_summary": "mutate before restore",
        },
    )
    assert updated.status_code == 200

    restored = client.post(f"/api/songs/{song['id']}/versions/{first_version['id']}/restore")
    assert restored.status_code == 200
    data = restored.json()
    assert data["lyrics"] == "old lyric"
    assert data["locked_hook"] == "old hook"
    assert data["current_stage"] == "lyrics_draft"
    versions = client.get(f"/api/songs/{song['id']}/versions").json()
    assert versions[0]["change_type"] == "restore"
    assert "回溯到" in versions[0]["summary"]


def test_generation_review_and_asset_bundle(client, access_song):
    review = client.post(
        f"/api/songs/{access_song['id']}/generation-reviews",
        json={
            "take_name": "Suno take 01",
            "text_feedback": "Hook 不够清楚，段落还可以。",
            "hook_accuracy": 2,
            "style_accuracy": 4,
            "section_structure": 4,
            "diction_singability": 3,
            "emotional_fit": 4,
            "production_usability": 3,
        },
    )
    assert review.status_code == 200
    assert review.json()["artifact_type"] == "generation_review"
    assert review.json()["content"]["next_revision_target"] == "hook_accuracy"

    upload = client.post(
        f"/api/songs/{access_song['id']}/assets",
        data={"role": "suno_midi"},
        files={"file": ("take.mid", b"MThd\x00\x00\x00\x06\x00\x01\x00\x01\x01\xe0MTrk\x00\x00\x00\x04\x00\xff/\x00", "audio/midi")},
    )
    assert upload.status_code == 200
    assert upload.json()["filename"] == "take.mid"

    bundle = client.post(f"/api/songs/{access_song['id']}/exports/asset-bundle")
    assert bundle.status_code == 200
    with zipfile.ZipFile(io.BytesIO(bundle.content)) as zf:
        names = set(zf.namelist())
    assert "song.md" in names
    assert "suno_prompt.md" in names
    assert "generation_reviews.md" in names
    assert "assets_manifest.json" in names
    assert "notes_for_cubase.txt" in names


def test_generation_review_uses_ai_when_available(client, access_song, monkeypatch):
    async def fake_chat(self, messages, temperature=0.7, max_tokens=1200, json_mode=False):
        return (
            True,
            """
            {
              "assistant_message": "AI 判断下一轮先改歌词咬字。",
              "next_revision_target": "lyrics",
              "next_revision_advice": "副歌保留 Hook，但把主歌长句拆短，让 Suno 更容易唱清楚。",
              "keep": ["Hook 情绪", "低密度编曲"],
              "change": ["主歌长句", "副歌前的铺垫"],
              "next_actions": ["修改歌词草稿", "重新生成 Lyrics Prompt"]
            }
            """,
        )

    monkeypatch.setattr("app.services.session_engine.DeepSeekClient.chat", fake_chat)
    review = client.post(
        f"/api/songs/{access_song['id']}/generation-reviews",
        json={
            "take_name": "Suno take ai",
            "text_feedback": "主歌唱不清，副歌情绪是对的。",
            "hook_accuracy": 4,
            "style_accuracy": 4,
            "section_structure": 3,
            "diction_singability": 2,
            "emotional_fit": 4,
            "production_usability": 3,
        },
    )
    assert review.status_code == 200
    data = review.json()
    assert data["content"]["source"] == "ai"
    assert data["content"]["next_revision_target"] == "lyrics"
    assert "主歌长句" in data["content"]["next_revision_advice"]


def test_chat_without_key_is_friendly(client, access_song):
    ep = client.get("/api/ep").json()
    response = client.post(
        "/api/chat",
        json={
            "ep_id": ep["id"],
            "song_id": access_song["id"],
            "mode": "critique",
            "user_message": "看看副歌方向",
        },
    )
    assert response.status_code == 200
    assert "DEEPSEEK_API_KEY" in response.json()["assistant_message"]
