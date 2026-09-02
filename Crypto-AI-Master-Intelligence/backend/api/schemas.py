from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class StatusUpdate(BaseModel):
    status: str
    reason: str | None = None


class NoteIn(BaseModel):
    body: str


class FillIn(BaseModel):
    module: str
    symbol: str
    side: str
    quantity: Decimal
    price: Decimal
    fee: Decimal = Decimal("0")
    funding_fee: Decimal = Decimal("0")
    gas: Decimal = Decimal("0")
    slippage: Decimal = Decimal("0")
    other_cost: Decimal = Decimal("0")
    venue: str | None = None
    wallet: str | None = None
    executed_at: datetime | None = None
    project_id: str | None = None
    note: str | None = None
    original_model_score: float | None = None
    original_model_version: str | None = None


class FootballTrackIn(BaseModel):
    match_external_id: str
    user_placed_bet: bool = False
    market: str | None = None
    selection: str | None = None
    stake: Decimal | None = None
    odds: Decimal | None = None


class SimulationIn(BaseModel):
    kind: str = Field(pattern="^(gbm|lottery)$")
    paths: int = 1_000_000
    parameters: dict = Field(default_factory=dict)


class RollbackIn(BaseModel):
    module: str
    version: str


class AlertResolveIn(BaseModel):
    resolution: str
