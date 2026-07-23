import aiohttp

from app.config import settings

_GROQ_TRANSCRIBE_URL = "https://api.groq.com/openai/v1/audio/transcriptions"


async def transcribe_voice(audio_bytes: bytes) -> str:
    form = aiohttp.FormData()
    form.add_field("file", audio_bytes, filename="voice.ogg", content_type="audio/ogg")
    form.add_field("model", "whisper-large-v3-turbo")
    form.add_field("language", "uz")

    async with aiohttp.ClientSession() as session:
        async with session.post(
            _GROQ_TRANSCRIBE_URL,
            data=form,
            headers={"Authorization": f"Bearer {settings.groq_api_key}"},
        ) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(f"Groq STT error {resp.status}: {text}")
            data = await resp.json()
            return data.get("text", "")
