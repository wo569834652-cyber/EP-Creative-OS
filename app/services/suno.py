from app.models import Song
from app.schemas import SunoResponse
from app.services.suno_engine import legacy_suno_response


def generate_suno_prompt(song: Song, db=None) -> SunoResponse:
    return legacy_suno_response(song, db=db)
