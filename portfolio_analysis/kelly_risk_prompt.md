You are an expert in portfolio and martingale risk analysis for FX EAs.

**EA Parameters:**
- Lot_Size: 0.01 (current), Max possible: 0.0252 (per MaxLot constraint and 10 orders)
- Lot_Multiplier: 1.8
- SL_Number_Of_Order: 10
- MaxLot: 5.0
- DrawDown_SL_Money: 600 (current), recommended: $2,238 (full Kelly), $1,119 (half Kelly)

**Account:**
- Deposit: $10,000

**Market:**
- Pip value per 0.01 lot on AUDCHF: $0.12521

**Portfolio Kelly:**
- Full Kelly allocation: $2,238
- Half Kelly allocation: $1,119

**Martingale sequence for recommended max Lot_Size (10 orders):**
[0.0252, 0.0454, 0.0817, 0.1471, 0.2647, 0.4765, 0.8577, 1.5439, 2.7791, 5.0024]

**Instructions:**
1. For both full and half Kelly, recommend:
   - The max safe initial Lot_Size (do not breach MaxLot at any step)
   - The max safe DrawDown_SL_Money
   - The full martingale lot sequence at that Lot_Size
   - The scaling factor relative to the current Lot_Size and DD stop
2. Explain the reasoning and any caveats, especially regarding pip risk or grid step.

**(Optional: If grid step in pips or basket SL is known, refine the calculation for pip-accurate risk.)**

---