"""visa_destinations 表 + 9 国种子数据 — V2 范围 = 美国 V2 启用,其他 V3+ 灰显"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime
import json

revision = "0002"
down_revision = "0001_init"
branch_labels = None
depends_on = None


DESTINATIONS = [
    {
        "country_code": "US",
        "country_name_i18n": {"zh-CN": "美国", "en": "United States", "id": "Amerika Serikat", "vi": "Hoa Kỳ"},
        "visa_types": ["tourism", "student"],
        "enabled": True,
        "display_order": 10,
        "image_url": "/images/usa.jpg",
    },
    {
        "country_code": "JP",
        "country_name_i18n": {"zh-CN": "日本", "en": "Japan", "id": "Jepang", "vi": "Nhật Bản"},
        "visa_types": ["tourism", "student"],
        "enabled": False,
        "display_order": 20,
        "image_url": "/images/japan.jpg",
    },
    {
        "country_code": "UK",
        "country_name_i18n": {"zh-CN": "英国", "en": "United Kingdom", "id": "Inggris", "vi": "Vương quốc Anh"},
        "visa_types": ["tourism", "student"],
        "enabled": False,
        "display_order": 30,
        "image_url": "/images/uk.jpg",
    },
    {
        "country_code": "AU",
        "country_name_i18n": {"zh-CN": "澳大利亚", "en": "Australia", "id": "Australia", "vi": "Úc"},
        "visa_types": ["tourism", "student"],
        "enabled": False,
        "display_order": 40,
        "image_url": "/images/australia.jpg",
    },
    {
        "country_code": "CA",
        "country_name_i18n": {"zh-CN": "加拿大", "en": "Canada", "id": "Kanada", "vi": "Canada"},
        "visa_types": ["tourism", "student"],
        "enabled": False,
        "display_order": 50,
        "image_url": "/images/canada.jpg",
    },
    {
        "country_code": "DE",
        "country_name_i18n": {"zh-CN": "德国(申根)", "en": "Germany (Schengen)", "id": "Jerman (Schengen)", "vi": "Đức (Schengen)"},
        "visa_types": ["tourism", "student"],
        "enabled": False,
        "display_order": 60,
        "image_url": "/images/eu.jpg",
    },
    {
        "country_code": "FR",
        "country_name_i18n": {"zh-CN": "法国(申根)", "en": "France (Schengen)", "id": "Prancis (Schengen)", "vi": "Pháp (Schengen)"},
        "visa_types": ["tourism", "student"],
        "enabled": False,
        "display_order": 70,
        "image_url": "/images/eu.jpg",
    },
    {
        "country_code": "SG",
        "country_name_i18n": {"zh-CN": "新加坡", "en": "Singapore", "id": "Singapura", "vi": "Singapore"},
        "visa_types": ["tourism", "student"],
        "enabled": False,
        "display_order": 80,
        "image_url": "/images/korea.jpg",
    },
    {
        "country_code": "NZ",
        "country_name_i18n": {"zh-CN": "新西兰", "en": "New Zealand", "id": "Selandia Baru", "vi": "New Zealand"},
        "visa_types": ["tourism", "student"],
        "enabled": False,
        "display_order": 90,
        "image_url": "/images/newzealand.jpg",
    },
]


def upgrade() -> None:
    op.create_table(
        "visa_destinations",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("country_code", sa.String(8), nullable=False, unique=True),
        sa.Column("country_name_i18n", sa.Text, nullable=False),
        sa.Column("visa_types", sa.Text, nullable=False),
        sa.Column("enabled", sa.Boolean, nullable=False, default=True),
        sa.Column("display_order", sa.Integer, nullable=False, default=0),
        sa.Column("image_url", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, default=datetime.utcnow),
    )
    op.create_index("idx_destinations_enabled_order", "visa_destinations", ["enabled", "display_order"])

    bind = op.get_bind()
    for d in DESTINATIONS:
        bind.execute(
            sa.text("""
                INSERT INTO visa_destinations
                  (country_code, country_name_i18n, visa_types, enabled, display_order, image_url, created_at)
                VALUES
                  (:cc, :name, :vt, :en, :ord, :img, :ts)
            """),
            {
                "cc": d["country_code"],
                "name": json.dumps(d["country_name_i18n"], ensure_ascii=False),
                "vt": json.dumps(d["visa_types"]),
                "en": d["enabled"],
                "ord": d["display_order"],
                "img": d["image_url"],
                "ts": datetime.utcnow(),
            }
        )


def downgrade() -> None:
    op.drop_index("idx_destinations_enabled_order", table_name="visa_destinations")
    op.drop_table("visa_destinations")
