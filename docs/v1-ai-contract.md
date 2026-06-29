# EP Creative OS V1 AI Contract

## DeepSeek Configuration

V1 uses DeepSeek's OpenAI-compatible chat completions endpoint.

Defaults:

- `DEEPSEEK_BASE_URL=https://api.deepseek.com`
- `DEEPSEEK_MODEL=deepseek-v4-pro`
- `DEEPSEEK_CONTEXT_WINDOW=1000000`

The context window setting is application configuration for budgeting and prompt assembly. It is not sent as a custom request field unless the API explicitly supports it.

## Runtime Rule

The model must not browse the web or research Suno prompting at runtime. Suno prompting methodology is encoded in the application as deterministic rules, templates, validators, and quality checks.

## Session Response Shape

The API should return human-readable guidance plus structured artifacts.

```json
{
  "session_id": 1,
  "stage": "hook_lab",
  "message": "Readable producer response.",
  "stage_recommendation": {
    "current_stage": "hook_lab",
    "next_stage": "structure_lab",
    "reason": "The hook selection criteria are satisfied.",
    "requires_user_confirmation": true
  },
  "artifacts": [
    {
      "id": 10,
      "type": "hook_set",
      "title": "Cold access-failure hooks",
      "summary": "Five short hooks built from system denial language.",
      "status": "pending",
      "recommended": true,
      "content": {}
    }
  ],
  "next_actions": [
    "Accept or discard the hook set.",
    "Lock one hook before moving to Structure Lab."
  ]
}
```

## Stage Behavior

## Diagnosis

Must cover:

- EP function
- current biggest problem
- strongest usable material
- recommended next stage
- risks

Artifact type: `diagnosis`.

## Hook Lab

Must produce 3 to 5 options.

Each hook includes:

- `hook_text`
- `why_it_works`
- `rhythm_notes`
- `suno_risk`
- `score`

Scoring criteria:

- short phrase preferred
- repeatability
- vowel/rhyme unity
- concept over-explaining penalty
- singability penalty for prose-like lines

Artifact type: `hook_set`.

## Structure Lab

Must recommend one route and optionally provide an experimental variant.

Routes:

- `classic_pop`
- `loop_mantra`
- `scene_cut`
- `error_system`
- `body_memory`
- `through_composed`

Each route includes:

- route name
- why it fits the song's EP function
- section map
- hook placement
- stability rating
- innovation rating
- Suno risks
- how to feed it to Suno

Artifact type: `structure_route`.

## Lyrics Draft

Must respect selected hook and structure route.

Rules:

- chorus should be short and melodic
- complex concepts go to verse, bridge, spoken/half-sung sections
- multilingual material must have function, not translation padding
- preserve the EP narrative role

Artifact type: `lyrics_draft`.

## Suno Prompt Lab

Must produce at most 3 prompt packs:

- `primary`
- `alternate`
- `experimental`

Must recommend exactly one.

Artifact type: `suno_prompt_pack`.

Prompt pack fields:

- `variant`
- `recommended`
- `recommendation_reason`
- `style_prompt`
- `lyrics_prompt`
- `negative_terms`
- `hook_delivery_notes`
- `section_control_notes`
- `revision_strategy`
- `suno_risks`
- `quality_checks`

Quality priority:

1. Hook and sections are more likely to be sung correctly.
2. The next revision target is clear.
3. Results are stable enough to iterate.
4. The song remains distinctive without sacrificing generation reliability.

## Generation Review

The AI does not analyze audio. It uses user feedback, scores, and uploaded file metadata.

Input fields:

- take name
- prompt pack version
- text feedback
- hook accuracy score
- style accuracy score
- section structure score
- diction/singability score
- emotional fit score
- production usability score
- uploaded asset references

Output:

- what worked
- what failed
- whether to revise Style Prompt, Lyrics Prompt, Hook, or Structure
- next prompt adjustment

Artifact type: `generation_review`.

## Asset Organizer

Must produce a clear asset bundle summary.

Artifact type: `asset_bundle`.

## Suno Prompt Engine Rules

Suno Prompt generation is not open-ended text generation. The program applies fixed rules.

Style Prompt must include:

- primary genre
- secondary genre
- BPM
- groove and drum behavior
- bass behavior
- harmony and instrument palette
- vocal direction
- mood
- production constraints
- forbidden terms

Style Prompt must not include:

- Mandarin
- Chinese
- 普通话
- 中文
- language-first phrasing
- literary synopsis
- excessive abstract concept stacks

Lyrics Prompt must include:

- vocal direction
- section labels from the selected structure route
- hook placement
- performance cues where useful
- revision intent

Lyrics Prompt should use tags such as:

- `[Verse]`
- `[Chorus]`
- `[Bridge]`
- `[Outro]`
- `(close vocal)`
- `(half-sung)`
- `(whispered)`

Structure labels are not fixed. They come from Structure Lab.

## Validation Checks

Every Suno Prompt Pack should be checked for:

- no forbidden language labels in Style Prompt
- BPM present
- groove/drums present
- bass present
- vocal direction present
- hook appears in Lyrics Prompt
- chorus or hook section is not too long
- negative terms present
- revision strategy present

The API can return warnings rather than blocking generation.
