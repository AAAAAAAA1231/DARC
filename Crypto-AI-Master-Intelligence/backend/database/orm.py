"""ORM tables for the closed-loop intelligence system."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, Boolean, DateTime, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.parsing import utcnow
from backend.database.session import Base


def _now() -> datetime:
    return utcnow()


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    dedup_key: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(256))
    chain: Mapped[str | None] = mapped_column(String(64), nullable=True)
    contract: Mapped[str | None] = mapped_column(String(128), nullable=True)
    website: Mapped[str | None] = mapped_column(String(512), nullable=True)
    twitter: Mapped[str | None] = mapped_column(String(256), nullable=True)
    symbol: Mapped[str | None] = mapped_column(String(64), nullable=True)
    narrative: Mapped[str | None] = mapped_column(String(64), nullable=True)
    identity_kind: Mapped[str] = mapped_column(String(32), default="chain_contract")
    status: Mapped[str] = mapped_column(String(32), default="PENDING", index=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)
    last_score: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    last_security: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_signal: Mapped[str | None] = mapped_column(String(32), nullable=True)
    hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    extra: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class ProjectSource(Base):
    __tablename__ = "project_sources"
    __table_args__ = (UniqueConstraint("project_id", "module", name="uq_project_source"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[str] = mapped_column(String(160), index=True)
    module: Mapped[str] = mapped_column(String(32), index=True)
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class ProjectStatusHistory(Base):
    __tablename__ = "project_status_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[str] = mapped_column(String(160), index=True)
    from_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_status: Mapped[str] = mapped_column(String(32))
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor: Mapped[str] = mapped_column(String(32), default="user")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ProjectNote(Base):
    __tablename__ = "project_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[str] = mapped_column(String(160), index=True)
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ScoreHistory(Base):
    __tablename__ = "score_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[str] = mapped_column(String(160), index=True)
    module: Mapped[str] = mapped_column(String(32), index=True)
    model_version: Mapped[str] = mapped_column(String(64), index=True)
    scores: Mapped[dict] = mapped_column(JSON)
    signal: Mapped[str | None] = mapped_column(String(32), nullable=True)
    explanation: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class SecurityScan(Base):
    __tablename__ = "security_scans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[str] = mapped_column(String(160), index=True)
    chain: Mapped[str | None] = mapped_column(String(64), nullable=True)
    contract: Mapped[str | None] = mapped_column(String(128), nullable=True)
    verdict: Mapped[str] = mapped_column(String(32), index=True)
    score: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    findings: Mapped[dict] = mapped_column(JSON)
    source: Mapped[str] = mapped_column(String(64))
    data_quality: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class CryptoAsset(Base):
    __tablename__ = "crypto_assets"
    __table_args__ = (UniqueConstraint("venue", "symbol", name="uq_asset_venue_symbol"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    venue: Mapped[str] = mapped_column(String(32))
    market_type: Mapped[str] = mapped_column(String(16))
    symbol: Mapped[str] = mapped_column(String(64), index=True)
    base: Mapped[str | None] = mapped_column(String(32), nullable=True)
    quote: Mapped[str | None] = mapped_column(String(32), nullable=True)
    extra: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class MarketData(Base):
    __tablename__ = "market_data"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    venue: Mapped[str] = mapped_column(String(32), index=True)
    symbol: Mapped[str] = mapped_column(String(64), index=True)
    interval: Mapped[str] = mapped_column(String(16))
    open_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    open: Mapped[Decimal] = mapped_column(Numeric(28, 12))
    high: Mapped[Decimal] = mapped_column(Numeric(28, 12))
    low: Mapped[Decimal] = mapped_column(Numeric(28, 12))
    close: Mapped[Decimal] = mapped_column(Numeric(28, 12))
    volume: Mapped[Decimal] = mapped_column(Numeric(28, 12))
    source: Mapped[str] = mapped_column(String(64))
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    data_quality: Mapped[str] = mapped_column(String(32), default="ok")


class CryptoMetric(Base):
    __tablename__ = "crypto_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    symbol: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(64))
    value: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    source: Mapped[str] = mapped_column(String(64))
    timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    confidence: Mapped[float] = mapped_column(Numeric(6, 4), default=0)
    data_quality: Mapped[str] = mapped_column(String(32), default="ok")


class BtcCycle(Base):
    __tablename__ = "btc_cycle"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    regime: Mapped[str] = mapped_column(String(32))
    phase: Mapped[str] = mapped_column(String(64))
    bull_score: Mapped[float] = mapped_column(Numeric(8, 4))
    bear_score: Mapped[float] = mapped_column(Numeric(8, 4))
    confidence: Mapped[float] = mapped_column(Numeric(6, 4))
    top_window: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    bottom_window: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    indicators: Mapped[dict] = mapped_column(JSON)
    missing_indicators: Mapped[dict] = mapped_column(JSON)
    source_status: Mapped[dict] = mapped_column(JSON)
    model_version: Mapped[str] = mapped_column(String(64))


class BtcCycleHistory(Base):
    __tablename__ = "btc_cycle_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    snapshot: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class FuturesPrediction(Base):
    __tablename__ = "futures_predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(64), index=True)
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    direction: Mapped[str] = mapped_column(String(16))
    confidence: Mapped[float] = mapped_column(Numeric(6, 4))
    current_price: Mapped[Decimal | None] = mapped_column(Numeric(28, 12), nullable=True)
    entry_zone: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    stop_loss: Mapped[Decimal | None] = mapped_column(Numeric(28, 12), nullable=True)
    take_profits: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    risk_reward: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    position_suggestion: Mapped[str | None] = mapped_column(Text, nullable=True)
    reasons: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    invalidation: Mapped[str | None] = mapped_column(Text, nullable=True)
    strategy_breakdown: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    model_version: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class SpotPrediction(Base):
    __tablename__ = "spot_predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    symbol: Mapped[str] = mapped_column(String(64), index=True)
    profile: Mapped[str] = mapped_column(String(32), default="BALANCED")
    current_price: Mapped[Decimal | None] = mapped_column(Numeric(28, 12), nullable=True)
    buy_zone: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    stop_loss: Mapped[Decimal | None] = mapped_column(Numeric(28, 12), nullable=True)
    take_profits: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    position_suggestion: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk: Mapped[str | None] = mapped_column(String(32), nullable=True)
    holding_period: Mapped[str | None] = mapped_column(String(64), nullable=True)
    score: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Numeric(6, 4), nullable=True)
    reasons: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    model_version: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class AirdropProject(Base):
    __tablename__ = "airdrop_projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[str] = mapped_column(String(160), index=True)
    chain: Mapped[str | None] = mapped_column(String(64), nullable=True)
    funding: Mapped[str] = mapped_column(String(64), default="UNKNOWN")
    estimated_valuation: Mapped[str] = mapped_column(String(64), default="UNKNOWN")
    participation_cost: Mapped[str] = mapped_column(String(64), default="UNKNOWN")
    expected_value_range: Mapped[str] = mapped_column(String(64), default="UNKNOWN")
    expected_roi: Mapped[str] = mapped_column(String(64), default="UNKNOWN")
    risk: Mapped[str] = mapped_column(String(32), default="UNKNOWN")
    difficulty: Mapped[str] = mapped_column(String(32), default="UNKNOWN")
    time_cost: Mapped[str] = mapped_column(String(64), default="UNKNOWN")
    recommended: Mapped[bool] = mapped_column(Boolean, default=False)
    fields: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class LaunchProject(Base):
    __tablename__ = "launch_projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[str] = mapped_column(String(160), index=True)
    launch_class: Mapped[str] = mapped_column(String(8), default="C")
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    fields: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class FootballMatch(Base):
    __tablename__ = "football_matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    competition: Mapped[str] = mapped_column(String(64), index=True)
    home: Mapped[str] = mapped_column(String(128))
    away: Mapped[str] = mapped_column(String(128))
    kickoff: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="SCHEDULED")
    home_goals: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_goals: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    data_quality: Mapped[str] = mapped_column(String(32), default="ok")


class FootballPrediction(Base):
    __tablename__ = "football_predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    match_external_id: Mapped[str] = mapped_column(String(64), index=True)
    home_win: Mapped[float] = mapped_column(Numeric(8, 6))
    draw: Mapped[float] = mapped_column(Numeric(8, 6))
    away_win: Mapped[float] = mapped_column(Numeric(8, 6))
    over_25: Mapped[float | None] = mapped_column(Numeric(8, 6), nullable=True)
    under_25: Mapped[float | None] = mapped_column(Numeric(8, 6), nullable=True)
    btts: Mapped[float | None] = mapped_column(Numeric(8, 6), nullable=True)
    top_scorelines: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    confidence: Mapped[float] = mapped_column(Numeric(6, 4))
    model_version: Mapped[str] = mapped_column(String(64))
    explanation: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class FootballBet(Base):
    __tablename__ = "football_bets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    match_external_id: Mapped[str] = mapped_column(String(64), index=True)
    prediction_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tracked: Mapped[bool] = mapped_column(Boolean, default=True)
    user_placed_bet: Mapped[bool] = mapped_column(Boolean, default=False)
    market: Mapped[str | None] = mapped_column(String(64), nullable=True)
    selection: Mapped[str | None] = mapped_column(String(64), nullable=True)
    stake: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    odds: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    result: Mapped[str | None] = mapped_column(String(32), nullable=True)
    payout: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    profit: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class LotteryResult(Base):
    __tablename__ = "lottery_results"
    __table_args__ = (UniqueConstraint("game", "issue", name="uq_lottery_issue"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game: Mapped[str] = mapped_column(String(32), index=True)
    issue: Mapped[str] = mapped_column(String(32), index=True)
    draw_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    numbers: Mapped[dict] = mapped_column(JSON)
    source: Mapped[str] = mapped_column(String(64))
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    data_quality: Mapped[str] = mapped_column(String(32), default="ok")


class LotteryPrediction(Base):
    __tablename__ = "lottery_predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game: Mapped[str] = mapped_column(String(32), index=True)
    combinations: Mapped[dict] = mapped_column(JSON)
    frequencies: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    coverage: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    risk: Mapped[str] = mapped_column(String(32))
    disclaimer: Mapped[str] = mapped_column(Text)
    model_version: Mapped[str] = mapped_column(String(64))
    simulation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class PortfolioPosition(Base):
    __tablename__ = "portfolio_positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    module: Mapped[str] = mapped_column(String(32), index=True)
    symbol: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), default="OPEN", index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(28, 12), default=0)
    avg_cost: Mapped[Decimal] = mapped_column(Numeric(28, 12), default=0)
    invested: Mapped[Decimal] = mapped_column(Numeric(28, 12), default=0)
    fees: Mapped[Decimal] = mapped_column(Numeric(28, 12), default=0)
    realized_pnl: Mapped[Decimal] = mapped_column(Numeric(28, 12), default=0)
    venue: Mapped[str | None] = mapped_column(String(64), nullable=True)
    wallet: Mapped[str | None] = mapped_column(String(128), nullable=True)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    original_model_score: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    original_model_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class PortfolioTransaction(Base):
    __tablename__ = "portfolio_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    position_id: Mapped[int] = mapped_column(Integer, index=True)
    side: Mapped[str] = mapped_column(String(16))
    quantity: Mapped[Decimal] = mapped_column(Numeric(28, 12))
    price: Mapped[Decimal] = mapped_column(Numeric(28, 12))
    fee: Mapped[Decimal] = mapped_column(Numeric(28, 12), default=0)
    funding_fee: Mapped[Decimal] = mapped_column(Numeric(28, 12), default=0)
    gas: Mapped[Decimal] = mapped_column(Numeric(28, 12), default=0)
    slippage: Mapped[Decimal] = mapped_column(Numeric(28, 12), default=0)
    other_cost: Mapped[Decimal] = mapped_column(Numeric(28, 12), default=0)
    venue: Mapped[str | None] = mapped_column(String(64), nullable=True)
    wallet: Mapped[str | None] = mapped_column(String(128), nullable=True)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class ModelVersion(Base):
    __tablename__ = "model_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    module: Mapped[str] = mapped_column(String(32), index=True)
    parameters: Mapped[dict] = mapped_column(JSON)
    dataset: Mapped[str | None] = mapped_column(String(256), nullable=True)
    backtest: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    performance: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    parent_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    active: Mapped[bool] = mapped_column(Boolean, default=False)


class ModelWeight(Base):
    __tablename__ = "model_weights"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version: Mapped[str] = mapped_column(String(64), index=True)
    strategy: Mapped[str] = mapped_column(String(64))
    weight: Mapped[float] = mapped_column(Numeric(8, 6))
    min_weight: Mapped[float] = mapped_column(Numeric(8, 6), default=0.02)
    max_weight: Mapped[float] = mapped_column(Numeric(8, 6), default=0.25)
    extras: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class ModelPerformance(Base):
    __tablename__ = "model_performance"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version: Mapped[str] = mapped_column(String(64), index=True)
    module: Mapped[str] = mapped_column(String(32), index=True)
    metrics: Mapped[dict] = mapped_column(JSON)
    sample_size: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class PredictionRecord(Base):
    __tablename__ = "prediction_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    module: Mapped[str] = mapped_column(String(32), index=True)
    subject: Mapped[str] = mapped_column(String(128), index=True)
    model_version: Mapped[str] = mapped_column(String(64), index=True)
    predicted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    direction: Mapped[str | None] = mapped_column(String(16), nullable=True)
    predicted_price: Mapped[Decimal | None] = mapped_column(Numeric(28, 12), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Numeric(6, 4), nullable=True)
    entry: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    stop_loss: Mapped[Decimal | None] = mapped_column(Numeric(28, 12), nullable=True)
    take_profits: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    actual_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    outcome: Mapped[str | None] = mapped_column(String(32), nullable=True)
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SimulationJob(Base):
    __tablename__ = "simulation_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    simulation_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    kind: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="QUEUED", index=True)
    paths: Mapped[int] = mapped_column(Integer)
    completed_paths: Mapped[int] = mapped_column(Integer, default=0)
    dataset: Mapped[str | None] = mapped_column(String(256), nullable=True)
    parameters: Mapped[dict] = mapped_column(JSON)
    model_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    strategy_weights: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    results: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    confidence_interval: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    progress: Mapped[float] = mapped_column(Numeric(6, 4), default=0)
    speed: Mapped[float | None] = mapped_column(Numeric(16, 2), nullable=True)
    eta_sec: Mapped[float | None] = mapped_column(Numeric(16, 2), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class SimulationResult(Base):
    __tablename__ = "simulation_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    simulation_id: Mapped[str] = mapped_column(String(64), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class DataSourceState(Base):
    __tablename__ = "data_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    status: Mapped[str] = mapped_column(String(32))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(256))
    body: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    channel: Mapped[str] = mapped_column(String(32), default="in_app")
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class SystemLog(Base):
    __tablename__ = "system_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    level: Mapped[str] = mapped_column(String(16), index=True)
    logger: Mapped[str] = mapped_column(String(64))
    event: Mapped[str] = mapped_column(String(128))
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class UserAction(Base):
    __tablename__ = "user_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class MajorChangeAlert(Base):
    __tablename__ = "major_change_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[str] = mapped_column(String(160), index=True)
    change_type: Mapped[str] = mapped_column(String(64))
    detail: Mapped[dict] = mapped_column(JSON)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    resolution: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ModelReview(Base):
    __tablename__ = "model_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version: Mapped[str] = mapped_column(String(64), index=True)
    module: Mapped[str] = mapped_column(String(32))
    summary: Mapped[dict] = mapped_column(JSON)
    strategy_breakdown: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
