You are an expert trading portfolio reviewer.

Given the following extracted trading performance tables (history and open trades) from a performance monitor, review the portfolio using the provided checklist below. Use your expertise to analyze each checklist item and provide actionable suggestions.

Performance Monitor Data:
History Trades Table:
{history_table}

Open Trades Table:
{open_table}

Checklist:
1. Capital and Risk Management
   - Is the actual capital requirement for each set appropriate compared to allocated capital? Is there sufficient buffer?
   - Is the maximum drawdown (MDD) within acceptable range?
   - Is leverage usage reasonable and not excessive?
   - Is reserve capital adequate for extreme market scenarios?

2. Positioning
   - Is each set’s lot size proportional to capital?
   - Is any single strategy dragging down overall performance?
   - Is risk distributed evenly, avoiding concentration?

3. Performance
   - Are there enough trades for reliable statistics?
   - Is the profit/loss ratio reasonable?
   - Is trade efficiency (return on capital) satisfactory?
   - Are there any long-term underperforming or high-risk sets that should be removed?

4. Cost Control
   - Are swap costs significantly eroding profits?
   - Is holding period causing excessive swap costs?
   - Are commission costs too high and impacting net profit?

5. Diversification
   - Is there over-concentration in a few currency pairs?
   - Does the portfolio cover multiple major currency zones (USD, EUR, JPY, GBP, AUD, CAD, NZD)?
   - Is there excessive correlation between pairs, causing same-direction risk?

6. Psychology and Discipline
   - Is floating P/L within psychological tolerance?
   - Is there a clear mental stop-loss?
   - Is there evidence of emotional deviation from strategy?
   - Is there a regular (monthly/quarterly) complete review process?

Return your analysis in the following JSON format:
{
  "checklist": [
    {
      "section": "Capital and Risk Management",
      "items": [
        {"item": "Capital buffer sufficient", "status": "pass/fail", "comment": "..."},
        {"item": "Max drawdown acceptable", "status": "pass/fail", "comment": "..."},
        ...
      ]
    },
    // ... other sections ...
  ],
  "summary": "Concise summary of main portfolio issues and improvements.",
  "action_recommendations": [
    "Actionable recommendation 1...",
    "Actionable recommendation 2..."
  ]
}