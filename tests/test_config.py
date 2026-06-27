import pytest
from pathlib import Path
from src.config import load_config, ScreenerConfig

YAML_PATH = Path(__file__).parent.parent / "conditions.yaml"


def test_load_config_returns_screener_config():
    cfg = load_config(YAML_PATH)
    assert isinstance(cfg, ScreenerConfig)


def test_trigger_market_threshold():
    cfg = load_config(YAML_PATH)
    assert cfg.trigger.market.threshold_pct == -10


def test_trigger_fresh_touch_days():
    cfg = load_config(YAML_PATH)
    assert cfg.trigger.market.fresh_touch_min_days == 90


def test_trigger_index_symbol():
    cfg = load_config(YAML_PATH)
    assert cfg.trigger.market.index_symbol == "^N225"


def test_output_formats():
    cfg = load_config(YAML_PATH)
    assert "csv" in cfg.output.format
    assert "console" in cfg.output.format


def test_dashboard_config_warning_deviation():
    cfg = load_config(YAML_PATH)
    assert cfg.dashboard.warning_deviation_pct == -7


def test_dashboard_config_danger_deviation():
    cfg = load_config(YAML_PATH)
    assert cfg.dashboard.danger_deviation_pct == -10


def test_dashboard_config_cache_ttl():
    cfg = load_config(YAML_PATH)
    assert cfg.dashboard.cache_ttl_minutes == 60
