"""Public platform pricing — no auth required."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.schemas.common import ApiResponse
from app.schemas.pricing import PlatformPricingResolved
from app.services.pricing_service import PricingService

router = APIRouter()


@router.get(
    "/current",
    response_model=ApiResponse[PlatformPricingResolved],
    summary="Current platform service fee (list + promo resolution)",
)
async def get_current_pricing(
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[PlatformPricingResolved]:
    svc = PricingService(db)
    data = await svc.get_current()
    return ApiResponse[PlatformPricingResolved](
        code="1000",
        message="OK",
        data=PlatformPricingResolved(**data),
    )
