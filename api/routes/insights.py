"""
Farmer insight routes beyond packaging:

- GET /api/v1/lowcost/{commodity_id}   low-cost, no-plastic storage options (sourced)
- GET /api/v1/market/price             mandi prices (Agmarknet via data.gov.in) + sell/hold hint
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query

from api import lowcost, market

router = APIRouter(prefix="/api/v1", tags=["Farmer insights"])


@router.get("/lowcost/{commodity_id}")
def get_lowcost(
    commodity_id: str,
    lang: str = Query(default="hi-IN"),
    physical_state: Optional[str] = Query(default=None),
) -> Dict[str, Any]:
    opts = lowcost.options_for(commodity_id, lang, physical_state)
    return {"commodity_id": commodity_id, "options": opts, "count": len(opts)}


@router.get("/market/price")
def get_market_price(
    commodity_id: str = Query(...),
    state: Optional[str] = Query(default=None),
    district: Optional[str] = Query(default=None),
    market_name: Optional[str] = Query(default=None, alias="market"),
    shelf_life_days: Optional[float] = Query(default=None, ge=0),
    lang: str = Query(default="hi-IN"),
) -> Dict[str, Any]:
    try:
        return market.price_insight(
            commodity_id,
            state=state,
            district=district,
            market_name=market_name,
            shelf_life_days=shelf_life_days,
            lang=lang,
        )
    except market.MarketUnavailable as exc:
        raise HTTPException(status_code=503, detail={"code": exc.code, "message": str(exc)})
