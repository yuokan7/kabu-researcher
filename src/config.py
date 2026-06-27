from pathlib import Path
from typing import Any
import yaml
from pydantic import BaseModel, Field, ConfigDict


class MarketTriggerConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    index_symbol: str
    threshold_pct: float
    fresh_touch_min_days: int
    entry_on_first_touch: bool = True


class CalibrationConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    lookback_years: int = 10
    method: str = "percentile"
    percentile: float = 3
    target_touch_count_min: int = 10
    target_touch_count_max: int = 20
    fallback_threshold_pct: float = -10


class IndividualTriggerConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    mode: str = "calibrated"
    fixed_threshold_pct: float = -10
    calibration: CalibrationConfig = Field(default_factory=CalibrationConfig)


class RankingConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    sort_by: list[str] = ["individual_deviation_depth", "net_income_growth"]
    sector_relative: bool = False


class TriggerConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    deviation_window: int = 25
    market: MarketTriggerConfig
    individual: IndividualTriggerConfig = Field(default_factory=IndividualTriggerConfig)
    ranking: RankingConfig = Field(default_factory=RankingConfig)


class OutputConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    format: list[str] = ["csv", "console"]
    csv_path: str = "./out/candidates.csv"
    pool_path: str = "./out/pool.csv"
    notify_webhook: str | None = None


class DataSourcesConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    fundamentals: str = "jquants"
    universe_prices: str = "jquants"
    trigger_prices: str = "yfinance"
    cache_db: str = "./data/cache.duckdb"


class DashboardConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    warning_deviation_pct: float = -7
    danger_deviation_pct: float = -10
    price_lookback_days: int = 60
    cache_ttl_minutes: int = 60
    fresh_touch_highlight_days: int = 90


class ScreenerConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    trigger: TriggerConfig
    output: OutputConfig
    data_sources: DataSourcesConfig = Field(default_factory=DataSourcesConfig)
    dashboard: DashboardConfig = Field(default_factory=DashboardConfig)


def load_config(path: Path | str = "conditions.yaml") -> ScreenerConfig:
    with open(path, encoding="utf-8") as f:
        raw: dict[str, Any] = yaml.safe_load(f)
    return ScreenerConfig.model_validate(raw)
