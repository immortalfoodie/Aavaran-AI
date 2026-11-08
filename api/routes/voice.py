"""
Aavaran Saathi voice routes — Gnani Prisma (STT) + Timbre (TTS) on top of the
deterministic Aavaran engine.

- GET  /api/v1/voice/status     : is Gnani configured? which models?
- POST /api/v1/voice/start      : open a Saathi session, get the spoken greeting
- POST /api/v1/voice/turn       : audio in  -> Prisma -> slots -> engine -> Timbre out
- POST /api/v1/voice/text-turn  : same dialogue with typed text (fallback / tests)
- POST /api/v1/voice/tts        : Timbre read-aloud for any result text (audio/mpeg)
- POST /api/v1/voice/feedback   : "kitne din chala?" spoken outcome -> feedback store
"""

from __future__ import annotations

import base64
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from api.voice import tts_cache
from api.voice.dialogue import (
    Session,
    TurnOutcome,
    _t,
    advance,
    build_recommend_input,
    hours_to_interval,
    intro_text,
    normalize_lang,
    parse_feedback,
    session_store,
    summarize_result,
)
from api.voice.gnani import SUPPORTED_LANGS, GnaniError, get_gnani_client
from api.voice.keyterms import build_keyterms
from api.voice.spoken import to_spoken
from engine.store import FeedbackRecord, global_feedback_store, global_result_store

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/voice", tags=["Voice (Gnani AI)"])

MAX_AUDIO_BYTES = 6 * 1024 * 1024  # ~30 s of 48 kHz WAV, well above a 16 kHz clip


# --------------------------------------------------------------------------- helpers
def _mode(mode: Optional[str]) -> str:
    return "business" if (mode or "").lower().startswith("bus") else "kisan"


def speak(text: str, lang: str) -> tuple[Optional[str], Optional[str]]:
    """Return (base64 mp3, error_code). Never raises: voice output is best-effort."""
    client = get_gnani_client()
    if not client.enabled or not text:
        return None, None if client.enabled else "NOT_CONFIGURED"
    spoken = to_spoken(text, lang)
    model, voice, language = client.tts_plan(lang)
    key = tts_cache.cache_key(model, voice, language, spoken)
    audio = tts_cache.get(key)
    if audio is None:
        try:
            audio = client.synthesize(spoken, lang)
        except GnaniError as exc:
            logger.warning("Timbre TTS failed: %s (%s)", exc, exc.code)
            return None, exc.code
        tts_cache.put(key, audio)
    return base64.b64encode(audio).decode("ascii"), None


def _slots_view(session: Session) -> Dict[str, Any]:
    view = dict(session.slots)
    if "hours_since" in view:
        view["time_interval"] = hours_to_interval(float(view["hours_since"]))
    return view


def _turn_payload(
    session: Session,
    outcome: TurnOutcome,
    transcript: str,
    want_audio: bool,
    stt: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    audio_b64, tts_error = speak(outcome.reply_text, session.lang) if want_audio else (None, None)
    payload: Dict[str, Any] = {
        "session_id": session.id,
        "mode": session.mode,
        "lang": session.lang,
        "transcript": transcript,
        "heard": outcome.heard,
        "slots": _slots_view(session),
        "status": outcome.status,
        "asked_slot": outcome.asked_slot,
        "reply_text": outcome.reply_text,
        "reply_audio_b64": audio_b64,
        "tts_error": tts_error,
        "stt": stt,
        "result": None,
        "recommend_input": None,
    }
    if outcome.result is not None:
        payload["result"] = summarize_result(outcome.result)
        payload["recommend_input"] = build_recommend_input(session)
    return payload


def _get_or_create(session_id: Optional[str], mode: str, lang: str) -> Session:
    session = session_store.get(session_id)
    if session is None:
        session = session_store.create(mode=mode, lang=lang)
    else:
        session.lang = lang  # user may switch language mid-conversation
    return session


# --------------------------------------------------------------------------- models
class StartRequest(BaseModel):
    mode: str = Field(default="kisan", description="kisan or business")
    lang: str = Field(default="hi-IN", description="hi-IN, mr-IN, en-IN or hi-en (Hinglish)")
    speak: bool = True


class TextTurnRequest(BaseModel):
    text: str = Field(default="", description="What the user said / typed")
    session_id: Optional[str] = None
    mode: str = "kisan"
    lang: str = "hi-IN"
    speak: bool = True


class TtsRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=1200)
    lang: str = "hi-IN"


# --------------------------------------------------------------------------- routes
@router.get("/status")
def voice_status() -> Dict[str, Any]:
    client = get_gnani_client()
    return {
        "gnani_enabled": client.enabled,
        "stt_model": client.stt_model if client.enabled else None,
        "tts_model": client.tts_model if client.enabled else None,
        "languages": list(SUPPORTED_LANGS),
        "keyterms_count": len(build_keyterms()),
    }


@router.post("/start")
def voice_start(req: StartRequest) -> Dict[str, Any]:
    lang = normalize_lang(req.lang)
    session = session_store.create(mode=_mode(req.mode), lang=lang)
    text = intro_text(session.mode, lang)
    session.turns.append({"role": "saathi", "text": text})
    audio_b64, tts_error = speak(text, lang) if req.speak else (None, None)
    return {
        "session_id": session.id,
        "mode": session.mode,
        "lang": lang,
        "status": "asking",
        "reply_text": text,
        "reply_audio_b64": audio_b64,
        "tts_error": tts_error,
        "slots": {},
    }


@router.post("/text-turn")
def voice_text_turn(req: TextTurnRequest) -> Dict[str, Any]:
    lang = normalize_lang(req.lang)
    session = _get_or_create(req.session_id, _mode(req.mode), lang)
    try:
        outcome = advance(session, req.text)
    except Exception as exc:  # engine failure must not kill the conversation
        logger.exception("Saathi turn failed")
        raise HTTPException(status_code=500, detail=f"Saathi could not process this turn: {exc}")
    return _turn_payload(session, outcome, req.text, req.speak)


@router.post("/turn")
async def voice_turn(
    audio_file: UploadFile = File(..., description="WAV/MP3/OGG/M4A clip, max 30 s"),
    session_id: Optional[str] = Form(default=None),
    mode: str = Form(default="kisan"),
    lang: str = Form(default="hi-IN"),
    speak_reply: bool = Form(default=True),
) -> Dict[str, Any]:
    lang = normalize_lang(lang)
    client = get_gnani_client()
    if not client.enabled:
        raise HTTPException(status_code=503, detail={"code": "NOT_CONFIGURED", "message": "Gnani voice is not configured on this server."})

    audio = await audio_file.read()
    if not audio:
        raise HTTPException(status_code=400, detail={"code": "EMPTY_AUDIO", "message": "No audio received."})
    if len(audio) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail={"code": "AUDIO_TOO_LARGE", "message": "Keep each answer under 30 seconds."})

    try:
        stt = client.transcribe(
            audio,
            filename=audio_file.filename or "speech.wav",
            lang=lang,
            keyterms=build_keyterms(),
            content_type=audio_file.content_type or "audio/wav",
        )
    except GnaniError as exc:
        status = exc.status_code if 400 <= exc.status_code < 600 else 502
        raise HTTPException(status_code=status, detail={"code": exc.code, "message": str(exc)})

    session = _get_or_create(session_id, _mode(mode), lang)
    try:
        outcome = advance(session, stt.transcript)
    except Exception as exc:
        logger.exception("Saathi turn failed")
        raise HTTPException(status_code=500, detail=f"Saathi could not process this turn: {exc}")

    stt_meta = {
        "model": stt.model,
        "detected_language": stt.detected_language,
        "latency_s": stt.latency_s,
        "request_id": stt.request_id,
    }
    return _turn_payload(session, outcome, stt.transcript, speak_reply, stt_meta)


@router.post("/tts")
def voice_tts(req: TtsRequest) -> Response:
    lang = normalize_lang(req.lang)
    client = get_gnani_client()
    if not client.enabled:
        raise HTTPException(status_code=503, detail={"code": "NOT_CONFIGURED", "message": "Gnani voice is not configured on this server."})
    audio_b64, err = speak(req.text, lang)
    if audio_b64 is None:
        raise HTTPException(status_code=502, detail={"code": err or "TTS_FAILED", "message": "Speech synthesis failed."})
    return Response(content=base64.b64decode(audio_b64), media_type="audio/mpeg", headers={"Cache-Control": "private, max-age=3600"})


@router.post("/feedback")
async def voice_feedback(
    result_id: str = Form(...),
    lang: str = Form(default="hi-IN"),
    text: Optional[str] = Form(default=None),
    audio_file: Optional[UploadFile] = File(default=None),
    speak_reply: bool = Form(default=True),
) -> Dict[str, Any]:
    lang = normalize_lang(lang)
    if global_result_store.get(result_id) is None:
        raise HTTPException(status_code=404, detail={"code": "UNKNOWN_RESULT", "message": "Recommendation not found."})

    transcript = (text or "").strip()
    if audio_file is not None and not transcript:
        client = get_gnani_client()
        if not client.enabled:
            raise HTTPException(status_code=503, detail={"code": "NOT_CONFIGURED", "message": "Gnani voice is not configured."})
        audio = await audio_file.read()
        try:
            transcript = client.transcribe(audio, filename=audio_file.filename or "speech.wav", lang=lang,
                                           keyterms=build_keyterms(),
                                           content_type=audio_file.content_type or "audio/wav").transcript
        except GnaniError as exc:
            raise HTTPException(status_code=502, detail={"code": exc.code, "message": str(exc)})

    parsed = parse_feedback(transcript)
    if parsed["actual_shelf_life_days"] is None:
        reply = _t("feedback_ask", lang)
        audio_b64, tts_error = speak(reply, lang) if speak_reply else (None, None)
        return {"status": "asking", "transcript": transcript, "reply_text": reply,
                "reply_audio_b64": audio_b64, "tts_error": tts_error, "record": None}

    record = FeedbackRecord(
        result_id=result_id,
        actual_shelf_life_days=float(parsed["actual_shelf_life_days"]),
        spoilage_observed=bool(parsed["spoilage_observed"]),
        comments=f"[voice:{lang}] {transcript}"[:500],
    )
    global_feedback_store.save(record)
    reply = _t("feedback_thanks", lang)
    audio_b64, tts_error = speak(reply, lang) if speak_reply else (None, None)
    return {"status": "saved", "transcript": transcript, "reply_text": reply,
            "reply_audio_b64": audio_b64, "tts_error": tts_error, "record": record.model_dump(mode="json")}
