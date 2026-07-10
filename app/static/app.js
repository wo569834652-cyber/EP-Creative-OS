let ep = null;
let eps = [];
let songs = [];
let stages = [];
let currentSong = null;
let currentEpId = null;
let artifacts = [];
let versions = [];
let assets = [];
let lastSession = null;
let selectedVersionId = null;
let stageRunning = false;
let sunoRunning = false;
let reviewSaving = false;
let bundleExporting = false;
let cubaseExporting = false;
let activeOverlay = null;
let overlayReturnFocus = null;
let lastUsedPromptSelection = null;

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

const stageActionHints = {
  diagnosis: "先生成诊断建议，保存后进入 Hook 实验室。",
  hook_lab: "先得到并保存一个 Hook 候选组，再进入结构实验室。",
  structure_lab: "先保存结构路线，再进入歌词草稿。",
  lyrics_draft: "先保存歌词草稿，再进入 Suno Prompt 实验室。",
  suno_prompt_lab: "生成并保存可复制到 Suno 的提示词。",
  generation_review: "记录一版 Suno 结果，系统会指出下一轮改哪里。",
  asset_organizer: "检查歌词、Prompt、复盘和上传文件，然后导出制作资料包。",
};

const stageRequiredArtifact = {
  diagnosis: "diagnosis",
  hook_lab: "hook_set",
  structure_lab: "structure_route",
  lyrics_draft: "lyrics_draft",
  suno_prompt_lab: "suno_prompt_pack",
};

function pendingArtifactsForCurrentStage() {
  const required = stageRequiredArtifact[currentSong?.current_stage];
  return artifacts.filter((item) => item.status === "pending" && (!required || item.artifact_type === required));
}

function acceptedArtifactsForCurrentStage() {
  const required = stageRequiredArtifact[currentSong?.current_stage];
  if (!required) return [];
  return artifacts.filter((item) => item.artifact_type === required && item.status === "accepted");
}

function nextStageForCurrentSong() {
  if (!currentSong) return null;
  if (lastSession?.stage === currentSong.current_stage) {
    return lastSession.stage_recommendation?.next_stage || nextStageKey(currentSong.current_stage);
  }
  return nextStageKey(currentSong.current_stage);
}

async function api(path, options = {}) {
  const headers = options.body instanceof FormData ? options.headers || {} : { "Content-Type": "application/json", ...(options.headers || {}) };
  const response = await fetch(path, { headers, ...options });
  if (!response.ok) {
    const text = await response.text();
    let message = text || response.statusText;
    try {
      const payload = JSON.parse(text);
      message = payload.detail || message;
    } catch (_) {
      // Keep the raw server text when it is not JSON.
    }
    throw new Error(message);
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
  if (typeof value.quality_score === "number") {
    const issues = (value.quality_issues || []).slice(0, 3).join("\n- ");
    return `质量评分：${value.quality_score}/100\n${issues ? `需要注意：\n- ${issues}` : "暂无明显质量问题。"}\n\n${value.lyrics || JSON.stringify(value, null, 2).slice(0, 500)}`;
  }
  if (value.recommended_hook) return `推荐 Hook：${value.recommended_hook}`;
  if (value.recommended_route) return `推荐路线：${value.recommended_route}`;
  if (value.recommended_variant) return `推荐方案：${value.recommended_variant}`;
  if (value.next_revision_advice) return value.next_revision_advice;
  return JSON.stringify(value, null, 2).slice(0, 700);
}

function qualityBadge(content) {
  if (!content || typeof content.quality_score !== "number") return "";
  const passed = content.quality_passed;
  const label = passed ? "可测试" : "需返工";
  const issues = (content.quality_issues || []).slice(0, 2).join("；");
  return `<div class="quality-badge ${passed ? "pass" : "warn"}">质量 ${content.quality_score}/100 · ${label}${issues ? ` · ${issues}` : ""}</div>`;
}

function promptPackQuality(pack) {
  if (!pack || typeof pack.style_specificity_score !== "number") return "";
  const failed = (pack.quality_checks || []).filter((item) => !item.passed).map((item) => item.label);
  return `<p class="${failed.length ? "prompt-source-warn" : "prompt-source-ok"}">Style 具体度 ${pack.style_specificity_score}/100${failed.length ? `，待补：${failed.slice(0, 2).join("、")}` : "，检查通过"}</p>`;
}

function packValidationSummary(pack) {
  const validation = pack.validation || {};
  const warnings = validation.warnings || [];
  const blocking = validation.blocking_issues || [];
  const warningPreview = warnings.slice(0, 2).join(" / ");
  return `
    <div class="prompt-metric-row">
      <span>Validation ${Number(validation.score || 0)}/100</span>
      <span>Warnings ${warnings.length}</span>
      <span>Specificity ${Number(pack.style_specificity_score || 0)}/100</span>
      <span>${(pack.source_trace?.feedback_used || []).length ? "已吸收最近生成复盘" : "暂无复盘输入"}</span>
    </div>
    ${warningPreview ? `<div class="validation-warning-preview">Warning: ${escapeHtml(warningPreview)}</div>` : ""}
    ${blocking.length ? `<div class="validation-blocking">Blocking: ${escapeHtml(blocking.join(" / "))}</div>` : ""}
  `;
}

function musicSpecSummary(pack) {
  const spec = pack.music_spec || {};
  const genre = [spec.primary_genre, spec.secondary_genre].filter(Boolean).join(" / ");
  return `
    <div class="music-spec-grid">
      <div><span>Genre</span><strong>${escapeHtml(genre || "-")}</strong></div>
      <div><span>BPM</span><strong>${escapeHtml(spec.bpm || "-")}</strong></div>
      <div><span>Vocal</span><strong>${escapeHtml(spec.vocal_delivery || spec.vocal_type || "-")}</strong></div>
      <div><span>Instrumentation</span><strong>${escapeHtml((spec.instrumentation || []).slice(0, 5).join(", ") || "-")}</strong></div>
      <div><span>Energy</span><strong>${escapeHtml(spec.energy_curve || "-")}</strong></div>
      <div><span>Mix/Space</span><strong>${escapeHtml(spec.mix_space || "-")}</strong></div>
    </div>
  `;
}

function advancedSettingsSummary(pack) {
  const settings = pack.advanced_settings || {};
  return `
    <div class="advanced-settings">
      <span>Weirdness <strong>${settings.weirdness ?? "-"}</strong></span>
      <span>Style Influence <strong>${settings.style_influence ?? "-"}</strong></span>
      <span>Audio Influence <strong>${settings.audio_influence ?? "-"}</strong></span>
    </div>
  `;
}

function compactSpecLine(pack) {
  const spec = pack.music_spec || {};
  const genre = [spec.primary_genre, spec.secondary_genre].filter(Boolean).join(" / ");
  return `<p class="compact-spec-line">${escapeHtml(genre || "-")} · ${escapeHtml(spec.bpm || "-")} BPM · ${escapeHtml(spec.vocal_delivery || spec.vocal_type || "-")}</p>`;
}

function producerDecisionSummary(pack) {
  const spec = pack.music_spec || {};
  const route = pack.route_spec || {};
  const trace = pack.source_trace || {};
  const feedbackUsed = trace.feedback_used || [];
  return `
    <div class="producer-decision-box">
      <strong>制作决策</strong>
      <p>EP function: ${escapeHtml(spec.use_case || "-")}</p>
      <p>Hook: ${escapeHtml(trace.hook || "-")}</p>
      <p>Route: ${escapeHtml(route.route || "-")} · ${escapeHtml(route.hook_placement || "-")}</p>
      <p>Stability: ${escapeHtml(route.stability_notes || "-")}</p>
      <p>Feedback learned: ${feedbackUsed.length ? "yes" : "not yet"}</p>
      <p>Next experiment: ${escapeHtml(pack.revision_strategy || "-")}</p>
    </div>
  `;
}

function feedbackSummary(pack) {
  const summary = pack.feedback_summary || {};
  if (!summary.review_count) return "";
  return `
    <div class="feedback-loop-box">
      <strong>已吸收最近生成复盘</strong>
      <p>Recurring: ${escapeHtml((summary.recurring_problems || []).join(", ") || "-")}</p>
      <p>Blocked: ${escapeHtml((summary.blocked_terms || []).slice(0, 6).join(", ") || "-")}</p>
      <p>Next bias: ${escapeHtml(summary.next_revision_bias || "-")}</p>
    </div>
  `;
}

function listChecks(title, items, className = "") {
  if (!items || !items.length) return `<div class="check-list ${className}"><strong>${title}</strong><p>none</p></div>`;
  return `<div class="check-list ${className}"><strong>${title}</strong><ul>${items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul></div>`;
}

function fullPackText(pack) {
  return [
    `VARIANT\n${pack.variant} / ${pack.variant_role}`,
    `STYLE PROMPT\n${pack.style_prompt || ""}`,
    `LYRICS PROMPT\n${pack.lyrics_prompt || ""}`,
    `EXCLUDE PROMPT\n${pack.exclude_prompt || ""}`,
    `ADVANCED SETTINGS\n${JSON.stringify(pack.advanced_settings || {}, null, 2)}`,
    `VALIDATION\n${JSON.stringify(pack.validation || {}, null, 2)}`,
    `SOURCE TRACE\n${JSON.stringify(pack.source_trace || {}, null, 2)}`,
  ].join("\n\n");
}

function sunoReadyText(pack) {
  return [
    `STYLE PROMPT\n${pack.style_prompt || ""}`,
    `LYRICS PROMPT\n${pack.lyrics_prompt || ""}`,
    `EXCLUDE PROMPT\n${pack.exclude_prompt || ""}`,
  ].join("\n\n");
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function copyText(text) {
  if (!text) {
    toast("没有可复制内容");
    return;
  }
  navigator.clipboard?.writeText(text).then(
    () => toast("已复制"),
    () => {
      const area = document.createElement("textarea");
      area.value = text;
      document.body.append(area);
      area.select();
      document.execCommand("copy");
      area.remove();
      toast("已复制");
    },
  );
}

function modal(id, open, trigger = document.activeElement) {
  const el = $(id);
  el.classList.toggle("open", open);
  el.setAttribute("aria-hidden", open ? "false" : "true");
  if (open) {
    activeOverlay = el;
    overlayReturnFocus = trigger;
    const firstInput = el.querySelector("input, textarea, select, button");
    firstInput?.focus();
  } else if (activeOverlay === el) {
    activeOverlay = null;
    const returnFocus = overlayReturnFocus;
    overlayReturnFocus = null;
    returnFocus?.focus();
  }
}

function promptSelectionValue(artifactId, variant) {
  return artifactId && variant ? `${artifactId}:${variant}` : "";
}

function parsePromptSelection(value) {
  const [artifactId, ...variantParts] = String(value || "").split(":");
  const variant = variantParts.join(":");
  return artifactId && variant ? { artifactId: Number(artifactId), variant } : null;
}

function markPromptUsed(artifact, pack) {
  lastUsedPromptSelection = { songId: currentSong?.id, artifactId: artifact.id, variant: pack.variant };
  const select = $("review-prompt-variant");
  const value = promptSelectionValue(artifact.id, pack.variant);
  if (select && [...select.options].some((option) => option.value === value)) select.value = value;
  updatePromptUsedLabel();
  toast(`已复制并标记本次使用：${pack.variant}`);
}

function hookSetView(artifact) {
  const content = artifact.content || {};
  const hooks = content.hooks || [];
  if (!hooks.length) return null;
  const wrap = document.createElement("div");
  wrap.className = "hook-version-list";
  const note = document.createElement("p");
  note.className = "hook-set-note";
  note.textContent = content.selection_note || "每个 Hook 是一个可测试版本方向。";
  wrap.append(note);
  hooks.forEach((hook, index) => {
    const item = document.createElement("section");
    item.className = `hook-version-item ${hook.hook_text === content.recommended_hook ? "recommended" : ""}`;
    item.innerHTML = `
      <div class="hook-version-head">
        <div>
          <strong>${escapeHtml(hook.version_label || `版本 ${index + 1}`)}${hook.hook_text === content.recommended_hook ? " / 推荐" : ""}</strong>
          <p>${escapeHtml(hook.angle || hook.why_it_works || "")}</p>
        </div>
        <span>分数 ${Number(hook.score || 0)} · 创新 ${Number(hook.innovation || 1)}</span>
      </div>
      <p class="hook-text">${escapeHtml(hook.hook_text || "")}</p>
      <div class="hook-version-grid">
        <div><span>适用</span><p>${escapeHtml(hook.use_case || "")}</p></div>
        <div><span>节奏</span><p>${escapeHtml(hook.rhythm_notes || "")}</p></div>
        <div><span>Suno 风险</span><p>${escapeHtml(hook.suno_risk || "")}</p></div>
      </div>
    `;
    wrap.append(item);
  });
  return wrap;
}

function promptPackView(artifact) {
  const content = artifact.content || {};
  const packs = content.packs || [];
  if (!packs.length) return null;

  const wrap = document.createElement("div");
  wrap.className = "prompt-pack-list";
  packs.forEach((pack) => {
    const item = document.createElement("section");
    item.className = `prompt-pack-item ${pack.recommended ? "recommended" : "collapsed"}`;
    item.innerHTML = `
      <div class="prompt-pack-head">
        <div>
          <strong>${pack.variant}${pack.recommended ? " / 推荐" : ""}</strong>
          <p>${pack.recommendation_reason || ""}</p>
          <p class="${pack.lyrics_source === "accepted_song_lyrics" ? "prompt-source-ok" : "prompt-source-warn"}">
            ${pack.lyrics_source === "accepted_song_lyrics" ? "Lyrics Prompt 已包含当前已接受歌词" : "Lyrics Prompt 仍是临时结构模板，请先接受歌词草稿后重新生成"}
          </p>
          ${promptPackQuality(pack)}
        </div>
        <div class="prompt-pack-actions"></div>
      </div>
      <div class="prompt-block">
        <div class="prompt-block-head"><span>Style Prompt</span></div>
        <pre>${pack.style_prompt || ""}</pre>
      </div>
      <div class="prompt-block">
        <div class="prompt-block-head"><span>Lyrics Prompt</span></div>
        <pre>${pack.lyrics_prompt || ""}</pre>
      </div>
      <div class="prompt-notes">
        <strong>修正策略</strong>
        <p>${pack.revision_strategy || ""}</p>
        <strong>风险</strong>
        <p>${(pack.suno_risks || []).join("；")}</p>
      </div>
    `;
    const actions = item.querySelector(".prompt-pack-actions");
    const toggle = button(pack.recommended ? "收起" : "展开", () => {
      item.classList.toggle("collapsed");
      toggle.textContent = item.classList.contains("collapsed") ? "展开" : "收起";
    });
    const copyStyle = button("复制本项 Style", () => copyText(pack.style_prompt));
    const copyLyrics = button("复制本项 Lyrics", () => copyText(pack.lyrics_prompt));
    const copyBoth = button(pack.recommended ? "复制推荐整套" : "复制整套", () => {
      markPromptUsed(artifact, pack);
      copyText(`STYLE PROMPT\n${pack.style_prompt}\n\nLYRICS PROMPT\n${pack.lyrics_prompt}`);
    });
    actions.append(toggle, copyStyle, copyLyrics, copyBoth);
    wrap.append(item);
  });
  return wrap;
}

function promptPackViewV2(artifact) {
  const content = artifact.content || {};
  const packs = [...(content.packs || [])].sort((left, right) => {
    const leftRecommended = left.recommended || left.variant === content.recommended_variant;
    const rightRecommended = right.recommended || right.variant === content.recommended_variant;
    return Number(rightRecommended) - Number(leftRecommended);
  });
  if (!packs.length) return null;

  const wrap = document.createElement("div");
  wrap.className = "prompt-pack-list";
  packs.forEach((pack) => {
    const isRecommended = pack.recommended || pack.variant === content.recommended_variant;
    const item = document.createElement("section");
    item.className = `prompt-pack-item ${isRecommended ? "recommended" : "collapsed"} ${pack.validation?.blocking_issues?.length ? "has-blocking" : ""}`;
    const validation = pack.validation || {};
    item.innerHTML = `
      <div class="prompt-pack-head">
        <div>
          <strong>${escapeHtml(pack.variant || "")}${pack.variant_role ? ` / ${escapeHtml(pack.variant_role)}` : ""}${isRecommended ? " / 推荐" : ""}</strong>
          <p>${escapeHtml(pack.recommendation_reason || "")}</p>
          ${compactSpecLine(pack)}
          ${packValidationSummary(pack)}
          <p class="${pack.lyrics_source === "accepted_song_lyrics" ? "prompt-source-ok" : "prompt-source-warn"}">
            ${pack.lyrics_source === "accepted_song_lyrics" ? "歌词提示已使用当前确认歌词" : "歌词提示仍是临时结构模板，请确认歌词后重新生成"}
          </p>
        </div>
        <div class="prompt-pack-actions"></div>
      </div>
      ${producerDecisionSummary(pack)}
      ${feedbackSummary(pack)}
      <details class="prompt-detail" open>
        <summary>音乐规格</summary>
        ${musicSpecSummary(pack)}
      </details>
      <details class="prompt-detail" open>
        <summary>高级参数</summary>
        ${advancedSettingsSummary(pack)}
      </details>
      <div class="prompt-block">
        <div class="prompt-block-head"><span>Style Prompt</span></div>
        <pre>${escapeHtml(pack.style_prompt || "")}</pre>
      </div>
      <div class="prompt-block">
        <div class="prompt-block-head"><span>Lyrics Prompt</span></div>
        <pre>${escapeHtml(pack.lyrics_prompt || "")}</pre>
      </div>
      <div class="prompt-block">
        <div class="prompt-block-head"><span>Exclude Prompt</span></div>
        <pre>${escapeHtml(pack.exclude_prompt || "")}</pre>
      </div>
      <details class="prompt-detail" ${isRecommended ? "open" : ""}>
        <summary>质量检查</summary>
        <div class="validation-grid">
          ${listChecks("Passed", validation.passed_checks || [], "pass")}
          ${listChecks("Warnings", validation.warnings || [], "warn")}
          ${listChecks("Blocking", validation.blocking_issues || [], "block")}
        </div>
      </details>
      <div class="prompt-notes">
        <strong>下一轮修正策略</strong>
        <p>${escapeHtml(pack.revision_strategy || "")}</p>
        <strong>来源记录</strong>
        <pre>${escapeHtml(JSON.stringify(pack.source_trace || {}, null, 2))}</pre>
      </div>
    `;
    const actions = item.querySelector(".prompt-pack-actions");
    const toggle = button(isRecommended ? "收起" : "展开", () => {
      item.classList.toggle("collapsed");
      toggle.textContent = item.classList.contains("collapsed") ? "展开" : "收起";
    });
    const copyStyle = button("复制 Style", () => copyText(pack.style_prompt));
    const copyLyrics = button("复制 Lyrics", () => copyText(pack.lyrics_prompt));
    const copyExclude = button("复制 Exclude", () => copyText(pack.exclude_prompt));
    const copySunoReady = button(isRecommended ? "复制可直接投喂 Suno（推荐）" : "复制可直接投喂 Suno", () => {
      markPromptUsed(artifact, pack);
      copyText(sunoReadyText(pack));
    }, isRecommended && !validation.blocking_issues?.length ? "strong-button prompt-primary-action" : "mini-button");
    if (validation.blocking_issues?.length) {
      copySunoReady.textContent = "复制风险版本";
      copySunoReady.title = `存在阻断问题：${validation.blocking_issues.join("；")}`;
    }
    const copyRecord = button("复制完整记录", () => copyText(fullPackText(pack)));
    actions.append(toggle, copyStyle, copyLyrics, copyExclude, copySunoReady, copyRecord);
    wrap.append(item);
  });
  return wrap;
}

function renderSongs() {
  const list = $("song-list");
  list.innerHTML = "";
  if (!songs.length) {
    list.innerHTML = `<div class="muted">这个项目还没有歌曲，点击“新建歌曲”开始。</div>`;
    return;
  }
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

function renderProjects() {
  const select = $("project-select");
  select.innerHTML = "";
  eps.forEach((item) => {
    const option = document.createElement("option");
    option.value = item.id;
    option.textContent = item.title || `未命名项目 #${item.id}`;
    option.selected = item.id === currentEpId;
    select.append(option);
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

function renderStageGuide() {
  const stage = stages.find((item) => currentSong && item.key === currentSong.current_stage);
  $("stage-guide-title").textContent = stage?.label || "未开始";
  $("stage-guide-description").textContent = stage?.description || "先新建歌曲，再开始诊断。";
  const list = $("stage-guide-checklist");
  list.innerHTML = "";
  (stage?.completion || ["创建歌曲档案"]).forEach((item) => {
    const li = document.createElement("li");
    li.textContent = item;
    list.append(li);
  });
  const pendingCount = pendingArtifactsForCurrentStage().length;
  const acceptedCount = acceptedArtifactsForCurrentStage().length;
  const next = nextStageForCurrentSong();
  if (!currentSong) {
    $("stage-guide-status").textContent = "先新建一首歌。";
  } else if (pendingCount) {
    $("stage-guide-status").textContent = `有 ${pendingCount} 个待确认产物，先保存或不采用。`;
  } else if (acceptedCount) {
    $("stage-guide-status").textContent = next && next !== "done" ? `可进入下一阶段：${stageLabels[next]}` : "已到最后阶段。";
  } else {
    $("stage-guide-status").textContent = stageActionHints[currentSong.current_stage] || "先生成本阶段建议。";
  }
}

function fillSongHeader() {
  if (!currentSong) {
    $("song-title").textContent = "新项目";
    $("song-function").textContent = "还没有歌曲，先新建一首歌。";
    $("current-stage-label").textContent = "未开始";
    $("locked-hook").textContent = "未锁定";
    $("structure-route").textContent = "未选择";
    $("prompt-pack").textContent = "未选择";
    return;
  }
  $("song-title").textContent = currentSong.title;
  $("song-function").textContent = currentSong.function_in_ep || "未填写 EP 功能";
  $("current-stage-label").textContent = stageLabels[currentSong.current_stage] || currentSong.current_stage;
  $("locked-hook").textContent = currentSong.locked_hook || "未锁定";
  $("structure-route").textContent = currentSong.current_structure_route || "未选择";
  $("prompt-pack").textContent = currentSong.current_prompt_pack_id ? `Artifact #${currentSong.current_prompt_pack_id}` : "未选择";
  $("session-goal").value = `推进《${currentSong.title}》的${stageLabels[currentSong.current_stage] || "当前"}阶段`;

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

function updateCurrentPromptLabel() {
  if (!currentSong) return;
  if (!currentSong.current_prompt_pack_id) {
    $("prompt-pack").textContent = "未选择";
    return;
  }
  const current = artifacts.find((item) => item.id === currentSong.current_prompt_pack_id);
  const content = current?.content || {};
  const recommended = content.recommended_variant || content.recommended_pack?.variant || "primary";
  $("prompt-pack").textContent = `Suno Prompt：${recommended}（推荐）`;
}

function updatePromptUsedLabel() {
  const selected = lastUsedPromptSelection?.songId === currentSong?.id ? lastUsedPromptSelection : null;
  $("prompt-used-variant").textContent = selected ? `${selected.variant} · Artifact #${selected.artifactId}` : "尚未标记";
}

function markSelectedReviewPromptUsed() {
  const selected = parsePromptSelection($("review-prompt-variant").value);
  lastUsedPromptSelection = selected ? { songId: currentSong?.id, ...selected } : null;
  updatePromptUsedLabel();
}

function renderPromptReviewOptions() {
  const select = $("review-prompt-variant");
  const previous = select.value;
  select.innerHTML = '<option value="">尚未选择 Prompt 版本</option>';
  artifacts
    .filter((artifact) => artifact.artifact_type === "suno_prompt_pack" && artifact.status !== "discarded")
    .forEach((artifact) => {
      const recommended = artifact.content?.recommended_variant || artifact.content?.recommended_pack?.variant;
      (artifact.content?.packs || []).forEach((pack) => {
        if (!pack.variant) return;
        const option = document.createElement("option");
        option.value = promptSelectionValue(artifact.id, pack.variant);
        option.textContent = `Artifact #${artifact.id} · ${pack.variant}${pack.variant === recommended ? " · 系统推荐" : ""}${artifact.status === "pending" ? " · 待确认" : ""}`;
        select.append(option);
      });
    });

  const copied = lastUsedPromptSelection?.songId === currentSong?.id
    ? promptSelectionValue(lastUsedPromptSelection.artifactId, lastUsedPromptSelection.variant)
    : "";
  const currentArtifact = artifacts.find((artifact) => artifact.id === currentSong?.current_prompt_pack_id);
  const currentRecommended = currentArtifact?.content?.recommended_variant || currentArtifact?.content?.recommended_pack?.variant;
  const currentValue = promptSelectionValue(currentArtifact?.id, currentRecommended);
  const preferred = [previous, copied, currentValue].find((value) => value && [...select.options].some((option) => option.value === value));
  select.value = preferred || "";
  updatePromptUsedLabel();
}

function artifactCard(artifact, pending = false) {
  const card = document.createElement("article");
  card.className = `artifact-card ${artifact.status === "pending" ? "pending" : ""} ${artifact.locked ? "locked" : ""}`;
  const label = artifactLabels[artifact.artifact_type] || artifact.artifact_type;
  const actionHint = artifactActionHint(artifact);
  const sourceText = artifact.content?.source === "ai" ? "AI 生成" : artifact.content?.fallback ? "本地草稿" : "";
  card.innerHTML = `
    <div class="artifact-meta">
      <span>${label}${sourceText ? ` · ${sourceText}` : ""}</span>
      <span>${artifact.locked ? "已锁定" : artifact.status === "accepted" ? "已接受" : artifact.status === "discarded" ? "已丢弃" : "待确认"}</span>
    </div>
    <p class="artifact-title">${artifact.title}</p>
    <p class="artifact-summary">${artifact.summary || ""}</p>
    <p class="artifact-impact">${actionHint}</p>
    ${qualityBadge(artifact.content)}
    <div class="artifact-preview">${shortJson(artifact.content)}</div>
  `;
  const actions = document.createElement("div");
  actions.className = "artifact-actions";

  if (artifact.status !== "discarded") {
    if (artifact.status === "pending") {
      actions.append(button("保存为可用版本", () => actArtifact(artifact.id, "accept"), "strong-button"));
      actions.append(button("不采用", () => actArtifact(artifact.id, "discard")));
    }
    actions.append(button("锁定为关键版本", () => actArtifact(artifact.id, "lock")));
    actions.append(button(`设为当前${currentNoun(artifact.artifact_type)}`, () => actArtifact(artifact.id, "set-current")));
  }
  card.append(actions);
  if (artifact.artifact_type === "suno_prompt_pack") {
    const preview = card.querySelector(".artifact-preview");
    if (preview) preview.remove();
    const packs = artifact.content?.packs || [];
    const isHarnessV2 = packs.some((pack) => pack.music_spec || pack.validation || pack.advanced_settings || pack.exclude_prompt);
    const view = isHarnessV2 ? promptPackViewV2(artifact) : promptPackView(artifact);
    if (!isHarnessV2) {
      const legacyNotice = document.createElement("p");
      legacyNotice.className = "legacy-prompt-notice";
      legacyNotice.textContent = "这是旧版 Prompt 包。重新生成后可获得质量检查、Exclude Prompt 和高级参数。";
      card.append(legacyNotice);
    }
    if (view) card.append(view);
  } else if (artifact.artifact_type === "hook_set") {
    const preview = card.querySelector(".artifact-preview");
    if (preview) preview.remove();
    const view = hookSetView(artifact);
    if (view) card.append(view);
  } else if (artifact.artifact_type === "lyrics_draft" && artifact.content?.lyrics) {
    const preview = card.querySelector(".artifact-preview");
    if (preview) {
      preview.textContent = artifact.content.lyrics;
      preview.classList.add("lyrics-preview");
    }
  }
  return card;
}

function currentNoun(type) {
  return {
    hook_set: " Hook",
    structure_route: "结构",
    lyrics_draft: "歌词",
    suno_prompt_pack: " Prompt 包",
  }[type] || "使用";
}

function artifactActionHint(artifact) {
  return {
    diagnosis: "保存后，这条诊断会进入版本板，作为下一阶段依据。",
    hook_set: "保存或锁定后，会更新当前 Hook 候选依据。",
    structure_route: "设为当前后，会更新当前结构路线。",
    lyrics_draft: "设为当前后，会写入歌曲歌词草稿。",
    suno_prompt_pack: "设为当前后，会更新右侧当前 Prompt 包，并写入歌曲档案。",
    generation_review: "保存后，会记录下一轮该优先修改哪里。",
    asset_bundle: "用于导出制作资料包前的检查。",
  }[artifact.artifact_type] || "保存后会进入右侧版本板。";
}

function button(label, onClick, className = "mini-button") {
  const el = document.createElement("button");
  el.className = className;
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

  if (!pending.length) pendingBox.innerHTML = `<div class="muted">还没有待确认内容。运行当前阶段后会出现在这里。</div>`;
  pending.forEach((artifact) => pendingBox.append(artifactCard(artifact, true)));

  if (!accepted.length) acceptedBox.innerHTML = `<div class="muted">还没有保存的创作产物。接受或锁定后会显示在这里。</div>`;
  accepted.forEach((artifact) => acceptedBox.append(artifactCard(artifact)));
}

function renderVersions() {
  const box = $("versions");
  box.innerHTML = "";
  if (!versions.length) {
    box.innerHTML = `<div class="muted">还没有版本记录。</div>`;
    return;
  }
  if (!selectedVersionId || !versions.some((version) => version.id === selectedVersionId)) {
    selectedVersionId = versions[0].id;
  }
  const selected = versions.find((version) => version.id === selectedVersionId) || versions[0];
  const snapshot = selected.content_snapshot || {};
  const selectWrap = document.createElement("div");
  selectWrap.className = "version-select-wrap";
  const select = document.createElement("select");
  select.setAttribute("aria-label", "选择版本");
  versions.forEach((version) => {
    const option = document.createElement("option");
    option.value = version.id;
    option.selected = version.id === selected.id;
    option.textContent = `v${version.version_number} · ${version.summary || version.change_summary || version.change_type}`;
    select.append(option);
  });
  select.onchange = (event) => {
    selectedVersionId = Number(event.target.value);
    renderVersions();
  };
  selectWrap.append(select);

  const detail = document.createElement("div");
  detail.className = "version-detail-card";
  detail.innerHTML = `
    <div class="version-detail-head">
      <div>
        <strong>v${selected.version_number}</strong>
        <p>${escapeHtml(selected.summary || selected.change_summary || selected.change_type)}</p>
      </div>
      <span>${escapeHtml(selected.change_type || "full")}</span>
    </div>
    <div class="version-detail-grid">
      <div><span>阶段</span><strong>${escapeHtml(stageLabels[snapshot.current_stage] || snapshot.current_stage || "未记录")}</strong></div>
      <div><span>Hook</span><strong>${escapeHtml(snapshot.locked_hook || "未锁定")}</strong></div>
      <div><span>结构</span><strong>${escapeHtml(snapshot.current_structure_route || "未选择")}</strong></div>
      <div><span>BPM</span><strong>${escapeHtml(snapshot.bpm || "")}</strong></div>
    </div>
    <div class="version-mini-preview">
      <span>歌词</span>
      <p>${escapeHtml(snapshot.lyrics ? snapshot.lyrics.slice(0, 180) : "暂无歌词")}</p>
    </div>
    <div class="version-mini-preview">
      <span>Style</span>
      <p>${escapeHtml(snapshot.style_prompt ? snapshot.style_prompt.slice(0, 180) : "暂无 Style Prompt")}</p>
    </div>
    <div class="version-actions"></div>
    <pre class="version-snapshot" hidden>${escapeHtml(versionSnapshot(selected))}</pre>
  `;
  const actions = detail.querySelector(".version-actions");
  const snapshotEl = detail.querySelector(".version-snapshot");
  const toggle = button("查看完整快照", () => {
    snapshotEl.hidden = !snapshotEl.hidden;
    toggle.textContent = snapshotEl.hidden ? "查看完整快照" : "收起完整快照";
  });
  const restore = button("回溯到此版本", () => restoreVersion(selected.id));
  restore.disabled = Boolean(currentSong && snapshot.title === currentSong.title && snapshot.lyrics === currentSong.lyrics && snapshot.current_stage === currentSong.current_stage);
  actions.append(toggle, restore);
  box.append(selectWrap, detail);
}

function versionSnapshot(version) {
  const snapshot = version.content_snapshot || {};
  const picked = {
    歌名: snapshot.title,
    阶段: stageLabels[snapshot.current_stage] || snapshot.current_stage,
    Hook: snapshot.locked_hook || "未锁定",
    结构路线: snapshot.current_structure_route || "未选择",
    BPM: snapshot.bpm,
    风格方向: snapshot.genre_direction || "",
    歌词预览: snapshot.lyrics ? snapshot.lyrics.slice(0, 360) : "暂无歌词",
    Style预览: snapshot.style_prompt ? snapshot.style_prompt.slice(0, 260) : "暂无 Style Prompt",
  };
  return JSON.stringify(picked, null, 2);
}

function renderAssets() {
  const box = $("asset-list");
  box.innerHTML = "";
  if (!assets.length) {
    box.innerHTML = `<div class="muted">还没有上传素材。</div>`;
    return;
  }
  assets.forEach((asset) => {
    const item = document.createElement("div");
    item.className = "asset-item";
    item.innerHTML = `<strong>${asset.filename}</strong><span class="muted">${asset.role} · ${Math.round(asset.size_bytes / 1024)} KB</span>`;
    box.append(item);
  });
}

async function refreshBoard() {
  if (!currentSong) {
    artifacts = [];
    versions = [];
    assets = [];
    renderArtifacts();
    renderPromptReviewOptions();
    renderVersions();
    renderAssets();
    renderStageGuide();
    return;
  }
  artifacts = await api(`/api/songs/${currentSong.id}/artifacts`);
  versions = await api(`/api/songs/${currentSong.id}/versions`);
  assets = await api(`/api/songs/${currentSong.id}/assets`);
  updateCurrentPromptLabel();
  renderArtifacts();
  renderPromptReviewOptions();
  renderVersions();
  renderAssets();
  renderStageGuide();
}

async function loadAll() {
  eps = await api("/api/eps");
  if (!eps.length) {
    ep = await api("/api/eps", {
      method: "POST",
      body: JSON.stringify({
        title: "新 EP 项目",
        one_liner: "",
        core_theme: "",
        world_view: "",
        emotional_keywords: [],
        aesthetic_keywords: [],
        sonic_layers: {},
        narrative_arc: "",
        song_list: [],
      }),
    });
    eps = await api("/api/eps");
  }
  currentEpId = currentEpId || (ep && ep.id) || eps.find((item) => item.title === "GROWING UP.EXE")?.id || eps[0].id;
  ep = await api(`/api/ep?ep_id=${currentEpId}`);
  stages = await api("/api/stages");
  songs = await api(`/api/songs?ep_id=${currentEpId}`);
  currentSong = currentSong ? songs.find((song) => song.id === currentSong.id) || songs[0] || null : songs.find((song) => song.title === "访问失败") || songs[0] || null;
  $("ep-title").textContent = ep.title;
  $("ep-line").textContent = ep.one_liner || "";
  renderProjects();
  renderSongs();
  renderStageProgress();
  fillSongHeader();
  await refreshBoard();
  renderStageGuide();
}

async function selectSong(id) {
  currentSong = await api(`/api/songs/${id}`);
  selectedVersionId = null;
  renderSongs();
  renderStageProgress();
  fillSongHeader();
  await refreshBoard();
}

async function selectProject(id) {
  currentEpId = Number(id);
  currentSong = null;
  selectedVersionId = null;
  await loadAll();
}

async function createProject() {
  modal("project-modal", true);
}

async function submitProject() {
  const name = $("new-ep-title").value.trim();
  if (!name) {
    toast("请先填写 EP 名称");
    return;
  }
  const firstSong = $("new-ep-first-song").value.trim() || "新歌草稿";
  ep = await api("/api/eps", {
    method: "POST",
    body: JSON.stringify({
      title: name,
      one_liner: $("new-ep-line").value.trim() || "新的 EP 创作项目",
      core_theme: "",
      world_view: "",
      emotional_keywords: [],
      aesthetic_keywords: [],
      sonic_layers: {},
      narrative_arc: "",
      song_list: [],
    }),
  });
  currentEpId = ep.id;
  currentSong = await api("/api/songs", {
    method: "POST",
    body: JSON.stringify({
      ep_id: currentEpId,
      title: firstSong,
      function_in_ep: "待定义",
      concept: "",
      emotional_goal: "",
      bpm: 92,
      genre_direction: "",
      language_plan: "",
      lyrics: "",
      style_prompt: "",
      lyrics_prompt: "",
      notes: "",
      current_stage: "diagnosis",
      stage_status: "not_started",
      locked_hook: "",
      current_structure_route: "",
      current_prompt_pack_id: null,
    }),
  });
  modal("project-modal", false);
  await loadAll();
  toast("新项目已创建");
}

async function createSong() {
  modal("song-modal", true);
}

async function submitSong() {
  if (!currentEpId) return;
  const title = $("new-song-title").value.trim();
  if (!title) {
    toast("请先填写歌名");
    return;
  }
  currentSong = await api("/api/songs", {
    method: "POST",
    body: JSON.stringify({
      ep_id: currentEpId,
      title,
      function_in_ep: $("new-song-function").value.trim() || "待定义",
      concept: $("new-song-concept").value.trim(),
      emotional_goal: "",
      bpm: 92,
      genre_direction: $("new-song-genre").value.trim(),
      language_plan: "",
      lyrics: "",
      style_prompt: "",
      lyrics_prompt: "",
      notes: "",
      current_stage: "diagnosis",
      stage_status: "not_started",
      locked_hook: "",
      current_structure_route: "",
      current_prompt_pack_id: null,
    }),
  });
  modal("song-modal", false);
  await loadAll();
  toast("新歌曲已创建");
}

async function runStage() {
  if (!currentSong || stageRunning) return;
  if (pendingArtifactsForCurrentStage().length) {
    toast("请先处理本阶段待确认创作产物");
    return;
  }
  stageRunning = true;
  const buttonEl = $("run-stage");
  const originalLabel = buttonEl.textContent;
  buttonEl.disabled = true;
  buttonEl.textContent = "AI 正在生成...";
  $("assistant-message").textContent = "正在调用 AI 推进当前阶段。歌词、结构和复盘阶段可能需要几十秒，请稍等。";
  try {
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
    toast("当前阶段已生成待确认创作产物");
  } finally {
    stageRunning = false;
    buttonEl.disabled = false;
    buttonEl.textContent = originalLabel;
  }
}

async function confirmNext() {
  if (!currentSong) return;
  const pendingCount = artifacts.filter((item) => item.status === "pending").length;
  if (pendingCount) {
    toast("请先处理待确认创作产物，再进入下一阶段");
    return;
  }
  if (stageRequiredArtifact[currentSong.current_stage] && !acceptedArtifactsForCurrentStage().length) {
    toast("请先生成并保存本阶段创作产物");
    return;
  }
  const next = nextStageForCurrentSong();
  if (!next) {
    toast("没有可推进的下一阶段");
    return;
  }
  currentSong = await api(`/api/songs/${currentSong.id}/stage/confirm`, {
    method: "POST",
    body: JSON.stringify({ next_stage: next }),
  });
  songs = await api(`/api/songs?ep_id=${currentEpId}`);
  renderSongs();
  renderStageProgress();
  fillSongHeader();
  await refreshBoard();
  lastSession = null;
  toast(`已进入：${stageLabels[next] || next}`);
}

function nextStageKey(stage) {
  const keys = stages.map((item) => item.key);
  const index = keys.indexOf(stage);
  if (index < 0 || index === keys.length - 1) return "done";
  return keys[index + 1];
}

async function makeSuno() {
  if (!currentSong || sunoRunning) return;
  const missing = [];
  if (!currentSong.locked_hook) missing.push("Hook");
  if (!currentSong.current_structure_route) missing.push("结构路线");
  if (!currentSong.lyrics) missing.push("歌词草稿");
  if (missing.length && currentSong.current_stage !== "suno_prompt_lab") {
    $("assistant-message").textContent = `还缺：${missing.join("、")}。\n建议先按阶段补齐：Hook 实验室 -> 结构实验室 -> 歌词草稿 -> Suno Prompt 实验室。\n如果你只是想快速试草稿，请先进入 Suno Prompt 实验室后再生成。`;
    toast("暂不生成：先补齐前置材料");
    return;
  }
  sunoRunning = true;
  const buttonEl = $("make-suno");
  const originalLabel = buttonEl.textContent;
  buttonEl.disabled = true;
  buttonEl.textContent = "正在生成 Prompt...";
  try {
    const data = await api(`/api/songs/${currentSong.id}/suno-prompt-packs`, { method: "POST", body: "{}" });
    $("assistant-message").textContent = `已生成 ${data.packs.length} 套 Suno Prompt Pack，推荐：${data.recommended_variant}`;
    await refreshBoard();
    toast("Suno Prompt 包已生成");
  } finally {
    sunoRunning = false;
    buttonEl.disabled = false;
    buttonEl.textContent = originalLabel;
  }
}

async function actArtifact(id, action) {
  await api(`/api/artifacts/${id}/${action}`, { method: "POST", body: "{}" });
  currentSong = await api(`/api/songs/${currentSong.id}`);
  songs = await api(`/api/songs?ep_id=${currentEpId}`);
  renderSongs();
  fillSongHeader();
  await refreshBoard();
  toast("已更新创作产物状态");
}

async function restoreVersion(versionId) {
  if (!currentSong) return;
  const version = versions.find((item) => item.id === versionId);
  const label = version ? `v${version.version_number}` : "这个版本";
  const confirmed = window.confirm(`确定把当前歌曲回溯到 ${label} 吗？系统会保留当前记录，并新增一个回溯版本。`);
  if (!confirmed) return;
  currentSong = await api(`/api/songs/${currentSong.id}/versions/${versionId}/restore`, {
    method: "POST",
    body: "{}",
  });
  songs = await api(`/api/songs?ep_id=${currentEpId}`);
  renderSongs();
  renderStageProgress();
  fillSongHeader();
  await refreshBoard();
  toast(`已回溯到 ${label}`);
}

async function saveReview() {
  if (!currentSong || reviewSaving) return;
  const promptSelection = parsePromptSelection($("review-prompt-variant").value);
  if ($("review-prompt-variant").options.length > 1 && !promptSelection) {
    toast("请先选择这次实际使用的 Prompt 版本");
    $("review-prompt-variant").focus();
    return;
  }
  const payload = {
    take_name: $("review-take").value,
    prompt_pack_artifact_id: promptSelection?.artifactId || null,
    prompt_pack_variant: promptSelection?.variant || null,
    text_feedback: $("review-feedback").value,
    hook_accuracy: Number($("score-hook").value),
    style_accuracy: Number($("score-style").value),
    section_structure: Number($("score-section").value),
    diction_singability: Number($("score-diction").value),
    emotional_fit: Number($("score-emotion").value),
    production_usability: Number($("score-production").value),
  };
  reviewSaving = true;
  const buttonEl = $("save-review");
  const originalLabel = buttonEl.textContent;
  buttonEl.disabled = true;
  buttonEl.textContent = "正在保存复盘...";
  try {
    const artifact = await api(`/api/songs/${currentSong.id}/generation-reviews`, { method: "POST", body: JSON.stringify(payload) });
    await refreshBoard();
    $("assistant-message").textContent = `生成复盘已保存：${artifact.summary || artifact.content?.next_revision_advice || payload.take_name}`;
    toast("生成复盘已保存");
  } finally {
    reviewSaving = false;
    buttonEl.disabled = false;
    buttonEl.textContent = originalLabel;
  }
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
  await refreshBoard();
  toast("素材已上传归档");
}

async function exportBundle() {
  if (!currentSong || bundleExporting) return;
  bundleExporting = true;
  const buttonEl = $("export-bundle");
  const originalLabel = buttonEl.textContent;
  buttonEl.disabled = true;
  buttonEl.textContent = "正在导出...";
  toast("正在打包制作资料");
  try {
    const response = await fetch(`/api/songs/${currentSong.id}/exports/asset-bundle`, { method: "POST" });
    if (!response.ok) {
      const text = await response.text();
      toast(text || "素材包导出失败，请检查是否已有可导出的内容");
      return;
    }
    await downloadResponse(response, `${currentSong.title || "song"}_asset_bundle.zip`);
    $("assistant-message").textContent = "制作资料包已生成，仅包含当前采用或已接受的创作产物，以及上传素材。";
    toast("正式制作资料包已开始下载");
  } finally {
    bundleExporting = false;
    buttonEl.disabled = false;
    buttonEl.textContent = originalLabel;
  }
}

async function downloadResponse(response, filename) {
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

async function exportCubase() {
  if (!currentSong || cubaseExporting) return;
  cubaseExporting = true;
  const buttonEl = $("export-cubase");
  const originalLabel = buttonEl.textContent;
  buttonEl.disabled = true;
  buttonEl.textContent = "正在导出...";
  try {
    const response = await fetch(`/api/songs/${currentSong.id}/exports/cubase-pack`, { method: "POST" });
    if (!response.ok) throw new Error((await response.text()) || "Cubase 包导出失败");
    await downloadResponse(response, `${currentSong.title || "song"}_cubase_pack.zip`);
    $("assistant-message").textContent = "Cubase 导入包已生成，包含 MIDI 骨架、编排表、Prompt 和导入说明；它不是 .cpr 工程文件。";
    toast("Cubase 导入包已开始下载");
  } finally {
    cubaseExporting = false;
    buttonEl.disabled = false;
    buttonEl.textContent = originalLabel;
  }
}

async function shutdownService() {
  const confirmed = window.confirm("要关闭 EP Creative OS 本地服务吗？关闭后刷新页面会打不开，需要重新双击启动文件。");
  if (!confirmed) return;
  const buttonEl = $("shutdown-service");
  buttonEl.disabled = true;
  buttonEl.textContent = "正在关闭...";
  $("assistant-message").textContent = "本地服务正在关闭。几秒后你可以直接关闭这个浏览器标签页；下次使用请双击“打开 EP Creative OS.bat”。";
  try {
    await fetch("/api/system/shutdown", { method: "POST" });
  } catch (_) {
    // The request may be interrupted because the server is shutting down.
  }
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
  songs = await api(`/api/songs?ep_id=${currentEpId}`);
  renderSongs();
  fillSongHeader();
  modal("archive-drawer", false);
  toast("歌曲档案已保存");
}

$("run-stage").onclick = () => runStage().catch((err) => toast(err.message));
$("confirm-next").onclick = () => confirmNext().catch((err) => toast(err.message));
$("make-suno").onclick = () => makeSuno().catch((err) => toast(err.message));
$("save-review").onclick = () => saveReview().catch((err) => toast(err.message));
$("asset-file").onchange = () => uploadAsset().catch((err) => toast(err.message));
$("export-bundle").onclick = () => exportBundle().catch((err) => toast(err.message));
$("export-cubase").onclick = () => exportCubase().catch((err) => toast(err.message));
$("shutdown-service").onclick = () => shutdownService().catch((err) => toast(err.message));
$("refresh-board").onclick = () => refreshBoard().catch((err) => toast(err.message));
$("review-prompt-variant").onchange = markSelectedReviewPromptUsed;
$("open-archive").onclick = () => modal("archive-drawer", true, $("open-archive"));
$("close-archive").onclick = () => modal("archive-drawer", false);
$("save-song").onclick = () => saveSong().catch((err) => toast(err.message));
$("project-select").onchange = (event) => selectProject(event.target.value).catch((err) => toast(err.message));
$("new-project").onclick = () => createProject().catch((err) => toast(err.message));
$("new-song").onclick = () => createSong().catch((err) => toast(err.message));
$("close-project-modal").onclick = () => modal("project-modal", false);
$("close-song-modal").onclick = () => modal("song-modal", false);
$("create-project-submit").onclick = () => submitProject().catch((err) => toast(err.message));
$("create-song-submit").onclick = () => submitSong().catch((err) => toast(err.message));

document.addEventListener("keydown", (event) => {
  if (!activeOverlay) return;
  if (event.key === "Escape") {
    event.preventDefault();
    modal(activeOverlay.id, false);
    return;
  }
  if (event.key !== "Tab") return;
  const focusable = [...activeOverlay.querySelectorAll('button:not([disabled]), input:not([disabled]), textarea:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])')]
    .filter((element) => !element.hidden && element.getClientRects().length);
  if (!focusable.length) return;
  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
});

loadAll().catch((err) => {
  console.error(err);
  toast(err.message);
});
