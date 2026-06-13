"""v2 API package — root router."""
from fastapi import APIRouter

from app.api.v2 import affiliate
from app.api.v2 import auth
from app.api.v2 import destinations
from app.api.v2 import insurance
from app.api.v2 import materials
from app.api.v2 import ocr
from app.api.v2 import orders
from app.api.v2 import payment
from app.api.v2 import sms


api_v2_router = APIRouter()
api_v2_router.include_router(affiliate.router, prefix="/affiliate", tags=["affiliate"])
api_v2_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_v2_router.include_router(destinations.router, prefix="/destinations", tags=["destinations"])
# B-W8-3 — 拒签险 service (Mock-only in V2, V2.1 wires 太平洋保险/众安保险)
api_v2_router.include_router(insurance.router, prefix="/insurance", tags=["insurance"])
api_v2_router.include_router(materials.router, prefix="/materials", tags=["materials"])
api_v2_router.include_router(ocr.router, prefix="/ocr", tags=["ocr"])
api_v2_router.include_router(orders.router, prefix="/orders", tags=["orders"])
api_v2_router.include_router(payment.router, prefix="/payment", tags=["payment"])
# B-W6-1 — standalone SMS service (Mock-only in V2)
api_v2_router.include_router(sms.router, prefix="/sms", tags=["sms"])
