from app.models import Song
from app.schemas import SunoResponse


NEGATIVE_STYLE_TERMS = ["Mandarin", "Chinese", "普通话", "中文", "language-focused", "spoken essay", "overly theatrical"]


def generate_suno_prompt(song: Song) -> SunoResponse:
    genre = song.genre_direction or "alternative pop / bedroom electronic"
    parts = [part.strip() for part in genre.replace(",", "/").split("/") if part.strip()]
    primary = parts[0] if parts else "alternative pop"
    secondary = parts[1] if len(parts) > 1 else "bedroom electronic"
    bpm = song.bpm or 92
    mood = song.emotional_goal or "restrained, intimate, slightly haunted"
    palette = "soft synth pads, muted electric piano, CRT-like hum textures, close dry vocal, subtle room tone"

    style_prompt = (
        f"Primary genre: {primary}; secondary genre: {secondary}; BPM: {bpm}; "
        "groove/drums: restrained mid-tempo pocket, tight kick, dry snare, sparse glitch percussion; "
        "bass: warm sub bass with simple repeated movement, never too busy; "
        f"harmony/instrument palette: {palette}; "
        "vocal direction: close, intimate, slightly breathy, controlled dynamics, hook doubled lightly; "
        f"mood: {mood}; "
        "forbidden terms: avoid language labels, avoid cinematic trailer, avoid EDM drop, avoid metal guitars."
    )

    hook_seed = "别关掉我" if "别关" in song.title else "我听见回音"
    if song.notes and "hook reference" in song.notes:
        hook_seed = song.notes.split("hook reference:", 1)[-1].strip().splitlines()[0].strip() or hook_seed

    lyrics_prompt = f"""[Global vocal direction]
Close, intimate lead vocal. Keep the chorus hook short and repeatable. Allow multilingual texture only when it serves character or interface feeling, not translation.

[Instrumental Intro]
4 bars. Room tone, soft machine hum, one simple motif.

[Verse]
Describe the concrete scene and body state. Put complex EP concept here, with conversational rhythm and enough rests.

[Pre-Chorus]
Increase tension with shorter lines. Let the narrator notice the system-like pattern behind the emotion.

[Chorus]
Use a short hook: "{hook_seed}". Repeat it with one small variation. Prioritize melody over explanation.

[Post-Chorus]
Optional chopped vocal or system-like response phrase, very sparse.

[Bridge]
Spoken-rap or half-sung reflection. Connect this song's EP function: {song.function_in_ep or "a fragment in the adult self-archive"}.

[Final Chorus]
Return to the hook with stronger doubles and one unresolved final line.

[Outro]
Fade with room tone, machine texture, and a small unfinished vocal fragment.
"""

    return SunoResponse(
        title=song.title,
        style_prompt=style_prompt,
        lyrics_prompt=lyrics_prompt,
        negative_style_terms=NEGATIVE_STYLE_TERMS,
        bpm=bpm,
        generation_notes="Style Prompt intentionally avoids language labels. Paste Lyrics Prompt into Suno lyric/instruction area and keep the chorus hook compact.",
    )
