"""
Pydantic Settings - all env-configurable values in one place.

Loaded from environment variables (and `.env` if present).
Every config item has a sane default so the dev environment boots
out of the box; production overrides via real env vars.
"""
from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# Project root & backend root resolved at import time so relative
# paths work the same in uvicorn, alembic and pytest.
BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Application configuration."""

    model_config = SettingsConfigDict(
        env_file=str(BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- App ---
    app_name: str = "Htex API"
    app_version: str = "0.1.0"
    env: Literal["dev", "test", "prod"] = "dev"
    debug: bool = True
    api_prefix: str = "/api/v2"

    # --- Server ---
    host: str = "0.0.0.0"
    port: int = 8000

    # --- Database ---
    # SQLite for dev. Override DATABASE_URL for Postgres in prod.
    database_url: str = Field(
        default=f"sqlite+aiosqlite:///{BACKEND_ROOT}/data/visa_mvp.db",
    )
    db_echo: bool = False

    # --- JWT ---
    # IMPORTANT: override JWT_SECRET in prod. >= 32 bytes recommended.
    jwt_secret: str = "dev-secret-change-me-in-prod-visa-mvp-2026"
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 120        # 2h per V2 §4.1.4
    refresh_token_ttl_days: int = 7           # 7d sliding per V2 §4.1.4

    # --- Password policy (V2 §4.1.4) ---
    bcrypt_cost: int = 12
    password_min_length: int = 8
    password_max_length: int = 32

    # --- Rate limit (V2 §9.4) ---
    rate_limit_per_ip_per_min: int = 100       # global
    rate_limit_slow_api_per_ip_per_min: int = 60

    # --- Celery / Redis ---
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # --- RAG auto-refresh (signature policy update) ---
    # Off by default: refresh hits real government websites, so opt-in via
    # env var (RAG_AUTO_REFRESH_ENABLED=1) before enabling in an environment
    # with outbound network access to avoid surprise traffic in dev/test.
    rag_auto_refresh_enabled: bool = False
    rag_auto_refresh_interval_hours: int = 24 * 7  # weekly

    # --- File / material service (V2 §4.3) ---
    material_storage_root: str = str(BACKEND_ROOT / "data" / "materials")
    material_url_ttl_seconds: int = 300          # 5 min signed URL
    material_max_file_size_mb: int = 10          # 10MB cap per V2 §5.2 IMAGE_FILE_SIZE_MAX
    # Privacy-first default: C-side uploads are ephemeral (/materials/process only).
    # Set MATERIAL_STORAGE_ENABLED=1 only for legacy/admin paths or integration tests.
    material_storage_enabled: bool = False
    # Image-quality + face-detection rules are gated on this until
    # OpenCV / PaddleOCR land in W3+:
    material_image_quality_enabled: bool = False

    # --- Logging ---
    log_dir: str = str(BACKEND_ROOT / "logs")
    log_level: str = "INFO"

    # --- System / scheduler auth (V2 §4.2.4 internal endpoints) ---
    # Shared-secret header `X-System-Key` used by the scheduler tick
    # endpoint. MUST be overridden in production via env var
    # `SYSTEM_API_KEY`. Default below is a clearly-non-prod value so
    # the endpoint refuses to boot in `env=prod` without an override.
    system_api_key: str = "dev-system-key-change-me-in-prod-visa-mvp-2026"

    # --- Admin panel (W14-3, W16-2) ---
    # DEV: set ADMIN_PASSWORD_SECRET in .env (local only, not committed).
    # PROD: inject via CI/CD secret / docker-compose secrets / vault.
    # admin_password (legacy) is deprecated; remove after migration.
    admin_password_secret: str = ""
    admin_password: str = "CHANGE_ME_IN_PROD"

    # --- OAuth providers ---
    google_client_id: str = ""      # set GOOGLE_CLIENT_ID in .env
    wechat_appid: str = ""          # set WECHAT_APPID in .env
    wechat_appsecret: str = ""      # set WECHAT_APPSECRET in .env

    # --- CORS (V2 §9 security) ---
    # Comma-separated list of allowed frontend origins.
    # Dev default includes localhost variants; prod MUST override via env var.
    # Example: https://visa.example.com,https://admin.example.com
    cors_allowed_origins: str = Field(
        default="http://localhost:5173,http://localhost:4173,http://localhost:3000",
    )

    # --- Security ---
    # Max request body size in MB (must match material_max_file_size_mb).
    max_request_size_mb: int = 10

    # --- Payment channel (V2 §4.5 — V2.1 stage — W10-4 wire-up) ---
    # All three fields are EMPTY BY DEFAULT in V2. V2 ships with the Mock
    # provider only (per Mavis 2026-06-12 10:54 decision: 支付全 Mock,
    # 后期 V2.1 阶段再接). When `stripe_secret_key` is blank,
    # `StripePaymentProvider` in `app/services/payment_provider.py` runs in
    # stub mode — every SDK call raises `NotImplementedError("V2.1 阶段接真")`
    # so the dev/test path stays credential-free. V2.1 activation:
    #   1. Apply for a Stripe account (test mode first: `sk_test_xxx`).
    #   2. Set the 3 fields in `.env` (NEVER commit real keys):
    #        STRIPE_SECRET_KEY=sk_test_xxx
    #        STRIPE_WEBHOOK_SECRET=whsec_xxx
    #        STRIPE_PAYOUT_ACCOUNT_ID=acct_xxx   (Connect / Affiliate transfer)
    #   3. macOS Keychain-backed env (preferred over .env in V2.1):
    #        security add-generic-password -s visa-mvp-stripe \
    #          -a STRIPE_SECRET_KEY -w 'sk_test_xxx'
    #      then a small launcher reads the Keychain item into the process env.
    #   4. Set PAYMENT_CHANNEL=stripe to route create/query/notify through
    #      StripePaymentProvider (requires STRIPE_SECRET_KEY).
    # SECURITY: All three are SECRETS. Never log them. Never echo them in
    # errors. Never commit a real key. macOS Keychain or a real secrets
    # manager (1Password CLI / AWS Secrets Manager / Vault) is the
    # recommended path — .env is acceptable for local dev only.
    payment_channel: Literal["mock", "stripe"] = "mock"
    stripe_secret_key: str = ""
    # Public key — safe to expose to the frontend for Stripe.js Elements.
    stripe_publishable_key: str = ""
    # `whsec_xxx` — used by `handle_notify` to verify the `Stripe-Signature`
    # header on inbound webhooks via `stripe.Webhook.construct_event`. If
    # blank, V2.1 webhook verification falls back to "no-signature" mode
    # (always reject) — production deploys MUST set this.
    stripe_webhook_secret: str = ""
    # `acct_xxx` — used by `payout()` to issue a real `stripe.Transfer` to
    # an affiliate partner's connected account. If blank, payout() raises
    # NotImplementedError (no fake transfer).
    stripe_payout_account_id: str = ""

    # --- LLM (W40 — itinerary auto-generation via MiniMax) ---
    # SECURITY: secret. Never log, never commit a real key — .env is
    # gitignored, local-dev only.
    minimax_api_key: str = ""
    minimax_api_base: str = "https://api.minimaxi.com/v1"
    minimax_model: str = "MiniMax-Text-01"

    # --- Product scope ---
    # Customer markets: Vietnam + Indonesia passport holders (overseas Web).
    # Visa destinations we file: US / Schengen / GB / AU only — see docs/PRODUCT_SCOPE.md.
    # RPA / insurance deferred — flip to true when ready.
    feature_rpa_enabled: bool = False
    feature_insurance_enabled: bool = False

    # --- Frontend base for email verification links (W1) ---
    # W1 dev default: localhost:5173. Prod: set APP_FRONTEND_BASE=https://htex.app
    app_frontend_base: str = "http://localhost:5173"

    # --- Email / Resend (registration verification codes) ---
    # RESEND_API_KEY is a secret — never log or commit. When blank, emails
    # land in logs/email_outbox/ (dev/test). When set, POST to Resend API.
    resend_api_key: str = ""
    email_from: str = "HTEX <noreply@htexvisa.com>"
    email_code_ttl_seconds: int = 600       # 10 minutes
    email_cooldown_seconds: int = 60
    email_daily_limit: int = 10

    # --- Privacy / support (self-service compliance) ---
    privacy_support_email: str = "privacy@htex.app"

    @property
    def email_backend(self) -> Literal["outbox", "resend"]:
        """Pick dispatch backend: Resend when API key present, else outbox stub."""
        return "resend" if self.resend_api_key.strip() else "outbox"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings accessor (avoids re-parsing .env on every call)."""
    return Settings()
