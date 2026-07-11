"""v2 API package — root router."""
from fastapi import APIRouter

from app.core.config import get_settings
from app.api.v2 import admin
# W62 — RAG 内容审核 (admin sub-router)
from app.api.v2 import admin_rag
# W37 — Cleanup & 72h user destroy endpoints (V2 §4.1.4 / §4.3.5)
from app.api.v2 import admin_cleanup
from app.api.v2 import affiliate
from app.api.v2 import auth
from app.api.v2 import destinations
# W31 — Visa eligibility quick-check (rule engine)
from app.api.v2 import diagnose
# W40 — LLM-assisted itinerary attraction fill-in (MiniMax)
from app.api.v2 import itinerary
from app.api.v2 import materials
# W41 — Personal aggregation (header dropdown: distinct applicants derived from orders)
from app.api.v2 import my
from app.api.v2 import ocr
from app.api.v2 import orders
from app.api.v2 import payment
# W1 — Personal profile (applicant library + email change)
from app.api.v2 import profile
# Case 4 — RAG: retrieval-augmented Q&A over official visa info
from app.api.v2 import rag
# W48 — Cross-device "scan QR to upload from phone" (in-memory sessions + SSE).
from app.api.v2 import transfer
from app.api.v2 import voice
# W48 — DS-160 browser extension (12-digit code redeem flow).
from app.api.v2 import ds160

# Deferred modules — import only when feature flags are on.
_settings = get_settings()
if _settings.feature_insurance_enabled:
    from app.api.v2 import insurance  # noqa: F401
if _settings.feature_rpa_enabled:
    from app.api.v2 import rpa  # noqa: F401


api_v2_router = APIRouter()
api_v2_router.include_router(admin.router, tags=["admin"])
# W62 — RAG 内容审核 (admin only, prefix already in admin_rag.router)
api_v2_router.include_router(admin_rag.router, tags=["admin-rag"])
# W37 — Cleanup & 72h user destroy (sub-router under /admin/cleanup)
api_v2_router.include_router(admin_cleanup.router, tags=["admin-cleanup"])
api_v2_router.include_router(affiliate.router, prefix="/affiliate", tags=["affiliate"])
api_v2_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_v2_router.include_router(destinations.router, prefix="/destinations", tags=["destinations"])
# W31 — Visa eligibility quick-check (rule engine over personal profile)
api_v2_router.include_router(diagnose.router, tags=["diagnose"])
# B-W8-3 — 拒签险 service (disabled — set FEATURE_INSURANCE_ENABLED=1)
if _settings.feature_insurance_enabled:
    api_v2_router.include_router(insurance.router, prefix="/insurance", tags=["insurance"])
# W40 — LLM-assisted itinerary generation
api_v2_router.include_router(itinerary.router, prefix="/itinerary", tags=["itinerary"])
api_v2_router.include_router(materials.router, prefix="/materials", tags=["materials"])
# W41 — Personal aggregation under /my/* (no extra prefix; my.router already has /my)
api_v2_router.include_router(my.router, tags=["my"])
api_v2_router.include_router(ocr.router, prefix="/ocr", tags=["ocr"])
api_v2_router.include_router(orders.router, prefix="/orders", tags=["orders"])
api_v2_router.include_router(payment.router, prefix="/payment", tags=["payment"])
# W1 — Personal profile (no extra prefix; profile.router already has prefix="/profile")
api_v2_router.include_router(profile.router, tags=["profile"])
# Case 4 — RAG endpoint (registered after rpa, no extra prefix; rag.router already has /rag prefix)
api_v2_router.include_router(rag.router, tags=["rag"])
# W19 — RPA submission (disabled — set FEATURE_RPA_ENABLED=1)
if _settings.feature_rpa_enabled:
    api_v2_router.include_router(rpa.router, tags=["rpa"])
# W14-5 — voice / speech-to-text endpoint
api_v2_router.include_router(voice.router, prefix="/voice", tags=["voice"])
# W48 — Cross-device QR transfer sessions (no extra prefix; transfer.router has /transfer)
api_v2_router.include_router(transfer.router, tags=["transfer"])
# W48 — DS-160 browser extension endpoints (no extra prefix; ds160.router has /ds160)
api_v2_router.include_router(ds160.router, tags=["ds160"])
