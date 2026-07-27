import aiohttp

from app.config import settings

_GROQ_TRANSCRIBE_URL = "https://api.groq.com/openai/v1/audio/transcriptions"


async def transcribe_voice(audio_bytes: bytes) -> str:
    form = aiohttp.FormData()
    form.add_field("file", audio_bytes, filename="voice.ogg", content_type="audio/ogg")
    # The "turbo" variant trades multilingual accuracy for speed (fewer
    # decoder layers), which hurts lower-resource languages like Uzbek
    # noticeably more than English - use the full model instead.
    form.add_field("model", "whisper-large-v3")
    form.add_field("language", "uz")

    async with aiohttp.ClientSession() as session:
        async with session.post(
            _GROQ_TRANSCRIBE_URL,
            data=form,
            headers={"Authorization": f"Bearer {settings.groq_api_key}"},
            # Groq's Whisper inference runs many times faster than real-time,
            # so 180s is generous headroom even for a long voice message -
            # set explicitly instead of relying on aiohttp's implicit default.
            timeout=aiohttp.ClientTimeout(total=180),
        ) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(f"Groq STT error {resp.status}: {text}")
            data = await resp.json()
            return data.get("text", "")
