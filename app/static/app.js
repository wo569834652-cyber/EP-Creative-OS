let ep = null;
let songs = [];
let stages = [];
let currentSong = null;
let artifacts = [];
let versions = [];
let lastSession = null;

const $ = (id) => document.getElementById(id);

const stageLabels = {
  diagnosis: "歌曲诊断",
  hook_lab: "Hook 实验室",
  structure_lab: "结构实验室",
  lyrics_draft: "歌词草稿",
  suno_prompt_lab: "Suno Prompt 实验室",
  generation_review: "生成复盘",
  asset_organizer: "素材整理",
  parked: "暂停",
  done: "完成",
};

const artifactLabels = {
  diagnosis: "诊断结论",
  hook_set: "Hook 候选组",
  structure_route: "结构路线",
  lyrics_draft: "歌词草稿",
  suno_prompt_pack: "Suno Prompt 包",
  generation_review: "生成复盘",
  asset_bundle: "素材整理包",
};

async function api(path, options = {}) {
  const headers = options.body instanceof FormData ? options.headers || {} : { "Content-Type": "application/json", ...(options.headers || {}) };
  const response = await fetch(path, { headers, ...options });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || response.statusText);
  }
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) return response.json();
  return response;
}

function toast(message) {
  const el = $("toast");
  el.textContent = message;
  el.hidden = false;
  window.setTimeout(() => {
    el.hidden = true;
  }, 2200);
}

function shortJson(value) {
  if (!value) return "";
  if (value.recommended_hook) return `推荐 Hook：${value.recommended_hook}`;
  if (value.recommended_route) return `推荐路线：${value.recommended_route}`;
  if (value.recommended_variant) return `推荐方案：${value.recommended_variant}`;
  if (value.next_revision_advice) return value.next_revision_advice;
  return JSON.stringify(value, null, 2).slice(0, 700);
}

function renderSongs() {
  const list = $("song-list");
  list.innerHTML = "";
  songs.forEach((song) => {
    const item = document.createElement("button");
    item.className = `song-item ${currentSong && currentSong.id === song.id ? "active" : ""}`;
    item.innerHTML = `
      <div class="song-title-row">
        <strong>${song.title}</strong>
        <span class="stage-badge">${stageLabels[song.current_stage] || song.current_stage}</span>
      </div>
      <div class="muted">${song.function_in_ep || "未填写 EP 功能"}</div>
    `;
    item.onclick = () => selectSong(song.id);
    list.appendChild(item);
  });
}

function renderStageProgress() {
  const box = $("stage-progress");
  box.innerHTML = "";
  stages.forEach((stage) => {
    const step = document.createElement("div");
    step.className = `stage-step ${currentSong && currentSong.current_stage === stage.key ? "active" : ""}`;
    step.textContent = stage.label;
    box.appendChild(step);
  });
}

function fillSongHeader() {
  if (!currentSong) return;
  $("song-title").textContent = currentSong.title;
  $("song-function").textContent = currentSong.function_in_ep || "未填写 EP 功能";
  $("current-stage-label").textContent = stageLabels[currentSong.current_stage] || currentSong.current_stage;
  $("locked-hook").textContent = currentSong.locked_hook || "未锁定";
  $("structure-route").textContent = currentSong.current_structure_route || "未选择";
  $("prompt-pack").textContent = currentSong.current_prompt_pack_id ? `Artifact #${currentSong.current_prompt_pack_id}` : "未选择";

  $("edit-title").value = currentSong.title || "";
  $("edit-function").value = currentSong.function_in_ep || "";
  $("edit-concept").value = currentSong.concept || "";
  $("edit-emotion").value = currentSong.emotional_goal || "";
  $("edit-bpm").value = currentSong.bpm || 92;
  $("edit-genre").value = currentSong.genre_direction || "";
  $("edit-language").value = currentSong.language_plan || "";
  $("edit-lyrics").value = currentSong.lyrics || "";
  $("edit-notes").value = currentSong.notes || "";
}

function artifactCard(artifact, pending = false) {
  const card = document.createElement("article");
  card.className = `artifact-card ${artifact.status === "pending" ? "pending" : ""} ${artifact.locked ? "locked" : ""}`;
  const label = artifactLabels[artifact.artifact_type] || artifact.artifact_type;
  card.innerHTML = `
    <div class="artifact-meta"><span>${label}</span><span>${artifact.locked ? "已锁定" : artifact.status === "accepted" ? "已接受" : artifact.status === "discarded" ? "已丢弃" : "待确认"}</span></div>
    <p class="artifact-title">${artifact.title}</p>
    <p class="artifact-summary">${artifact.summary || ""}</p>
    <div class="artifact-preview">${shortJson(artifact.content)}</div>
  `;
  const actions = document.createElement("div");
  actions.className = "artifact-actions";

  if (artifact.status !== "discarded") {
    if (artifact.status === "pending") {
      actions.append(button("接受", () => actArtifact(artifact.id, "accept")));
      actions.append(button("丢弃", () => actArtifact(artifact.id, "discard")));
    }
    actions.append(button("锁定", () => actArtifact(artifact.id, "lock")));
    actions.append(button("设为当前", () => actArtifact(artifact.id, "set-current")));
  }
  card.append(actions);
  return card;
}

function button(label, onClick) {
  const el = document.createElement("button");
  el.className = "mini-button";
  el.textContent = label;
  el.onclick = onClick;
  return el;
}

function renderArtifacts() {
  const pendingBox = $("pending-artifacts");
  const acceptedBox = $("accepted-artifacts");
  pendingBox.innerHTML = "";
  acceptedBox.innerHTML = "";

  const pending = artifacts.filter((item) => item.status === "pending");
  const accepted = artifacts.filter((item) => item.status !== "pending" && item.status !== "discarded");
  $("pending-count").textContent = pending.length;

  if (!pending.length) pendingBox.innerHTML = `<div class="muted">没有待确认 Artifact。</div>`;
  pending.forEach((artifact) => pendingBox.append(artifactCard(artifact, true)));

  if (!accepted.length) acceptedBox.innerHTML = `<div class="muted">还没有已接受的 Artifact。</div>`;
  accepted.forEach((artifact) => acceptedBox.append(artifactCard(artifact)));
}

function renderVersions() {
  const box = $("versions");
  box.innerHTML = "";
  if (!versions.length) {
    box.innerHTML = `<div class="muted">还没有版本记录。</div>`;
    return;
  }
  versions.forEach((version) => {
    const item = document.createElement("div");
    item.className = "version-card";
    item.innerHTML = `<strong>v${version.version_number}</strong><br><span class="muted">${version.summary || version.change_summary || version.change_type}</span>`;
    box.append(item);
  });
}

async function refreshBoard() {
  if (!currentSong) return;
  artifacts = await api(`/api/songs/${currentSong.id}/artifacts`);
  versions = await api(`/api/songs/${currentSong.id}/versions`);
  renderArtifacts();
  renderVersions();
}

async function loadAll() {
  ep = await api("/api/ep");
  stages = await api("/api/stages");
  songs = await api("/api/songs");
  currentSong = currentSong ? songs.find((song) => song.id === currentSong.id) || songs[0] : songs.find((song) => song.title === "访问失败") || songs[0];
  $("ep-title").textContent = ep.title;
  $("ep-line").textContent = ep.one_liner || "";
  renderSongs();
  renderStageProgress();
  fillSongHeader();
  await refreshBoard();
}

async function selectSong(id) {
  currentSong = await api(`/api/songs/${id}`);
  renderSongs();
  renderStageProgress();
  fillSongHeader();
  await refreshBoard();
}

async function runStage() {
  if (!currentSong) return;
  lastSession = await api(`/api/songs/${currentSong.id}/sessions`, {
    method: "POST",
    body: JSON.stringify({
      output_mode: $("output-mode").value,
      user_goal: $("session-goal").value,
      user_message: $("session-message").value,
    }),
  });
  $("assistant-message").textContent = lastSession.assistant_message;
  await refreshBoard();
  toast("当前阶段已生成待确认 Artifact");
}

async function confirmNext() {
  if (!currentSong) return;
  const next = lastSession?.stage_recommendation?.next_stage || nextStageKey(currentSong.current_stage);
  if (!next) {
    toast("没有可推进的下一阶段");
    return;
  }
  currentSong = await api(`/api/songs/${currentSong.id}/stage/confirm`, {
    method: "POST",
    body: JSON.stringify({ next_stage: next }),
  });
  songs = await api("/api/songs");
  renderSongs();
  renderStageProgress();
  fillSongHeader();
  await refreshBoard();
  toast(`已进入：${stageLabels[next] || next}`);
}

function nextStageKey(stage) {
  const keys = stages.map((item) => item.key);
  const index = keys.indexOf(stage);
  if (index < 0 || index === keys.length - 1) return "done";
  return keys[index + 1];
}

async function makeSuno() {
  if (!currentSong) return;
  const data = await api(`/api/songs/${currentSong.id}/suno-prompt-packs`, { method: "POST", body: "{}" });
  $("assistant-message").textContent = `已生成 ${data.packs.length} 套 Suno Prompt Pack，推荐：${data.recommended_variant}`;
  await refreshBoard();
  toast("Suno Prompt 包已生成");
}

async function actArtifact(id, action) {
  await api(`/api/artifacts/${id}/${action}`, { method: "POST", body: "{}" });
  currentSong = await api(`/api/songs/${currentSong.id}`);
  songs = await api("/api/songs");
  renderSongs();
  fillSongHeader();
  await refreshBoard();
  toast("Artifact 状态已更新");
}

async function saveReview() {
  if (!currentSong) return;
  const payload = {
    take_name: $("review-take").value,
    text_feedback: $("review-feedback").value,
    hook_accuracy: Number($("score-hook").value),
    style_accuracy: Number($("score-style").value),
    section_structure: Number($("score-section").value),
    diction_singability: Number($("score-diction").value),
    emotional_fit: Number($("score-emotion").value),
    production_usability: Number($("score-production").value),
  };
  await api(`/api/songs/${currentSong.id}/generation-reviews`, { method: "POST", body: JSON.stringify(payload) });
  await refreshBoard();
  toast("生成复盘已保存");
}

async function uploadAsset() {
  if (!currentSong) return;
  const file = $("asset-file").files[0];
  if (!file) return;
  const form = new FormData();
  form.append("role", "suno_audio");
  form.append("file", file);
  await api(`/api/songs/${currentSong.id}/assets`, { method: "POST", body: form });
  $("asset-file").value = "";
  toast("素材已上传归档");
}

async function exportBundle() {
  if (!currentSong) return;
  window.location.href = `/api/songs/${currentSong.id}/exports/asset-bundle`;
}

async function saveSong() {
  if (!currentSong) return;
  currentSong = await api(`/api/songs/${currentSong.id}`, {
    method: "PUT",
    body: JSON.stringify({
      title: $("edit-title").value,
      function_in_ep: $("edit-function").value,
      concept: $("edit-concept").value,
      emotional_goal: $("edit-emotion").value,
      bpm: Number($("edit-bpm").value || 92),
      genre_direction: $("edit-genre").value,
      language_plan: $("edit-language").value,
      lyrics: $("edit-lyrics").value,
      style_prompt: currentSong.style_prompt || "",
      lyrics_prompt: currentSong.lyrics_prompt || "",
      notes: $("edit-notes").value,
      current_stage: currentSong.current_stage,
      stage_status: currentSong.stage_status,
      locked_hook: currentSong.locked_hook || "",
      current_structure_route: currentSong.current_structure_route || "",
      current_prompt_pack_id: currentSong.current_prompt_pack_id,
      change_summary: "歌曲档案编辑",
    }),
  });
  songs = await api("/api/songs");
  renderSongs();
  fillSongHeader();
  $("archive-drawer").classList.remove("open");
  toast("歌曲档案已保存");
}

$("run-stage").onclick = () => runStage().catch((err) => toast(err.message));
$("confirm-next").onclick = () => confirmNext().catch((err) => toast(err.message));
$("make-suno").onclick = () => makeSuno().catch((err) => toast(err.message));
$("save-review").onclick = () => saveReview().catch((err) => toast(err.message));
$("asset-file").onchange = () => uploadAsset().catch((err) => toast(err.message));
$("export-bundle").onclick = () => exportBundle();
$("refresh-board").onclick = () => refreshBoard().catch((err) => toast(err.message));
$("open-archive").onclick = () => $("archive-drawer").classList.add("open");
$("close-archive").onclick = () => $("archive-drawer").classList.remove("open");
$("save-song").onclick = () => saveSong().catch((err) => toast(err.message));

loadAll().catch((err) => {
  console.error(err);
  toast(err.message);
});
