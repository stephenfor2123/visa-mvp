"""VisaDestination ORM model"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func
from app.core.db import Base


class VisaDestination(Base):
    __tablename__ = "visa_destinations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    country_code = Column(String(8), nullable=False, unique=True)
    country_name_i18n = Column(String, nullable=False)  # JSON 字符串
    visa_types = Column(String, nullable=False)         # JSON 字符串数组
    enabled = Column(Boolean, nullable=False, default=True)
    display_order = Column(Integer, nullable=False, default=0)
    image_url = Column(String(512), nullable=True)
    # Atlys-style cards (W28): price / validity / processing time
    visa_fee_usd = Column(Integer, nullable=True, comment="Price in USD cents — display only, billing via Stripe")
    valid_days = Column(Integer, nullable=True, comment="Visa validity in days (e.g. 730 = 2 years)")
    process_days = Column(Integer, nullable=True, comment="Typical processing days — used to compute ETA timestamp")
    created_at = Column(DateTime, nullable=False, server_default=func.now())