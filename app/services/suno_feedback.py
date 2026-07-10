import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CreativeArtifact, Song


PROBLEM_RULES = [
    ("hook_clarity", ["hook unclear", "hook is unclear", "hook not clear", "Hook 不清楚", "hook 不清楚", "不清楚"]),
    ("style_drift", ["style drift", "style missed", "风格偏离", "风格跑偏"]),
    ("heavy_drums", ["drums too heavy", "heavy drums", "鼓太重", "鼓太猛"]),
    ("over_sweet_vocal", ["vocal too sweet", "too sweet", "人声太甜", "太甜"]),
    ("unclear_verse_diction", ["verse unclear", "diction unclear", "主歌唱不清", "咬字不清"]),
    ("messy_structure", ["messy structure", "structure confused", "结构混乱", "段落混乱"]),
    ("production_unusable", ["production unusable", "unusable", "制作不可用", "难用"]),
]

ADVICE = {
    "hook_clarity": "strengthen hook repetition / chorus clarity",
    "style_drift": "tighten genre, groove, and instrument palette",
    "heavy_drums": "drums softened / reduce percussion density",
    "over_sweet_vocal": "less sweet, more restrained vocal",
    "unclear_verse_diction": "shorten lyric lines / clearer diction",
    "messy_structure": "reduce section labels / clarify chorus and bridge",
    "production_unusable": "simplify arrangement / dry vocal / clearer pulse",
}


def _match_problem(text: str) -> list[str]:
    found = []
    for key, terms in PROBLEM_RULES:
        if any(term.lower() in text.lower() for term in terms):
            found.append(key)
    return found


def _terms(text: str) -> list[str]:
    candidates = re.findall(r"[A-Za-z][A-Za-z -]{2,32}|[\u4e00-\u9fff]{2,8}", text or "")
    cleaned = []
    for item in candidates:
        term = item.strip(" -").lower()
        if len(term) >= 2 and term not in cleaned:
            cleaned.append(term)
    return cleaned[:12]


def summarize_generation_reviews(db: Session, song: Song, limit: int = 5) -> dict:
    reviews = list(
        db.scalars(
            select(CreativeArtifact)
            .where(CreativeArtifact.song_id == song.id)
            .where(CreativeArtifact.artifact_type == "generation_review")
            .where(CreativeArtifact.status == "accepted")
            .order_by(CreativeArtifact.created_at.desc())
            .limit(limit)
        ).all()
    )
    recurring: list[str] = []
    blocked_terms: list[str] = []
    winning_terms: list[str] = []
    feedback_used: list[dict] = []

    for artifact in reviews:
        content = artifact.content or {}
        text = " ".join(
            str(content.get(key) or "")
            for key in ["text_feedback", "next_revision_target", "next_revision_advice"]
        )
        problems = _match_problem(text)
        for problem in problems:
            if problem not in recurring:
                recurring.append(problem)
        scores = content.get("scores") or {}
        for score_key, value in scores.items():
            if isinstance(value, int | float) and value <= 2:
                mapped = {
                    "hook_accuracy": "hook_clarity",
                    "style_accuracy": "style_drift",
                    "section_structure": "messy_structure",
                    "diction_singability": "unclear_verse_diction",
                    "production_usability": "production_unusable",
                }.get(score_key)
                if mapped and mapped not in recurring:
                    recurring.append(mapped)
            if isinstance(value, int | float) and value >= 4:
                label = score_key.replace("_", " ")
                if label not in winning_terms:
                    winning_terms.append(label)
        blocked_terms.extend([term for term in _terms(text) if term not in blocked_terms][:4])
        feedback_used.append(
            {
                "artifact_id": artifact.id,
                "take_name": content.get("take_name") or artifact.title,
                "prompt_pack_trace": content.get("prompt_pack_trace") or {},
                "next_revision_target": content.get("next_revision_target", ""),
                "next_revision_advice": content.get("next_revision_advice", ""),
            }
        )

    bias_parts = [ADVICE[item] for item in recurring if item in ADVICE]
    return {
        "review_count": len(reviews),
        "winning_terms": winning_terms[:8],
        "blocked_terms": blocked_terms[:10],
        "recurring_problems": recurring[:8],
        "next_revision_bias": "; ".join(bias_parts) if bias_parts else "",
        "feedback_used": feedback_used,
    }
