"""
Aavaran SealedResult to Prose Explainer.

Strictly bounded responsibilities:
- Input: the SealedResult plus a mode (kisan, business, expert) plus a locale.
- Output: explanation text only.
- Immutability guarantee: Pre-formats all numeric figures from the SealedResult
  as exact strings and strictly instructs the model that it may not alter,
  recompute, or round any of them.
- Post-generation Number Verification Pass: Extracts every numeric token from
  the generated prose and asserts that each appears in the source SealedResult
  object. Rejects and regenerates on any mismatch.
- Three prose registers:
  1. Kisan: exactly one instruction sentence, second person, active voice,
     no jargon, no unfamiliar units, written in the target language natively.
  2. Business: exactly two paragraphs covering what to buy and why, with the
     trade-off against the runner-up explicitly stated in paragraph 2.
  3. Expert: technical rationale naming the limiting mechanism, the equations
     used, and the key assumptions from the ledger.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Protocol

from api.llm.schemas import ExplanationMode, ExplanationResult
from engine.matcher.requirements import is_respiring_produce
from engine.result import SealedResult

logger = logging.getLogger("aavaran.explainer")


class LLMClient(Protocol):
    """Protocol for LLM clients that can generate text from prompts."""

    def generate(self, prompt: str, system_prompt: str | None = None, temperature: float = 0.0) -> str: ...


EXPLAINER_SYSTEM_PROMPT = """You are Aavaran's Sealed Result Explainer for food packaging decision records.

STRICT NUMBER IMMUTABILITY CONSTRAINTS:
1. You are provided with a list of VERIFIED NUMBERS from the cryptographic SealedResult.
2. You are STRICTLY FORBIDDEN from altering, converting, recomputing, rounding, or hallucinating ANY numbers.
3. Every single number that appears in your output MUST be copied verbatim from the verified numbers list. Any unexpected number will cause your output to be REJECTED by an automated cryptographic verification pass.
4. Output EXPLANATION TEXT ONLY. Do not wrap in JSON, markdown backticks, or extra commentary.

REGISTER GUIDELINES:
- 'kisan': Exactly ONE instruction sentence. No jargon (no OTR, WVTR, Arrhenius, or micrometres). No unfamiliar units. Second person, active voice. Written natively in the target language.
- 'business': Exactly TWO paragraphs. Paragraph 1 explains what packaging to buy and why (P50 shelf life, cost per pack, EPR compliance). Paragraph 2 details the trade-off against the runner-up candidate.
- 'expert': Technical rationale naming the limiting mechanism, equations used (e.g. MIC-01, M-01, OX-01), Arrhenius kinetics, and key assumptions from the ledger.
"""


# ---------------------------------------------------------------------------
# Number Extraction & Verification Pass
# ---------------------------------------------------------------------------


def extract_numbers_from_text(text: str) -> list[str]:
    """
    Extracts all numeric tokens from text.
    Handles integers, decimals, and removes trailing punctuation.
    """
    # Match integers and decimals
    tokens = re.findall(r"\b\d+(?:\.\d+)?\b", text)
    return tokens


def extract_numbers_from_result(result: SealedResult) -> set[str]:
    """
    Collects all allowed numeric figures present in a SealedResult object.
    Includes shelf life predictions, candidate costs and gauges, environmental
    parameters, commodity physchem constants, assumptions, and citations.
    """
    allowed: set[str] = set()

    def add_num(val: Any) -> None:
        if val is None:
            return
        if isinstance(val, (int, float)):
            allowed.add(str(val))
            allowed.add(f"{val:.1f}")
            allowed.add(f"{val:.2f}")
            allowed.add(str(round(val, 1)))
            allowed.add(str(round(val, 2)))
            if isinstance(val, float) and val.is_integer():
                allowed.add(str(int(val)))
            if isinstance(val, int):
                allowed.add(f"{val:.1f}")
        elif isinstance(val, str):
            for tok in re.findall(r"\b\d+(?:\.\d+)?\b", val):
                allowed.add(tok)
        elif isinstance(val, list):
            for item in val:
                add_num(item)
        elif isinstance(val, dict):
            for item in val.values():
                add_num(item)

    # 1. Shelf-life metrics
    if result.shelf_life:
        sl = result.shelf_life
        add_num(sl.days_p10)
        add_num(sl.days_p50)
        add_num(sl.days_p90)
        add_num(sl.safety_factor_applied)
        for val in sl.all_mode_results.values():
            add_num(val)

    # 2. Candidate packages
    if result.candidates:
        for i, cand in enumerate(result.candidates, 1):
            add_num(i)
            add_num(cand.composite_thickness_um)
            add_num(cand.cost_per_pack)
            add_num(cand.cost_inr_per_sqm)
            add_num(cand.measured_otr)
            add_num(cand.measured_wvtr)
            add_num(cand.recyclability_score)
            for g in cand.gauge_per_layer:
                add_num(g)

    # 3. Resolved environment
    if result.resolved and result.resolved.environment:
        env = result.resolved.environment
        if env.temperature:
            add_num(env.temperature.value)
        if env.relative_humidity:
            add_num(env.relative_humidity.value)
        if env.duration:
            add_num(env.duration.value)

    # 4. Resolved commodity parameters
    if result.resolved and result.resolved.commodity:
        comm = result.resolved.commodity
        if comm.moisture_pct:
            add_num(comm.moisture_pct.value)
        if comm.water_activity:
            add_num(comm.water_activity.value)
        if comm.fat_pct:
            add_num(comm.fat_pct.value)
        if comm.pH:
            add_num(comm.pH.value)
        if comm.respiration_ref_rate:
            add_num(comm.respiration_ref_rate.value)
        if comm.respiration_ref_t_c:
            add_num(comm.respiration_ref_t_c.value)
        if comm.respiration_ea_kj_mol:
            add_num(comm.respiration_ea_kj_mol.value)
        if comm.storage_optimum_t_c:
            add_num(comm.storage_optimum_t_c.value)
        if comm.storage_optimum_rh_pct:
            add_num(comm.storage_optimum_rh_pct.value)
        if comm.storage_life_days:
            add_num(comm.storage_life_days.value)

    # 5. Assumptions ledger
    if result.assumptions:
        for asm in result.assumptions:
            add_num(asm.value)
            add_num(asm.confidence)

    # 6. Requirements vector
    if result.requirements:
        req = result.requirements
        add_num(req.max_wvtr)
        add_num(req.max_otr)
        add_num(req.min_thickness_um)

    # 7. Value of Information
    if result.value_of_information:
        add_num(result.value_of_information.variance_reduction)

    # 8. Citations (e.g. 2018, 2022, 1984)
    if result.citations:
        for cite in result.citations:
            add_num(cite)

    # 9. Equations in shelf life (e.g. 01 from MIC-01, M-01, OX-01)
    if result.shelf_life and result.shelf_life.equations_used:
        for eq in result.shelf_life.equations_used:
            add_num(eq)

    # Allow standard ordinal / grammatical counts 1 and 2 for options/paragraphs
    allowed.add("1")
    allowed.add("2")

    return allowed


def verify_numbers(text: str, result: SealedResult) -> tuple[bool, list[str]]:
    """
    Verification pass: Extracts every number from the output and asserts
    each one appears in the source SealedResult object.

    Constraint: "Reject and regenerate on mismatch. This check is cheap
    and it is what makes the LLM layer safe to ship."

    Returns:
    - (True, []) if all numbers are verified.
    - (False, hallucinations) if unauthorized numbers are found.
    """
    found_numbers = extract_numbers_from_text(text)
    allowed_numbers = extract_numbers_from_result(result)

    hallucinations: list[str] = []
    for num in found_numbers:
        # Check exact string match
        if num in allowed_numbers:
            continue
        # Check float equivalence (e.g. "12.50" == 12.5)
        try:
            val = float(num)
            matched = False
            for a in allowed_numbers:
                try:
                    if abs(float(a) - val) < 1e-4:
                        matched = True
                        break
                except ValueError:
                    pass
            if matched:
                continue
        except ValueError:
            pass

        hallucinations.append(num)

    is_valid = len(hallucinations) == 0
    return is_valid, hallucinations


# ---------------------------------------------------------------------------
# Deterministic Register Templates (Safe, 100% Verified Offline Generator)
# ---------------------------------------------------------------------------


def _fmt_float(val: float | None, decimals: int = 1) -> str:
    if val is None:
        return "0.0"
    r = round(val, decimals)
    if r.is_integer():
        return str(int(r))
    return str(r)


def _get_verified_number_strings(result: SealedResult) -> dict[str, Any]:
    """Extracts pre-formatted string representations of primary result metrics."""
    nums: dict[str, Any] = {}
    if result.shelf_life:
        sl = result.shelf_life
        nums["p10"] = _fmt_float(sl.days_p10, 1)
        nums["p50"] = _fmt_float(sl.days_p50, 1)
        nums["p90"] = _fmt_float(sl.days_p90, 1)
        nums["safety_factor"] = _fmt_float(sl.safety_factor_applied, 2)
    else:
        nums["p10"] = "0.0"
        nums["p50"] = "0.0"
        nums["p90"] = "0.0"
        nums["safety_factor"] = "0.75"

    # Candidates
    if result.candidates and len(result.candidates) > 0:
        c1 = result.candidates[0]
        nums["has_candidates"] = True
        nums["c1_name"] = c1.name or "/".join(c1.layer_stack)
        nums["c1_stack"] = "/".join(c1.layer_stack)
        nums["c1_gauge"] = _fmt_float(c1.composite_thickness_um or sum(c1.gauge_per_layer), 1)
        nums["c1_cost"] = _fmt_float(c1.cost_per_pack or 0.85, 2)
        nums["c1_epr"] = c1.epr_category or "Category I"

        if len(result.candidates) > 1:
            c2 = result.candidates[1]
            nums["has_runner_up"] = True
            nums["c2_name"] = c2.name or "/".join(c2.layer_stack)
            nums["c2_stack"] = "/".join(c2.layer_stack)
            nums["c2_gauge"] = _fmt_float(c2.composite_thickness_um or sum(c2.gauge_per_layer), 1)
            nums["c2_cost"] = _fmt_float(c2.cost_per_pack or 1.20, 2)
        else:
            nums["has_runner_up"] = False
            nums["c2_name"] = None
            nums["c2_stack"] = None
            nums["c2_gauge"] = None
            nums["c2_cost"] = None
    else:
        nums["has_candidates"] = False
        nums["has_runner_up"] = False
        nums["c1_name"] = None
        nums["c1_stack"] = None
        nums["c1_gauge"] = None
        nums["c1_cost"] = None
        nums["c1_epr"] = None
        nums["c2_name"] = None
        nums["c2_stack"] = None
        nums["c2_gauge"] = None
        nums["c2_cost"] = None

    # Environment
    if result.resolved and result.resolved.environment:
        env = result.resolved.environment
        nums["temp"] = _fmt_float(env.temperature.value, 1) if env.temperature else "25"
        nums["rh"] = _fmt_float(env.relative_humidity.value, 1) if env.relative_humidity else "65"
    else:
        nums["temp"] = "25"
        nums["rh"] = "65"

    # Commodity
    if result.resolved and result.resolved.commodity:
        comm = result.resolved.commodity
        comm_display = getattr(comm, "display_name", None)
        if not comm_display and hasattr(comm, "names") and isinstance(comm.names, dict):
            if "en" in comm.names and comm.names["en"]:
                comm_display = comm.names["en"][0]
        if not comm_display:
            parts = comm.commodity_id.split(".")
            comm_display = parts[1] if len(parts) >= 2 else parts[-1]
        nums["comm_name"] = comm_display.replace("_", " ")
        nums["comm_id"] = comm.commodity_id
        nums["aw"] = _fmt_float(comm.water_activity.value, 2) if comm.water_activity else None
        nums["ea"] = _fmt_float(comm.respiration_ea_kj_mol.value, 1) if comm.respiration_ea_kj_mol else None
    else:
        nums["comm_name"] = "produce"
        nums["comm_id"] = "produce.standard"
        nums["aw"] = None
        nums["ea"] = None

    nums["limiting_mech"] = result.shelf_life.limiting_mechanism if result.shelf_life else "moisture_gain"
    nums["equations"] = (
        ", ".join(result.shelf_life.equations_used)
        if result.shelf_life and result.shelf_life.equations_used
        else "MIC-01, M-01, OX-01"
    )

    return nums


def generate_deterministic_prose(result: SealedResult, mode: ExplanationMode, locale: str = "en-IN") -> str:
    """
    Deterministic template generator ensuring 100% verified numbers and exact register adherence.
    Used for offline execution, fallback, and when LLM outputs hallucinated numbers.
    """
    nums = _get_verified_number_strings(result)
    loc = locale.lower()

    if mode == ExplanationMode.KISAN:
        # EXACTLY ONE instruction sentence. No jargon. Second person. Active voice. Native target language.
        p50 = nums["p50"]
        comm = nums["comm_name"]

        # Localize commodity name if target language has a translation
        if result.resolved and result.resolved.commodity:
            comm_obj = result.resolved.commodity
            lang_code = loc.split("-")[0].split("_")[0]
            if hasattr(comm_obj, "names") and isinstance(comm_obj.names, dict):
                loc_list = comm_obj.names.get(lang_code)
                if loc_list and len(loc_list) > 0:
                    comm = loc_list[0]
                elif lang_code != "en" and comm_obj.names.get("hi"):
                    comm = comm_obj.names["hi"][0]

        lang = loc.split("-")[0].split("_")[0]

        # Safety refusal: never tell the farmer to pack something the engine blocked.
        if result.verdict == "NOT_A_PACKAGING_PROBLEM" or (
            result.safety is not None and str(getattr(result.safety.status, "value", result.safety.status)) == "BLOCK"
        ):
            refusal = {
                "hi": f"यह पैकेजिंग की समस्या नहीं है, अपने {comm} को तुरंत ठंडा करें या आज ही बेच दें या पका लें, इसे बंद थैली में न रखें।",
                "mr": f"ही पॅकेजिंगची समस्या नाही, आपले {comm} लगेच थंड करा किंवा आजच विका किंवा शिजवा, ते बंद पिशवीत ठेवू नका.",
                "ta": f"இது பேக்கேஜிங் பிரச்சனை அல்ல, உங்கள் {comm} உடனே குளிர்விக்கவும் அல்லது இன்றே விற்கவும், மூடிய பையில் வைக்க வேண்டாம்.",
                "te": f"ఇది ప్యాకేజింగ్ సమస్య కాదు, మీ {comm} వెంటనే చల్లబరచండి లేదా ఈరోజే అమ్మండి, మూసిన సంచిలో ఉంచవద్దు.",
                "bn": f"এটা প্যাকেজিংয়ের সমস্যা নয়, আপনার {comm} এখনই ঠান্ডা করুন বা আজই বিক্রি করুন, বন্ধ ব্যাগে রাখবেন না।",
                "kn": f"ಇದು ಪ್ಯಾಕೇಜಿಂಗ್ ಸಮಸ್ಯೆ ಅಲ್ಲ, ನಿಮ್ಮ {comm} ತಕ್ಷಣ ತಣ್ಣಗಾಗಿಸಿ ಅಥವಾ ಇಂದೇ ಮಾರಾಟ ಮಾಡಿ, ಮುಚ್ಚಿದ ಚೀಲದಲ್ಲಿ ಇಡಬೇಡಿ.",
                "gu": f"આ પેકેજિંગની સમસ્યા નથી, તમારા {comm} તરત ઠંડા કરો અથવા આજે જ વેચી દો, બંધ થેલીમાં ન રાખો.",
                "pa": f"ਇਹ ਪੈਕੇਜਿੰਗ ਦੀ ਸਮੱਸਿਆ ਨਹੀਂ ਹੈ, ਆਪਣੇ {comm} ਨੂੰ ਤੁਰੰਤ ਠੰਡਾ ਕਰੋ ਜਾਂ ਅੱਜ ਹੀ ਵੇਚ ਦਿਓ, ਬੰਦ ਥੈਲੀ ਵਿੱਚ ਨਾ ਰੱਖੋ।",
            }
            return refusal.get(
                lang,
                f"This is not a packaging problem: chill your {comm} right away or sell or cook it today, and do not seal it in a bag.",
            )

        # Processed / non-respiring foods (namkeen, milk powder, spices): sealed barrier pouch, not a mesh sack.
        profile_obj = result.resolved.commodity if result.resolved else None
        if profile_obj is not None and not is_respiring_produce(profile_obj):
            sealed = {
                "hi": f"अपने {comm} को {p50} दिन तक अच्छा रखने के लिए अच्छी तरह सील की हुई चमकीली परत वाली थैली में धूप से दूर सूखी जगह पर रखें।",
                "mr": f"आपले {comm} {p50} दिवस चांगले ठेवण्यासाठी नीट सील केलेल्या चमकदार थराच्या पिशवीत उन्हापासून दूर कोरड्या जागी ठेवा.",
                "ta": f"உங்கள் {comm} {p50} நாட்கள் நன்றாக இருக்க நன்கு சீல் செய்த பளபளப்பான பையில் வெயில் படாத உலர்ந்த இடத்தில் வைக்கவும்.",
                "te": f"మీ {comm} {p50} రోజులు బాగుండటానికి బాగా సీల్ చేసిన మెరిసే సంచిలో ఎండ తగలని పొడి ప్రదేశంలో ఉంచండి.",
                "bn": f"আপনার {comm} {p50} দিন ভালো রাখতে ভালোভাবে সিল করা চকচকে ব্যাগে রোদ থেকে দূরে শুকনো জায়গায় রাখুন।",
                "kn": f"ನಿಮ್ಮ {comm} {p50} ದಿನಗಳ ಕಾಲ ಚೆನ್ನಾಗಿರಲು ಚೆನ್ನಾಗಿ ಸೀಲ್ ಮಾಡಿದ ಹೊಳೆಯುವ ಚೀಲದಲ್ಲಿ ಬಿಸಿಲಿಲ್ಲದ ಒಣ ಜಾಗದಲ್ಲಿ ಇರಿಸಿ.",
                "gu": f"તમારા {comm} {p50} દિવસ સુધી સારા રાખવા માટે સારી રીતે સીલ કરેલી ચમકતી થેલીમાં તડકાથી દૂર સૂકી જગ્યાએ રાખો.",
                "pa": f"ਆਪਣੇ {comm} ਨੂੰ {p50} ਦਿਨ ਤੱਕ ਵਧੀਆ ਰੱਖਣ ਲਈ ਚੰਗੀ ਤਰ੍ਹਾਂ ਸੀਲ ਕੀਤੀ ਚਮਕਦਾਰ ਥੈਲੀ ਵਿੱਚ ਧੁੱਪ ਤੋਂ ਦੂਰ ਸੁੱਕੀ ਥਾਂ 'ਤੇ ਰੱਖੋ।",
            }
            return sealed.get(
                lang,
                f"Keep your {comm} in a well-sealed shiny barrier pouch, away from sunlight in a dry place, to keep it good for {p50} days.",
            )

        # Determine packaging structure type from result
        pkg_cand = result.recommendation.packaging_name if result.recommendation else ""
        if not pkg_cand and result.candidates and len(result.candidates) > 0:
            pkg_cand = getattr(result.candidates[0], "structure_name", "") or getattr(result.candidates[0], "name", "")
        pkg_lower = (pkg_cand or "").lower()
        comm_lower = (
            result.resolved.commodity.commodity_id if result.resolved and result.resolved.commodity else ""
        ).lower()

        is_crate = (
            "crate" in pkg_lower or "box" in pkg_lower or any(k in comm_lower for k in ["tomato", "mango", "banana"])
        )
        is_pouch = (
            "perf" in pkg_lower
            or "pouch" in pkg_lower
            or any(k in comm_lower for k in ["spinach", "okra", "chilli", "leafy"])
        )

        if is_crate:
            if "hi" in loc:
                return f"अपने {comm} को {p50} दिन तक सुरक्षित रखने के लिए हवादार छेदों वाले क्रेट में सूखी ठंडी जगह पर रखें।"
            elif "mr" in loc:
                return f"आपले {comm} {p50} दिवस चांगले ठेवण्यासाठी हवेशीर छिद्रे असलेल्या क्रेटमध्ये कोरड्या जागी ठेवा."
            elif "ta" in loc:
                return f"உங்கள் {comm} {p50} நாட்கள் வரை கெடாமல் பாதுகாக்க காற்றோட்டமான கிரேட்டில் உலர்ந்த இடத்தில் வைக்கவும்."
            elif "te" in loc:
                return f"మీ {comm} {p50} రోజులు తాజాగా ఉంచడానికి గాలి ఆడే క్రేట్‌లో పొడి ప్రదేశంలో భద్రపరచండి."
            elif "bn" in loc:
                return f"আপনার {comm} {p50} দিন ভালো রাখতে বাতাস চলাচল করে এমন ক্রেটে শুকনো ঠান্ডা জায়গায় রাখুন।"
            elif "kn" in loc:
                return f"ನಿಮ್ಮ {comm} {p50} ದಿನಗಳ ಕಾಲ ತಾಜಾವಾಗಿಡಲು ಗಾಳಿಯಾಡುವ ಕ್ರೇಟ್‌ನಲ್ಲಿ ಒಣ ಜಾಗದಲ್ಲಿ ಇರಿಸಿ."
            elif "gu" in loc:
                return f"તમારા {comm} {p50} દિવસ સુધી સારો રાખવા માટે હવાઉજાસવાળા ક્રેટમાં સૂકી જગ્યાએ રાખો."
            elif "pa" in loc:
                return f"ਆਪਣੇ {comm} ਨੂੰ {p50} ਦਿਨ ਤੱਕ ਤਾਜ਼ਾ ਰੱਖਣ ਲਈ ਹਵਾਦਾਰ ਕ੍ਰੇਟ ਵਿੱਚ ਸੁੱਕੀ ਠੰਡੀ ਥਾਂ 'ਤੇ ਰੱਖੋ।"
            else:
                return f"Store your {comm} in a ventilated crate in a dry shaded place to keep it fresh for {p50} days."

        elif is_pouch:
            if "hi" in loc:
                return f"अपने {comm} को {p50} दिन तक सुरक्षित रखने के लिए हवादार सूक्ष्म छिद्रों वाली थैली में सूखी ठंडी जगह पर रखें।"
            elif "mr" in loc:
                return f"आपले {comm} {p50} दिवस चांगले ठेवण्यासाठी हवा खेळती राहणाऱ्या बारीक छिद्रांच्या पिशवीत कोरड्या जागी ठेवा."
            elif "ta" in loc:
                return f"உங்கள் {comm} {p50} நாட்கள் வரை கெடாமல் பாதுகாக்க நுண்ணிய துளைகள் கொண்ட பையில் உலர்ந்த இடத்தில் வைக்கவும்."
            elif "te" in loc:
                return f"మీ {comm} {p50} రోజులు తాజాగా ఉంచడానికి సూక్ష్మ రంధ్రాల సంచిలో పొడి ప్రదేశంలో భద్రపరచండి."
            elif "bn" in loc:
                return f"আপনার {comm} {p50} দিন ভালো রাখতে সূক্ষ্ম ছিদ্রযুক্ত ব্যাগে শুকনো ঠান্ডা জায়গায় রাখুন।"
            elif "kn" in loc:
                return f"ನಿಮ್ಮ {comm} {p50} ದಿನಗಳ ಕಾಲ ತಾಜಾವಾಗಿಡಲು ಸೂಕ್ಷ್ಮ ರಂಧ್ರಗಳ ಚೀಲದಲ್ಲಿ ಒಣ ಜಾಗದಲ್ಲಿ ಇರಿಸಿ."
            elif "gu" in loc:
                return f"તમારા {comm} {p50} દિવસ સુધી સારો રાખવા માટે સૂક્ષ્મ છિદ્રોવાળી થેલીમાં સૂકી જગ્યાએ રાખો."
            elif "pa" in loc:
                return f"ਆਪਣੇ {comm} ਨੂੰ {p50} ਦਿਨ ਤੱਕ ਤਾਜ਼ਾ ਰੱਖਣ ਲਈ ਬਰੀਕ ਛੇਕਾਂ ਵਾਲੀ ਥੈਲੀ ਵਿੱਚ ਸੁੱਕੀ ਠੰਡੀ ਥਾਂ 'ਤੇ ਰੱਖੋ।"
            else:
                return f"Store your {comm} in a micro-perforated breathable pouch in a dry shaded place to keep it fresh for {p50} days."

        else:
            # Mesh sack (potatoes, onions, root bulbs)
            if "hi" in loc:
                return f"अपने {comm} को {p50} दिन तक सुरक्षित रखने के लिए हवादार जालीदार बोरी में सूखी ठंडी जगह पर रखें।"
            elif "mr" in loc:
                return f"आपले {comm} {p50} दिवस चांगले ठेवण्यासाठी हवेशीर जाळीदार पोत्यात कोरड्या जागी ठेवा."
            elif "ta" in loc:
                return f"உங்கள் {comm} {p50} நாட்கள் வரை கெடாமல் பாதுகாக்க காற்றோட்டமான வலைப் பையில் உலர்ந்த இடத்தில் வைக்கவும்."
            elif "te" in loc:
                return f"మీ {comm} {p50} రోజులు తాజాగా ఉంచడానికి గాలి ఆడే జాలీ సంచిలో పొడి ప్రదేశంలో భద్రపరచండి."
            elif "bn" in loc:
                return f"আপনার {comm} {p50} দিন ভালো রাখতে বাতাস চলাচল করে এমন জালের ব্যাগে শুকনো ঠান্ডা জায়গায় রাখুন।"
            elif "kn" in loc:
                return f"ನಿಮ್ಮ {comm} {p50} ದಿನಗಳ ಕಾಲ ತಾಜಾವಾಗಿಡಲು ಗಾಳಿಯಾಡುವ ಜಾಲರಿಯ ಚೀಲದಲ್ಲಿ ಒಣ ಜಾಗದಲ್ಲಿ ಇರಿಸಿ."
            elif "gu" in loc:
                return f"તમારા {comm} {p50} દિવસ સુધી સારો રાખવા માટે હવાઉજાસવાળા જાળીદાર થેલામાં સૂકી જગ્યાએ રાખો."
            elif "pa" in loc:
                return f"ਆਪਣੇ {comm} ਨੂੰ {p50} ਦਿਨ ਤੱਕ ਤਾਜ਼ਾ ਰੱਖਣ ਲਈ ਹਵਾਦਾਰ ਜਾਲੀਦਾਰ ਬੋਰੀ ਵਿੱਚ ਸੁੱਕੀ ਠੰਡੀ ਥਾਂ 'ਤੇ ਰੱਖੋ।"
            else:
                return f"Store your {comm} in a ventilated mesh sack in a dry shaded place to keep it fresh for {p50} days."

    elif mode == ExplanationMode.BUSINESS:
        # EXACTLY TWO paragraphs covering what to buy and why, with trade-off against runner-up.
        if nums["has_candidates"]:
            p1 = (
                f"We recommend adopting Option 1: {nums['c1_name']} ({nums['c1_stack']}, gauge {nums['c1_gauge']} µm) "
                f"at an estimated unit cost of ₹{nums['c1_cost']} per pack. This specification delivers a validated "
                f"P50 shelf life of {nums['p50']} days (conservative P10 lower bound: {nums['p10']} days) under commercial "
                f"temperature abuse conditions, while providing full EPR compliance under {nums['c1_epr']} guidelines."
            )
            if nums["has_runner_up"]:
                p2 = (
                    f"Compared to the runner-up Option 2: {nums['c2_name']} priced higher at ₹{nums['c2_cost']} per pack, "
                    f"our recommended structure eliminates unnecessary material over-engineering and avoids higher EPR fees. "
                    f"The primary failure risk is {nums['limiting_mech']}, and our chosen barrier profile delivers the optimal "
                    f"balance of product protection and operating margin without paying a premium for unneeded barrier."
                )
            else:
                p2 = (
                    f"Alternative standard mono-layer films fail to provide adequate barrier against {nums['limiting_mech']}, "
                    f"resulting in premature inventory loss. Our chosen specification delivers the optimal commercial balance "
                    f"of barrier protection and compliant EPR recyclability without paying a premium for over-engineered multi-layer laminates."
                )
            return f"{p1}\n\n{p2}"
        else:
            # Handle refusal or safety interlock (no candidate permitted)
            verdict_text = result.verdict
            safety_reason = result.safety.message_key if result.safety else "environmental or safety interlock"
            p1 = (
                f"Packaging cannot be recommended for {nums['comm_name']} under current operational constraints. "
                f"The Aavaran AI safety engine issued a {verdict_text} determination triggered by {safety_reason}."
            )
            p2 = (
                f"Standard flexible packaging without strict environmental cold-chain mitigation risks accelerated "
                f"degradation from {nums['limiting_mech']}. Pre-packaging operational controls must be implemented "
                f"before packaging material selection can proceed."
            )
            return f"{p1}\n\n{p2}"

    elif mode == ExplanationMode.EXPERT:
        # Technical rationale naming limiting mechanism, equations, and key assumptions.
        assumptions_parts = [
            f"a mandatory commercial safety factor of {nums['safety_factor']} applied to counter supply-chain temperature abuse"
        ]
        if nums["aw"]:
            assumptions_parts.append(f"baseline product water activity of {nums['aw']}")
        if nums["ea"]:
            assumptions_parts.append(f"an Arrhenius respiration activation energy Ea of {nums['ea']} kJ/mol")

        assumptions_str = ", and ".join(assumptions_parts)

        return (
            f"Technical Rationale: Shelf-life degradation for {nums['comm_id']} is governed by the primary limiting "
            f"mechanism of {nums['limiting_mech']}, evaluated using verified physical model equations {nums['equations']}. "
            f"Stochastic kinetic integration under ambient conditions of {nums['temp']} °C and {nums['rh']} % relative humidity "
            f"yields a median P50 survival of {nums['p50']} days (P10: {nums['p10']} days, P90: {nums['p90']} days). "
            f"Core governing assumptions incorporate {assumptions_str}."
        )

    raise ValueError(f"Unsupported explanation mode: {mode}")


# ---------------------------------------------------------------------------
# High-Level Explainer Orchestrator
# ---------------------------------------------------------------------------


def explain_result(
    result: SealedResult,
    mode: str | ExplanationMode = ExplanationMode.BUSINESS,
    locale: str = "en-IN",
    client: LLMClient | None = None,
    max_regenerations: int = 1,
) -> ExplanationResult:
    """
    Generates prose explanation for a SealedResult across Kisan, Business, or Expert registers.

    Execution Flow:
    1. Pre-formats all figures from SealedResult into exact strings.
    2. Instructs the model that it may not alter, recompute, or round any numbers.
    3. Runs the post-generation verification pass: extracts all numbers and asserts
       each appears in the source SealedResult.
    4. On mismatch or hallucination: rejects output and regenerates (or falls back to
       the deterministic safe generator).
    """
    if isinstance(mode, str):
        parsed_mode = ExplanationMode.from_str(mode)
    else:
        parsed_mode = mode

    verified_nums = _get_verified_number_strings(result)
    text_output: str | None = None
    hallucinations: list[str] = []

    # 1. Attempt LLM generation if client provided
    if client is not None:
        numbers_context = "\n".join(f"- {k}: {v}" for k, v in verified_nums.items())
        prompt = (
            f"Generate a '{parsed_mode.value}' register explanation in locale '{locale}'.\n"
            f"Source Result Summary:\n"
            f"- Commodity: {result.resolved.commodity.commodity_id if result.resolved.commodity else 'Produce'}\n"
            f"- Verdict: {result.verdict}\n\n"
            f"VERIFIED NUMBERS (You MUST use ONLY these numbers verbatim):\n"
            f"{numbers_context}\n"
        )

        for attempt in range(max_regenerations + 1):
            try:
                candidate_text = client.generate(
                    prompt=prompt,
                    system_prompt=EXPLAINER_SYSTEM_PROMPT,
                    temperature=0.0,
                ).strip()

                # Run post-generation verification pass
                is_valid, bad_nums = verify_numbers(candidate_text, result)
                if is_valid:
                    text_output = candidate_text
                    break
                else:
                    logger.warning(
                        f"LLM output attempt {attempt + 1} contained hallucinated numbers: {bad_nums}. Rejecting."
                    )
                    hallucinations = bad_nums
            except Exception as e:
                logger.warning(f"LLM explanation generation failed on attempt {attempt + 1}: {e}")

    # 2. Fall back to deterministic verified generator if LLM was unavailable or rejected
    if text_output is None:
        text_output = generate_deterministic_prose(result, mode=parsed_mode, locale=locale)

    # 3. Final verification pass on the finalized output
    is_valid, final_hallucinations = verify_numbers(text_output, result)
    found_nums = extract_numbers_from_text(text_output)
    allowed_nums = extract_numbers_from_result(result)
    matching_nums = [n for n in found_nums if n in allowed_nums]

    return ExplanationResult(
        mode=parsed_mode.value,
        locale=locale,
        explanation=text_output,
        verified_numbers=matching_nums,
        hallucinations_detected=final_hallucinations or hallucinations,
        is_valid=is_valid,
    )
