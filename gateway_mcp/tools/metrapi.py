from __future__ import annotations

import json

from mcp.types import ToolAnnotations

from gateway_mcp.services.metrapi import gab_page
from gateway_mcp.tools.runtime import ToolRun


def register_metrapi_tools(mcp) -> None:
    @mcp.tool(annotations=ToolAnnotations(title="Metrapi: оценить страницу ГАБ"))
    async def gateway_metrapi_gab_page(
        offset: int = 0,
        limit: int = 50,
        price_max_rub: int = 200_000_000,
        target_yield_pct: float = 10,
    ) -> str:
        """Fetch and score one page of commercial sale listings without exposing the API key."""
        run = ToolRun.start(tool="gateway_metrapi_gab_page", system="metrapi", scope="crm:write", arguments={"offset": offset, "limit": limit, "price_max_rub": price_max_rub, "target_yield_pct": target_yield_pct})
        try:
            run.require_scope()
            result = await gab_page(offset=offset, limit=limit, price_max_rub=price_max_rub, target_yield_pct=target_yield_pct)
            run.finish()
            return json.dumps(result, ensure_ascii=False)
        except PermissionError as exc:
            run.denied(exc)
            raise
        except Exception as exc:
            run.error(exc)
            raise
