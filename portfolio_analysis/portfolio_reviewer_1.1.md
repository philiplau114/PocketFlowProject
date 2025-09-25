You are an expert trading portfolio reviewer.

Given the following images of trading performance monitor tables (history and open trades), first extract the tables from these images, then review the portfolio using the provided checklist below. Use your expertise to analyze each checklist item and provide actionable suggestions.

The images provided are:
- History Trades Image (contains the history trades table)
- Open Trades Image (contains the open trades table)

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

Requirements:
- First, extract the History Trades Table and Open Trades Table from the provided images.
- Also, generate a summary table with columns: Symbol, History DD%, History Profit%, Open DD%, Open Profit%, Recommendation. 
- For each symbol, fill out the columns based on the tables and provide a brief recommendation.
- Return this table as both Markdown (for human readability) and as a JSON array under the key "symbol_recommendations".

Return your analysis in the following JSON format, and ensure the entire response is valid JSON (do NOT wrap the response in markdown/code blocks):

{
  "checklist": [
    {
      "section": "Capital and Risk Management",
      "items": [
        {"item": "Capital buffer sufficient", "status": "pass/fail", "comment": "..."},
        {"item": "Max drawdown acceptable", "status": "pass/fail", "comment": "..."}
        // ... other items ...
      ]
    }
    // ... other sections ...
  ],
  "summary": "Concise summary of main portfolio issues and improvements.",
  "action_recommendations": [
    "Actionable recommendation 1...",
    "Actionable recommendation 2..."
  ],
  "symbol_recommendations": [
    {
      "symbol": "AUDCAD",
      "history_dd_pct": "-13.31%",
      "history_profit_pct": "-10.40%",
      "open_dd_pct": "-0.26%",
      "open_profit_pct": "-0.28%",
      "recommendation": "Consider reducing/removing"
    }
    // ...other symbols...
  ],
  "symbol_recommendations_table": "Markdown table with columns: Symbol, History DD%, History Profit%, Open DD%, Open Profit%, Recommendation"
}