You are an expert trading portfolio reviewer.
Given the following extracted trading performance tables (history and open trades) from a performance monitor, review the portfolio using the provided checklist.
Output your analysis in the specified JSON format.

Performance Monitor Data:
History Trades Table:
{history_table}

Open Trades Table:
{open_table}

Checklist:

1. Capital and Risk Management
   - Check each set's actual capital requirement vs allocated capital. Ensure sufficient buffer.
   - Confirm if maximum drawdown (MDD) is acceptable.
   - Evaluate leverage usage.
   - Assess reserve capital adequacy.

2. Positioning
   - Lot size proportionality.
   - Single-strategy drag.
   - Balance of risk.

3. Performance
   - Number of trades/data reliability.
   - Profit/loss ratio.
   - Trade efficiency.
   - Need to remove underperforming/high-risk sets.

4. Cost Control
   - Swap cost impact.
   - Holding period vs swap cost.
   - Commission impact.

5. Diversification
   - Over-concentration in pairs.
   - Coverage of major currencies.
   - Pair correlation.

6. Psychology and Discipline
   - Is floating P/L within tolerance?
   - Clear mental stop-loss?
   - Emotional deviation from strategy?
   - Regular review?

Please return your analysis in the following JSON format:
{
  "checklist": [
    {
      "section": "Capital and Risk Management",
      "items": [
        {"item": "Check capital requirement vs buffer", "status": "pass/fail", "comment": "..."},
        {"item": "Max drawdown acceptable", "status": "pass/fail", "comment": "..."},
        ...
      ]
    },
    {
      "section": "Positioning",
      "items": [
        ...
      ]
    },
    ...
  ],
  "summary": "Concise summary of main portfolio issues and improvements.",
  "action_recommendations": [
    "Recommendation 1...",
    "Recommendation 2..."
  ]
}