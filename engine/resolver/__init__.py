"""
Aavaran Resolver Layer.

Provides sparse-input resolution for commodities, post-harvest states,
environmental climatology, multi-leg journeys, and uncertainty propagation.
"""

from engine.resolver.environment import (
    JourneyLeg,
    lookup_climatology,
    resolve_environment,
    resolve_multi_leg_journey,
)
from engine.resolver.hierarchy import (
    ResolutionResult,
    match_class_envelope,
    match_commodity_id,
    match_cultivar,
    match_group,
    resolve_commodity,
)
from engine.resolver.modifiers import (
    ElapsedLifeResult,
    StateModifierResult,
    apply_modifiers,
    consume_elapsed_life,
)
from engine.resolver.uncertainty import (
    UncertaintyResult,
    compute_sensitivity_analysis,
    propagate,
    value_of_information,
)

__all__ = [
    "ElapsedLifeResult",
    "JourneyLeg",
    "ResolutionResult",
    "StateModifierResult",
    "UncertaintyResult",
    "apply_modifiers",
    "compute_sensitivity_analysis",
    "consume_elapsed_life",
    "lookup_climatology",
    "match_class_envelope",
    "match_commodity_id",
    "match_cultivar",
    "match_group",
    "propagate",
    "resolve_commodity",
    "resolve_environment",
    "resolve_multi_leg_journey",
    "value_of_information",
]
