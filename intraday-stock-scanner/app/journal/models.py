from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Asset(Base):
    __tablename__ = "assets"
    symbol: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    asset_type: Mapped[str] = mapped_column(String)
    sector: Mapped[str | None] = mapped_column(String, nullable=True)
    industry: Mapped[str | None] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime)


class DailyStat(Base):
    __tablename__ = "daily_stats"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String, index=True)
    date: Mapped[date] = mapped_column(Date)
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[float] = mapped_column(Float)
    dollar_volume: Mapped[float] = mapped_column(Float)
    atr20_pct: Mapped[float] = mapped_column(Float)
    avg_dollar_volume_20d: Mapped[float] = mapped_column(Float)


class WatchlistSnapshot(Base):
    __tablename__ = "watchlist_snapshots"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scan_date: Mapped[date] = mapped_column(Date, index=True)
    symbol: Mapped[str] = mapped_column(String, index=True)
    pms_score: Mapped[float] = mapped_column(Float)
    pms_rank: Mapped[int] = mapped_column(Integer)
    gap_pct: Mapped[float] = mapped_column(Float)
    pm_dollar_vol: Mapped[float] = mapped_column(Float)
    catalyst_score: Mapped[float] = mapped_column(Float)
    selected_flag: Mapped[bool] = mapped_column(Boolean, default=True)


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime, index=True)
    symbol: Mapped[str] = mapped_column(String, index=True)
    side: Mapped[str] = mapped_column(String)
    setup: Mapped[str] = mapped_column(String)
    score: Mapped[float] = mapped_column(Float)
    grade: Mapped[str] = mapped_column(String)
    entry_low: Mapped[float] = mapped_column(Float)
    entry_high: Mapped[float] = mapped_column(Float)
    stop: Mapped[float] = mapped_column(Float)
    tp1: Mapped[float] = mapped_column(Float)
    tp2: Mapped[float] = mapped_column(Float)
    risk_pct: Mapped[float] = mapped_column(Float)
    rr_tp1: Mapped[float] = mapped_column(Float)
    rr_tp2: Mapped[float] = mapped_column(Float)
    invalidate_if: Mapped[str] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(Text)
    market_regime: Mapped[str | None] = mapped_column(String, nullable=True)
    raw_metrics_json: Mapped[str] = mapped_column(Text)


class AlertOutcome(Base):
    __tablename__ = "alert_outcomes"
    alert_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    horizon_5m_ret: Mapped[float] = mapped_column(Float)
    horizon_10m_ret: Mapped[float] = mapped_column(Float)
    horizon_20m_ret: Mapped[float] = mapped_column(Float)
    horizon_30m_ret: Mapped[float] = mapped_column(Float)
    hit_tp1_first: Mapped[bool] = mapped_column(Boolean)
    hit_tp2_first: Mapped[bool] = mapped_column(Boolean)
    hit_sl_first: Mapped[bool] = mapped_column(Boolean)
    mfe_pct: Mapped[float] = mapped_column(Float)
    mae_pct: Mapped[float] = mapped_column(Float)
    closed_label: Mapped[str] = mapped_column(String)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime)


class FilterRejection(Base):
    __tablename__ = "filter_rejections"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime)
    symbol: Mapped[str] = mapped_column(String, index=True)
    setup: Mapped[str] = mapped_column(String)
    reason: Mapped[str] = mapped_column(Text)
    metrics_json: Mapped[str] = mapped_column(Text)
