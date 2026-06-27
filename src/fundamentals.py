from dataclasses import dataclass
from src.jquants import FinancialStatement


@dataclass
class FundamentalResult:
    code: str             # "3038"
    symbol: str           # "3038.T"
    name: str
    revenue_growth_pct: float   # 直近期の売上高YoY成長率(%)
    net_income_growth_pct: float


def calc_yoy_growth(current: float | None, previous: float | None) -> float | None:
    """前年比成長率(%)を返す。計算不能な場合はNone。"""
    if current is None or previous is None or previous == 0:
        return None
    return (current - previous) / abs(previous) * 100


def passes_growth_filter(
    stmts: list[FinancialStatement],
    min_yoy_pct: float,
    consecutive_periods: int,
    require_positive_cf: bool,
) -> FundamentalResult | None:
    """
    財務諸表リストが成長フィルタを通過するか判定する。
    通過した場合は FundamentalResult を返し、不通過は None を返す。
    stmts は period 昇順でソート済みであること。
    """
    # 有効な通期データのみ抽出（売上高と純利益がある期）
    valid = [s for s in stmts if s.net_sales is not None and s.net_income is not None]
    if len(valid) < consecutive_periods + 1:
        return None

    # 直近 consecutive_periods 期分のYoY成長率を確認
    recent = valid[-(consecutive_periods + 1):]  # +1は比較用の前期分
    for i in range(1, len(recent)):
        rev_growth = calc_yoy_growth(recent[i].net_sales, recent[i - 1].net_sales)
        inc_growth = calc_yoy_growth(recent[i].net_income, recent[i - 1].net_income)

        if rev_growth is None or rev_growth < min_yoy_pct:
            return None
        if inc_growth is None or inc_growth < min_yoy_pct:
            return None
        if require_positive_cf and recent[i].operating_cf is not None and recent[i].operating_cf <= 0:
            return None

    latest = recent[-1]
    prev    = recent[-2]
    return FundamentalResult(
        code=valid[0].code,
        symbol=f"{valid[0].code}.T",
        name="",
        revenue_growth_pct=calc_yoy_growth(latest.net_sales, prev.net_sales) or 0.0,
        net_income_growth_pct=calc_yoy_growth(latest.net_income, prev.net_income) or 0.0,
    )


def filter_by_fundamentals(
    statements: dict[str, list[FinancialStatement]],
    names: dict[str, str],
    min_revenue_yoy_pct: float,
    min_income_yoy_pct: float,
    consecutive_periods: int,
    require_positive_cf: bool,
) -> list[FundamentalResult]:
    """全銘柄の財務データから業績フィルタを通過した銘柄リストを返す。"""
    results = []
    for code, stmts in statements.items():
        result = passes_growth_filter(
            stmts,
            min_yoy_pct=min(min_revenue_yoy_pct, min_income_yoy_pct),
            consecutive_periods=consecutive_periods,
            require_positive_cf=require_positive_cf,
        )
        if result is None:
            continue
        if result.revenue_growth_pct < min_revenue_yoy_pct:
            continue
        if result.net_income_growth_pct < min_income_yoy_pct:
            continue
        result.name = names.get(code, "")
        results.append(result)
    return results
