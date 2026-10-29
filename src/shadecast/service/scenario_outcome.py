"""What a scenario buys on its tile against doing nothing, and which model answered."""

from __future__ import annotations

from pydantic import BaseModel


class ScenarioOutcome(BaseModel):
    city: str
    tile: str
    model_id: str
    kind: str
    arrangement: str
    coverage: float  # share of the feasible ground planted
    tile_fraction: float  # share of the whole tile planted, comparable with a stored design
    trees: int
    cost_usd: float
    unit_cost: float  # USD per square metre the cost was priced at
    maintenance: float  # yearly maintenance share of capital the cost was priced at
    threshold: float  # mean radiant temperature in C the exposed people and degree-hours were counted above
    baseline_exposure: float
    baseline_at_risk: int
    exposure_drop: float
    excess_removed: float
    people: int
    equity_gap_change: float
    efficiency: float
    surrogate_seconds: float
