# Aavaran AI (आवरण): Solution Pitch

**A voice-first food packaging and storage advisor for Indian farmers and small food businesses, built on Gnani AI Prisma (speech-to-text) and Timbre (text-to-speech).**

**Live app:** https://aavaran-ai-final.vercel.app/ · **Demo video:** https://youtu.be/mdLuSGNFSLk · **Code:** https://github.com/immortalfoodie/Aavaran-AI

## The problem

India loses a large share of its fruit and vegetables between harvest and sale. Small food makers (namkeen, atta, dal, spices, paneer) pick packaging by trial and error. Existing tools expect lab parameters typed into English forms, which rules out most of the people who need them. Many cases also have no packaging fix at all, and no tool says so.

## The solution

The user **speaks** to *Aavaran Saathi* in their own language, for example *"कांदा आहे, काल काढला, शेडमध्ये ठेवला"*.

1. **Gnani Prisma v3.0** transcribes the speech. Keyterms from our knowledge base bias it toward crop names and local terms.
2. Saathi asks **one short question at a time**, and only for what is missing (crop, condition, harvest date, storage place; or product, pack size, target shelf life).
3. A **deterministic physics and regulation engine** (respiration, moisture and gas transfer, FSSAI and plastic-waste/EPR rules) works out the packaging, the expected days of shelf life and the ₹ cost per pack.
4. **Gnani Timbre** speaks the answer back. Hinglish uses the Timbre v2.5 `hi-en` voice.

No LLM produces the numbers. Every spoken figure comes from the engine, so the advice is the same each time and can be traced.

## What makes it different

- **Honest refusals:** for cut produce in the heat or paneer outside a fridge, it says *"this is not a packaging problem: chill it or sell it today."* It also warns about chilling injury.
- **10 languages**, including Hinglish and Marathi, plus a hands-free mode.
- **20 foods:** 14 fresh crops and 6 kirana products.
- **Low-cost, plastic-free options** (zero-energy cool chamber, ventilated onion store, clay-pot cooler), each with ₹ cost and days gained, drawn from 29 cited sources.
- **"Sell today or store?":** today's mandi price for the user's district from Agmarknet (data.gov.in).
- **Feedback by voice:** users can report how long their stock actually lasted.
- **98.4% accuracy** (63 of 64) on our golden test set.

## Who it is for

- **Farmers, FPOs and mandi traders** handling potato, onion, tomato, banana, mango, okra, chilli and other crops.
- **Kirana shops and small food makers** repacking atta, dal, namkeen, spices, milk powder and paneer.

## Impact

Less post-harvest loss, better prices from knowing when to sell or hold, and less wasted packaging. All of it comes through a voice conversation in the user's own language, with no typing and no English needed.

## Tech stack

FastAPI (Python) backend · React + Vite frontend · Gnani Prisma STT and Timbre TTS · Agmarknet API · Docker on Render and Vercel.
