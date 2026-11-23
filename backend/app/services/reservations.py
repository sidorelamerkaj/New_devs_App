from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional

import asyncpg

from app.config import settings

_pool: Optional[asyncpg.Pool] = None
_MONEY = Decimal("0.01")


async def _get_pool() -> asyncpg.Pool:
    # old pool looked for supabase settings that aren't set here, so it
    # always failed and both clients got the same hardcoded mock totals
    global _pool
    if _pool is None:
        dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
        _pool = await asyncpg.create_pool(dsn, min_size=1, max_size=5)
    return _pool


def _money(amount: Decimal) -> str:
    # round the total once. rounding each booking (333.333 -> 333.33) was a cent short
    return str(Decimal(amount).quantize(_MONEY, rounding=ROUND_HALF_UP))


def _month_bounds(year: int, month: int) -> tuple[datetime, datetime]:
    # naive on purpose. the property timezone gets applied in the query
    start = datetime(year, month, 1)
    if month == 12:
        end = datetime(year + 1, 1, 1)
    else:
        end = datetime(year, month + 1, 1)
    return start, end


async def calculate_monthly_revenue(
    property_id: str,
    month: int,
    year: int,
    tenant_id: str,
) -> Dict[str, Any]:
    start_local, end_local = _month_bounds(year, month)
    pool = await _get_pool()

    query = """
        SELECT
            COALESCE(SUM(r.total_amount), 0) AS total_revenue,
            COUNT(r.id) AS reservation_count,
            MAX(r.currency) AS currency
        FROM properties p
        LEFT JOIN reservations r
            ON r.property_id = p.id
           AND r.tenant_id = p.tenant_id
           -- beach house is paris (utc+1 in feb). 29 feb 23:30 utc is already 1 march there,
           -- so a utc cutoff was dropping the 1250 booking from sunset's march total
           AND (r.check_in_date AT TIME ZONE p.timezone) >= $3::timestamp
           AND (r.check_in_date AT TIME ZONE p.timezone) < $4::timestamp
        WHERE p.id = $1
          AND p.tenant_id = $2
    """

    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, property_id, tenant_id, start_local, end_local)

    if row is None:
        total = Decimal("0")
        count = 0
        currency = "USD"
    else:
        total = Decimal(row["total_revenue"])
        count = int(row["reservation_count"])
        currency = row["currency"] or "USD"

    return {
        "property_id": property_id,
        "tenant_id": tenant_id,
        "total": _money(total),
        "currency": currency,
        "count": count,
        "month": month,
        "year": year,
    }


async def list_tenant_properties(tenant_id: str) -> List[Dict[str, str]]:
    # dropdown used to be a hardcoded list of every property, both companies
    pool = await _get_pool()
    query = """
        SELECT id, name, timezone
        FROM properties
        WHERE tenant_id = $1
        ORDER BY name
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, tenant_id)
    return [
        {"id": row["id"], "name": row["name"], "timezone": row["timezone"]}
        for row in rows
    ]
