---
name: portfolio-complexity
description: Classifies an investment portfolio as Stable, Conservative, Balanced, or Dynamic from typed allocation percentages or an uploaded allocation chart. Use when a user asks to determine portfolio complexity, risk profile, model-portfolio fit, or compare an allocation with the four reference portfolios.
compatibility: Requires Python 3.8+ only when using the bundled deterministic classifier.
metadata:
  version: "1.0.0"
---

# Portfolio complexity classification

Classify a portfolio against the four model portfolios in
[`references/model-portfolios.md`](references/model-portfolios.md). Accept either:

- typed allocation percentages; or
- an image containing a portfolio allocation chart or table.

This classification describes allocation complexity/risk posture. It is not investment advice.

## Workflow

1. Extract percentages for these seven canonical asset classes:
   - `absolute_return`
   - `real_estate`
   - `commodities`
   - `investment_grade_bonds`
   - `high_yield_bonds`
   - `cash`
   - `equities`
2. Map synonymous or Hungarian labels using the reference file.
3. For an image:
   - Prefer printed percentages in the legend or table over estimating pie-slice areas.
   - Record unreadable values as unknown; never silently treat them as zero.
   - Ask the user to confirm uncertain values before classification.
4. Validate every value:
   - Reject negative or non-numeric percentages.
   - Treat an omitted asset class as zero only when the user supplied a complete allocation.
   - If the total is between `99.5` and `100.5`, normalize to exactly 100.
   - Otherwise, stop and ask for a corrected allocation.
5. Run the deterministic classifier:

   ```powershell
   python portfolio-complexity\scripts\classify_portfolio.py --allocation-json '{"absolute_return":0,"real_estate":10,"commodities":10,"investment_grade_bonds":28,"high_yield_bonds":0,"cash":18,"equities":34}'
   ```

6. Present:
   - portfolio type: `Stable`, `Conservative`, `Balanced`, or `Dynamic`;
   - confidence: `High`, `Medium`, or `Low`;
   - normalized allocation;
   - closest and second-closest model, including their RMS distances;
   - the main allocation differences from the closest model.
7. If confidence is Low, describe the result as the nearest model rather than a definitive classification.

## Response format

Use this compact structure:

```text
Portfolio type: Balanced
Confidence: High

Why:
- Closest model: Balanced (RMS distance: 0.0 percentage points)
- Next closest: Conservative (RMS distance: 8.2 percentage points)
- Main differences: none

Allocation used:
- Real estate: 10.0%
- Commodities: 10.0%
- Investment-grade bonds: 28.0%
- Cash: 18.0%
- Equities: 34.0%
```

Omit zero-value categories from the display unless they help explain the result.

## Interpretation rules

- Do not classify based only on the portfolio name printed in an image; use its allocation.
- Do not equate this result with suitability for a particular investor.
- Do not predict returns or imply guarantees.
- Mention concentration, illiquidity, or unusual allocations when material, even if the nearest-model match is clear.
- Preserve the user's original units and labels in the explanation when useful.
