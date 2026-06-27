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
    """APIレスポンスのリストから FinancialStatement のリストを生成する。"""
    def _f(v) -> float | None:
        try:
            return float(v) if v not in (None, "", "－", "-") else None
        except (ValueError, TypeError):
            return None

    results = []
    for item in data:
        if item.get("CurPerType") != "FY":
            continue
        code = item.get("LocalCode", item.get("Code", ""))
        if len(code) == 5:
            code = code[:4]
        period_end = item.get("CurPerEn", item.get("DiscDate", ""))
        period = period_end[:7] if period_end else ""
        results.append(FinancialStatement(
            code=code,
            period=period,
            net_sales=_f(item.get("Sales")),
            net_income=_f(item.get("Profit")),
            operating_cf=_f(item.get("CFO")),
        ))
    return results


def get_all_statements_bulk(
    id_token: str,
    lookback_months: int = 36,
    delay_sec: float = 1.0,
) -> dict[str, list[FinancialStatement]]:
    """
    日付ベースで全銘柄の財務諸表を一括取得する。
    1銘柄ずつ叩く代わりに、開示日ベースでまとめて取得するため
    APIコール数が大幅に削減される（4000回 → 約36回）。
    """
    result: dict[str, list[FinancialStatement]] = {}

    # 過去 lookback_months ヶ月の月末日をイテレート
    today = date.today()
    check_date = today.replace(day=1) - timedelta(days=1)  # 先月末

    _debug_printed = False  # 最初の1件だけフィールド名をデバッグ出力

    for month_idx in range(lookback_months):
        date_str = check_date.strftime("%Y-%m-%d")

        for attempt in range(3):
            r = requests.get(
                f"{_BASE}/fins/summary",
                headers=_headers(id_token),
                params={"date": date_str},
                timeout=60,
            )
            if r.status_code == 429:
                wait = 2 ** attempt * 10
                print(f"  [WARN] {date_str}: HTTP 429 — {wait}s待機")
                time.sleep(wait)
                continue
            if r.status_code == 200:
                data = r.json().get("data", [])
                if not _debug_printed and data:
                    print(f"  [DEBUG] {date_str} サンプル1件のキー: {list(data[0].keys())}")
                    print(f"  [DEBUG] サンプルデータ: {data[0]}")
                    _debug_printed = True
                stmts = _parse_statements(data)
                for stmt in stmts:
                    if stmt.code not in result:
                        result[stmt.code] = []
                    result[stmt.code].append(stmt)
            break

        if month_idx > 0 and month_idx % 6 == 0:
            print(f"  財務データ取得中... {month_idx}/{lookback_months}ヶ月")

        # 前月末へ
        check_date = check_date.replace(day=1) - timedelta(days=1)
        time.sleep(delay_sec)

    # 各銘柄の statements を period 昇順にソートして重複除去
    for code in result:
        seen = set()
        deduped = []
        for stmt in sorted(result[code], key=lambda s: s.period):
            if stmt.period not in seen:
                seen.add(stmt.period)
                deduped.append(stmt)
        result[code] = deduped

    return result


# 後方互換性のため旧関数も残す（直接呼び出しは非推奨）
def get_all_statements(
    id_token: str,
    codes: list[str],
    delay_sec: float = 1.0,
) -> dict[str, list[FinancialStatement]]:
    """非推奨: get_all_statements_bulk を使うこと。"""
    return get_all_statements_bulk(id_token, lookback_months=36, delay_sec=delay_sec)
