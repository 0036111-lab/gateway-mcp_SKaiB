from __future__ import annotations

import re
from typing import Any

import httpx

from gateway_mcp.services.managed_integrations import integration_value


def _number(value: str | None) -> float | None:
    if not value:
        return None
    normalized = re.sub(r"[^\d.,]", "", value).replace(",", ".")
    try:
        return float(normalized)
    except ValueError:
        return None


def _price_drop(item: dict[str, Any]) -> float:
    current = float(item.get("price") or 0)
    values = [current, float(item.get("price_prev") or 0)]
    for event in item.get("price_history") or []:
        values.extend((float(event.get("old") or 0), float(event.get("new") or 0)))
    peak = max(values, default=0)
    return round((peak - current) / peak * 100, 1) if peak and current < peak else 0.0


def evaluate_gab(item: dict[str, Any], *, target_yield_pct: float = 10) -> dict[str, Any]:
    description = str(item.get("description") or "")
    map_match = re.search(r"МАП\s*[:—-]?\s*([\d\s.,]+)", description, re.I)
    gap_match = re.search(r"ГАП\s*[:—-]?\s*([\d\s.,]+)", description, re.I)
    monthly_rent = _number(map_match.group(1) if map_match else None)
    annual_rent = _number(gap_match.group(1) if gap_match else None)
    price = float(item.get("price") or 0)
    gross_yield = None
    if price and monthly_rent:
        gross_yield = monthly_rent * 12 / price * 100
    elif price and annual_rent:
        gross_yield = annual_rent / price * 100
    tenant_signal = bool(re.search(r"арендатор|готовый арендный бизнес|\bГАБ\b", description, re.I))
    drop = _price_drop(item)
    score = (3 if tenant_signal else 0) + (4 if monthly_rent or annual_rent else 0)
    score += 4 if gross_yield and gross_yield >= target_yield_pct - 1 else 2 if gross_yield and gross_yield >= 7 else 0
    score += 2 if drop >= 10 else 1 if drop >= 3 else 0
    area = float(item.get("area_total") or 0)
    return {
        "source": item.get("source"),
        "source_id": item.get("source_id"),
        "dedupe_key": f"{item.get('source')}:{item.get('source_id')}",
        "url": item.get("url"),
        "address": item.get("address"),
        "commercial_types": item.get("commercial_types") or [],
        "area_sqm": area or None,
        "asking_price_rub": price or None,
        "price_per_sqm_rub": round(price / area) if price and area else None,
        "monthly_rent_claimed_rub": monthly_rent,
        "annual_rent_claimed_rub": annual_rent,
        "gross_yield_calculated_pct": round(gross_yield, 1) if gross_yield else None,
        "price_drop_pct": drop,
        "tenant_signal": tenant_signal,
        "selection_score": score,
        "verification_status": "требует проверки",
    }


async def gab_page(*, offset: int, limit: int, price_max_rub: int, target_yield_pct: float) -> dict[str, Any]:
    api_key = integration_value("metrapi", "METRAPI_API_KEY")
    if not api_key:
        raise RuntimeError("Metrapi integration is not configured")
    base_url = integration_value("metrapi", "METRAPI_BASE_URL", "https://api.metrapi.ru").rstrip("/")
    params: list[tuple[str, str | int]] = [
        ("city", "msk"), ("city", "spb"), ("deal_type", "sale"),
        ("realty_type", "commercial"), ("price_max", price_max_rub),
        ("price_changed", 1), ("price_history", 1), ("dedupe", "true"),
        ("limit", max(1, min(limit, 50))), ("offset", max(0, offset)),
    ]
    for commercial_type in ("retail", "warehouse", "office", "free_purpose"):
        params.append(("commercial_type", commercial_type))
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(f"{base_url}/v1/items", params=params, headers={"X-Api-Key": api_key})
        response.raise_for_status()
        payload = response.json()
    evaluated = [evaluate_gab(item, target_yield_pct=target_yield_pct) for item in payload.get("items", [])]
    selected = sorted((item for item in evaluated if item["selection_score"] >= 5), key=lambda item: item["selection_score"], reverse=True)
    return {"offset": offset, "received": len(evaluated), "selected": selected, "next_offset": offset + len(evaluated) if len(evaluated) == limit else None}
