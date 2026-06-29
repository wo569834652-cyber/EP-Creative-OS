STAGES = [
    "diagnosis",
    "hook_lab",
    "structure_lab",
    "lyrics_draft",
    "suno_prompt_lab",
    "generation_review",
    "asset_organizer",
]


STAGE_LABELS = {
    "diagnosis": "歌曲诊断",
    "hook_lab": "Hook 实验室",
    "structure_lab": "结构实验室",
    "lyrics_draft": "歌词草稿",
    "suno_prompt_lab": "Suno Prompt 实验室",
    "generation_review": "生成复盘",
    "asset_organizer": "素材整理",
    "parked": "暂停",
    "done": "完成",
}


STAGE_DESCRIPTIONS = {
    "diagnosis": "判断歌曲在 EP 叙事中的功能和当前最该解决的问题。",
    "hook_lab": "生成短、可重复、可唱的 Hook 候选并推荐一个。",
    "structure_lab": "选择结构路线，不把所有歌压成同一套段落模板。",
    "lyrics_draft": "把 Hook 和结构路线扩展成可唱歌词草稿。",
    "suno_prompt_lab": "生成最多三套可复制的 Suno Prompt Pack，并推荐一套。",
    "generation_review": "记录 Suno 结果反馈，不伪装成音频分析。",
    "asset_organizer": "整理歌词、Prompt、复盘、上传素材并导出素材包。",
}


STAGE_COMPLETION = {
    "diagnosis": ["明确 EP 功能", "明确最大问题", "推荐下一阶段"],
    "hook_lab": ["至少一个推荐 Hook", "说明节奏和 Suno 风险"],
    "structure_lab": ["选定结构路线", "说明 Hook 出现位置", "提供可选创新方案"],
    "lyrics_draft": ["生成分段歌词", "副歌短句优先", "复杂概念放入主歌或桥段"],
    "suno_prompt_lab": ["最多三套 Prompt Pack", "推荐一套", "通过质量检查"],
    "generation_review": ["记录文字反馈", "记录打分", "给出下一轮修正方向"],
    "asset_organizer": ["生成素材清单", "导出素材包", "不承诺 Cubase 原生工程"],
}


def next_stage(stage: str) -> str | None:
    if stage not in STAGES:
        return None
    index = STAGES.index(stage)
    if index >= len(STAGES) - 1:
        return "done"
    return STAGES[index + 1]


def stage_metadata() -> list[dict]:
    return [
        {
            "key": stage,
            "label": STAGE_LABELS[stage],
            "description": STAGE_DESCRIPTIONS[stage],
            "completion": STAGE_COMPLETION[stage],
        }
        for stage in STAGES
    ]
