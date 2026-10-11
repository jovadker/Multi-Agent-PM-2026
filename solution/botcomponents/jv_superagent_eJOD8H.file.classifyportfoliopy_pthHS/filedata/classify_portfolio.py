#!/usr/bin/env python3
"""Classify an asset allocation against four reference portfolios."""

from __future__ import annotations

import argparse
import json
import math
import sys
from typing import Dict, Mapping


ASSET_CLASSES = (
    "absolute_return",
    "real_estate",
    "commodities",
    "investment_grade_bonds",
    "high_yield_bonds",
    "cash",
    "equities",
)

MODEL_PORTFOLIOS: Mapping[str, Mapping[str, float]] = {
    "Stable": {
        "absolute_return": 0.0,
        "real_estate": 50.0,
        "commodities": 0.0,
        "investment_grade_bonds": 50.0,
        "high_yield_bonds": 0.0,
        "cash": 0.0,
        "equities": 0.0,
    },
    "Conservative": {
        "absolute_return": 0.0,
        "real_estate": 20.0,
        "commodities": 10.0,
        "investment_grade_bonds": 24.0,
        "high_yield_bonds": 0.0,
        "cash": 26.0,
        "equities": 20.0,
    },
    "Balanced": {
        "absolute_return": 0.0,
        "real_estate": 10.0,
        "commodities": 10.0,
        "investment_grade_bonds": 28.0,
        "high_yield_bonds": 0.0,
        "cash": 18.0,
        "equities": 34.0,
    },
    "Dynamic": {
        "absolute_return": 0.0,
        "real_estate": 5.0,
        "commodities": 10.0,
        "investment_grade_bonds": 26.4,
        "high_yield_bonds": 0.0,
        "cash": 11.0,
        "equities": 47.6,
    },
}


def parse_allocation(raw_json: str) -> Dict[str, float]:
    try:
        value = json.loads(raw_json)
    except json.JSONDecodeError as error:
        raise ValueError(f"Allocation is not valid JSON: {error.msg}") from error

    if not isinstance(value, dict):
        raise ValueError("Allocation JSON must be an object.")

    unknown = sorted(set(value) - set(ASSET_CLASSES))
    if unknown:
        raise ValueError(f"Unknown asset classes: {', '.join(unknown)}")

    allocation: Dict[str, float] = {}
    for asset_class in ASSET_CLASSES:
        raw_value = value.get(asset_class, 0.0)
        if isinstance(raw_value, bool) or not isinstance(raw_value, (int, float)):
            raise ValueError(f"{asset_class} must be a number.")
        number = float(raw_value)
        if not math.isfinite(number) or number < 0:
            raise ValueError(f"{asset_class} must be a finite, non-negative number.")
        allocation[asset_class] = number

    total = sum(allocation.values())
    if not 99.5 <= total <= 100.5:
        raise ValueError(
            f"Allocation totals {total:.2f}%; expected a value between 99.5% and 100.5%."
        )

    return {
        asset_class: percentage * 100.0 / total
        for asset_class, percentage in allocation.items()
    }


def rms_distance(
    allocation: Mapping[str, float], model: Mapping[str, float]
) -> float:
    squared_difference = sum(
        (allocation[asset_class] - model[asset_class]) ** 2
        for asset_class in ASSET_CLASSES
    )
    return math.sqrt(squared_difference / len(ASSET_CLASSES))


def classify(allocation: Mapping[str, float]) -> Dict[str, object]:
    ranked = sorted(
        (
            {
                "portfolio_type": portfolio_type,
                "rms_distance": rms_distance(allocation, model),
            }
            for portfolio_type, model in MODEL_PORTFOLIOS.items()
        ),
        key=lambda result: result["rms_distance"],
    )
    closest, second = ranked[:2]
    closest_distance = float(closest["rms_distance"])
    lead = float(second["rms_distance"]) - closest_distance

    if closest_distance <= 5.0 and lead >= 3.0:
        confidence = "High"
    elif closest_distance <= 10.0 and lead >= 2.0:
        confidence = "Medium"
    else:
        confidence = "Low"

    closest_model = MODEL_PORTFOLIOS[str(closest["portfolio_type"])]
    differences = sorted(
        (
            {
                "asset_class": asset_class,
                "percentage_point_difference": allocation[asset_class]
                - closest_model[asset_class],
            }
            for asset_class in ASSET_CLASSES
            if abs(allocation[asset_class] - closest_model[asset_class]) >= 0.05
        ),
        key=lambda item: abs(float(item["percentage_point_difference"])),
        reverse=True,
    )

    return {
        "portfolio_type": closest["portfolio_type"],
        "confidence": confidence,
        "normalized_allocation": {
            asset_class: round(allocation[asset_class], 4)
            for asset_class in ASSET_CLASSES
        },
        "closest_model": {
            "portfolio_type": closest["portfolio_type"],
            "rms_distance": round(closest_distance, 4),
        },
        "second_closest_model": {
            "portfolio_type": second["portfolio_type"],
            "rms_distance": round(float(second["rms_distance"]), 4),
        },
        "differences_from_closest": [
            {
                "asset_class": item["asset_class"],
                "percentage_point_difference": round(
                    float(item["percentage_point_difference"]), 4
                ),
            }
            for item in differences
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Classify a portfolio as Stable, Conservative, Balanced, or Dynamic."
    )
    parser.add_argument(
        "--allocation-json",
        required=True,
        help="JSON object containing percentages by canonical asset-class key.",
    )
    args = parser.parse_args()

    try:
        allocation = parse_allocation(args.allocation_json)
        result = classify(allocation)
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
