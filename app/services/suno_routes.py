from copy import deepcopy


ROUTE_REGISTRY = {
    "classic_pop": {
        "route": "classic_pop",
        "section_map": [
            {"label": "[Intro]", "purpose": "establish pulse and motif", "delivery": "instrumental or hummed fragment", "hook_instruction": "hint at hook contour only"},
            {"label": "[Verse]", "purpose": "place the concrete song image", "delivery": "low, clear, short lines", "hook_instruction": "do not spend the hook yet"},
            {"label": "[Pre-Chorus]", "purpose": "tighten tension into chorus", "delivery": "shorter rising phrases", "hook_instruction": "prepare the hook with one pickup"},
            {"label": "[Chorus]", "purpose": "make the memory point obvious", "delivery": "repeatable melodic lines", "hook_instruction": "start with the hook and repeat once"},
            {"label": "[Bridge]", "purpose": "one new angle, stripped", "delivery": "half-sung, less percussion", "hook_instruction": "avoid adding a new hook"},
            {"label": "[Final Chorus]", "purpose": "return with restrained lift", "delivery": "doubled hook, same lyric anchor", "hook_instruction": "repeat the hook clearly"},
        ],
        "arrangement_motion": "stable verse-pre-chorus-chorus shape with one stripped bridge",
        "hook_placement": "chorus first line, final chorus first line, optional outro tag",
        "stability_notes": "highest stability route for Suno section parsing",
        "suno_risks": ["can feel too standard if images are vague"],
        "stability_score": 9,
    },
    "loop_mantra": {
        "route": "loop_mantra",
        "section_map": [
            {"label": "[Loop A]", "purpose": "introduce a short mantra", "delivery": "soft repeated hook", "hook_instruction": "repeat the hook as the loop seed"},
            {"label": "[Memory Insert]", "purpose": "add one concrete image", "delivery": "half-sung fragment", "hook_instruction": "answer the hook, do not replace it"},
            {"label": "[Loop B]", "purpose": "mutate rhythm and texture", "delivery": "same words, changed cadence", "hook_instruction": "keep hook wording stable"},
            {"label": "[Exit]", "purpose": "thin the loop down", "delivery": "near-whisper, fewer drums", "hook_instruction": "leave one final hook echo"},
        ],
        "arrangement_motion": "mantra loop mutates every 8 bars and ends thinner than it starts",
        "hook_placement": "every loop entrance",
        "stability_notes": "stable if the hook stays very short",
        "suno_risks": ["can become static if the loop has too many words"],
        "stability_score": 7,
    },
    "scene_cut": {
        "route": "scene_cut",
        "section_map": [
            {"label": "[Scene One]", "purpose": "first image or camera setup", "delivery": "close vocal, visual nouns", "hook_instruction": "hide the hook as an image"},
            {"label": "[Cut]", "purpose": "scene/cut/image transition", "delivery": "brief rhythmic reset", "hook_instruction": "use one hook word as the cut point"},
            {"label": "[Scene Two]", "purpose": "new location or time jump", "delivery": "slightly brighter cadence", "hook_instruction": "approach hook from a new angle"},
            {"label": "[Chorus]", "purpose": "resolve the image transition into memory", "delivery": "clear repeated hook", "hook_instruction": "repeat the hook after the scene cut"},
            {"label": "[Final Image]", "purpose": "last camera frame", "delivery": "minimal, visual, unresolved", "hook_instruction": "one final hook fragment"},
        ],
        "arrangement_motion": "camera-like scene cuts and image transition moves before the chorus locks in",
        "hook_placement": "after the main cut and as the final image tag",
        "stability_notes": "keep each scene short so Suno does not treat it as spoken script",
        "suno_risks": ["too many scene labels can fragment the song"],
        "stability_score": 6,
    },
    "error_system": {
        "route": "error_system",
        "section_map": [
            {"label": "[System Intro]", "purpose": "access failure motif", "delivery": "machine hum and short denial phrase", "hook_instruction": "state the denial hook once"},
            {"label": "[Cache Verse]", "purpose": "old chat or old room fragments", "delivery": "half-sung, dry vocal", "hook_instruction": "do not explain the full system metaphor"},
            {"label": "[Retry Pre-Chorus]", "purpose": "failed attempt tension", "delivery": "short command-like lines", "hook_instruction": "tighten into the hook"},
            {"label": "[Access Failure Chorus]", "purpose": "denial becomes the chorus", "delivery": "repeat hook clearly", "hook_instruction": "hook first, then one answer line"},
            {"label": "[Old Version Bridge]", "purpose": "old self cannot reopen", "delivery": "stripped, half-spoken", "hook_instruction": "return to one denial phrase"},
            {"label": "[Final Chorus]", "purpose": "failed-login motif returns", "delivery": "restrained double", "hook_instruction": "repeat hook and stop unresolved"},
        ],
        "arrangement_motion": "access failure, retry, denial motif, then failed-login outro",
        "hook_placement": "system intro, access failure chorus, final chorus",
        "stability_notes": "use only for explicit error-system or access failure narratives",
        "suno_risks": ["can become spoken-word if system words dominate"],
        "stability_score": 5,
    },
    "body_memory": {
        "route": "body_memory",
        "section_map": [
            {"label": "[Breath Intro]", "purpose": "body reaction and breath", "delivery": "audible inhale, close vocal", "hook_instruction": "hint hook in breath rhythm"},
            {"label": "[Verse - Body]", "purpose": "physical response", "delivery": "short tactile images", "hook_instruction": "keep hook off-screen"},
            {"label": "[Pulse Lift]", "purpose": "movement and touch become rhythm", "delivery": "more pulse, still restrained", "hook_instruction": "prepare hook with body action"},
            {"label": "[Chorus]", "purpose": "emotion lands in the body", "delivery": "clear repeated hook", "hook_instruction": "repeat hook with breath spacing"},
            {"label": "[Bridge - Tactile]", "purpose": "touch, movement, memory residue", "delivery": "sparse, tactile, half-sung", "hook_instruction": "one quiet hook echo"},
        ],
        "arrangement_motion": "breath/body/tactile/movement cues drive density changes",
        "hook_placement": "chorus, bridge echo, final breath tag",
        "stability_notes": "works when images are physical instead of abstract",
        "suno_risks": ["overwritten body details can become prose"],
        "stability_score": 6,
    },
    "through_composed": {
        "route": "through_composed",
        "section_map": [
            {"label": "[Opening]", "purpose": "begin the melodic path", "delivery": "new line shape", "hook_instruction": "state only a tiny hook seed"},
            {"label": "[Development]", "purpose": "keep moving without full repetition", "delivery": "fresh melody, related rhythm", "hook_instruction": "avoid full chorus repeat"},
            {"label": "[Echo Phrase]", "purpose": "one returning echo phrase", "delivery": "same phrase, different harmony", "hook_instruction": "repeat the echo phrase exactly"},
            {"label": "[Turn]", "purpose": "change texture or perspective", "delivery": "reduced drums", "hook_instruction": "do not add another refrain"},
            {"label": "[Final Echo]", "purpose": "reduced repetition ending", "delivery": "minimal, unresolved", "hook_instruction": "bring back the echo once"},
        ],
        "arrangement_motion": "through-composed development with reduced repetition and one echo phrase",
        "hook_placement": "one echo phrase mid-song and final echo",
        "stability_notes": "less repetitive, so the echo phrase must be clear",
        "suno_risks": ["lower hook recall if the echo phrase is too subtle"],
        "stability_score": 4,
    },
}


def get_route_spec(route: str | None) -> dict:
    route_key = (route or "").strip() or "classic_pop"
    if route_key not in ROUTE_REGISTRY:
        spec = deepcopy(ROUTE_REGISTRY["classic_pop"])
        spec["requested_route"] = route_key
        spec["warnings"] = [f"Unknown route `{route_key}` fell back to classic_pop for stability."]
        return spec
    spec = deepcopy(ROUTE_REGISTRY[route_key])
    spec["warnings"] = []
    return spec
