# EA Portfolio Risk Scaling Automation — Integration Design

---

## **1. Data Requirements**

- **EA Spec CSV**  
  Source: `config.EA_SPEC_PATH` (e.g., "PhoenixSpec.csv")
- **AI API Key**  
  Source: `user.open_router_api_key`
- **Strategies & Parameters**  
  Source: Query from your SQL for portfolio, parses param_array JSON for each strategy.
- **Pip Value Table**  
  Source: Query, covers all ccy_pair in portfolio.
- **Kelly Analysis Results**  
  Source: `analysis_results` (already built from trade records)
- **Portfolio Kelly Cap**  
  **NEW:** Compute as the sum of all positive Kelly fractions in portfolio, capped at 1.0 (or user-adjustable).
- **Risk Cap**  
  User input, Kelly, Monte Carlo, or portfolio cap.

---

## **2. Workflow**

### **A. Trigger Flow**
- After `analysis_results` is built (after user clicks "Run Position Sizing & Monte Carlo Risk Analysis"), show a button: **"Run EA Risk Scaling/AI Extraction"**

### **B. Load & Prepare Data**
- Load EA Spec (CSV → markdown/table string for prompt).
- Query strategies for this portfolio (with param_array).
- Query latest pip values and build symbol→pip_value dict.

### **C. AI Batch Extraction**
- For each batch of 4 strategies:
    - Format AI prompt (EA Spec + 4 param_arrays as JSON).
    - Call OpenRouter API, parse JSON result.
    - Save all AI outputs.

### **D. Join Pip Value**
- For each strategy, join symbol→pip_value.

### **E. Join Kelly Fraction**
- For each strategy, join Kelly Fraction from `analysis_results` by strategy_name.

### **F. Portfolio Kelly Cap Calculation**
- **Portfolio Kelly Cap = min(1.0, sum of all positive Kelly fractions in portfolio)**
- Optionally, user can adjust this cap in UI.

### **G. Risk Calculations (per strategy)**
- For each strategy:
    - Compute **total potential loss** (sum over martingale_lot_sequence × pip_value × Martingala_Pips)
    - **Scaling factor** = portfolio Kelly cap (or user risk cap) / total potential loss
    - **Max safe initial Lot_Size** = current Lot_Size × scaling factor
    - **Max safe DrawDown_SL_Money** = total potential loss
    - Save all fields for output.

### **H. Display Results**
- Show results in a new DataFrame/table per strategy:
    - strategy_name, symbol, Kelly Fraction, Portfolio Kelly Cap, scaling factor, MaxSafeInitialLotSize, MaxSafeDrawDown, martingale_lot_sequence, notes, calculation_logic

- Optionally: export, filter, or re-run with different caps.

---

## **3. Portfolio Kelly Cap Calculation**

```python
def calc_portfolio_kelly_cap(analysis_results):
    # analysis_results: list of dicts with 'Kelly Fraction' (may be "N/A" or string)
    kellys = [
        float(sr['Kelly Fraction'])
        for sr in analysis_results
        if sr.get('Kelly Fraction') not in (None, "N/A", "") and float(sr['Kelly Fraction']) > 0
    ]
    return min(1.0, sum(kellys)) if kellys else 0.0
```

---

## **4. Key Functions**

### **A. Format AI Prompt**

```python
def format_ea_risk_profile_prompt(ea_spec_md, strategies_df):
    # ea_spec_md: markdown string of EA spec
    # strategies_df: DataFrame with each row: strategy_name, param_array
    prompt = f"EA Spec:\n{ea_spec_md}\n\n"
    prompt += "Strategies:\n"
    for idx, row in strategies_df.iterrows():
        prompt += f'# {row["strategy_name"]}\n{json.dumps(row["param_array"], ensure_ascii=False)}\n\n'
    prompt += "[Insert AI prompt instruction block here]"  # Use your v2.0 prompt here
    return prompt
```

### **B. Risk Calculation**

```python
def compute_strategy_risk_fields(ai_strategy, pip_value, kelly_fraction, portfolio_kelly_cap):
    lots = ai_strategy["martingale_lot_sequence"]
    pips = ai_strategy["Martingala_Pips"]
    # Use custom pip steps if Custom_Martingala present
    pip_steps = ai_strategy.get("Custom_Martingala") or [pips]*len(lots)
    total_loss = sum(lot * pip_value * step for lot, step in zip(lots, pip_steps))
    scaling_factor = (portfolio_kelly_cap / total_loss) if (portfolio_kelly_cap and total_loss) else None
    max_safe_lot_size = ai_strategy["Lot_Size"] * scaling_factor if scaling_factor else None
    return {
        "strategy_name": ai_strategy["strategy_name"],
        "Kelly Fraction": kelly_fraction,
        "Portfolio Kelly Cap": portfolio_kelly_cap,
        "scaling_factor": scaling_factor,
        "max_safe_lot_size": max_safe_lot_size,
        "max_safe_drawdown": total_loss,
        "current_lot_size": ai_strategy["Lot_Size"],
        "current_drawdown": total_loss,
        "martingale_lot_sequence": lots,
        "notes": ai_strategy.get("notes"),
        "calculation_logic": ai_strategy.get("calculation_logic")
    }
```

---

## **5. Integration with portfolio_management.py**

- After `analysis_results`, add a button to trigger the above process.
- Show a results table/DataFrame with scaling and caps.
- Allow user to download/export results or rerun with different caps.

---

## **6. What You Need to Provide**

- Confirm EA spec CSV location in `config.py`
- Confirm OpenRouter API key for user (already provided)
- Confirm pip value table covers all portfolio symbols (already provided)
- Confirm analysis_results is always available after MC/Kelly run (already implemented)
- Add UI/option for adjusting portfolio Kelly Cap if needed

---

## **7. Summary Table**

| Field                   | Source                          | Notes                  |
|-------------------------|---------------------------------|------------------------|
| strategy_name           | AI/SQL                          |                        |
| symbol                  | AI/SQL                          |                        |
| param_array             | SQL                             |                        |
| pip_value               | pip_values table                |                        |
| Kelly Fraction          | analysis_results                |                        |
| Portfolio Kelly Cap     | computed (see above)            |                        |
| martingale_lot_sequence | AI batch output                 |                        |
| scaling_factor          | computed                        |                        |
| max_safe_lot_size       | computed                        |                        |
| max_safe_drawdown       | computed                        |                        |
| notes, calculation_logic| AI output                       |                        |

---

*This design covers all requirements for robust, auditable, and portfolio-aware EA scaling for risk management and optimization.*