# -*- coding: utf-8 -*-
"""代表ダッシュボード：経営ポートフォリオの読込と「選択と集中」スコア算出。

- config/portfolio.yaml を読み込む
- 各事業を「魅力度 × 実現性」で採点し、優先度と象限（4象限）を計算する
- スコア計算は副作用のない純関数（tests/test_portfolio.py で検証）

象限（threshold を境に高/低を分ける）:
  高魅力 × 高実現 → 集中投資（本命）
  高魅力 × 低実現 → 育成・検証
  低魅力 × 高実現 → 効率運用
  低魅力 × 低実現 → 撤退・保留候補
"""
from __future__ import annotations

from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parent.parent
PORTFOLIO_PATH = _ROOT / "config" / "portfolio.yaml"

# 象限ラベル（(魅力度高?, 実現性高?) → ラベル）
QUADRANTS = {
    (True, True): "集中投資（本命）",
    (True, False): "育成・検証",
    (False, True): "効率運用",
    (False, False): "撤退・保留候補",
}


def load_portfolio(path: Path | str | None = None) -> dict:
    """portfolio.yaml を読み込んで dict で返す。"""
    p = Path(path) if path else PORTFOLIO_PATH
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _mean(axes: dict | None) -> float:
    """スコア辞書の平均。空なら 0.0。"""
    if not axes:
        return 0.0
    vals = [float(v) for v in axes.values() if v is not None]
    return round(sum(vals) / len(vals), 2) if vals else 0.0


def score_venture(venture: dict, threshold: float = 3.0) -> dict:
    """1事業の魅力度・実現性・優先度・象限を計算して付与した dict を返す。

    - 魅力度 / 実現性 : 各軸スコア（1〜5）の平均
    - 優先度         : 魅力度 × 実現性（両方高いほど大きい。最大25）
    - 象限           : threshold を境にした4象限ラベル
    """
    attr = _mean(venture.get("attractiveness"))
    feas = _mean(venture.get("feasibility"))
    priority = round(attr * feas, 2)
    quadrant = QUADRANTS[(attr >= threshold, feas >= threshold)]
    out = dict(venture)
    out["_attractiveness"] = attr
    out["_feasibility"] = feas
    out["_priority"] = priority
    out["_quadrant"] = quadrant
    return out


def scored_ventures(portfolio: dict) -> list[dict]:
    """全事業をスコア付けし、優先度の高い順に並べて返す。"""
    threshold = float(portfolio.get("threshold", 3.0))
    scored = [score_venture(v, threshold) for v in portfolio.get("ventures", [])]
    scored.sort(key=lambda v: v["_priority"], reverse=True)
    return scored
