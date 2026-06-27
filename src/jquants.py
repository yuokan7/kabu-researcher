import os
import time
import requests
from dataclasses import dataclass


_BASE = "https://api.jquants.com/v2"

_MARKET_CODE = {
    "プライム":    "0111",
    "スタンダード": "0121",
    "グロース":    "0131",
}


@dataclass
class StockInfo:
    code: str     # "3038"
    symbol: str   # "3038.T"
    name: str
    market: str


@dataclass
class FinancialStatement:
    code: str
    period: str          # "2024-03" など
    net_sales: float | None
    net_income: float | None
    operating_cf: float | None


def _headers(api_key: str) -> dict[str, str]:
    return {"x-api-key": api_key}


def get_id_token(email: str, password: str) -> str:
    """後方互換性のためのラッパー。V2ではAPIキーを直接使うため、
    環境変数 JQUANTS_API_KEY を返す。email/passwordは使用しない。"""
    api_key = os.environ.get("JQUANTS_API_KEY", "")
    if not api_key:
        raise ValueError(
            "J-Quants V2 ではAPIキー方式を使用します。"
            "環境変数 JQUANTS_API_KEY を設定してください。"
        )
    return api_key


def get_listed_stocks(id_token: str, markets: list[str]) -> list[StockInfo]:
    """全上場銘柄リストを取得し、対象市場のみ返す。"""
    r = requests.get(
        f"{_BASE}/equities/master",
        headers=_headers(id_token),
        timeout=30,
    )
    r.raise_for_status()

    target = {_MARKET_CODE[m] for m in markets if m in _MARKET_CODE}
    stocks = []
    for item in r.json().get("data", []):
        if item.get("Mkt") not in target:
            continue
        code = item["Code"]
        if len(code) == 5:
            code = code[:4]  # 5桁→4桁
        stocks.append(StockInfo(
            code=code,
            symbol=f"{code}.T",
            name=item.get("CoName", ""),
            market=item.get("MktNm", ""),
        ))
    return stocks


def get_statements_for_code(id_token: str, code: str) -> list[FinancialStatement]:
    """特定銘柄の財務諸表（通期のみ）を取得する。"""
    r = requests.get(
        f"{_BASE}/fins/summary",
        headers=_headers(id_token),
        params={"code": code},
        timeout=30,
    )
    if r.status_code != 200:
        return []

    def _f(v) -> float | None:
        try:
            return float(v) if v not in (None, "", "－", "-") else None
        except (ValueError, TypeError):
            return None

    results = []
    for item in r.json().get("data", []):
        # 通期（FY）のみ対象
        if item.get("CurPerType") != "FY":
            continue
        # 期末日から年月を取得
        period_end = item.get("CurPerEn", item.get("DiscDate", ""))
        period = period_end[:7] if period_end else ""
        results.append(FinancialStatement(
            code=code,
            period=period,
            net_sales=_f(item.get("Sales")),
            net_income=_f(item.get("Profit")),
            operating_cf=_f(item.get("CFO")),
        ))
    return sorted(results, key=lambda s: s.period)


def get_all_statements(
    id_token: str,
    codes: list[str],
    delay_sec: float = 0.3,
) -> dict[str, list[FinancialStatement]]:
    """複数銘柄の財務諸表を一括取得する（レート制限対策のdelay付き）。"""
    result: dict[str, list[FinancialStatement]] = {}
    for i, code in enumerate(codes):
        if i > 0 and i % 100 == 0:
            print(f"  財務データ取得中... {i}/{len(codes)}")
        result[code] = get_statements_for_code(id_token, code)
        time.sleep(delay_sec)
    return result
