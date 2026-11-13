"""Tests for statement transposition and ratio derivation."""

from datetime import date

import pytest

from openbb_wmshare.utils.statements import (
    collect,
    compute_ratios,
    parse_period,
    pivot,
)

INCOME_ROWS = [
    {
        "k": "total_revenue",
        "cn": "营业收入",
        "vals": {"2025": 168_838_102_514.79, "2024": 170_899_152_276.34},
    },
    {
        "k": "operating_cost",
        "cn": "营业成本",
        "vals": {"2025": 20_000_000_000.0, "2024": 21_000_000_000.0},
    },
    {"k": "operating_profit", "cn": "营业利润", "vals": {"2025": 120_000_000_000.0}},
    {"k": "total_profit", "cn": "利润总额", "vals": {"2025": 121_000_000_000.0}},
    {"k": "net_profit", "cn": "净利润", "vals": {"2025": 90_000_000_000.0}},
    {"k": "np_parent", "cn": "归母净利润", "vals": {"2025": 88_000_000_000.0}},
    {"k": "__gm", "cn": "毛利率(派生)", "vals": {"2025": 0.88}},
]

BALANCE_ROWS = [
    {
        "k": "total_assets",
        "cn": "总资产",
        "vals": {"2025": 300_000_000_000.0, "2024": 270_000_000_000.0},
    },
    {"k": "total_liabilities", "cn": "总负债", "vals": {"2025": 60_000_000_000.0}},
    {"k": "total_equity", "cn": "所有者权益", "vals": {"2025": 240_000_000_000.0}},
    {"k": "total_parent_equity", "cn": "归母权益", "vals": {"2025": 230_000_000_000.0}},
    {"k": "total_current_assets", "cn": "流动资产", "vals": {"2025": 200_000_000_000.0}},
    {"k": "total_current_liabilities", "cn": "流动负债", "vals": {"2025": 50_000_000_000.0}},
    {"k": "inventories", "cn": "存货", "vals": {"2025": 20_000_000_000.0}},
    {"k": "monetary_funds", "cn": "货币资金", "vals": {"2025": 100_000_000_000.0}},
]


@pytest.mark.parametrize(
    ("token", "year", "period", "ending"),
    [
        ("2025", 2025, "FY", date(2025, 12, 31)),
        ("2025-Q4", 2025, "Q4", date(2025, 12, 31)),
        ("2025:Q2", 2025, "Q2", date(2025, 6, 30)),
        ("2025-H1", 2025, "H1", date(2025, 6, 30)),
        ("2025-12-31", 2025, "FY", date(2025, 12, 31)),
    ],
)
def test_parse_period(token, year, period, ending):
    assert parse_period(token) == (year, period, ending)


def test_parse_period_handles_garbage():
    assert parse_period("n/a") == (None, None, None)
    assert parse_period("") == (None, None, None)


def test_pivot_turns_period_columns_into_rows():
    records = pivot(INCOME_ROWS)

    assert len(records) == 2
    assert records[0]["period_ending"] == date(2025, 12, 31)
    assert records[0]["fiscal_year"] == 2025
    assert records[0]["fiscal_period"] == "FY"
    assert records[0]["total_revenue"] == pytest.approx(168_838_102_514.79)
    assert records[1]["period_ending"] == date(2024, 12, 31)


def test_pivot_drops_derived_ratio_rows():
    records = pivot(INCOME_ROWS)
    assert all("__gm" not in record for record in records)


def test_pivot_omits_items_absent_from_a_period():
    """operating_profit only exists for 2025, so 2024 must not carry a bogus value."""
    records = pivot(INCOME_ROWS)
    by_year = {r["fiscal_year"]: r for r in records}
    assert "operating_profit" in by_year[2025]
    assert "operating_profit" not in by_year[2024]


def test_pivot_on_empty_input_returns_nothing():
    assert pivot([]) == []


def test_collect_indexes_by_item_then_period():
    collected = collect(BALANCE_ROWS)
    assert collected["total_assets"]["2025"] == pytest.approx(300_000_000_000.0)
    assert collected["total_assets"]["2024"] == pytest.approx(270_000_000_000.0)


def test_compute_ratios_derives_margins_and_leverage():
    records = compute_ratios(INCOME_ROWS, BALANCE_ROWS)
    latest = next(r for r in records if r["fiscal_year"] == 2025)

    # gross margin uses total_revenue - operating_cost when no gross_profit row exists
    assert latest["gross_margin"] == pytest.approx(
        (168_838_102_514.79 - 20_000_000_000.0) / 168_838_102_514.79
    )
    assert latest["net_margin"] == pytest.approx(90_000_000_000.0 / 168_838_102_514.79)
    assert latest["debt_to_assets"] == pytest.approx(60_000_000_000.0 / 300_000_000_000.0)
    assert latest["current_ratio"] == pytest.approx(4.0)
    assert latest["quick_ratio"] == pytest.approx((200 - 20) / 50)
    assert latest["cash_ratio"] == pytest.approx(2.0)


def test_compute_ratios_averages_assets_across_periods():
    """ROA divides by the mean of opening and closing assets, not just closing."""
    records = compute_ratios(INCOME_ROWS, BALANCE_ROWS)
    latest = next(r for r in records if r["fiscal_year"] == 2025)
    mean_assets = (300_000_000_000.0 + 270_000_000_000.0) / 2

    assert latest["return_on_assets"] == pytest.approx(90_000_000_000.0 / mean_assets)


def test_compute_ratios_prefers_parent_equity_for_roe():
    records = compute_ratios(INCOME_ROWS, BALANCE_ROWS)
    latest = next(r for r in records if r["fiscal_year"] == 2025)
    assert latest["return_on_equity"] == pytest.approx(88_000_000_000.0 / 230_000_000_000.0)


def test_ratios_are_none_instead_of_raising_on_missing_inputs():
    """A statement gap must yield None, never a divide-by-zero or a silent 0."""
    records = compute_ratios(
        [{"k": "total_revenue", "vals": {"2025": 100.0}}],
        [{"k": "total_assets", "vals": {"2025": 0.0}}],
    )
    latest = records[0]
    assert latest["return_on_assets"] is None
    assert latest["current_ratio"] is None
    assert latest["gross_margin"] is None
