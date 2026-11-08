"""
Aavaran Compliance Engine.

Data-driven packaging regulatory compliance evaluator following Section 6 of BLUEPRINT.md.
"""

from engine.compliance.evaluator import (
    RuleEngine,
    epr_cost_estimate,
    evaluate,
    evaluate_predicate,
    get_rule_engine,
)
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

__all__ = [
    "Rule",
    "RuleEffect",
    "RuleSeverity",
    "ComplianceIssue",
    "ComplianceWarning",
    "RuleTraceEntry",
    "ComplianceReport",
    "EprCostEstimate",
    "RuleEngine",
    "get_rule_engine",
    "evaluate",
    "evaluate_predicate",
    "epr_cost_estimate",
]
