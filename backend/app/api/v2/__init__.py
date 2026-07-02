"""v2 API package — root router."""
from fastapi import APIRouter

from app.api.v2 import admin
# W37 — Cleanup & 72h user destroy endpoints (V2 §4.1.4 / §4.3.5)
from app.api.v2 import admin_cleanup
from app.api.v2 import affiliate
from app.api.v2 import auth
from app.api.v2 import destinations
# W31 — Visa eligibility quick-check (rule engine)
from app.api.v2 import diagnose
from app.api.v2 import insurance
# W40 — LLM-assisted itinerary attraction fill-in (MiniMax)
from app.api.v2 import itinerary
from app.api.v2 import materials
# W41 — Personal aggregation (header dropdown: distinct applicants derived from orders)
from app.api.v2 import my
from app.api.v2 import ocr
from app.api.v2 import orders
from app.api.v2 import payment
# W19 — RPA submission (was missing from api_v2_router include list, endpoint registered but unreachable)
from app.api.v2 import rpa
from app.api.v2 import voice
# Case 4 — RAG: retrieval-augmented Q&A over official visa info
from app.api.v2 import rag


api_v2_router = APIRouter()
api_v2_router.include_router(admin.router, tags=["admin"])
# W37 — Cleanup & 72h user destroy (sub-router under /admin/cleanup)
api_v2_router.include_router(admin_cleanup.router, tags=["admin-cleanup"])
api_v2_router.include_router(affiliate.router, prefix="/affiliate", tags=["affiliate"])
api_v2_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_v2_router.include_router(destinations.router, prefix="/destinations", tags=["destinations"])
# W31 — Visa eligibility quick-check (rule engine over personal profile)
api_v2_router.include_router(diagnose.router, tags=["diagnose"])
# B-W8-3 — 拒签险 service (Mock-only in V2, V2.1 wires 太平洋保险/众安保险)
api_v2_router.include_router(insurance.router, prefix="/insurance", tags=["insurance"])
# W40 — LLM-assisted itinerary generation
api_v2_router.include_router(itinerary.router, prefix="/itinerary", tags=["itinerary"])
api_v2_router.include_router(materials.router, prefix="/materials", tags=["materials"])
# W41 — Personal aggregation under /my/* (no extra prefix; my.router already has /my)
api_v2_router.include_router(my.router, tags=["my"])
api_v2_router.include_router(ocr.router, prefix="/ocr", tags=["ocr"])
api_v2_router.include_router(orders.router, prefix="/orders", tags=["orders"])
api_v2_router.include_router(payment.router, prefix="/payment", tags=["payment"])
# Case 4 — RAG endpoint (registered after rpa, no extra prefix; rag.router already has /rag prefix)
api_v2_router.include_router(rag.router, tags=["rag"])
# W19 — RPA submission endpoint (no extra prefix; rpa.router already has prefix="/rpa")
api_v2_router.include_router(rpa.router, tags=["rpa"])
# W14-5 — voice / speech-to-text endpoint
api_v2_router.include_router(voice.router, prefix="/voice", tags=["voice"])
