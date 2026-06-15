"""/api/v2/destinations — 国家列表(V2 范围 = 美国 V2 启用)"""
import json
from typing import Optional, List

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.logging import get_logger
from app.schemas.common import ApiResponse
from app.models.destination import VisaDestination

logger = get_logger()

router = APIRouter(tags=["destinations"])


class DestinationOut(BaseModel):
    id: int
    country_code: str
    country_name: str
    visa_types: List[str]
    image_url: Optional[str]
    enabled: bool

    model_config = {"from_attributes": True}


@router.get("", response_model=ApiResponse[List[DestinationOut]])
async def list_destinations(
    db: AsyncSession = Depends(get_db),
    visa_type: Optional[str] = Query(None, description="按签种过滤: tourism | student"),
    lang: str = Query("zh-CN", description="返回国家名的语种: zh-CN | en | id | vi"),
):
    """返回国家列表。
    Spec: V2 范围 = 美国 enabled=true,其他 8 国 enabled=false(灰显,V3+ 开放)。
    """
    stmt = select(VisaDestination).order_by(VisaDestination.display_order)
    if visa_type:
        # visa_types 字段是 JSON 字符串,需要客户端或 DB 层过滤;这里只过滤 enabled
        pass
    rows = (await db.execute(stmt)).scalars().all()

    items = []
    for r in rows:
        try:
            name_map = json.loads(r.country_name_i18n)
        except Exception:
            name_map = {"zh-CN": r.country_code}
        if visa_type:
            try:
                types = json.loads(r.visa_types)
            except Exception:
                types = []
            if visa_type not in types:
                continue
        items.append(DestinationOut(
            id=r.id,
            country_code=r.country_code,
            country_name=name_map.get(lang, name_map.get("en", r.country_code)),
            visa_types=json.loads(r.visa_types) if r.visa_types else [],
            image_url=r.image_url,
            enabled=r.enabled,
        ))

    return ApiResponse(code="1000", message="OK", data=items)
