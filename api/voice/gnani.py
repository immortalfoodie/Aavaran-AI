"""
Gnani AI speech client for Aavaran AI.

Wraps two Gnani (Vachana) REST APIs:
- Prisma  (speech-to-text):  POST https://api.vachana.ai/stt/v3
- Timbre  (text-to-speech):  POST https://api.vachana.ai/api/v1/tts/inference

The API key is read from the server environment (GNANI_API_KEY) and is never
sent to the browser. All calls go through this module so they can be mocked
in tests with an httpx transport.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Iterable, Optional

import httpx

logger = logging.getLogger(__name__)

STT_URL = "https://api.vachana.ai/stt/v3"
TTS_URL = "https://api.vachana.ai/api/v1/tts/inference"

DEFAULT_STT_MODEL = "prisma-v3.0"
DEFAULT_TTS_MODEL = "timbre-v3.0"

# Languages Aavaran AI's Saarthi supports end-to-end.
# "hi-en" is Hinglish: STT gets a multi-language hint, TTS gets the Hindi voice
# (Timbre v3.0 voices speak every language; v2.5 has a dedicated Hinglish voice).
SUPPORTED_LANGS = ("hi-IN", "mr-IN", "en-IN", "hi-en", "ta-IN", "te-IN", "kn-IN", "gu-IN", "pa-IN", "bn-IN")

# Prisma v3.0 language hints. These are hints, not locks. Hinglish gets a multi-language hint.
STT_LANGUAGE_HINT = {code: code for code in SUPPORTED_LANGS if code != "hi-en"}
STT_LANGUAGE_HINT["hi-en"] = "hi-IN,en-IN"

# Timbre language codes
TTS_LANGUAGE = {code: code for code in SUPPORTED_LANGS if code != "hi-en"}
TTS_LANGUAGE["hi-en"] = "hi-IN"

# Default voices per model. Timbre v3.0 voices speak all 10 languages.
DEFAULT_VOICES = {
    "timbre-v3.0": dict.fromkeys(SUPPORTED_LANGS, "Shivani"),
    "timbre-v2.5": {
        "hi-IN": "Nalini", "mr-IN": "Zahira", "en-IN": "Kaveri", "hi-en": "Poorvi", "ta-IN": "Asmita",
        "te-IN": "Suhana", "kn-IN": "Saanvi", "gu-IN": "Falak", "pa-IN": "Mehuli", "bn-IN": "Kirra",
    },
}

STT_TOPIC = (
    "Indian farmer or small food business asking how to pack and store fresh produce "
    "or packaged food: crop name, cut or whole, days since harvest, storage in shed, "
    "cold storage or ice, pack size in grams, shelf life in days."
)


class GnaniError(Exception):
    """Raised for any failed Gnani API call. `code` is a short machine-readable reason."""

    def __init__(self, message: str, status_code: int = 0, code: str = "GNANI_ERROR") -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code


@dataclass
class SttResult:
    transcript: str
    model: Optional[str] = None
    detected_language: Optional[str] = None
    request_id: Optional[str] = None
    latency_s: Optional[float] = None
    raw: dict = field(default_factory=dict)


def _error_from_response(resp: httpx.Response) -> GnaniError:
    code = "GNANI_ERROR"
    message = f"Gnani API returned HTTP {resp.status_code}"
    try:
        body = resp.json()
    except Exception:
        body = None
    if isinstance(body, dict):
        detail = body.get("detail")
        err = body.get("error")
        if isinstance(detail, dict):
            code = str(detail.get("error_code") or code)
            message = str(detail.get("message") or message)
        elif isinstance(err, dict):
            code = str(err.get("type") or code)
            message = str(err.get("message") or message)
        elif isinstance(body.get("code"), str):
            code = body["code"]
            message = str(body.get("message") or message)
        elif body.get("message"):
            message = str(body["message"])
    if resp.status_code == 401 and code == "GNANI_ERROR":
        code = "INVALID_API_KEY"
    elif resp.status_code == 402:
        code = "INSUFFICIENT_CREDITS"
    elif resp.status_code == 429 and code == "GNANI_ERROR":
        code = "RATE_LIMITED"
    elif resp.status_code == 504 and code == "GNANI_ERROR":
        code = "UPSTREAM_TIMEOUT"
    return GnaniError(message, status_code=resp.status_code, code=code)


class GnaniClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        stt_model: Optional[str] = None,
        tts_model: Optional[str] = None,
        tts_voice: Optional[str] = None,
        transport: Optional[httpx.BaseTransport] = None,
        timeout_s: float = 45.0,
    ) -> None:
        self.api_key = api_key if api_key is not None else os.environ.get("GNANI_API_KEY", "")
        self.stt_model = stt_model or os.environ.get("GNANI_STT_MODEL") or DEFAULT_STT_MODEL
        self.tts_model = tts_model or os.environ.get("GNANI_TTS_MODEL") or DEFAULT_TTS_MODEL
        self.tts_voice_override = tts_voice or os.environ.get("GNANI_TTS_VOICE") or None
        self._transport = transport
        self._timeout = timeout_s

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def _client(self) -> httpx.Client:
        return httpx.Client(transport=self._transport, timeout=self._timeout)

    def _headers(self) -> dict:
        if not self.api_key:
            raise GnaniError("GNANI_API_KEY is not configured on the server.", 503, "NOT_CONFIGURED")
        return {"X-API-Key-ID": self.api_key}

    def voice_for(self, lang: str) -> str:
        if self.tts_voice_override:
            return self.tts_voice_override
        voices = DEFAULT_VOICES.get(self.tts_model, DEFAULT_VOICES[DEFAULT_TTS_MODEL])
        return voices.get(lang, next(iter(voices.values())))

    # ------------------------------------------------------------------ STT
    def transcribe(
        self,
        audio: bytes,
        filename: str = "speech.wav",
        lang: str = "hi-IN",
        keyterms: Optional[Iterable[str]] = None,
        topic: Optional[str] = STT_TOPIC,
        content_type: str = "audio/wav",
    ) -> SttResult:
        """Transcribe a short (<= 30 s) clip with Gnani Prisma."""
        if not audio:
            raise GnaniError("Empty audio upload.", 400, "EMPTY_AUDIO")

        is_v3 = self.stt_model.startswith("prisma-v3")
        data: dict[str, str] = {
            "language_code": STT_LANGUAGE_HINT.get(lang, lang) if is_v3 else STT_LANGUAGE_HINT.get(lang, lang).split(",")[0],
            "format": "transcribe",
        }
        if is_v3:
            data["model"] = self.stt_model
            terms = [t for t in (keyterms or []) if t][:200]
            if terms:
                data["keyterms"] = ",".join(terms)
            if topic:
                data["topic"] = topic[:1600]

        try:
            with self._client() as client:
                resp = client.post(
                    STT_URL,
                    headers=self._headers(),
                    files={"audio_file": (filename, audio, content_type)},
                    data=data,
                )
        except httpx.HTTPError as exc:
            raise GnaniError(f"Could not reach Gnani STT: {exc}", 502, "NETWORK_ERROR") from exc

        if resp.status_code != 200:
            raise _error_from_response(resp)
        body = resp.json()
        if body.get("success") is False:
            raise _error_from_response(resp)
        return SttResult(
            transcript=str(body.get("transcript") or "").strip(),
            model=body.get("model"),
            detected_language=body.get("detected_language_code"),
            request_id=body.get("request_id"),
            latency_s=body.get("end_to_end_latency"),
            raw=body,
        )

    # ------------------------------------------------------------------ TTS
    def tts_plan(self, lang: str) -> tuple[str, str, str]:
        """(model, voice, language) to use for a Saarthi language.

        Hinglish goes to Timbre v2.5's dedicated code-mixed voice (Poorvi, `hi-en`),
        which reads Latin-script Hinglish naturally. Everything else uses the
        configured model (Timbre v3.0 by default).
        """
        if lang == "hi-en" and not self.tts_voice_override:
            return "timbre-v2.5", "Poorvi", "hi-en"
        return self.tts_model, self.voice_for(lang), TTS_LANGUAGE.get(lang, lang)

    def synthesize(self, text: str, lang: str = "hi-IN", voice: Optional[str] = None, speed: float = 1.0) -> bytes:
        """Synthesize speech with Gnani Timbre. Returns MP3 bytes."""
        text = (text or "").strip()
        if not text:
            raise GnaniError("Empty text for synthesis.", 400, "EMPTY_TEXT")
        model, plan_voice, language = self.tts_plan(lang)
        payload = {
            "text": text,
            "model": model,
            "voice": voice or plan_voice,
            "language": language,
            "speed": max(0.85, min(1.15, speed)),
            "audio_config": {"container": "mp3", "sample_rate": 24000, "num_channels": 1, "bitrate": "64k"},
        }
        try:
            with self._client() as client:
                resp = client.post(TTS_URL, headers=self._headers(), json=payload)
        except httpx.HTTPError as exc:
            raise GnaniError(f"Could not reach Gnani TTS: {exc}", 502, "NETWORK_ERROR") from exc
        if resp.status_code != 200:
            raise _error_from_response(resp)
        ctype = resp.headers.get("content-type", "")
        if "json" in ctype:
            # Errors are JSON; audio is binary.
            raise _error_from_response(resp)
        return resp.content


_default_client: Optional[GnaniClient] = None
_override_client: Optional[GnaniClient] = None


def get_gnani_client() -> GnaniClient:
    """Process-wide client, re-created if the env key changes."""
    global _default_client
    if _override_client is not None:
        return _override_client
    key = os.environ.get("GNANI_API_KEY", "")
    if _default_client is None or _default_client.api_key != key:
        _default_client = GnaniClient(api_key=key)
    return _default_client


def set_gnani_client(client: Optional[GnaniClient]) -> None:
    """Override the process-wide client (used by tests). Pass None to clear."""
    global _override_client
    _override_client = client
