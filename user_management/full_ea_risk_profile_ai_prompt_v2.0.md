Given the EA specification (EA Spec) and a list of parameter-value pairs for each strategy, please extract and infer all risk-relevant parameters and computed values needed for downstream risk and portfolio calculations.

- EA Spec
- [Insert EA Spec table or summary here]

- Stragey Parameter and Values
- [Insert each strategy’s parameter-value pairs as JSON]

- EAs may use different logic for martingale, grid, or fixed lot orders, and may or may not have parameters like Martingala_Pips, SL_Number_Of_Order, MaxLot, Lot_Size, DrawDown_SL_Money, or custom lots/distances.
- If any item is not present, return `null` and explain in the notes.
- For EAs with no martingale/grid component, return an empty martingale_lot_sequence and set all martingale/grid-specific fields to `null`.
- For any strategy with Lot_Size, Lot_Multiplier, MaxLot, and SL_Number_Of_Order (or equivalent), you must calculate the full martingale_lot_sequence:
    - Start from Lot_Size.
    - For each subsequent order, multiply the previous lot by Lot_Multiplier.
    - If any lot would exceed MaxLot, cap it at MaxLot.
    - Stop when the sequence reaches SL_Number_Of_Order.
    - Output the sequence as an array of floats in martingale_lot_sequence.
- If the EA uses a custom lot sequence (Custom_Lot) or custom pip sequence (Custom_Martingala), use those instead of standard logic and explain in both `notes` and `calculation_logic`.
- Only output an empty martingale_lot_sequence if there is truly no martingale or grid logic in the EA.
- Never skip this calculation if standard martingale parameters are present, even if Custom_Lot is null.
- For each strategy, in addition to the standard fields, include:

- `calculation_logic`: (string) A step-by-step explanation or formula used to compute `martingale_lot_sequence`, referencing parameter names and how MaxLot and SL_Number_Of_Order are applied.
  - Example: "Started with Lot_Size=0.01, multiplied each subsequent lot by Lot_Multiplier=1.8, capped each value at MaxLot=5.0, repeated until SL_Number_Of_Order=10 was reached. Sequence: [0.01, 0.018, ...]."
  - If custom or dynamic logic is used, explain how it was applied.

For each strategy, output:

- `strategy_name`: (string) Unique name or set file identifier.
- `martingale_lot_sequence`: (array of floats or empty) The full progression of lots the EA would use for a new signal, based on the current Lot_Size and parameters.
- `Martingala_Pips`: (float or null) Pips between orders; `null` if not used.
- `SL_Number_Of_Order`: (integer or null) Max open orders before stop; `null` if not used.
- `MaxLot`: (float or null) The max lot size per order, or `null` if not capped.
- `Lot_Size`: (float) The initial lot size or equivalent as used by the EA.
- `DrawDown_SL_Money`: (float or null) Max allowed floating loss for close-all, or `null` if not present.
- `Custom_Lot`: (array of floats or null) If a custom lot sequence is specified, output the array, else `null`.
- `Custom_Martingala`: (array of floats or null) If a custom pip sequence is specified, output the array, else `null`.
- `notes`: (string) Any special logic, missing/ambiguous fields, non-standard EA behavior, or how the lot sequence and parameters were determined.
- `calculation_logic`: (string) Step-by-step, parameter-referenced explanation of how the sequence was calculated, including capping and stop conditions.

- Do **not** include `Pip value` or `Kelly cap` in the output, as these come from your lookup table/risk model.

**Output Format:**
Return a JSON array, one object per strategy. Example:
```json
[
  {
    "strategy_name": "A Strategy Name",
    "martingale_lot_sequence": [0.01, 0.018, 0.0324, 0.05832, 0.104976, 0.1889568, 0.34012224, 0.612220032, 1.102, 1.984],
    "Martingala_Pips": 15,
    "SL_Number_Of_Order": 10,
    "MaxLot": 5.0,
    "Lot_Size": 0.01,
    "DrawDown_SL_Money": 600,
    "Custom_Lot": null,
    "Custom_Martingala": null,
    "notes": "Standard martingale logic; cap each order at MaxLot param.",
    "calculation_logic": "Started with Lot_Size=0.01. For each subsequent order, multiplied the previous lot by Lot_Multiplier=1.8. If the calculated lot exceeded MaxLot=5.0, capped it at 5.0. Continued until SL_Number_Of_Order=10 was reached. Sequence: [0.01, 0.018, 0.0324, 0.05832, ...]."
  },
  {
    "strategy_name": "GridEA_FixedLots.set",
    "martingale_lot_sequence": [],
    "Martingala_Pips": 20,
    "SL_Number_Of_Order": null,
    "MaxLot": null,
    "Lot_Size": 0.05,
    "DrawDown_SL_Money": null,
    "Custom_Lot": null,
    "Custom_Martingala": null,
    "notes": "Grid system, no martingale logic, no SL_Number_Of_Order or DrawDown_SL_Money.",
    "calculation_logic": "No martingale logic present. Only grid logic used, so martingale_lot_sequence is empty."
  }
]
```
- **Return only the JSON array.**
- If you cannot determine a value for any field, set it to `null` and explain in `notes`.
- If the EA uses custom or dynamic logic, describe it in both `notes` and `calculation_logic`.