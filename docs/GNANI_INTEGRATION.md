# How Aavaran AI uses Gnani AI

Aavaran AI puts a voice front door ("Aavaran Saathi") on a deterministic food-packaging engine. Gnani's models are the interface. The packaging decisions themselves are made by physics models and
regulation rules, never by a language model.

## Models and endpoints

| Gnani model | Endpoint | What it does in Aavaran |
| :-- | :-- | :-- |
| **Prisma v3.0** (STT) | `POST https://api.vachana.ai/stt/v3` (multipart) | Transcribes each spoken answer (≤ 25 s WAV, 16 kHz mono) |
| **Timbre v3.0** (TTS) | `POST https://api.vachana.ai/api/v1/tts/inference` (JSON → MP3) | Speaks every question and answer in Hindi, Marathi, English, Tamil, Telugu, Kannada, Gujarati, Punjabi and Bengali (voice: Shivani, which speaks all 10) |
| **Timbre v2.5** `hi-en` | same endpoint, voice **Poorvi** | Speaks Hinglish replies with Gnani's dedicated code-mixed voice |

Auth: `X-API-Key-ID` header. The key is read on the server from `GNANI_API_KEY` and is never sent to the browser.

## The request flow

```
Browser (web/src/voice)
  getUserMedia → Web Audio → 16 kHz mono WAV encoder (Prisma does not take Chrome's webm)
  POST /api/v1/voice/turn  (audio_file, session_id, lang, mode)
        │
FastAPI (api/routes/voice.py)
  1. Prisma v3.0  language_code = hi-IN | mr-IN | en-IN | "hi-IN,en-IN" (Hinglish)
                  format = transcribe
                  keyterms = every commodity name in the knowledge base, in every language
                             (aloo, कांदा, फरसाण, bhindi …) + mandi words (shed, barf, crate …), ≤ 200
                  topic    = "farmer / small food business asking how to pack and store …"
  2. Saathi dialogue (api/voice/dialogue.py)
       extracts slots: crop, cut/whole/washed/bruised, time since harvest, storage
                       (business: product, pack grams, required shelf life, storage for perishables)
       missing slot?  → ask ONE short question in the user's language
       all present?   → run the Aavaran AI engine (engine/orchestrate.py)
       engine refused → speak the refusal and what to do instead (chill / process / sell today)
       engine's value-of-information says storage would cut uncertainty ≥ 10 %? → ask one more question
  3. Spoken-number normaliser (api/voice/spoken.py): "₹1.75" → "एक रुपये पचहत्तर पैसे", "20u" → "बीस माइक्रोन",
     shelf life floored to whole days (never rounded up)
  4. Timbre → MP3, cached on disk by sha1(model, voice, language, text), so fixed questions cost credits once
        │
Browser plays the MP3, shows the transcript, the understood "slot chips", and the full result screen
```

Other voice endpoints:

- `POST /api/v1/voice/tts`: Timbre read-aloud for any result card. Kisan mode's 🔊 button uses it.
- `POST /api/v1/voice/feedback`: the farmer says how many days the stock actually lasted ("बारह दिन ठीक रहा"). Prisma
  transcribes it, and it is stored against the sealed result for calibration.
- `GET /api/v1/voice/status`: tells the frontend whether Gnani is configured.

## Hands-free conversation

Turning on the "🙌 hands-free" switch makes the browser stop recording automatically at the end of an utterance,
after about 1.2 s of silence following speech (`createEndpointer` in `web/src/voice/recorder.ts`). It also drops a
clip in which nobody spoke for 8 s. After Timbre finishes speaking a question, Saathi starts listening again, so a
farmer with full hands never has to tap.

This uses Prisma's REST endpoint rather than the streaming WebSocket. Browsers cannot attach the `X-API-Key-ID`
header to a WebSocket, so streaming would need a server-side relay. That relay is the next latency improvement.

## Languages

Saathi speaks 10 languages: `hi-IN`, `mr-IN`, `en-IN`, Hinglish, `ta-IN`, `te-IN`, `kn-IN`, `gu-IN`, `pa-IN` and `bn-IN`.
Every spoken sentence lives in `api/voice/texts.py`. The Tamil, Telugu, Kannada, Gujarati, Punjabi and Bengali text
was machine-drafted and is marked for native-speaker review.

## Why the design looks like this

- **No numbers come from a language model.** Every number Saathi says (days, ₹ per pack) comes from the sealed
  engine result. Tests check that TTS text contains no raw digits and that business replies quote the engine's
  candidate price.
- **Safety refusal is spoken, not hidden.** Cut potato kept at 30 °C or paneer outside the fridge gets
  "यह पैकेजिंग की समस्या नहीं है …" rather than a packaging recommendation.
- **Prisma context biasing is generated from data.** Adding a commodity JSON to `kb/commodities/` automatically
  adds its local names to the recogniser's keyterms.
- **Graceful degradation.** Without `GNANI_API_KEY` or without network, the same dialogue runs on typed text and
  the browser's built-in speech, and the offline PWA engine still works.

## Fixes to the underlying engine made along the way

Wiring voice to the engine exposed two bugs. Both are fixed and covered by tests:

1. The Kisan explanation told users to keep blocked produce (for example cut potato) "in a mesh sack". It also
   suggested a mesh sack for namkeen and milk powder. It now speaks the refusal for blocked results and a sealed
   barrier pouch for non-respiring foods.
2. For dairy and other non-respiring foods, the film matcher's prediction overrode a much shorter microbial limit
   (paneer at 4 °C was predicted to last 135 days). Microbial time now caps shelf life for non-respiring foods. The
   golden benchmark went from 62/64 to 63/64 (`PRO-PAN-01` now passes at 11 days).

## Tests

`tests/test_voice.py` (30 tests) covers:

- the Gnani request shape, headers, Hinglish voice routing and error mapping, using a mocked `httpx` transport
  with no real API calls
- Hindi, Marathi and Hinglish slot extraction
- refusal, auto-routing from Kisan to Business, the perishable storage question and honest unknown-crop replies
- TTS caching and spoken feedback

`web/src/voice/wav.test.ts` checks the WAV header, sample rate and resampling.
