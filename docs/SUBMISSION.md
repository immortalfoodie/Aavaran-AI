# Submission kit: Great Indian AI Internship Challenge (Gnani AI)

Deadline: **10 Nov 2026, 11:59 PM IST**. Primary award: **Real Deal**. Also relevant: Mixed Vibes (Hinglish voice),
Main Character (Marathi), Jugaad Genius.

## Project details (paste into the form)

**Title:** Aavaran AI: a voice-first food packaging advisor for farmers and small food businesses

**Problem:** Fresh produce spoils between harvest and sale, and small food makers often pick packaging by trial and
error. The people facing this can't type lab parameters into an English form, and they need a tool that will also
tell them when *no* packaging will save the food.

**What's inside:**

- Saathi speaks 10 Indian languages, including Hinglish, and has a hands-free mode.
- It covers 20 foods: 14 fresh crops plus namkeen, milk powder, paneer, turmeric, atta and toor dal for kirana shops.
- It suggests low-cost, no-plastic storage options with ₹ cost and days gained, from 29 cited sources.
- It shows today's mandi price (Agmarknet) with "sell today or store?" guidance.
- It warns about chilling injury and refuses unsafe cases.

**Target users:**

- Farmers, FPOs and mandi traders handling potato, onion, tomato, banana, mango, okra, spinach and green chilli.
- Small food businesses packing namkeen, milk powder, paneer and turmeric.

**What it does:** The user talks to Aavaran Saathi in Hindi, Marathi, Hinglish or English. Saathi asks only for what
is missing (crop, condition, when harvested, where stored; or product, pack size, required shelf life), then runs a
deterministic physics and regulation engine and speaks the answer:

- which packaging to use
- about how many days it will last
- ₹ per pack for businesses
- when relevant, "this is not a packaging problem — chill it or sell it today"

Users can later report by voice how long the stock actually lasted.

**Gnani models / APIs used:**

- Prisma v3.0 speech-to-text, with knowledge-base keyterms and a topic hint.
- Timbre v3.0 text-to-speech, plus Timbre v2.5 `hi-en` (Poorvi) for Hinglish.
- Details: [docs/GNANI_INTEGRATION.md](GNANI_INTEGRATION.md).

**Team contributions:** _fill in: name, role, what you built_

## 60-second demo script

Use synthetic data only. Record on a phone, ideally outdoors or in a market so the background noise is real.

| Time | Screen | Say / show |
| :-- | :-- | :-- |
| 0–6 s | Landing, Kisan mode | "Farmers lose produce after harvest. Aavaran lets them just *ask*." Tap **साथी से बात करें** |
| 6–20 s | Saathi, **मराठी** | Say: *"कांदा आहे, काल काढला."* Saathi asks: *"हे कुठे ठेवले आहे?"* Say: *"शेडमध्ये."* Timbre speaks the answer. Tap **पूर्ण उत्तर पाहा** to show the result card |
| 20–35 s | Start again, **Hinglish** | Say: *"Aloo kaata hua do din pehle, shed mein rakha hai."* Timbre: *"Dhyaan dijiye, yeh packaging ki problem nahi hai…"* Show the red safety screen. Caption: **"It refuses when packaging can't make food safe."** |
| 35–50 s | Saathi, **हिंदी** | Say: *"मैं नमकीन बेचता हूँ, 200 ग्राम का पैकेट, छह महीने चलना चाहिए।"* The app switches itself to Business mode; Timbre gives ₹/pack and warns it's below the 180-day target |
| 50–55 s | Onion result screen | Scroll to "💡 Low-cost options" (ventilated onion store, ₹ and days) and "📈 Sell today or store?" (today's mandi price) |
| 55–60 s | Result screen | Tap **बोलकर बताइए कितने दिन चला** to show voice feedback. End card: *"Gnani Prisma + Timbre · physics engine · Hindi, Marathi, Hinglish."* |

## Social post draft (LinkedIn / X)

Tag Gnani AI. The post must be live **before** you submit.

> Built **Aavaran AI** for #GreatIndianAIInternshipChallenge 🎙📦
>
> A farmer can now *say* "कांदा आहे, काल काढला, शेडमध्ये ठेवला" and hear back which packaging to use and how
> long it will last, in Marathi, Hindi or Hinglish.
>
> 🗣 Speech in: Gnani AI Prisma
> 🔊 Voice out: Gnani AI Timbre
> ⚙️ Decisions: a physics + FSSAI rules engine, not an LLM guess
> ⚠️ It also says "this is not a packaging problem" when no bag can make cut produce safe in the heat
>
> Demo 👇 [video link] · Try it: [app link]
>
> @Gnani AI #GnaniAI #GreatIndianAIInternshipChallenge

## Pre-submit checklist

- [ ] Register for the challenge; claim the 5,000 credits; create an API key at app.gnani.ai/voice
- [ ] Backend host environment: add `GNANI_API_KEY` and `DATA_GOV_IN_API_KEY` (one free personal key from data.gov.in → My Account; it works for every dataset), then redeploy
- [ ] Ask native speakers to check the Tamil, Telugu, Kannada, Gujarati, Punjabi and Bengali lines in `api/voice/texts.py` and `web/src/i18n/*.json`
- [ ] Add real photos for guava, cauliflower, cabbage, grapes, pomegranate and brinjal in `web/public/images/crops/` (they show a generic image now)
- [ ] Be transparent: the Aavaran AI engine predates the challenge window; the voice layer and features listed here were built for it
- [ ] Open the Vercel app → Kisan mode → Saathi header shows "Voice by Gnani AI" (not "Browser voice")
- [ ] Record the 60 s demo (public link), using synthetic data only
- [ ] Publish the post with both hashtags and nominate it in the form
- [ ] Fill the form: title, problem, users, models used, each member's contribution
