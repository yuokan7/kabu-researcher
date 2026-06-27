from src.jquants import FinancialStatement
from src.fundamentals import (
    calc_yoy_growth,
    passes_growth_filter,
    filter_by_fundamentals,
    FundamentalResult,
)


def _stmt(period: str, sales: float | None, income: float | None, ocf: float | None) -> FinancialStatement:
    return FinancialStatement(code="3038", period=period, net_sales=sales, net_income=income, operating_cf=ocf)


# --- calc_yoy_growth ---

def test_calc_yoy_growth_positive():
    assert calc_yoy_growth(120.0, 100.0) == 20.0

def test_calc_yoy_growth_zero_previous():
    assert calc_yoy_growth(100.0, 0.0) is None

def test_calc_yoy_growth_none_values():
    assert calc_yoy_growth(None, 100.0) is None
    assert calc_yoy_growth(100.0, None) is None


# --- passes_growth_filter ---

def test_passes_growth_filter_all_ok():
    stmts = [
        _stmt("2022", 100, 50, 80),
        _stmt("2023", 125, 65, 90),  # +25%, +30%
        _stmt("2024", 160, 85, 100), # +28%, +30%
        _stmt("2025", 200, 110, 120),# +25%, +29%
    ]
    result = passes_growth_filter(stmts, min_revenue_yoy_pct=20.0, min_income_yoy_pct=20.0, consecutive_periods=3, require_positive_cf=True)
    assert result is not None
    assert result.revenue_growth_pct >= 20.0

def test_passes_growth_filter_insufficient_growth():
    stmts = [
        _stmt("2022", 100, 50, 80),
        _stmt("2023", 110, 55, 90),  # +10% (不足)
        _stmt("2024", 125, 65, 100),
        _stmt("2025", 150, 80, 120),
    ]
    result = passes_growth_filter(stmts, min_revenue_yoy_pct=20.0, min_income_yoy_pct=20.0, consecutive_periods=3, require_positive_cf=True)
    assert result is None

def test_passes_growth_filter_negative_cf():
    stmts = [
        _stmt("2022", 100, 50, 80),
        _stmt("2023", 125, 65, -10),  # 営業CFマイナス
        _stmt("2024", 160, 85, 100),
        _stmt("2025", 200, 110, 120),
    ]
    result = passes_growth_filter(stmts, min_revenue_yoy_pct=20.0, min_income_yoy_pct=20.0, consecutive_periods=3, require_positive_cf=True)
    assert result is None

def test_passes_growth_filter_insufficient_periods():
    stmts = [
        _stmt("2024", 160, 85, 100),
        _stmt("2025", 200, 110, 120),
    ]
    result = passes_growth_filter(stmts, min_revenue_yoy_pct=20.0, min_income_yoy_pct=20.0, consecutive_periods=3, require_positive_cf=True)
    assert result is None


# --- filter_by_fundamentals ---

def test_filter_by_fundamentals_returns_passing_stocks():
    statements = {
        "3038": [
            _stmt("2022", 100, 50, 80),
            _stmt("2023", 125, 65, 90),
            _stmt("2024", 160, 85, 100),
            _stmt("2025", 200, 110, 120),
        ],
        "9999": [  # 成長率不足
            _stmt("2022", 100, 50, 80),
            _stmt("2023", 105, 52, 85),
            _stmt("2024", 110, 54, 90),
            _stmt("2025", 115, 56, 95),
        ],
    }
    names = {"3038": "神戸物産", "9999": "テスト会社"}
    results = filter_by_fundamentals(
        statements=statements,
        names=names,
        min_revenue_yoy_pct=20.0,
        min_income_yoy_pct=20.0,
        consecutive_periods=3,
        require_positive_cf=True,
    )
    codes = [r.symbol for r in results]
    assert "3038.T" in codes
    assert "9999.T" not in codes
