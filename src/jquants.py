import os
import time
import requests
from dataclasses import dataclass
from datetime import date, timedelta


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


def get_id_token(_email: str = "", _password: str = "") -> str:
    """V2 APIキー方式のラッパー。引数は後方互換性のために残すが使用しない。
    環境変数 JQUANTS_API_KEY からAPIキーを読む。"""
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


def _parse_statements(data: list[dict]) -> list[FinancialStatement]:
    """APIレスポンスのリストから FinancialStatement のリストを生成する。

    J-Quants V2 /fins/summary のフィールド:
      Sales=売上高(実績), NP=当期純利益(実績), CFO=営業CF(実績)
      FSales/FNP=予想値（EarnForecastRevision等）
    Salesが空のレコード（予想修正等）はスキップして実績のみを使う。
    """
    def _f(v) -> float | None:
        try:
            return float(v) if v not in (None, "", "－", "-") else None
        except (ValueError, TypeError):
            return None

    results = []
    for item in data:
        if item.get("CurPerType") != "FY":
            continue
        net_sales = _f(item.get("Sales"))
        if net_sales is None:
            continue  # 予想修正レコードはSalesが空 → スキップ
        code = item.get("LocalCode", item.get("Code", ""))
        if len(code) == 5:
            code = code[:4]
        period_end = item.get("CurPerEn", item.get("DiscDate", ""))
        period = period_end[:7] if period_end else ""
        results.append(FinancialStatement(
            code=code,
            period=period,
            net_sales=net_sales,
            net_income=_f(item.get("NP")),   # Profit → NP が正しいフィールド名
            operating_cf=_f(item.get("CFO")),
        ))
    return results


def _earnings_season_dates(years_back: int = 4) -> list[str]:
    """
    決算発表が集中する月の全日程を返す（新しい順）。
    - 3月期決算 → 5月・6月に発表
    - 9月期決算 → 11月・12月に発表
    - 12月期決算 → 2月・3月に発表
    """
    from calendar import monthrange

    today = date.today()
    dates: set[str] = set()

    for yr_offset in range(years_back + 1):
        yr = today.year - yr_offset
        for month in [2, 3, 5, 6, 11, 12]:
            _, n_days = monthrange(yr, month)
            for day in range(1, n_days + 1):
                d = date(yr, month, day)
                if d <= today:
                    dates.add(d.strftime("%Y-%m-%d"))

    return sorted(dates, reverse=True)  # 新しい順


def get_all_names(id_token: str) -> dict[str, str]:
    """全市場の銘柄コード→日本語名の辞書を返す（市場フィルタなし）。"""
    r = requests.get(f"{_BASE}/equities/master", headers=_headers(id_token), timeout=30)
    if r.status_code != 200:
        return {}
    result = {}
    for item in r.json().get("data", []):
        code = item.get("Code", "")
        if len(code) == 5:
            code = code[:4]
        result[code] = item.get("CoName", "")
    return result


def get_all_statements_bulk(
    id_token: str,
    lookback_months: int = 36,   # 後方互換のため引数は残すが未使用
    delay_sec: float = 0.5,
) -> dict[str, list[FinancialStatement]]:
    """
    決算発表シーズン（5・6・11・12・2・3月）の毎日を指定して
    全銘柄の通期財務諸表を取得する。
    約720 APIコール（4年分）、delay 0.5s で約6分。
    """
    result: dict[str, list[FinancialStatement]] = {}
    target_dates = _earnings_season_dates(years_back=4)
    total = len(target_dates)

    for i, date_str in enumerate(target_dates):
        if i > 0 and i % 120 == 0:
            print(f"  財務データ取得中... {i}/{total}日 ({len(result)}銘柄)")

        for attempt in range(3):
            r = requests.get(
                f"{_BASE}/fins/summary",
                headers=_headers(id_token),
                params={"date": date_str},
                timeout=30,
            )
            if r.status_code == 429:
                wait = 2 ** attempt * 5
                print(f"  [WARN] {date_str}: HTTP 429 — {wait}s待機")
                time.sleep(wait)
                continue
            if r.status_code == 200:
                stmts = _parse_statements(r.json().get("data", []))
                for stmt in stmts:
                    if stmt.code not in result:
                        result[stmt.code] = []
                    result[stmt.code].append(stmt)
            break

        time.sleep(delay_sec)

    # period 昇順ソート + 重複除去
    for code in result:
        seen: set[str] = set()
        deduped = []
        for stmt in sorted(result[code], key=lambda s: s.period):
            if stmt.period not in seen:
                seen.add(stmt.period)
                deduped.append(stmt)
        result[code] = deduped

    return result


def get_all_statements(
    id_token: str,
    codes: list[str],
    delay_sec: float = 0.5,
) -> dict[str, list[FinancialStatement]]:
    return get_all_statements_bulk(id_token)
