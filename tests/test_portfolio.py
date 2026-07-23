# -*- coding: utf-8 -*-
"""選択と集中スコア（portfolio）の検証。"""
from dips import portfolio


def test_load_portfolio_has_ventures():
    pf = portfolio.load_portfolio()
    assert pf.get("ventures"), "portfolio.yaml に ventures が必要"
    ids = {v.get("id") for v in pf["ventures"]}
    assert {"drone_school", "costume_app"} <= ids


def test_mean_empty_is_zero():
    assert portfolio._mean({}) == 0.0
    assert portfolio._mean(None) == 0.0


def test_mean_rounds():
    assert portfolio._mean({"a": 4, "b": 3, "c": 5}) == 4.0
    assert portfolio._mean({"a": 4, "b": 3}) == 3.5


def test_score_venture_priority_is_product():
    v = {"attractiveness": {"x": 4, "y": 4}, "feasibility": {"x": 2, "y": 4}}
    s = portfolio.score_venture(v, threshold=3.0)
    assert s["_attractiveness"] == 4.0
    assert s["_feasibility"] == 3.0
    assert s["_priority"] == 12.0


def test_quadrant_boundaries():
    # 高魅力(>=3) × 高実現(>=3)
    hi = portfolio.score_venture(
        {"attractiveness": {"a": 4}, "feasibility": {"a": 4}}, 3.0)
    assert hi["_quadrant"] == "集中投資（本命）"
    # 高魅力 × 低実現
    grow = portfolio.score_venture(
        {"attractiveness": {"a": 5}, "feasibility": {"a": 2}}, 3.0)
    assert grow["_quadrant"] == "育成・検証"
    # 低魅力 × 高実現
    eff = portfolio.score_venture(
        {"attractiveness": {"a": 2}, "feasibility": {"a": 5}}, 3.0)
    assert eff["_quadrant"] == "効率運用"
    # 低魅力 × 低実現
    out = portfolio.score_venture(
        {"attractiveness": {"a": 1}, "feasibility": {"a": 2}}, 3.0)
    assert out["_quadrant"] == "撤退・保留候補"


def test_scored_ventures_sorted_by_priority_desc():
    pf = portfolio.load_portfolio()
    scored = portfolio.scored_ventures(pf)
    priorities = [v["_priority"] for v in scored]
    assert priorities == sorted(priorities, reverse=True)
