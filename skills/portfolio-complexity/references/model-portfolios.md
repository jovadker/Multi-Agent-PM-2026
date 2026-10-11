# Model portfolio reference

Percentages are based on the supplied four-portfolio reference chart.

| Canonical asset class | Stable | Conservative | Balanced | Dynamic |
|---|---:|---:|---:|---:|
| Absolute return | 0.0 | 0.0 | 0.0 | 0.0 |
| Real estate | 50.0 | 20.0 | 10.0 | 5.0 |
| Commodities | 0.0 | 10.0 | 10.0 | 10.0 |
| Investment-grade bonds | 50.0 | 24.0 | 28.0 | 26.4 |
| High-yield bonds | 0.0 | 0.0 | 0.0 | 0.0 |
| Cash | 0.0 | 26.0 | 18.0 | 11.0 |
| Equities | 0.0 | 20.0 | 34.0 | 47.6 |

## Label aliases

| Canonical key | Common labels |
|---|---|
| `absolute_return` | absolute return, absolute-return alternatives, alternatív - abszolút hozam |
| `real_estate` | real estate, property, ingatlan, alternatív - ingatlan |
| `commodities` | commodities, raw materials, nyersanyag, alternatív - nyersanyag |
| `investment_grade_bonds` | investment-grade bonds, IG bonds, kötvény - befektetési kategória |
| `high_yield_bonds` | high-yield bonds, HY bonds, kötvény - magas hozamú |
| `cash` | cash, liquidity, készpénz |
| `equities` | equities, stocks, shares, részvény |

## Distance and confidence

The classifier computes the root-mean-square (RMS) percentage-point difference
between the submitted allocation and every model allocation. The model with the
smallest distance is the result.

Confidence is:

- **High**: closest distance is at most 5 points and leads the next model by at
  least 3 points.
- **Medium**: closest distance is at most 10 points and leads by at least 2
  points.
- **Low**: all other cases.

These thresholds identify model fit; they do not measure statistical certainty
or investor suitability.
