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
from app.services.suno_engine import _recommend
from app.services.suno_routes import get_route_spec
from app.services.suno_validation import validate_lyrics_prompt, validate_style_prompt


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


def test_hook_lab_generates_versioned_variants_and_avoids_previous(client):
    ep = client.post(
        "/api/eps",
        json={
            "title": "HOOK VERSION EP",
            "one_liner": "测试 Hook 版本",
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
            "title": "夜班电梯",
            "function_in_ep": "从现实疲惫转入旧关系",
            "concept": "凌晨电梯里的人不想回家，也不想再解释",
            "emotional_goal": "低电量、克制、麻木",
            "bpm": 92,
            "genre_direction": "bedroom pop / lo-fi electronic",
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

    first = client.post(f"/api/songs/{song['id']}/sessions", json={"user_message": "先给一组稳定和创新 Hook"}).json()
    first_hooks = first["artifacts"][0]["content"]["hooks"]
    assert len(first_hooks) >= 5
    assert len({hook["hook_text"] for hook in first_hooks}) == len(first_hooks)
    assert all(hook["version_label"] for hook in first_hooks)
    assert all(hook["angle"] for hook in first_hooks)
    assert any(hook["innovation"] >= 3 for hook in first_hooks)

    second = client.post(f"/api/songs/{song['id']}/sessions", json={"user_message": "再换一组，不要重复上一轮"}).json()
    second_hooks = second["artifacts"][0]["content"]["hooks"]
    first_texts = {hook["hook_text"] for hook in first_hooks}
    second_texts = {hook["hook_text"] for hook in second_hooks}
    assert second["artifacts"][0]["content"]["avoid_previous_hooks"]
    assert second_texts != first_texts


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
    assert data["recommended_variant"] in {pack["variant"] for pack in data["packs"]}
    assert sum(1 for pack in data["packs"] if pack["recommended"]) == 1
    recommended = next(pack for pack in data["packs"] if pack["recommended"])
    style = recommended["style_prompt"]
    assert "BPM" in style
    assert "primary genre" in style
    assert "arrangement movement" in style
    assert recommended["style_specificity_score"] >= 70
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


def _create_harness_song(client, **overrides):
    ep = client.post(
        "/api/eps",
        json={
            "title": overrides.pop("ep_title", "HARNESS TEST EP"),
            "one_liner": "Harness loop tests",
            "core_theme": "",
            "world_view": "",
            "emotional_keywords": [],
            "aesthetic_keywords": [],
            "sonic_layers": {},
            "narrative_arc": "",
            "song_list": [],
        },
    ).json()
    payload = {
        "ep_id": ep["id"],
        "title": "Harness Song",
        "function_in_ep": "tests the closed-loop Suno prompt workflow",
        "concept": "a late-night room where one phrase keeps returning",
        "emotional_goal": "cold, restrained, intimate",
        "bpm": 92,
        "genre_direction": "bedroom pop / lo-fi electronic",
        "language_plan": "Chinese lyric with short English hook only",
        "lyrics": "[Verse]\nlate light on the desk\n\n[Chorus]\nstay with me\nstay with me",
        "style_prompt": "",
        "lyrics_prompt": "",
        "notes": "",
        "current_stage": "suno_prompt_lab",
        "stage_status": "not_started",
        "locked_hook": "stay with me",
        "current_structure_route": "classic_pop",
        "current_prompt_pack_id": None,
    }
    payload.update(overrides)
    response = client.post("/api/songs", json=payload)
    assert response.status_code == 200
    return response.json()


def test_suno_prompt_pack_contains_full_harness_fields(client):
    song = _create_harness_song(client)
    response = client.post(f"/api/songs/{song['id']}/suno-prompt-packs")
    assert response.status_code == 200
    pack = response.json()["packs"][0]
    for field in [
        "music_spec",
        "route_spec",
        "exclude_prompt",
        "advanced_settings",
        "validation",
        "source_trace",
        "variant_role",
    ]:
        assert field in pack
    assert pack["validation"]["score"] > 0
    assert pack["advanced_settings"]["style_influence"] is not None


def test_suno_feedback_changes_next_prompt_pack(client):
    song = _create_harness_song(client)
    review = client.post(
        f"/api/songs/{song['id']}/generation-reviews",
        json={
            "take_name": "feedback take",
            "text_feedback": "drums too heavy, vocal too sweet, Hook is unclear",
            "hook_accuracy": 2,
            "style_accuracy": 3,
            "section_structure": 3,
            "diction_singability": 3,
            "emotional_fit": 4,
            "production_usability": 3,
        },
    )
    assert review.status_code == 200
    data = client.post(f"/api/songs/{song['id']}/suno-prompt-packs").json()
    recommended = next(pack for pack in data["packs"] if pack["recommended"])
    style = recommended["style_prompt"].lower()
    lyrics = recommended["lyrics_prompt"].lower()
    exclude = recommended["exclude_prompt"].lower()
    assert "drums softened" in style
    assert "less sweet" in style or "restrained vocal" in style
    assert lyrics.count("stay with me") >= 2
    assert "heavy drums" in exclude
    assert recommended["source_trace"]["feedback_used"]


def test_all_structure_routes_have_distinct_prompt_behavior(client):
    expectations = {
        "scene_cut": ["scene", "cut", "image transition"],
        "body_memory": ["breath", "body", "tactile", "movement"],
        "through_composed": ["through-composed", "echo", "reduced repetition"],
    }
    for route in ["classic_pop", "loop_mantra", "scene_cut", "error_system", "body_memory", "through_composed"]:
        song = _create_harness_song(client, title=f"Route {route}", current_structure_route=route, ep_title=f"EP {route}")
        pack = client.post(f"/api/songs/{song['id']}/suno-prompt-packs").json()["packs"][0]
        combined = f"{pack['style_prompt']} {pack['lyrics_prompt']} {pack['route_spec']['arrangement_motion']}".lower()
        if route in expectations:
            assert all(term in combined for term in expectations[route])
        if route != "error_system":
            assert "access failure" not in combined
            assert "failed-login" not in combined
            assert "denial motif" not in combined


def test_validation_blocks_language_label_pollution(client):
    song = _create_harness_song(
        client,
        genre_direction="Mandarin Chinese bedroom pop / 中文 R&B",
        emotional_goal="普通话 cold intimate vocal",
    )
    pack = client.post(f"/api/songs/{song['id']}/suno-prompt-packs").json()["packs"][0]
    style = pack["style_prompt"]
    assert "Mandarin" not in style
    assert "Chinese" not in style
    assert "普通话" not in style
    assert "中文" not in style
    assert pack["validation"]["warnings"]
    assert "primary genre" in style


def test_style_validator_blocks_actual_language_label_leak():
    music_spec = {
        "primary_genre": "bedroom pop",
        "secondary_genre": "lo-fi electronic",
        "bpm": 92,
        "instrumentation": ["dry kick"],
        "source_notes": [],
    }
    result = validate_style_prompt(
        "primary genre: bedroom pop; secondary genre: lo-fi electronic; BPM: 92; vocal direction: close; instrumentation: dry kick; groove/drums: soft pulse; bass/low-end: warm sub; mix/space: dry room; Mandarin Chinese vocal.",
        music_spec,
    )
    assert result["blocking_issues"]
    assert result["score"] <= 68


def test_lyrics_validator_does_not_require_control_prose_revision_target():
    result = validate_lyrics_prompt(
        "[Verse]\nI wait by the door\n[Chorus]\naccess denied\naccess denied",
        "access denied",
        {"section_map": [{"label": "Verse"}, {"label": "Chorus"}]},
    )
    assert "revision target present" not in result["blocking_issues"]
    assert not result["blocking_issues"]


def test_unknown_structure_route_falls_back_to_classic_pop_with_warning(client):
    route = get_route_spec("unknown_route")
    assert route["route"] == "classic_pop"
    assert route["warnings"]
    song = _create_harness_song(client, current_structure_route="unknown_route")
    pack = client.post(f"/api/songs/{song['id']}/suno-prompt-packs").json()["packs"][0]
    assert pack["route_spec"]["route"] == "classic_pop"
    assert pack["route_spec"]["warnings"]


def test_recommended_pack_uses_validation_score():
    high = {
        "variant": "alternate",
        "variant_role": "bold",
        "validation": {"score": 92, "blocking_issues": []},
        "route_spec": {"stability_score": 7},
        "source_trace": {"feedback_used": []},
    }
    low = {
        "variant": "primary",
        "variant_role": "safe",
        "validation": {"score": 45, "blocking_issues": ["missing BPM"]},
        "route_spec": {"stability_score": 9},
        "source_trace": {"feedback_used": []},
    }
    recommended = _recommend([low, high], {"review_count": 0})
    assert recommended["variant"] == "alternate"
    assert high["recommended"] is True
    assert low["recommended"] is False


def test_generation_review_rejects_invalid_prompt_pack_id(client):
    song_a = _create_harness_song(client, ep_title="REVIEW TRACE A")
    song_b = _create_harness_song(client, ep_title="REVIEW TRACE B")
    pack_b = client.post(f"/api/songs/{song_b['id']}/suno-prompt-packs").json()["artifact"]
    missing = client.post(
        f"/api/songs/{song_a['id']}/generation-reviews",
        json={"take_name": "bad missing", "prompt_pack_artifact_id": 999999, "text_feedback": "ok"},
    )
    assert missing.status_code == 404
    cross_song = client.post(
        f"/api/songs/{song_a['id']}/generation-reviews",
        json={"take_name": "bad cross", "prompt_pack_artifact_id": pack_b["id"], "text_feedback": "ok"},
    )
    assert cross_song.status_code == 422


def test_generation_review_records_prompt_pack_trace(client):
    song = _create_harness_song(client)
    pack_artifact = client.post(f"/api/songs/{song['id']}/suno-prompt-packs").json()["artifact"]
    alternate = next(pack["variant"] for pack in pack_artifact["content"]["packs"] if pack["variant"] != pack_artifact["content"]["recommended_variant"])
    review = client.post(
        f"/api/songs/{song['id']}/generation-reviews",
        json={
            "take_name": "trace ok",
            "prompt_pack_artifact_id": pack_artifact["id"],
            "prompt_pack_variant": alternate,
            "text_feedback": "Hook is unclear",
        },
    )
    assert review.status_code == 200
    trace = review.json()["content"]["prompt_pack_trace"]
    assert trace["prompt_pack_artifact_id"] == pack_artifact["id"]
    assert trace["variant"] == alternate
    assert trace["validation_score"] is not None

    invalid_variant = client.post(
        f"/api/songs/{song['id']}/generation-reviews",
        json={"take_name": "bad variant", "prompt_pack_artifact_id": pack_artifact["id"], "prompt_pack_variant": "missing"},
    )
    assert invalid_variant.status_code == 422


def test_asset_bundle_includes_exclude_and_validation(client):
    song = _create_harness_song(client)
    prompt = client.post(f"/api/songs/{song['id']}/suno-prompt-packs")
    assert prompt.status_code == 200
    client.post(f"/api/artifacts/{prompt.json()['artifact']['id']}/accept")
    bundle = client.post(f"/api/songs/{song['id']}/exports/asset-bundle")
    assert bundle.status_code == 200
    with zipfile.ZipFile(io.BytesIO(bundle.content)) as zf:
        suno_md = zf.read("suno_prompt.md").decode("utf-8")
    assert "Exclude Prompt" in suno_md
    assert "Advanced Settings" in suno_md
    assert "Validation Summary" in suno_md
    assert "Route Spec" in suno_md
    assert "Feedback Summary" in suno_md
    assert "Weirdness:" in suno_md
