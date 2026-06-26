let ep = null;
let songs = [];
let currentSong = null;

const $ = (id) => document.getElementById(id);

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || response.statusText);
  }
  return response.json();
}

function splitList(value) {
  return value.split(",").map((item) => item.trim()).filter(Boolean);
}

function setStatus(text) {
  $("status").textContent = text;
}

function fillEp() {
  $("ep-title").value = ep.title || "";
  $("ep-one-liner").value = ep.one_liner || "";
  $("ep-core-theme").value = ep.core_theme || "";
  $("ep-world-view").value = ep.world_view || "";
  $("ep-emotional").value = (ep.emotional_keywords || []).join(", ");
  $("ep-aesthetic").value = (ep.aesthetic_keywords || []).join(", ");
  $("ep-sonic").value = JSON.stringify(ep.sonic_layers || {}, null, 2);
  $("ep-arc").value = ep.narrative_arc || "";
}

function renderSongs() {
  const list = $("song-list");
  list.innerHTML = "";
  songs.forEach((song) => {
    const item = document.createElement("div");
    item.className = `song-item ${currentSong && currentSong.id === song.id ? "active" : ""}`;
    item.innerHTML = `<strong>${song.title}</strong><br><span>${song.function_in_ep || ""}</span>`;
    item.onclick = () => selectSong(song.id);
    list.appendChild(item);
  });
}

function fillSong() {
  if (!currentSong) return;
  $("song-title").value = currentSong.title || "";
  $("song-function").value = currentSong.function_in_ep || "";
  $("song-concept").value = currentSong.concept || "";
  $("song-emotional").value = currentSong.emotional_goal || "";
  $("song-bpm").value = currentSong.bpm || 92;
  $("song-genre").value = currentSong.genre_direction || "";
  $("song-language").value = currentSong.language_plan || "";
  $("song-lyrics").value = currentSong.lyrics || "";
  $("song-style").value = currentSong.style_prompt || "";
  $("song-lyrics-prompt").value = currentSong.lyrics_prompt || "";
  $("song-notes").value = currentSong.notes || "";
}

async function loadVersions() {
  if (!currentSong) return;
  const versions = await api(`/api/songs/${currentSong.id}/versions`);
  const box = $("versions");
  box.innerHTML = "";
  versions.forEach((version) => {
    const item = document.createElement("div");
    item.className = "version-item";
    item.textContent = `v${version.version_number} ${version.change_type} - ${version.change_summary}`;
    box.appendChild(item);
  });
}

async function loadAll() {
  setStatus("loading");
  ep = await api("/api/ep");
  songs = await api("/api/songs");
  currentSong = currentSong ? songs.find((song) => song.id === currentSong.id) || songs[0] : songs[0];
  fillEp();
  renderSongs();
  fillSong();
  await loadVersions();
  setStatus("ready");
}

async function selectSong(id) {
  currentSong = await api(`/api/songs/${id}`);
  renderSongs();
  fillSong();
  await loadVersions();
}

$("save-ep").onclick = async () => {
  let sonic = {};
  try {
    sonic = JSON.parse($("ep-sonic").value || "{}");
  } catch (err) {
    alert("Sonic Layers JSON 格式不正确");
    return;
  }
  ep = await api("/api/ep", {
    method: "PUT",
    body: JSON.stringify({
      title: $("ep-title").value,
      one_liner: $("ep-one-liner").value,
      core_theme: $("ep-core-theme").value,
      world_view: $("ep-world-view").value,
      emotional_keywords: splitList($("ep-emotional").value),
      aesthetic_keywords: splitList($("ep-aesthetic").value),
      sonic_layers: sonic,
      narrative_arc: $("ep-arc").value,
      song_list: songs.map((song) => song.title),
    }),
  });
  setStatus("EP saved");
};

$("new-song").onclick = async () => {
  currentSong = await api("/api/songs", {
    method: "POST",
    body: JSON.stringify({ title: "Untitled Song", ep_id: ep.id, bpm: 92 }),
  });
  await loadAll();
};

$("save-song").onclick = async () => {
  if (!currentSong) return;
  currentSong = await api(`/api/songs/${currentSong.id}`, {
    method: "PUT",
    body: JSON.stringify({
      title: $("song-title").value,
      function_in_ep: $("song-function").value,
      concept: $("song-concept").value,
      emotional_goal: $("song-emotional").value,
      bpm: Number($("song-bpm").value || 92),
      genre_direction: $("song-genre").value,
      language_plan: $("song-language").value,
      lyrics: $("song-lyrics").value,
      style_prompt: $("song-style").value,
      lyrics_prompt: $("song-lyrics-prompt").value,
      notes: $("song-notes").value,
      change_summary: "Saved from frontend",
    }),
  });
  await loadAll();
  setStatus("song saved");
};

$("gen-hooks").onclick = async () => {
  if (!currentSong) return;
  const data = await api(`/api/songs/${currentSong.id}/hooks`, {
    method: "POST",
    body: JSON.stringify({ hook_goal: $("hook-goal").value, count: 6 }),
  });
  $("tool-output").textContent = JSON.stringify(data, null, 2);
  await loadVersions();
};

$("gen-suno").onclick = async () => {
  if (!currentSong) return;
  const data = await api(`/api/songs/${currentSong.id}/suno`, { method: "POST", body: "{}" });
  $("tool-output").textContent = JSON.stringify(data, null, 2);
  await selectSong(currentSong.id);
};

$("export-pack").onclick = () => {
  if (!currentSong) return;
  window.location.href = `/api/songs/${currentSong.id}/exports/cubase-pack`;
};

$("send-chat").onclick = async () => {
  if (!currentSong) return;
  const data = await api("/api/chat", {
    method: "POST",
    body: JSON.stringify({
      ep_id: ep.id,
      song_id: currentSong.id,
      mode: $("chat-mode").value,
      user_message: $("chat-message").value,
    }),
  });
  $("chat-output").textContent = `${data.assistant_message}\n\nActions:\n${(data.suggested_actions || []).join("\n")}`;
};

loadAll().catch((err) => {
  console.error(err);
  setStatus("error");
  alert(err.message);
});
