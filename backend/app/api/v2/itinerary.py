"""
/api/v2/itinerary/* — W40/W41/W42 LLM-assisted itinerary fill-in.

  - POST /api/v2/itinerary/generate   (fill blank transport/hotel/attraction via MiniMax)

City is always user-supplied and never touched here; blank transport/hotel/
attraction entries get filled in, in the caller's locale, using flight
context (outbound origin/destination + independently-editable return
origin/destination, flight numbers, dates) to reason about which day is the
arrival/departure day — matched by date, not by table position.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.errors import BizException, ErrorCode
from app.core.logging import get_logger
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.common import ApiResponse
from app.services.llm.itinerary_generator import generate_itinerary_fields
from app.services.llm.minimax_client import MiniMaxError, get_minimax_client

router = APIRouter()
_log = get_logger()


class ItineraryDay(BaseModel):
    day: int = Field(..., ge=1)
    date: str = ""
    city: str = ""
    transport: str = ""
    hotel: str = ""
    attraction: str = ""
    # W47: English mirrors for the bilingual visa PDF (target language + English).
    # Filled by the LLM for every day; left empty when unknown (e.g. user hand-edited).
    city_en: str = ""
    hotel_en: str = ""
    attraction_en: str = ""


class FlightContext(BaseModel):
    origin: str = ""
    destination: str = ""
    flight_out_no: str = ""
    flight_back_no: str = ""
    depart_date: str = ""
    return_date: str = ""
    # W42: return leg is independently editable (open-jaw trips — the return
    # doesn't have to go back to the same city the outbound came from).
    return_origin: str = ""
    return_destination: str = ""


class GenerateItineraryRequest(BaseModel):
    country_name: str = ""
    lang: str = "zh-CN"
    days: list[ItineraryDay] = Field(default_factory=list)
    flight: Optional[FlightContext] = None


class GenerateItineraryResponse(BaseModel):
    days: list[ItineraryDay]


@router.post("/generate", response_model=ApiResponse[GenerateItineraryResponse], summary="LLM-fill blank itinerary transport/hotel/attraction fields")
async def generate_itinerary(
    body: GenerateItineraryRequest,
    current_user: User = Depends(get_current_user),
) -> ApiResponse[GenerateItineraryResponse]:
    if not get_minimax_client().configured:
        raise BizException(ErrorCode.LLM_NOT_CONFIGURED, message="LLM service is not configured")
    if not body.days:
        raise BizException(ErrorCode.INVALID_PARAMS, message="days is empty")

    try:
        filled = await generate_itinerary_fields(
            days=[d.model_dump() for d in body.days],
            country_name=body.country_name or "the destination country",
            lang=body.lang,
            flight_ctx=body.flight.model_dump() if body.flight else None,
        )
    except MiniMaxError as exc:
        _log.warning("itinerary generation failed user_id={}: {}", current_user.id, exc)
        raise BizException(ErrorCode.LLM_UPSTREAM_ERROR, message=str(exc)) from exc

    payload = GenerateItineraryResponse(days=[ItineraryDay(**d) for d in filled])
    return ApiResponse[GenerateItineraryResponse](code="1000", message="OK", data=payload)
