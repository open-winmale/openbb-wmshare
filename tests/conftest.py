"""Offline test scaffolding.

The fetchers need a client whose call signatures match ``wmshare.Client``'s
friendly API. ``wmshare.demo_client()`` looks similar but is narrower — for
example its ``kline.bars`` accepts no ``freq`` argument — so wrapping it
directly would make tests pass only because the production signature is never
exercised. ``FakeClient`` mirrors the real signatures and serves canned data
shaped exactly like live responses.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest

STATEMENT_PERIODS = ["2025", "2024", "2023"]

INCOME_ROWS = [
    {
        "k": "total_revenue",
        "cn": "营业收入",
        "vals": {
            "2025": 168_838_102_514.79,
            "2024": 170_899_152_276.34,
            "2023": 147_693_604_994.14,
        },
    },
    {
        "k": "operating_cost",
        "cn": "营业成本",
        "vals": {"2025": 20_000_000_000.0, "2024": 21_000_000_000.0, "2023": 19_000_000_000.0},
    },
    {
        "k": "operating_profit",
        "cn": "营业利润",
        "vals": {"2025": 120_000_000_000.0, "2024": 118_000_000_000.0, "2023": 100_000_000_000.0},
    },
    {
        "k": "total_profit",
        "cn": "利润总额",
        "vals": {"2025": 121_000_000_000.0, "2024": 119_000_000_000.0, "2023": 101_000_000_000.0},
    },
    {
        "k": "net_profit",
        "cn": "净利润",
        "vals": {"2025": 90_000_000_000.0, "2024": 88_000_000_000.0, "2023": 75_000_000_000.0},
    },
    {
        "k": "np_parent",
        "cn": "归母净利润",
        "vals": {"2025": 88_000_000_000.0, "2024": 86_000_000_000.0, "2023": 74_000_000_000.0},
    },
    {"k": "eps_basic", "cn": "基本每股收益", "vals": {"2025": 70.0, "2024": 68.0, "2023": 60.0}},
    {"k": "__gm", "cn": "毛利率(派生)", "vals": {"2025": 0.88, "2024": 0.87, "2023": 0.87}},
]

BALANCE_ROWS = [
    {
        "k": "total_assets",
        "cn": "资产总计",
        "vals": {"2025": 300_000_000_000.0, "2024": 270_000_000_000.0, "2023": 250_000_000_000.0},
    },
    {
        "k": "total_liabilities",
        "cn": "负债合计",
        "vals": {"2025": 60_000_000_000.0, "2024": 55_000_000_000.0, "2023": 50_000_000_000.0},
    },
    {
        "k": "total_equity",
        "cn": "所有者权益合计",
        "vals": {"2025": 240_000_000_000.0, "2024": 215_000_000_000.0, "2023": 200_000_000_000.0},
    },
    {
        "k": "total_parent_equity",
        "cn": "归母所有者权益",
        "vals": {"2025": 230_000_000_000.0, "2024": 205_000_000_000.0, "2023": 190_000_000_000.0},
    },
    {
        "k": "total_current_assets",
        "cn": "流动资产合计",
        "vals": {"2025": 200_000_000_000.0, "2024": 180_000_000_000.0, "2023": 170_000_000_000.0},
    },
    {
        "k": "total_current_liabilities",
        "cn": "流动负债合计",
        "vals": {"2025": 50_000_000_000.0, "2024": 45_000_000_000.0, "2023": 40_000_000_000.0},
    },
    {
        "k": "inventories",
        "cn": "存货",
        "vals": {"2025": 20_000_000_000.0, "2024": 18_000_000_000.0, "2023": 16_000_000_000.0},
    },
    {
        "k": "monetary_funds",
        "cn": "货币资金",
        "vals": {"2025": 100_000_000_000.0, "2024": 90_000_000_000.0, "2023": 80_000_000_000.0},
    },
    {
        "k": "accounts_receivable",
        "cn": "应收账款",
        "vals": {"2025": 5_000_000_000.0, "2024": 4_500_000_000.0, "2023": 4_000_000_000.0},
    },
]

CASHFLOW_ROWS = [
    {
        "k": "net_cash_operating",
        "cn": "经营活动现金流量净额",
        "vals": {"2025": 95_000_000_000.0, "2024": 90_000_000_000.0},
    },
    {
        "k": "net_cash_investing",
        "cn": "投资活动现金流量净额",
        "vals": {"2025": -15_000_000_000.0, "2024": -12_000_000_000.0},
    },
    {
        "k": "net_cash_financing",
        "cn": "筹资活动现金流量净额",
        "vals": {"2025": -40_000_000_000.0, "2024": -38_000_000_000.0},
    },
    {
        "k": "net_cash_increase",
        "cn": "现金净增加额",
        "vals": {"2025": 40_000_000_000.0, "2024": 40_000_000_000.0},
    },
    {
        "k": "cash_end",
        "cn": "期末现金余额",
        "vals": {"2025": 100_000_000_000.0, "2024": 60_000_000_000.0},
    },
]

STATEMENTS: dict[str, list[dict]] = {
    "fin.income_statement": INCOME_ROWS,
    "fin.balance_sheet": BALANCE_ROWS,
    "fin.cashflow_statement": CASHFLOW_ROWS,
}

DIVIDENDS = [
    {
        "announce": "2026-06-05",
        "ccy": "CNY",
        "content": "每10股派36.00元",
        "dps": 3.6,
        "ex_date": "2026-06-12",
        "ex_div": "2026-06-12",
        "net_profit": 0,
        "pay": "2026-06-20",
        "payout_ratio": 0.75,
        "sas": "2025:Q4",
        "total": 4_500_000_000.0,
    },
    {
        "announce": "2025-06-06",
        "ccy": "CNY",
        "content": "每10股派30.00元",
        "dps": 3.0,
        "ex_date": "2025-06-13",
        "ex_div": "2025-06-13",
        "net_profit": 0,
        "pay": "2025-06-20",
        "payout_ratio": 0.72,
        "sas": "2024:Q4",
        "total": 3_800_000_000.0,
    },
]

INDEX_KEYS = ["index.hs300", "index.csi500", "index.sz50", "index.shzs", "index.cybz"]

INDEX_MEMBERS = [
    {
        "symbol": "600519",
        "name": "贵州茅台",
        "mv": 1_740_176_092_672.05,
        "pe_ttm": 22.5,
        "pb": 8.1,
        "roe_ttm": 0.31,
    },
    {
        "symbol": "000001",
        "name": "平安银行",
        "mv": 225_884_887_824.72,
        "pe_ttm": 5.2,
        "pb": 0.55,
        "roe_ttm": 0.11,
    },
]

INDEX_WEIGHTS = [
    {"symbol": "600519", "weight": 0.071},
    {"symbol": "000001", "weight": 0.012},
]

SYMBOL_TABLE = {
    "cn": [
        {"code": "600519", "name": "贵州茅台", "pinyin": "guizhoumaotai", "abbr": "GZMT"},
        {"code": "000001", "name": "平安银行", "pinyin": "pinganyinhang", "abbr": "PAYH"},
    ],
    "hk": [{"code": "00700", "name": "腾讯控股", "pinyin": "tengxunkonggu", "abbr": "TXKG"}],
    "us": [{"code": "AAPL", "name": "Apple Inc", "pinyin": "", "abbr": "AAPL"}],
}


def _bars(n: int = 120, start: str = "2026-01-02") -> list[dict]:
    """Synthesise a deterministic ascending daily series."""
    from datetime import date, timedelta

    first = date.fromisoformat(start)
    bars = []
    price = 100.0
    for i in range(n):
        day = first + timedelta(days=i)
        if day.weekday() >= 5:
            continue
        price *= 1.001
        bars.append(
            {
                "date": day.isoformat(),
                "open": round(price * 0.998, 2),
                "high": round(price * 1.005, 2),
                "low": round(price * 0.995, 2),
                "close": round(price, 2),
                "volume": 1_000_000.0 + i,
                "amount": round((1_000_000.0 + i) * price, 2),
                "percent": 0.001,
                "sas": f"{day.year}:D{i:03d}",
            }
        )
    return bars


_FULL_SERIES = _bars(n=5000, start="2014-01-02")
"""One long series spanning every range the tests request (2014 → 2027)."""


class _Kline:
    """Mirror of ``wmshare.api.KlineApi``'s relevant surface."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def bars(
        self,
        symbol: str,
        n: int | None = None,
        adj: str | None = None,
        begin: str | None = None,
        end: str | None = None,
        freq: str | None = None,
        _raw: bool = False,
        _df: bool = False,
    ) -> list[dict]:
        self.calls.append({"symbol": symbol, "adj": adj, "begin": begin, "end": end, "freq": freq})
        series = [dict(bar) for bar in _FULL_SERIES]
        if begin:
            series = [b for b in series if b["date"] >= begin]
        if end:
            series = [b for b in series if b["date"] <= end]
        if n is not None:
            series = series[: int(n)]
        if adj:
            series = [{**b, "close": round(b["close"] * 0.5, 2)} for b in series]
        if freq:
            series = series[: max(1, len(series) // 5)]
        return series

    def index_live_many(self, keys: list[str]) -> dict[str, dict]:
        """Emulate ``kline.query_index_last_live_many``: canon-keyed snapshots.

        Live rows key by ``<nnnnnn>.INDEX`` and carry a decimal ``percent``
        (unlike index *bars*, where percent is a percentage number), no
        ``prev_close``, and ``turnover_rate``/``amplitude`` extras.
        """
        snaps: dict[str, dict] = {}
        for sym in keys:
            bars = [b for b in _FULL_SERIES if b["date"] >= "2026-10-01"]
            latest, previous = bars[-1], bars[-2]
            snaps[str(sym).upper()] = {
                "amount": latest["amount"],
                "amplitude": 0.0125,
                "asof": "2026-10-30 15:00:00",
                "change": round(latest["close"] - previous["close"], 4),
                "close": latest["close"],
                "date": latest["date"],
                "high": latest["high"],
                "low": latest["low"],
                "open": latest["open"],
                "percent": 0.001,
                "refreshed_at": "2026-10-30 15:00:30",
                "source": "tencent_index",
                "symbol": str(sym).upper(),
                "turnover_rate": 0.0097,
                "volume": latest["volume"],
            }
        return snaps

    def anchor_bars(self, symbol: str, limit: int | None, anchor_date: str | None) -> list[dict]:
        """Emulate ``kline.query_at_anchor`` for index bars.

        Real rows carry ``samplingTs`` epoch seconds and a *percentage number*
        in ``percent`` (``-0.78`` means -0.78%), which is the opposite of the
        equity convention — the fetcher normalises both.
        """
        series = [bar for bar in _FULL_SERIES if not anchor_date or bar["date"] <= anchor_date]
        series = sorted(series, key=lambda bar: bar["date"], reverse=True)
        count = int(limit or 500)
        page = series[:count]
        chronological = sorted(_FULL_SERIES, key=lambda bar: bar["date"])
        out: list[dict] = []
        for bar in page:
            earlier = [c for c in chronological if c["date"] < bar["date"]]
            prev = earlier[-1] if earlier else None
            pct = ((bar["close"] / prev["close"]) - 1) if prev and prev["close"] else 0.0
            stamp = int(dt.datetime.fromisoformat(bar["date"]).replace(tzinfo=dt.UTC).timestamp())
            out.append(
                {
                    "samplingTs": stamp,
                    "open": bar["open"],
                    "high": bar["high"],
                    "low": bar["low"],
                    "close": bar["close"],
                    "volume": bar["volume"],
                    "amount": bar["amount"],
                    # a percentage number, not a decimal
                    "percent": round(pct * 100, 4),
                    "prev_close": prev["close"] if prev else None,
                }
            )
        return out

    def snapshot(self, symbol: str) -> dict:
        bars = _FULL_SERIES
        latest, previous = bars[-1], bars[-2]
        change = (latest["close"] / previous["close"]) - 1
        return {
            "symbol": symbol,
            "name": "贵州茅台",
            "close": latest["close"],
            "percent": round(change, 6),
            "volume": latest["volume"],
            "amount": latest["amount"],
            "mv": 1_740_176_092_672.05,
            "mv_free": 1_740_176_092_672.05,
            "ma20": latest["close"] * 0.98,
            "ma60": latest["close"] * 0.96,
            "ma120": latest["close"] * 0.94,
            "chg_5d": 0.014,
            "chg_10d": 0.019,
            "chg_20d": 0.095,
            "chg_90d": 0.020,
            "roi_1y": 0.013,
            "kline_date": latest["date"],
            "industry": "industry.S34",
            "is_st": False,
            "is_suspend": False,
        }

    def live(self, symbol: str) -> dict:
        return self.snapshot(symbol)

    def batch_live(self, symbols: list[str]) -> dict:
        return {symbol: self.snapshot(symbol) for symbol in symbols}

    def min1(self, symbol: str) -> dict:
        return {"trading_day": "2026-10-30", "bars": [], "bar_n": 0}

    def is_etf(self, symbol: str) -> bool:
        return False


# hk/us rows via the unified cli.statements entry: same transposed shape as
# cn, but k holds the market's native subject names (camelCase). The provider
# maps them onto standard fields via camel->snake + market overrides.
MKT_STATEMENTS: dict[str, list[dict]] = {
    "income": [
        {
            "k": "totalOperatingRevenue",
            "cn": "totalOperatingRevenue",
            "vals": {"2026": 400_000_000_000.0, "2025": 385_000_000_000.0},
        },
        {
            "k": "grossProfit",
            "cn": "grossProfit",
            "vals": {"2026": 190_000_000_000.0, "2025": 180_000_000_000.0},
        },
        {
            "k": "parentNetProfit",
            "cn": "parentNetProfit",
            "vals": {"2026": 99_000_000_000.0, "2025": 95_000_000_000.0},
        },
        {"k": "basicEps", "cn": "basicEps", "vals": {"2026": 6.5, "2025": 6.1}},
    ],
    "balance": [
        {
            "k": "totalAsset",
            "cn": "totalAsset",
            "vals": {"2026": 350_000_000_000.0, "2025": 340_000_000_000.0},
        },
        {
            "k": "totalLiab",
            "cn": "totalLiab",
            "vals": {"2026": 200_000_000_000.0, "2025": 190_000_000_000.0},
        },
        {
            "k": "cashandCashEquivalents",
            "cn": "cashandCashEquivalents",
            "vals": {"2026": 60_000_000_000.0, "2025": 55_000_000_000.0},
        },
    ],
    "cashflow": [
        {
            "k": "netCashFlowfromOperatingActivities",
            "cn": "netCashFlowfromOperatingActivities",
            "vals": {"2026": 90_000_000_000.0, "2025": 85_000_000_000.0},
        },
        {
            "k": "endingCashandCashEquivalents",
            "cn": "endingCashandCashEquivalents",
            "vals": {"2026": 40_000_000_000.0, "2025": 37_000_000_000.0},
        },
    ],
}

_STATEMENT_DOMAINS = {
    "income": "fin.income_statement",
    "balance": "fin.balance_sheet",
    "cashflow": "fin.cashflow_statement",
}


class _Statements:
    """Mirror of ``wmshare.api.StatementsApi``'s used surface (cn + hk/us rows).

    Records the last call kwargs so contract tests can assert the period 二档
    threading without a live gateway.
    """

    last_kwargs: dict | None = None

    def _rows(self, symbol: str, kind: str) -> list[dict]:
        code = str(symbol or "").strip()
        if code.isdigit() and len(code) == 6:  # A 股裸码 → cn LIST 投影行
            return STATEMENTS[_STATEMENT_DOMAINS[kind]]
        return MKT_STATEMENTS[kind]

    def income(
        self, symbol: str, years: int = 5, scope: str = "合并", period: str = "annual", **_kw: Any
    ) -> list[dict]:
        _Statements.last_kwargs = {
            "symbol": symbol,
            "years": years,
            "scope": scope,
            "period": period,
        }
        return list(self._rows(symbol, "income"))

    def balance(
        self, symbol: str, years: int = 5, scope: str = "合并", period: str = "annual", **_kw: Any
    ) -> list[dict]:
        _Statements.last_kwargs = {
            "symbol": symbol,
            "years": years,
            "scope": scope,
            "period": period,
        }
        return list(self._rows(symbol, "balance"))

    def cashflow(
        self, symbol: str, years: int = 5, scope: str = "合并", period: str = "annual", **_kw: Any
    ) -> list[dict]:
        _Statements.last_kwargs = {
            "symbol": symbol,
            "years": years,
            "scope": scope,
            "period": period,
        }
        return list(self._rows(symbol, "cashflow"))

    def years(self, symbol: str, kind: str = "income", **_kw: Any) -> list[str]:
        return STATEMENT_PERIODS


class _Dividend:
    def history(
        self,
        symbol: str,
        limit: int | None = None,
        begin: str | None = None,
        end: str | None = None,
        _raw: bool = False,
        _df: bool = False,
    ) -> list[dict]:
        rows = list(DIVIDENDS)
        if begin:
            rows = [r for r in rows if r["ex_date"] >= begin]
        if end:
            rows = [r for r in rows if r["ex_date"] <= end]
        return rows[: int(limit)] if limit else rows

    def last(self, symbol: str, _raw: bool = False) -> dict:
        return DIVIDENDS[0]

    def yield_ttm(self, symbol: str) -> float:
        return 0.0373

    def payout_ttm(self, symbol: str) -> float:
        return 0.75

    def dps(self, symbol: str) -> float:
        return 3.6


class _Indicator:
    def metrics(
        self, symbol: str, codes: list[str], fut_symbol: str | None = None
    ) -> dict[str, float]:
        values = {
            "$PE_TTM_LAST": 22.5,
            "$PB": 8.1,
            "$PS_TTM_LAST": 9.4,
            "$MV_LAST": 1_740_176_092_672.05,
            "$ROE_TTM_LAST": 0.31,
            "$EPS_DPPR_TTM_LAST": 70.0,
            "$BONUS_RATE_TTM_LAST": 0.0373,
            "$TR_TTM_LAST": 168_838_102_514.79,
            "$NP_TTM_LAST": 90_000_000_000.0,
            "$PCT_PE_TTM_10Y_LAST": 0.42,
            # Profile bundle. A US listing has no $STYLE_INDUSTRY, so the
            # fetcher must omit that code there rather than batch it and fail.
            "$NAME": "贵州茅台",
            "$INDUSTRY_CUR": "industry.S340501",
            "$STYLE_INDUSTRY": "大消费",
            "$ORG_ORGTYPE": 1,
            "$ORG_LISTINGDATE": "2001-08-27",
            # Curated ratio codes used to overlay the newest period.
            "$GM": 0.91,
            "$ROIC_LAST": 0.29,
            "$TA_TURNOVER": 0.42,
            "$TL_RATE_LAST": 0.17,
            "$QUICK_RATIO_LAST": 3.1,
        }
        if getattr(self, "market", "cn") == "us" and "$STYLE_INDUSTRY" in codes:
            raise AssertionError("us profile must not request $STYLE_INDUSTRY (undefined upstream)")
        return {code: values.get(code) for code in codes if code in values}

    def get(self, symbol: str, code: str, fut_symbol: str | None = None) -> float | None:
        return self.metrics(symbol, [code]).get(code)

    def basic(self, symbol: str) -> dict:
        return {"pe_ttm": 22.5, "pb": 8.1, "turnover_rate": 0.002, "total_mv": 1.74e12}

    def financials(self, symbol: str) -> dict:
        return {"roe_ttm": 0.31, "roe_avg": 0.3, "eps_ttm": 70.0}


class _Info:
    def profile(self, symbol: str) -> dict:
        return {
            "name": "贵州茅台",
            "industry": "industry.S340501",
            "industry_name": "白酒",
            "style_industry": "大消费",
            "org_type": 1,
            "listing_date": "2001-08-27",
        }


class _Index:
    def keys(self, _df: bool = False) -> list[str]:
        return list(INDEX_KEYS)

    def members(
        self, key: str, sort_by: str | None = None, top_n: int | None = None, _df: bool = False
    ) -> list[dict]:
        rows = list(INDEX_MEMBERS)
        return rows[: int(top_n)] if top_n else rows

    def weights(self, key: str, top_n: int | None = None, _df: bool = False) -> list[dict]:
        rows = list(INDEX_WEIGHTS)
        return rows[: int(top_n)] if top_n else rows

    def valuation(self, key: str, points: int | None = None) -> dict:
        return {"pe": 13.42, "pb": 1.25, "dv": 0.0231}

    def universe_keys(self, group: str = "broad") -> list[str]:
        if group == "industry":
            return ["industry.S11", "industry.S22"]
        if group == "dividend":
            return ["index.csidividend"]
        return list(INDEX_KEYS)

    def trend(self, key: str, window: str = "5y") -> dict:
        return {"ok": True, "key": key, "pe_pct": 0.35, "pb_pct": 0.28}


class FakeClient:
    """Canned stand-in for ``wmshare.Client`` with production-matching signatures."""

    def __init__(self, market: str = "cn") -> None:
        self.market = market
        self.kline = _Kline()
        self.statements = _Statements()
        self.dividend = _Dividend()
        self.indicator = _Indicator()
        self.indicator.market = market
        self.info = _Info()
        self.index = _Index()
        self.screener = self._Screener()
        self._Screener._outer = self
        self.filings = _Filings()
        self.equity = _Equity()
        self.moneyflow = _Moneyflow()
        self.margin = _Margin()
        self.cbond = _Cbond()
        self.segments = _Segments()
        self.forecast = _Forecast()
        self.estimates = _Estimates()

    def call(
        self,
        name: str,
        /,
        _raw: bool = False,
        _df: bool = False,
        _units: str = "base",
        **kwargs: Any,
    ) -> Any:
        """Emulate ``Client.call`` for the catalog functions the models use."""
        if name == "indices.members":
            return self.index.members(kwargs.get("key"))
        if name == "indices.weights":
            return self.index.weights(kwargs.get("key"))
        if name == "kline.query_at_anchor":
            return self.kline.anchor_bars(
                kwargs.get("sym"), kwargs.get("limit"), kwargs.get("anchor_date")
            )
        if name == "kline.query_index_last_live_many":
            return self.kline.index_live_many(kwargs.get("keys") or [])
        if name == "stocks.industry_members":
            return self.industry_members(kwargs.get("ind"))
        if name == "screener.query":
            return {
                "count": 108,
                "rows": [
                    {
                        "symbol": "900948",
                        "name": "伊泰B股",
                        "$BONUS_RATE_3Y_AVG_LAST": 0.2104,
                        "$ROE_TTM_LAST": 0.1631,
                    },
                    {
                        "symbol": "600519",
                        "name": "贵州茅台",
                        "$BONUS_RATE_3Y_AVG_LAST": 0.0373,
                        "$ROE_TTM_LAST": 0.31,
                    },
                ],
            }
        raise AssertionError(f"FakeClient.call received an unexpected function: {name}")

    def industry_members(self, ind: str | None) -> list[dict]:
        """Emulate ``stocks.industry_members``: member rows of one industry."""
        return [{"symbol": "600519", "name": "贵州茅台", "industry": ind, "industry_name": "白酒"}]

    class _Screener:
        """Mirror of ``wmshare.api.ScreenerApi``'s used surface."""

        def index_top_movers(self, limit: int = 20, desc: bool = True) -> list[dict]:
            return self._outer.screener_top_movers(limit, desc)

        def query(
            self,
            where: str,
            order: str | None = None,
            desc: bool = True,
            limit: int = 50,
            offset: int = 0,
            fields: list[str] | None = None,
            idx: str | None = None,
            _df: bool = False,
        ) -> dict:
            return {
                "count": 108,
                "rows": [
                    {
                        "symbol": "900948",
                        "name": "伊泰B股",
                        "$BONUS_RATE_3Y_AVG_LAST": 0.2104,
                        "$ROE_TTM_LAST": 0.1631,
                    },
                    {
                        "symbol": "600519",
                        "name": "贵州茅台",
                        "$BONUS_RATE_3Y_AVG_LAST": 0.0373,
                        "$ROE_TTM_LAST": 0.31,
                    },
                ],
            }

    def screener_top_movers(self, limit: int, desc: bool) -> list[dict]:
        """Emulate ``screener.index_top_movers``: symbol/name/percent rows only."""
        movers = [
            {"symbol": "300528", "name": "幸福蓝海", "percent": 0.2001},
            {"symbol": "600519", "name": "贵州茅台", "percent": 0.0102},
            {"symbol": "000001", "name": "平安银行", "percent": -0.0198},
        ]
        rows = sorted(movers, key=lambda r: r["percent"], reverse=desc)
        return rows[: int(limit)]


class _Moneyflow:
    """Mirror of ``wmshare.api.MoneyflowApi``."""

    def bars(
        self,
        symbol: str,
        n: int | None = None,
        begin: str | None = None,
        end: str | None = None,
        _raw: bool = False,
        _df: bool = False,
    ) -> list[dict]:
        return [
            {
                "date": "2026-10-30",
                "net_mf": 328_649_400,
                "elg_net": -7_507_400,
                "lg_net": -125_033_400,
                "md_net": 41_427_500,
                "sm_net": 91_113_200,
            },
            {
                "date": "2026-10-29",
                "net_mf": 366_153_399,
                "elg_net": -120_158_100,
                "lg_net": 12_153_900,
                "md_net": -61_535_500,
                "sm_net": 169_539_700,
            },
        ][: int(n or 20)]


class _Margin:
    """Mirror of ``wmshare.api.MarginApi``."""

    def query(self, symbol: str, limit: int = 20, _df: bool = False) -> list[dict]:
        return [
            {
                "trade_date": "2026-11-12",
                "fin_balance": 15_214_545_810,
                "fin_buy_amt": 371_880_306,
                "fin_repay_amt": 250_843_687,
                "loan_balance": 305_393_968.5,
                "loan_repay_vol": 5400,
                "loan_sell_vol": 7900,
                "secucode": "600519.SH",
                "security_code": "600519",
                "security_name": "贵州茅台",
            },
        ][: int(limit)]


class _Cbond:
    """Mirror of ``wmshare.api.CbondApi.board``."""

    def board(self, _raw: bool = False, _df: bool = False) -> list[dict]:
        return [
            {
                "asOf": "2026-11-13",
                "bondCode": "111027",
                "bondName": "百龙转债",
                "bondPrice": 101.2,
                "convertPrice": 19.42,
                "bondRating": "AA",
                "stockCode": "000829",
                "remainSize": 6.2,
                "bias20": None,
            },
        ]


class _Filings:
    """Mirror of ``wmshare.api.FilingsApi``."""

    def list(
        self, symbol: str, kind: str = "all", limit: int = 10, _df: bool = False
    ) -> list[dict]:
        rows = [
            {
                "notice_date": "2026-04-17",
                "notice_type": "年报",
                "pdf_url": "https://res.example/fr/600519_2025Y_a.pdf",
                "report_date": "2025-12-31",
                "title": "贵州茅台:2025年年度报告",
            },
            {
                "notice_date": "2025-08-15",
                "notice_type": "半年报",
                # one link-less row: the fetcher must skip it (report_url required)
                "pdf_url": "",
                "report_date": "2025-06-30",
                "title": "贵州茅台:2025年半年度报告",
            },
        ]
        if kind != "all":
            rows = [r for r in rows if kind == "annual" and r["notice_type"] == "年报"]
        return rows[: int(limit)]


class _Equity:
    """Mirror of ``wmshare.api.EquityApi``'s used surface."""

    def query_executives(self, symbol: str, _df: bool = False) -> list[dict]:
        return [
            {
                "person_name": "陈华",
                "position": "董事长,法定代表人,董事",
                "salary": None,
                "hold_num": None,
                "sex": "男",
                "birth_year": "1972",
                "age": "54",
                "high_degree": "硕士",
                "nationality": "",
                "incumbent_time": "2025-11-28至今",
            },
            {
                "person_name": "王莉",
                "position": "代理总经理,董事",
                "salary": 1200000.0,
                "hold_num": 55000.0,
                "sex": "女",
                "birth_year": "1973",
                "age": "53",
                "high_degree": "硕士",
                "nationality": "中国",
                "incumbent_time": "2023-08-19至今",
            },
        ]

    def query_capital_change(self, symbol: str) -> dict:
        return {"free_shares": 1250081601, "total_shares": 1250081601}

    def query_institution_detail(
        self, symbol: str, limit: int = 20, _df: bool = False
    ) -> list[dict]:
        return [
            {
                "holder_name": "中国贵州茅台酒厂(集团)有限责任公司",
                "org_type": "07",
                "report_date": "2026-06-30",
                "total_shares": 681282935,
                "hold_value": 807654106613.15,
                "total_shares_ratio": 0.5449907706,
                "free_shares_ratio": 0.5449907706,
            },
            {
                # no report_date: the fetcher must skip this row
                "holder_name": "睿远稳益增强30天持有债券A",
                "org_type": "01",
                "total_shares": 67000,
            },
        ][: int(limit)]

    def query_exec_change(self, symbol: str) -> dict:
        return {
            "average_price": 725.92,
            "change_after_holdnum": 0,
            "change_num": -700,
            "end_date": "2018-09-26",
            "executive_name": "万波",
            "executive_relation": "本人",
            "holder_name": "万波",
            "position": "高级管理人员",
            "trade_way": "二级市场买卖",
        }


class _Segments:
    """Mirror of ``wmshare.api.SegmentsApi``."""

    def periods(self, symbol: str) -> dict:
        return {"clean_last": "2026:Q3", "clean_last_q4": "2026:Q4"}

    def products(
        self, symbol: str, source: str = "clean", limit: int = 20, _df: bool = False
    ) -> list[dict]:
        return [
            {
                "name": "茅台酒",
                "tr": 125_000_000_000.0,
                "tr_text": "1250.00亿",
                "cost": 15_000_000_000.0,
                "margin": 0.88,
                "ratio": 0.85,
            },
            {
                "name": "系列酒",
                "tr": 18_000_000_000.0,
                "tr_text": "180.00亿",
                "cost": 5_000_000_000.0,
                "margin": 0.72,
                "ratio": 0.12,
            },
        ]

    def business(
        self, symbol: str, source: str = "clean", limit: int = 20, _df: bool = False
    ) -> list[dict]:
        return [{"name": "酒类销售", "tr": 143_000_000_000.0, "margin": 0.87}]

    def region(self, symbol: str, source: str = "clean", limit: int = 20, _df: bool = False) -> Any:
        if source == "clean":
            return {
                "source": "clean",
                "report_sas": "2026:Q3",
                "domestic": {"tr": 129_252_586_100, "pct": 0.987, "margin": 0, "yoy": 0.038},
                "overseas": {"tr": 1_641_408_900, "pct": 0.0125, "margin": 0, "yoy": -0.578},
            }
        return [
            {"name": "国内", "tr": 129_252_586_100, "tr_text": "1292.53亿"},
            {"name": "国外", "tr": 1_641_408_900, "tr_text": "16.41亿"},
        ]


class _Forecast:
    """Mirror of ``wmshare.api.ForecastApi``."""

    def disclosure_history(self, symbol: str, limit: int = 8, _df: bool = False) -> list[dict]:
        return [
            {
                "actual_publish_date": "2026-10-31",
                "change_count": 0,
                "first_appoint_date": "2026-10-31",
                "is_publish": "1",
                "latest_appoint_date": "2026-10-31",
                "report_date": "2026-09-30",
                "report_type_name": "2026年 三季报",
            },
            {
                "actual_publish_date": None,
                "change_count": 1,
                "first_appoint_date": "2026-04-20",
                "is_publish": "0",
                "latest_appoint_date": "2026-04-25",
                "report_date": "2026-12-31",
                "report_type_name": "2026年 年报",
            },
        ]


class _Estimates:
    """Mirror of ``wmshare.api.EstimatesApi``."""

    def query_forecast(self, symbol: str, limit: int = 8, _df: bool = False) -> list[dict]:
        base = {
            "author": None,
            "compre_rating": "",
            "compre_rating_num": None,
            "date_type": "",
            "industry": "",
            "info_code": "",
            "parent_netprofit1": None,
            "parent_netprofit2": None,
            "parent_netprofit3": None,
            "parent_netprofit4": None,
            "rating": "",
            "rating_add_num": None,
            "rating_buy_num": None,
            "rating_neutral_num": None,
            "publish_date": "2026-10-01",
        }
        return [
            {
                **base,
                "org_code": "00000000",
                "org_name": "近六月平均",
                "eps1": 65.85,
                "eps2": 67.25,
                "eps3": 71.13,
                "eps4": 75.18,
                "pe1": 19.11,
                "pe2": 18.71,
                "pe3": 17.69,
                "pe4": 16.74,
            },
            {
                **base,
                "org_code": "10002602",
                "org_name": "某某证券",
                "author": "研究员甲",
                "rating": "买入",
                "eps1": 66.5,
                "eps2": 68.0,
                "eps3": 72.0,
                "eps4": None,
                "pe1": 18.9,
                "pe2": 18.4,
                "pe3": 17.4,
                "pe4": None,
            },
        ][: int(limit)]


class FakeCatalog:
    """Stand-in for ``wmshare.catalog.Catalog`` limited to symbol search."""

    def symbols_search(self, query: str, market: str = "cn", limit: int = 20) -> list[dict]:
        rows = SYMBOL_TABLE.get(market, [])
        term = str(query or "").casefold()
        if not term:
            return []
        hits = [
            row
            for row in rows
            if term in row["code"].casefold()
            or term in row["name"].casefold()
            or term in row["pinyin"].casefold()
        ]
        return hits[:limit]


@pytest.fixture
def fake_client(monkeypatch: pytest.MonkeyPatch) -> FakeClient:
    """Route every model's client lookups to one ``FakeClient``.

    Patches every ``openbb_wmshare.models.*`` module that bound ``get_client``,
    discovered by package walk so a newly added model cannot silently fall
    through to the real API (that exact miss once sent a test to production).
    The statement models reach ``get_client`` through ``_statements``; the
    discovery walk covers it like any other module.
    """
    import importlib
    import pkgutil

    from openbb_wmshare import models, utils

    client = FakeClient()

    stub = lambda *a, **k: client  # noqa: E731 - one shared fake for all modules
    seen: set[str] = set()
    for info in pkgutil.iter_modules(models.__path__):
        module = importlib.import_module(f"openbb_wmshare.models.{info.name}")
        if hasattr(module, "get_client"):
            monkeypatch.setattr(module, "get_client", stub, raising=True)
            seen.add(info.name)
    for info in pkgutil.iter_modules(utils.__path__):
        module = importlib.import_module(f"openbb_wmshare.utils.{info.name}")
        if hasattr(module, "get_client"):
            monkeypatch.setattr(module, "get_client", stub, raising=True)
            seen.add(info.name)
    monkeypatch.setattr(utils, "get_client", stub, raising=True)

    assert seen, "fixture found no model modules to patch; import layout changed?"
    return client


@pytest.fixture
def fake_catalog(monkeypatch: pytest.MonkeyPatch) -> FakeCatalog:
    """Patch ``wmshare.load`` so equity search runs offline."""
    import wmshare

    catalog = FakeCatalog()
    monkeypatch.setattr(wmshare, "load", lambda *a, **k: catalog)
    return catalog
