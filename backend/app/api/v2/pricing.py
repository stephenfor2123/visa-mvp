"""Public platform pricing — no auth required."""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.schemas.common import ApiResponse
from app.schemas.pricing import PlatformPricingResolved
from app.services.pricing_service import PricingService

router = APIRouter()


@router.get(
    "/current",
    response_model=ApiResponse[PlatformPricingResolved],
    summary="Current platform service fee (optional country + visa_type)",
)
async def get_current_pricing(
    db: AsyncSession = Depends(get_db),
    country_code: Optional[str] = Query(
        None, min_length=2, max_length=8, description="Destination country, e.g. US"
    ),
    visa_type: Optional[str] = Query(
        None, min_length=1, max_length=32, description="Visa type, e.g. tourism"
    ),
) -> ApiResponse[PlatformPricingResolved]:
    svc = PricingService(db)
    data = await svc.get_current(country_code=country_code, visa_type=visa_type)
    return ApiResponse[PlatformPricingResolved](
        code="1000",
        message="OK",
        data=PlatformPricingResolved(**data),
    )
