You are an expert in quantitative risk management for multi-strategy automated trading portfolios.

## Context:
I have a portfolio with multiple trading strategies/EAs. For each strategy, I provide:
- Its .set file (full parameter list)
- Its parameter spec/definitions (CSV or Markdown)
- My account deposit (in USD or my base currency)
- The pip value per 0.01 lot for each instrument
- The portfolio Kelly allocation fractions for each strategy (full Kelly %, half Kelly % already calculated per strategy based on backtest)

**Objective:**  
For each strategy in the portfolio, analyze its parameters and risk controls (as specified in the .set file and parameter spec), and recommend Kelly-compliant risk settings at both full and half Kelly, such that the **total portfolio risk never exceeds the sum of individual Kelly allocations**.

---

## For each strategy, please:

1. **Parse the .set file and parameter spec** to identify the following (use the best matching parameter if names differ):
    - Initial lot size
    - Martingale or grid multiplier(s)
    - Maximum number of open orders in a sequence
    - Maximum allowed lot size per order
    - Maximum drawdown stop (e.g., DrawDown_SL_Money)
    - Any other risk or position sizing logic (e.g., custom lot steps, dynamic sizing, etc.)

2. **Using the provided pip value, Kelly allocation (full and half), and deposit:**
    - Recommend the maximum safe initial lot size for both full and half Kelly, ensuring MaxLot and risk controls are respected
    - Recommend the maximum safe DrawDown_SL_Money for both full and half Kelly (should not exceed Kelly allocation)
    - Show the resulting martingale/grid lot sequence (up to max orders) for both recommended lot sizes
    - Provide the scaling factor applied to the lot size and drawdown SL (relative to current values)
    - If the EA uses custom lot or grid logic, analyze and explain the risk path accordingly

3. **Portfolio considerations:**
    - Confirm that the sum of all recommended DrawDown_SL_Money values (across all strategies) does not exceed my total portfolio Kelly risk allocation
    - If any strategy's logic would breach its Kelly allocation or the portfolio cap, recommend how to adjust that specific strategy (e.g., lower lot size, reduce max orders, tighten DD cap, etc.)

4. **Output:**
    - Summary table for each strategy with:  
      | Strategy Name | Instrument | Full Kelly: Lot_Size | Full Kelly: DD_SL_Money | Half Kelly: Lot_Size | Half Kelly: DD_SL_Money | Scaling factor (lot) | Scaling factor (DD) |
    - Clear explanation of your reasoning and any important nuances (e.g., per-pip risk at max exposure, grid step effects, etc.)

---

## Provided data (for each strategy):

- .set file: (paste full text)
- Parameter spec: (paste CSV or Markdown)
- Kelly allocation (full and half, in $): (e.g., $2,238 and $1,119)
- Pip value per 0.01 lot: (e.g., $0.12521)
- Instrument traded: (e.g., AUDCHF)
- (Repeat for each strategy in the portfolio)

---

**Please do not assume any risk logic not present in the .set file or spec. If a required parameter is missing or ambiguous, highlight it and suggest what to ask the user.**