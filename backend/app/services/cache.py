import json
import os
from typing import Any, Dict

import redis.asyncio as redis

redis_client = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))


async def get_revenue_summary(
    property_id: str,
    tenant_id: str,
    month: int = 3,
    year: int = 2024,
) -> Dict[str, Any]:
    # prop-001 exists for both sunset and ocean. keying only on the property id
    # meant the first company to load it left their total in redis for 5 minutes
    cache_key = f"revenue:{tenant_id}:{property_id}:{year}:{month:02d}"

    cached = await redis_client.get(cache_key)
    if cached:
        data = json.loads(cached)
        # extra check in case an old key is still hanging around
        if (
            data.get("tenant_id") == tenant_id
            and data.get("property_id") == property_id
            and data.get("month") == month
            and data.get("year") == year
        ):
            return data

    from app.services.reservations import calculate_monthly_revenue

    result = await calculate_monthly_revenue(property_id, month, year, tenant_id)
    await redis_client.setex(cache_key, 300, json.dumps(result))
    return result
