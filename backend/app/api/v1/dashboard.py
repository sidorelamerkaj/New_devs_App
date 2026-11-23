from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Any, Dict

from app.services.cache import get_revenue_summary
from app.services.reservations import list_tenant_properties
from app.core.auth import authenticate_request as get_current_user

router = APIRouter()


def _tenant_id(current_user: Any) -> str:
    if isinstance(current_user, dict):
        tenant_id = current_user.get("tenant_id")
    else:
        tenant_id = getattr(current_user, "tenant_id", None)
    if not tenant_id:
        # don't fall back to a shared tenant, that was mixing the two clients
        raise HTTPException(status_code=401, detail="Tenant could not be resolved")
    return tenant_id


@router.get("/dashboard/properties")
async def get_dashboard_properties(
    current_user: Any = Depends(get_current_user),
) -> Dict[str, Any]:
    tenant_id = _tenant_id(current_user)
    properties = await list_tenant_properties(tenant_id)
    return {"properties": properties}


@router.get("/dashboard/summary")
async def get_dashboard_summary(
    property_id: str,
    month: int = Query(3, ge=1, le=12),
    year: int = Query(2024, ge=2000, le=2100),
    current_user: Any = Depends(get_current_user),
) -> Dict[str, Any]:
    tenant_id = _tenant_id(current_user)
    revenue_data = await get_revenue_summary(property_id, tenant_id, month, year)

    # send the total as a string. json numbers are floats and the cents were drifting
    return {
        "property_id": revenue_data["property_id"],
        "total_revenue": revenue_data["total"],
        "currency": revenue_data["currency"],
        "reservations_count": revenue_data["count"],
        "month": revenue_data["month"],
        "year": revenue_data["year"],
    }
