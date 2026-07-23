const GROQ_TRANSCRIBE_URL = "https://api.groq.com/openai/v1/audio/transcriptions";

export async function transcribeVoice(apiKey: string, audioBytes: Uint8Array): Promise<string> {
  const form = new FormData();
  form.append("file", new Blob([audioBytes]), "voice.ogg");
  form.append("model", "whisper-large-v3-turbo");
  form.append("language", "uz");

  const res = await fetch(GROQ_TRANSCRIBE_URL, {
    method: "POST",
    headers: { Authorization: `Bearer ${apiKey}` },
    body: form,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Groq STT error ${res.status}: ${text}`);
  }
  const data = await res.json();
  return (data.text as string) ?? "";
}
