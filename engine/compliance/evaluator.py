"""
Aavaran Data-Driven Compliance Rule Evaluator.

Strictly follows Section 6 of BLUEPRINT.md.
All regulations live in versioned YAML files and are evaluated as a rule set.
No regulations are hardcoded in application logic.
"""

from datetime import date, datetime
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Set, Tuple, Union
import yaml

from engine.compliance.schema import (
    ComplianceIssue,
    ComplianceReport,
    ComplianceWarning,
    EprCostEstimate,
    Rule,
    RuleEffect,
    RuleSeverity,
    RuleTraceEntry,
)


DEFAULT_RULES_DIR = Path(__file__).resolve().parent / "rules"


def _normalize_dict(obj: Any) -> Any:
    """Recursively converts Pydantic models or custom objects to plain dictionaries."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict") and callable(obj.dict):
        return obj.dict()
    if isinstance(obj, dict):
        return {k: _normalize_dict(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_normalize_dict(item) for item in obj]
    return obj


def resolve_path(path: str, context: Dict[str, Any]) -> Any:
    """
    Resolves a dot-delimited path (e.g. 'material.recycled_content_pct') in the context dictionary.
    Includes smart aliases:
    - 'material' -> 'package' -> 'candidate'
    - 'commodity' -> 'product'
    - 'market' -> 'destination_market'
    """
    if path in context:
        return context[path]

    parts = path.split(".")
    curr = context

    for i, part in enumerate(parts):
        if not isinstance(curr, dict):
            if hasattr(curr, part):
                curr = getattr(curr, part)
                continue
            return None

        if part in curr:
            curr = curr[part]
        elif part == "material" and "package" in curr:
            curr = curr["package"]
        elif part == "package" and "material" in curr:
            curr = curr["material"]
        elif part == "material" and "candidate" in curr:
            curr = curr["candidate"]
        elif part == "package" and "candidate" in curr:
            curr = curr["candidate"]
        elif part == "product" and "commodity" in curr:
            curr = curr["commodity"]
        elif part == "commodity" and "product" in curr:
            curr = curr["product"]
        else:
            # Fallback: if single key without prefix, search under package and product
            if i == 0 and len(parts) == 1:
                pkg = context.get("package") or context.get("material") or {}
                if isinstance(pkg, dict) and part in pkg:
                    return pkg[part]
                prd = context.get("product") or context.get("commodity") or {}
                if isinstance(prd, dict) and part in prd:
                    return prd[part]
            return None

    return curr


def evaluate_condition(actual: Any, expected: Any) -> bool:
    """
    Evaluates a single predicate operator or value comparison.
    Supports:
    - Primitives: direct equality (case-insensitive for strings)
    - Dictionaries: operators {eq, ne, gt, gte, lt, lte, in, not_in, contains, contains_any, contains_all, exists, regex}
    - Lists: membership (actual in expected)
    """
    if isinstance(expected, dict):
        # Operators evaluation
        for op, target in expected.items():
            op_lower = op.lower()

            if op_lower == "eq":
                if isinstance(actual, str) and isinstance(target, str):
                    if actual.strip().lower() != target.strip().lower():
                        return False
                elif actual != target:
                    return False

            elif op_lower == "ne":
                if isinstance(actual, str) and isinstance(target, str):
                    if actual.strip().lower() == target.strip().lower():
                        return False
                elif actual == target:
                    return False

            elif op_lower == "gt":
                if actual is None or not isinstance(actual, (int, float)):
                    return False
                if not (actual > target):
                    return False

            elif op_lower == "gte":
                if actual is None or not isinstance(actual, (int, float)):
                    return False
                if not (actual >= target):
                    return False

            elif op_lower == "lt":
                if actual is None or not isinstance(actual, (int, float)):
                    return False
                if not (actual < target):
                    return False

            elif op_lower == "lte":
                if actual is None or not isinstance(actual, (int, float)):
                    return False
                if not (actual <= target):
                    return False

            elif op_lower == "in":
                if actual is None:
                    return False
                if not isinstance(target, (list, tuple, set)):
                    target = [target]
                
                # If actual is a collection (e.g. list of materials), check intersection
                if isinstance(actual, (list, tuple, set)):
                    actual_lower = [str(x).lower() for x in actual]
                    target_lower = [str(y).lower() for y in target]
                    if not any(x in target_lower for x in actual_lower):
                        return False
                else:
                    actual_str = str(actual).strip().lower()
                    target_strs = [str(item).strip().lower() for item in target]
                    if actual_str not in target_strs:
                        return False

            elif op_lower == "not_in":
                if actual is None:
                    return True
                if not isinstance(target, (list, tuple, set)):
                    target = [target]
                actual_str = str(actual).strip().lower()
                target_strs = [str(item).strip().lower() for item in target]
                if actual_str in target_strs:
                    return False

            elif op_lower == "contains":
                if actual is None:
                    return False
                if isinstance(actual, (list, tuple, set)):
                    target_str = str(target).strip().lower()
                    if not any(str(item).strip().lower() == target_str for item in actual):
                        return False
                elif isinstance(actual, str):
                    if str(target).strip().lower() not in actual.strip().lower():
                        return False
                else:
                    return False

            elif op_lower == "contains_any":
                if actual is None:
                    return False
                target_list = target if isinstance(target, (list, tuple, set)) else [target]
                target_set = {str(item).strip().lower() for item in target_list}
                if isinstance(actual, (list, tuple, set)):
                    actual_set = {str(item).strip().lower() for item in actual}
                    if not (actual_set & target_set):
                        return False
                elif isinstance(actual, str):
                    actual_lower = actual.strip().lower()
                    if not any(t.lower() in actual_lower for t in target_list):
                        return False
                else:
                    return False

            elif op_lower == "contains_all":
                if actual is None:
                    return False
                target_list = target if isinstance(target, (list, tuple, set)) else [target]
                if isinstance(actual, (list, tuple, set)):
                    actual_set = {str(item).strip().lower() for item in actual}
                    for item in target_list:
                        if str(item).strip().lower() not in actual_set:
                            return False
                elif isinstance(actual, str):
                    actual_lower = actual.strip().lower()
                    for item in target_list:
                        if str(item).strip().lower() not in actual_lower:
                            return False
                else:
                    return False

            elif op_lower == "exists":
                has_value = actual is not None
                if has_value != bool(target):
                    return False

            elif op_lower == "regex":
                if actual is None:
                    return False
                if not re.search(str(target), str(actual), re.IGNORECASE):
                    return False

            else:
                # Unknown operator
                return False

        return True

    elif isinstance(expected, list):
        if actual is None:
            return False
        if isinstance(actual, (list, tuple, set)):
            return bool({str(x).lower() for x in actual} & {str(y).lower() for y in expected})
        return str(actual).strip().lower() in [str(item).strip().lower() for item in expected]

    elif isinstance(expected, bool):
        return bool(actual) is expected

    elif isinstance(expected, (int, float)):
        if actual is None:
            return False
        try:
            return float(actual) == float(expected)
        except (ValueError, TypeError):
            return False

    elif isinstance(expected, str):
        if actual is None:
            return False
        return str(actual).strip().lower() == expected.strip().lower()

    return actual == expected


def evaluate_predicate(predicate: Dict[str, Any], context: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    """
    Evaluates a JSON-path style predicate against the context dictionary.
    Returns (matches: bool, trace: Dict[str, Any]).
    Supports logical combinators 'and', 'or', 'not'.
    """
    if not predicate:
        return True, {"condition": "empty_predicate", "result": True}

    details = {}

    # Handle logical combinators if present at root
    if "or" in predicate and isinstance(predicate["or"], list):
        sub_traces = []
        any_match = False
        for sub_pred in predicate["or"]:
            matched, sub_trace = evaluate_predicate(sub_pred, context)
            sub_traces.append(sub_trace)
            if matched:
                any_match = True
                break
        details["or"] = sub_traces
        return any_match, details

    if "and" in predicate and isinstance(predicate["and"], list):
        sub_traces = []
        for sub_pred in predicate["and"]:
            matched, sub_trace = evaluate_predicate(sub_pred, context)
            sub_traces.append(sub_trace)
            if not matched:
                details["and"] = sub_traces
                return False, details
        details["and"] = sub_traces
        return True, details

    if "not" in predicate and isinstance(predicate["not"], dict):
        matched, sub_trace = evaluate_predicate(predicate["not"], context)
        details["not"] = sub_trace
        return (not matched), details

    # Standard path -> condition pairs (AND semantics)
    for path, condition in predicate.items():
        if path in ("and", "or", "not"):
            continue

        actual_val = resolve_path(path, context)
        matched = evaluate_condition(actual_val, condition)
        details[path] = {
            "actual": actual_val,
            "expected": condition,
            "matched": matched,
        }
        if not matched:
            return False, details

    return True, details


class RuleEngine:
    """
    Loads, caches, and indexes regulatory rule sets from YAML files.
    """

    def __init__(self, rules_dir: Optional[Union[str, Path]] = None):
        self.rules_dir = Path(rules_dir) if rules_dir else DEFAULT_RULES_DIR
        self._rules: List[Rule] = []
        self._rules_by_id: Dict[str, Rule] = {}
        self.reload()

    def reload(self) -> None:
        """Loads or reloads all YAML rule files from the rules directory."""
        self._rules.clear()
        self._rules_by_id.clear()

        if not self.rules_dir.exists():
            return

        for filepath in sorted(self.rules_dir.glob("*.yaml")) + sorted(self.rules_dir.glob("*.yml")):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                if not data:
                    continue
                if not isinstance(data, list):
                    data = [data]

                for item in data:
                    if isinstance(item, dict):
                        rule = Rule(**item)
                        self._rules.append(rule)
                        self._rules_by_id[rule.id] = rule
            except Exception as e:
                raise ValueError(f"Failed to load compliance rules from {filepath}: {e}") from e

    @property
    def rules(self) -> List[Rule]:
        return list(self._rules)

    def get_rule(self, rule_id: str) -> Optional[Rule]:
        return self._rules_by_id.get(rule_id)

    def get_rules_for_market(self, destination_market: str = "IN") -> List[Rule]:
        """Returns active rules applicable to the given destination market."""
        market = destination_market.upper()
        if market == "ALL":
            return list(self._rules)
        return [r for r in self._rules if r.jurisdiction.upper() in (market, "GLOBAL")]

    def get_stale_rules(self, days_threshold: int = 180, as_of: Optional[date] = None) -> List[Rule]:
        """Returns all rules whose last_verified date is older than days_threshold."""
        ref_date = as_of or date.today()
        return [r for r in self._rules if r.is_stale(days_threshold=days_threshold, as_of=ref_date)]


# Global singleton instance of RuleEngine
_GLOBAL_ENGINE: Optional[RuleEngine] = None


def get_rule_engine(rules_dir: Optional[Union[str, Path]] = None) -> RuleEngine:
    global _GLOBAL_ENGINE
    if _GLOBAL_ENGINE is None or rules_dir is not None:
        _GLOBAL_ENGINE = RuleEngine(rules_dir=rules_dir)
    return _GLOBAL_ENGINE


def _build_context(
    package: Any,
    product: Any,
    destination_market: str,
    extra_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Constructs an enriched evaluation context dictionary from candidate package,
    product profile, destination market, and caller-supplied context.
    """
    pkg_dict = _normalize_dict(package) if package else {}
    prod_dict = _normalize_dict(product) if product else {}
    extra = _normalize_dict(extra_context) if extra_context else {}

    # Inferred properties on package
    if isinstance(pkg_dict, dict):
        layer_stack = pkg_dict.get("layer_stack") or []
        if isinstance(layer_stack, list):
            pkg_dict.setdefault("is_multilayer", len(layer_stack) > 1)
            # Infer contact layer (first or last layer, standard sealant is last)
            if "contact_layer" not in pkg_dict and layer_stack:
                pkg_dict["contact_layer"] = layer_stack[-1]
            
            # Infer plastic presence
            plastic_names = {"pe", "pp", "pet", "bopp", "cpp", "lldpe", "hdpe", "ldpe", "bopa", "nylon", "evoh", "pvdc"}
            contains_plastic = any(any(p in str(lyr).lower() for p in plastic_names) for lyr in layer_stack)
            pkg_dict.setdefault("contains_plastic", contains_plastic)

            # Check layer materials for convenience
            pkg_dict.setdefault("layer_materials", [str(l).lower() for l in layer_stack])

        # Composite thickness inference
        if "composite_thickness_um" not in pkg_dict or pkg_dict.get("composite_thickness_um") is None:
            gauges = pkg_dict.get("gauge_per_layer") or pkg_dict.get("gauge_per_layer_um") or []
            if gauges and isinstance(gauges, list):
                try:
                    pkg_dict["composite_thickness_um"] = sum(float(g) for g in gauges)
                except (ValueError, TypeError):
                    pass

        # Standard packaged commodity defaults
        pkg_dict.setdefault("is_packaged_commodity", True)

    # Inferred properties on product
    if isinstance(prod_dict, dict):
        prod_dict.setdefault("is_food", True)
        prod_dict.setdefault("is_infant_food", False)
        prod_dict.setdefault("exempt_from_nutrition_table", False)

    context: Dict[str, Any] = {
        "destination_market": destination_market.upper(),
        "jurisdiction": destination_market.upper(),
        "market": {"jurisdiction": destination_market.upper()},
        "package": pkg_dict,
        "material": pkg_dict,
        "candidate": pkg_dict,
        "product": prod_dict,
        "commodity": prod_dict,
        "contact": extra.get("contact", "direct"),
        "functionality_impairment_certified": False,
        "indian_standard_available": True,
        "brand_owner": {"is_micro_or_small": False},
    }

    # Deep-merge extra context
    for k, v in extra.items():
        if k in ("package", "material") and isinstance(v, dict):
            context["package"].update(v)
            context["material"] = context["package"]
        elif k in ("product", "commodity") and isinstance(v, dict):
            context["product"].update(v)
            context["commodity"] = context["product"]
        elif k == "brand_owner" and isinstance(v, dict):
            context["brand_owner"].update(v)
        else:
            context[k] = v

    return context


def evaluate(
    package: Any,
    product: Any,
    destination_market: str = "IN",
    context: Optional[Dict[str, Any]] = None,
    eval_date: Optional[date] = None,
    engine: Optional[RuleEngine] = None,
) -> ComplianceReport:
    """
    Evaluates a candidate package plus product against all active regulations
    for the destination market.

    Returns a full ComplianceReport including rules fired, passed, blocking issues,
    required documents, warnings, and comprehensive audit trace.
    """
    eng = engine or get_rule_engine()
    ref_date = eval_date or date.today()
    eval_context = _build_context(package, product, destination_market, context)

    rules_to_evaluate = eng.get_rules_for_market(destination_market)

    rules_fired: List[Rule] = []
    rules_passed: List[Rule] = []
    blocking_issues: List[ComplianceIssue] = []
    required_docs_set: Set[str] = set()
    warnings: List[ComplianceWarning] = []
    trace: List[RuleTraceEntry] = []

    for rule in rules_to_evaluate:
        # Check date applicability
        if not rule.is_active_on(ref_date):
            continue

        fired, predicate_details = evaluate_predicate(rule.applies_when, eval_context)

        is_passed = True
        if fired:
            rules_fired.append(rule)

            if rule.effect == RuleEffect.BLOCK:
                is_passed = False
                blocking_issues.append(
                    ComplianceIssue(
                        rule_id=rule.id,
                        effect=rule.effect,
                        instrument=rule.instrument,
                        clause=rule.clause,
                        message=rule.message_en,
                        severity=rule.severity,
                        source_url=rule.source_url,
                        requires_document=rule.requires_document,
                    )
                )

            elif rule.effect in (RuleEffect.REQUIRE, RuleEffect.CONDITIONAL):
                if rule.requires_document:
                    required_docs_set.add(rule.requires_document.strip())

            elif rule.effect == RuleEffect.WARN:
                warnings.append(
                    ComplianceWarning(
                        rule_id=rule.id,
                        instrument=rule.instrument,
                        clause=rule.clause,
                        message=rule.message_en,
                        severity=rule.severity,
                        source_url=rule.source_url,
                        requires_document=rule.requires_document,
                    )
                )
                if rule.requires_document:
                    required_docs_set.add(rule.requires_document.strip())
        else:
            rules_passed.append(rule)

        trace.append(
            RuleTraceEntry(
                rule_id=rule.id,
                jurisdiction=rule.jurisdiction,
                instrument=rule.instrument,
                clause=rule.clause,
                effect=rule.effect,
                fired=fired,
                passed=is_passed,
                severity=rule.severity,
                message=rule.message_en,
                requires_document=rule.requires_document,
                source_url=rule.source_url,
                last_verified=rule.last_verified,
                details=predicate_details,
            )
        )

    # Sort required documents stably
    required_documents = sorted(required_docs_set)
    is_compliant = len(blocking_issues) == 0

    return ComplianceReport(
        is_compliant=is_compliant,
        destination_market=destination_market.upper(),
        evaluated_at=datetime.now(),
        rules_evaluated_count=len(rules_to_evaluate),
        rules_fired_count=len(rules_fired),
        rules_passed_count=len(rules_passed),
        rules_fired=rules_fired,
        rules_passed=rules_passed,
        blocking_issues=blocking_issues,
        required_documents=required_documents,
        warnings=warnings,
        trace=trace,
    )


# ---------------------------------------------------------------------------
# Section 6.2 & 6.3: Extended Producer Responsibility (EPR) Cost Engine
# ---------------------------------------------------------------------------

# Statutory recycling target percentages per Schedule II of PWM Rules 2022
RECYCLING_TARGETS: Dict[str, Dict[str, float]] = {
    "2024-25": {"Cat I": 0.50, "Cat II": 0.30, "Cat III": 0.30, "Cat IV": 0.0},
    "2025-26": {"Cat I": 0.60, "Cat II": 0.40, "Cat III": 0.40, "Cat IV": 0.0},
    "2026-27": {"Cat I": 0.70, "Cat II": 0.50, "Cat III": 0.50, "Cat IV": 0.0},
    "2027-28": {"Cat I": 0.80, "Cat II": 0.60, "Cat III": 0.60, "Cat IV": 0.0},
}

# Indicative market rates for plastic recycling credits (INR per metric tonne)
# Reflects recycling difficulty: Cat III multi-material laminates have significantly higher credit costs
DEFAULT_CREDIT_RATES_INR_PER_TONNE: Dict[str, float] = {
    "Cat I": 2000.0,    # Rigid plastics (HDPE/PP/PET bottles/tubs - established mechanical recycling)
    "Cat II": 4000.0,   # Flexible mono-material polyolefin films (BOPP/PE/CPP)
    "Cat III": 7500.0,  # Multi-layered plastics with foil/paper (cement kiln co-processing / pyrolysis)
    "Cat IV": 0.0,      # Certified compostable plastics (exempt from recycling targets per IS 17088)
}


def _normalize_epr_category(cat: Optional[str]) -> str:
    """Maps various category representations to canonical 'Cat I', 'Cat II', 'Cat III', 'Cat IV'."""
    if not cat:
        return "Cat II"
    c = str(cat).strip().upper()
    if "CAT IV" in c or "CATEGORY IV" in c or "COMPOST" in c:
        return "Cat IV"
    if "CAT III" in c or "CATEGORY III" in c or "MLP" in c or "MULTI" in c:
        return "Cat III"
    if "CAT II" in c or "CATEGORY II" in c or "FLEXIBLE" in c:
        return "Cat II"
    if "CAT I" in c or "CATEGORY I" in c or "RIGID" in c:
        return "Cat I"
    return "Cat II"


def epr_cost_estimate(
    structure: Union[Any, Dict[str, Any], str],
    annual_volume: int,
    pack_area_m2: float = 0.055,
    pack_weight_g: Optional[float] = None,
    is_msme: bool = False,
    financial_year: str = "2026-27",
    custom_credit_rates: Optional[Dict[str, float]] = None,
) -> EprCostEstimate:
    """
    Calculates the indicative annual rupee liability and per-pack EPR cost for plastic packaging
    under India's Plastic Waste Management (PWM) Rules 2022 Schedule II.

    Args:
        structure: PackageCandidate, StructureRecord, dict, or category string.
        annual_volume: Total packaging units produced or filled per annum.
        pack_area_m2: Total packaging surface area in square metres (default 0.055 m²).
        pack_weight_g: Direct plastic weight per pack in grams (if known).
        is_msme: If True, applies the Micro and Small Enterprise exemption (₹0 liability).
        financial_year: Target financial year ("2024-25" to "2027-28").
        custom_credit_rates: Optional override dictionary of EPR credit costs per metric tonne.
    """
    norm_struct = _normalize_dict(structure)
    category_raw = None
    composite_thickness_um = None

    if isinstance(norm_struct, dict):
        category_raw = norm_struct.get("epr_category")
        composite_thickness_um = norm_struct.get("composite_thickness_um")
        if not composite_thickness_um:
            gauges = norm_struct.get("gauge_per_layer") or norm_struct.get("gauge_per_layer_um") or []
            if gauges and isinstance(gauges, list):
                try:
                    composite_thickness_um = sum(float(g) for g in gauges)
                except (ValueError, TypeError):
                    pass
    elif isinstance(norm_struct, str):
        category_raw = norm_struct

    canonical_category = _normalize_epr_category(category_raw)

    # Calculate or resolve pack weight
    if pack_weight_g is not None and pack_weight_g > 0:
        resolved_weight_g = float(pack_weight_g)
    else:
        # Physical estimation from area, gauge, and density
        thickness = composite_thickness_um if composite_thickness_um and composite_thickness_um > 0 else 60.0
        # Area in cm², thickness in cm -> volume in cm³
        area_cm2 = pack_area_m2 * 10000.0
        thickness_cm = thickness * 1e-4
        vol_cm3 = area_cm2 * thickness_cm
        # Average density ~1.0 g/cm³ for flexible multi-laminates
        density_g_cm3 = 1.05 if canonical_category == "Cat III" else 0.95
        resolved_weight_g = round(vol_cm3 * density_g_cm3, 2)
        if resolved_weight_g <= 0:
            resolved_weight_g = 3.5  # Standard 100g snack pouch baseline

    # Total annual plastic tonnage (metric tonnes)
    total_plastic_tonnes = (annual_volume * resolved_weight_g) / 1_000_000.0

    # Statutory recycling target percentage
    fy_targets = RECYCLING_TARGETS.get(financial_year, RECYCLING_TARGETS["2026-27"])
    target_pct = fy_targets.get(canonical_category, 0.50)

    # Required recycling obligation in tonnes
    target_obligation_tonnes = total_plastic_tonnes * target_pct

    # Market credit rate per tonne
    rates = dict(DEFAULT_CREDIT_RATES_INR_PER_TONNE)
    if custom_credit_rates:
        rates.update(custom_credit_rates)
    credit_rate = rates.get(canonical_category, 4000.0)

    # Apply MSME exemption or compute liability
    if is_msme:
        total_liability_inr = 0.0
        cost_per_pack_inr = 0.0
        notes = "Exempt from EPR recycling and credit purchase obligation under PWM Rules 2022 Schedule II Clause 5.1 (MSME Exemption)."
    elif canonical_category == "Cat IV":
        total_liability_inr = 0.0
        cost_per_pack_inr = 0.0
        notes = "Category IV certified compostable packaging is exempt from plastic recycling credit targets under IS 17088."
    else:
        total_liability_inr = round(target_obligation_tonnes * credit_rate, 2)
        cost_per_pack_inr = round(total_liability_inr / annual_volume, 4) if annual_volume > 0 else 0.0
        notes = (
            f"Statutory {financial_year} recycling obligation: {int(target_pct * 100)}% of annual tonnage "
            f"at ₹{int(credit_rate):,}/tonne market credit cost."
        )

    breakdown = {
        "pack_area_m2": pack_area_m2,
        "composite_thickness_um": composite_thickness_um,
        "pack_weight_g": resolved_weight_g,
        "annual_volume": annual_volume,
        "total_tonnes": round(total_plastic_tonnes, 4),
        "target_percentage": target_pct,
        "obligation_tonnes": round(target_obligation_tonnes, 4),
        "credit_rate_inr_per_tonne": credit_rate,
        "financial_year": financial_year,
        "is_msme_exempt": is_msme,
    }

    return EprCostEstimate(
        epr_category=canonical_category,
        annual_volume=annual_volume,
        pack_weight_g=round(resolved_weight_g, 2),
        total_plastic_tonnes=round(total_plastic_tonnes, 4),
        recycling_target_pct=target_pct,
        target_obligation_tonnes=round(target_obligation_tonnes, 4),
        credit_rate_inr_per_tonne=credit_rate,
        total_liability_inr=total_liability_inr,
        cost_per_pack_inr=cost_per_pack_inr,
        is_msme_exempt=is_msme,
        financial_year=financial_year,
        breakdown=breakdown,
        notes=notes,
    )
