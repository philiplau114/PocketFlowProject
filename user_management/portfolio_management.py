import streamlit as st
import pandas as pd
from db_utils import (
    get_db,
    fetch_user_by_username,
    get_user_portfolios,
    create_portfolio,
    get_portfolio_strategies,
    add_strategy_to_portfolio,
    remove_strategy_from_portfolio,
    get_portfolio_currency_correlation,
    aggregate_correlation,
)
from position_sizing import kelly_fraction
import config
from session_manager import is_authenticated, sync_streamlit_session

import seaborn as sns
import matplotlib.pyplot as plt
import sqlalchemy
import numpy as np
import os
import requests

# --- Import your TradeRecord ORM/model ---
from db.db_models import TradeRecord

# --- OpenRouter integration ---
def get_open_router_api_key():
    key = st.session_state.get("open_router_api_key")
    if key:
        return key
    username = st.session_state.get("username")
    if username:
        import redis
        r = redis.Redis(host='localhost', port=6379, db=0)
        val = r.get(f"user:{username}:open_router_api_key")
        if val:
            return val.decode()
    return None

def call_openrouter_ai(prompt, api_key, model="gpt-4o"):  # Standardized to gpt-4o
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    data = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a financial risk advisor for trading portfolios."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 800,
        "temperature": 0.7
    }
    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        response.raise_for_status()
        res_json = response.json()
        return res_json["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Could not retrieve AI advice: {e}"

def load_prompt_md(md_path):
    if os.path.exists(md_path):
        with open(md_path, "r", encoding="utf-8") as f:
            return f.read()
    else:
        return None

st.set_page_config(page_title="Portfolio Management", layout="wide")
st.markdown(
    """
    <style>
    .block-container { max-width: 100% !important; padding: 2rem 2rem 2rem 2rem; }
    .element-container { width: 100% !important; }
    .stDataFrame, .stSelectbox, .stDataEditor { width: 100% !important; }
    </style>
    """,
    unsafe_allow_html=True
)
st.title("💼 Portfolio Management")

# --- AUTH CHECK ---
if not is_authenticated(st.session_state):
    st.warning("You must be logged in as a Trader to view this page.")
    st.stop()
sync_streamlit_session(st.session_state, st.session_state["username"])
username = st.session_state.get("username")
user_role = st.session_state.get("user_role")

# --- DB ENGINE ---
if hasattr(config, "SQLALCHEMY_DATABASE_URL") and config.SQLALCHEMY_DATABASE_URL:
    DB_URL = config.SQLALCHEMY_DATABASE_URL
else:
    DB_URL = (
        f"mysql+pymysql://{config.MYSQL_USER}:{config.MYSQL_PASSWORD}"
        f"@{config.MYSQL_HOST}:{config.MYSQL_PORT}/{config.MYSQL_DATABASE}"
    )
engine = sqlalchemy.create_engine(DB_URL)
session = get_db()

# --- Get current user object and user_id ---
user = fetch_user_by_username(session, username)
if not user:
    st.error("User not found.")
    st.stop()
user_id = user.id

# --- Portfolio Creation & Selection ---
st.subheader("Your Portfolios")
user_portfolios = get_user_portfolios(session, user_id)
if not user_portfolios:
    st.info("You have no portfolio yet.")
    with st.form("create_portfolio_form"):
        portfolio_name = st.text_input("Portfolio Name", value=f"{username}'s Portfolio")
        description = st.text_area("Description", value="")
        create_btn = st.form_submit_button("Create Portfolio")
        if create_btn and portfolio_name:
            new_portfolio = create_portfolio(session, user_id, portfolio_name, description)
            if new_portfolio:
                st.success("Portfolio created!")
                st.rerun()
            else:
                st.error("Failed to create portfolio.")
    st.stop()

# Pick portfolio to manage (if multiple, let user pick)
portfolio_options = {p.portfolio_name: p for p in user_portfolios}
portfolio_choice = st.selectbox(
    "Select portfolio to manage",
    list(portfolio_options.keys()),
    index=0
)
portfolio = portfolio_options[portfolio_choice]

st.write(f"**Portfolio:** {portfolio.portfolio_name}")
st.write(f"**Description:** {portfolio.description}")

# --- Strategies in Portfolio & Remove ---
portfolio_df = get_portfolio_strategies(session, portfolio.id)
st.subheader("Strategies in Portfolio")

max_portfolio_page_size = min(50, len(portfolio_df))
portfolio_page_size = st.number_input(
    "Records per page (Portfolio strategies)", 
    min_value=1, 
    max_value=max_portfolio_page_size if max_portfolio_page_size > 0 else 1, 
    value=min(10, max_portfolio_page_size if max_portfolio_page_size > 0 else 1), 
    step=1
)

portfolio_num_pages = max((len(portfolio_df) - 1) // portfolio_page_size + 1, 1)
portfolio_page_num = st.number_input(
    "Portfolio Page", 
    min_value=1, 
    max_value=portfolio_num_pages, 
    value=1, 
    step=1
)
portfolio_start_idx = (portfolio_page_num - 1) * portfolio_page_size
portfolio_end_idx = portfolio_start_idx + portfolio_page_size
portfolio_paged_df = portfolio_df.iloc[portfolio_start_idx:portfolio_end_idx].reset_index(drop=True)

if not portfolio_paged_df.empty:
    max_setfile_len = portfolio_paged_df["set_file_name"].map(len).max() if "set_file_name" in portfolio_paged_df else 20
    setfile_col_width = min(max(200, max_setfile_len * 9), 600)
    st.data_editor(
        portfolio_paged_df[["set_file_name", "symbol", "net_profit", "weighted_score", "win_rate"]],
        width="stretch",
        hide_index=True,
        column_config={"set_file_name": st.column_config.Column(width=setfile_col_width)},
        disabled=True,
        key="portfolio_strategy_table"
    )
    with st.expander("Remove strategies from portfolio"):
        remove_ids = st.multiselect(
            "Select strategies to remove",
            portfolio_paged_df["metric_id"].tolist(),
            format_func=lambda x: portfolio_paged_df[portfolio_paged_df["metric_id"]==x]["set_file_name"].values[0]
        )
        if st.button("Remove Selected"):
            for metric_id in remove_ids:
                remove_strategy_from_portfolio(session, portfolio.id, metric_id)
            st.success("Removed selected strategies.")
            st.rerun()
else:
    st.info("Your portfolio is empty. Add strategies below.")

st.markdown("---")

# --- User Rank for Available Strategies ---
st.sidebar.header("Available Strategies Filter")
available_user_rank = st.sidebar.number_input(
    "Show available strategies with rank (rn):",
    min_value=1,
    value=1,
    step=1,
    help="Show top N available strategies per symbol"
)

def load_available_strategies_with_rank(user_rank):
    query = """
    SELECT
      metric_id,
      set_file_name,
      symbol,
      net_profit,
      max_drawdown,
      total_trades,
      recovery_factor,
      weighted_score,
      normalized_total_distance_to_good,
      win_rate,
      profit_factor,
      expected_payoff,
      status,
      criteria_reason,
      created_at
    FROM (
      SELECT
        id AS metric_id,
        set_file_name,
        symbol,
        net_profit,
        max_drawdown,
        total_trades,
        recovery_factor,
        weighted_score,
        normalized_total_distance_to_good,
        win_rate,
        profit_factor,
        expected_payoff,
        criteria_passed AS status,
        criteria_reason,
        created_at,
        ROW_NUMBER() OVER (
          PARTITION BY v_test_metrics_scored.symbol
          ORDER BY v_test_metrics_scored.normalized_total_distance_to_good,
                   v_test_metrics_scored.weighted_score DESC
        ) AS rn
      FROM v_test_metrics_scored
    ) AS rank_metrics
    WHERE rn <= %s
    ORDER BY normalized_total_distance_to_good, weighted_score DESC
    """
    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params=(user_rank,))
    return df

st.subheader("Available Strategies")
available_df = load_available_strategies_with_rank(available_user_rank)
st.write(f"Number of available strategies found: {len(available_df)} for top {available_user_rank} per symbol")

max_available_page_size = min(50, len(available_df))
default_available_page_size = min(10, max_available_page_size if max_available_page_size > 0 else 1)
available_records_per_page_key = f"available_records_per_page_{len(available_df)}_{available_user_rank}"

available_page_size = st.number_input(
    "Records per page (Available strategies)", 
    min_value=1, 
    max_value=max_available_page_size if max_available_page_size > 0 else 1, 
    value=st.session_state.get("available_page_size", default_available_page_size), 
    step=1,
    key=available_records_per_page_key
)
st.session_state["available_page_size"] = available_page_size

available_num_pages = max((len(available_df) - 1) // available_page_size + 1, 1)
available_page_num = st.number_input(
    "Available Strategies Page", 
    min_value=1, 
    max_value=available_num_pages, 
    value=1, 
    step=1
)
available_start_idx = (available_page_num - 1) * available_page_size
available_end_idx = available_start_idx + available_page_size
available_paged_df = available_df.iloc[available_start_idx:available_end_idx].reset_index(drop=True)

if not available_df.empty:
    available_paged_df = available_paged_df[
        ~available_paged_df["metric_id"].isin(
            portfolio_df["metric_id"] if not portfolio_df.empty else []
        )
    ]
    max_setfile_len_avail = available_paged_df["set_file_name"].map(len).max() if not available_paged_df.empty else 20
    setfile_col_width_avail = min(max(200, max_setfile_len_avail * 9), 600)
    st.data_editor(
        available_paged_df,
        width="stretch",
        hide_index=True,
        column_config={"set_file_name": st.column_config.Column(width=setfile_col_width_avail)},
        disabled=True,
        key="available_strategy_table"
    )
    add_ids = st.multiselect(
        "Select strategies to add",
        available_paged_df["metric_id"].tolist(),
        format_func=lambda x: available_paged_df[available_paged_df["metric_id"]==x]["set_file_name"].values[0]
    )
    if st.button("Add Selected"):
        for metric_id in add_ids:
            add_strategy_to_portfolio(session, portfolio.id, metric_id)
        st.success("Added selected strategies to portfolio.")
        st.rerun()
else:
    st.info("No strategies available for portfolio.")

st.markdown("---")
st.subheader("Portfolio Analysis & Tools")

# --- Currency Correlation Assessment ---
if not portfolio_df.empty:
    st.markdown("**Currency Correlation Assessment:**")
    corr_df = get_portfolio_currency_correlation(session, portfolio.id, timeframe='H1')
    if not corr_df.empty:
        agg = aggregate_correlation(corr_df)
        st.write(f"**Average Correlation:** {agg['average_correlation']:.2f}")
        st.write(f"**Max Correlation:** {agg['max_correlation']:.2f}")
        if agg['high_corr_pairs']:
            st.warning(f"Highly correlated pairs (>0.7): {agg['high_corr_pairs']}")
        st.write("#### Correlation Heatmap")

        def build_symmetric_matrix(corr_df, symbol_list):
            matrix = pd.DataFrame(np.nan, index=symbol_list, columns=symbol_list)
            for _, row in corr_df.iterrows():
                s1, s2, corr = row['symbol1'], row['symbol2'], row['correlation']
                matrix.loc[s1, s2] = corr
                matrix.loc[s2, s1] = corr
            np.fill_diagonal(matrix.values, 1.0)
            return matrix

        symbol_list = sorted(set(corr_df['symbol1']).union(set(corr_df['symbol2'])))
        heatmap_matrix = build_symmetric_matrix(corr_df, symbol_list)
        mask = np.eye(heatmap_matrix.shape[0], dtype=bool)
        fig, ax = plt.subplots()
        sns.heatmap(heatmap_matrix, annot=True, fmt=".2f", cmap="coolwarm", ax=ax, mask=mask)
        st.pyplot(fig)
    else:
        st.info("No correlation data found for selected strategies.")

    st.markdown("**Position Sizing & Monte Carlo Risk Analysis:**")
    # --- Analysis Results and AI Advice ---
    if "df_analysis" in st.session_state:
        df_analysis = st.session_state.df_analysis
        st.dataframe(df_analysis)
        st.info("Kelly and risk metrics are now calculated directly from trade records.")

        st.markdown("---")
        st.markdown("### 💡 Get AI Portfolio Insight")
        prompt_md_path = os.path.join(os.path.dirname(__file__), "portfolio_risk_analysis_v1.0.md")
        base_prompt = load_prompt_md(prompt_md_path)
        if base_prompt:
            table_csv = df_analysis.to_csv(index=False)
            full_prompt = f"{base_prompt}\n\nHere is the risk analysis table for your portfolio strategies as CSV data:\n\n{table_csv}\n\nPlease provide insights and actionable advice for the user."
            if st.button("Get AI Insight"):
                api_key = get_open_router_api_key()
                if api_key:
                    with st.spinner("Getting AI-powered insight..."):
                        ai_advice = call_openrouter_ai(full_prompt, api_key, model="gpt-4o")  # Standardized here too
                    st.session_state.ai_advice = ai_advice
                else:
                    st.warning("No OpenRouter API key found for this user. Please set your API key in your profile/settings.")
        else:
            st.warning("AI prompt file not found. Please check portfolio_risk_analysis_v1.0.md in user_management directory.")

        if "ai_advice" in st.session_state:
            st.markdown("#### AI Portfolio Insight")
            st.write(st.session_state.ai_advice)
    else:
        run_mc_risk_analysis = st.button("Run Position Sizing & Monte Carlo Risk Analysis")
        if run_mc_risk_analysis:
            analysis_results = []
            for idx, row in portfolio_df.iterrows():
                strategy_name = row.get('set_file_name', f"Strategy {idx+1}")
                test_metrics_id = row.get('metric_id') or row.get('test_metrics_id')

                # --- Query all trade records for this strategy ---
                trade_records = session.query(TradeRecord).filter_by(test_metrics_id=test_metrics_id).all()
                profits = [tr.profit for tr in trade_records if tr.profit is not None]
                n_trades = len(profits)

                # --- Calculate win rate, average win, average loss from trade records ---
                win_trades = [p for p in profits if p > 0]
                loss_trades = [p for p in profits if p < 0]
                num_win = len(win_trades)
                num_loss = len(loss_trades)

                win_rate = (num_win / n_trades) if n_trades > 0 else None
                avg_win = np.mean(win_trades) if num_win > 0 else None
                avg_loss = np.mean(loss_trades) if num_loss > 0 else None

                # --- Kelly Fraction ---
                kelly = None
                if win_rate is not None and avg_win is not None and avg_loss is not None and avg_loss != 0:
                    kelly = kelly_fraction(win_rate, avg_win, avg_loss)

                # --- Monte Carlo from trade records (empirical) ---
                if n_trades > 0:
                    def monte_carlo_from_trades(profits, n_trades=1000, n_trials=5000):
                        results = []
                        for _ in range(n_trials):
                            sampled_outcomes = np.random.choice(profits, size=n_trades, replace=True)
                            cum_results = np.cumsum(sampled_outcomes)
                            results.append(cum_results)
                        results = np.array(results)
                        max_drawdown = np.max(np.maximum.accumulate(results, axis=1) - results, axis=1)
                        ruin_prob = np.mean(np.min(results, axis=1) < -1000)
                        return {
                            "max_drawdown": float(np.median(max_drawdown)),
                            "ruin_prob": float(ruin_prob),
                            "return_distribution": results[:, -1].tolist()
                        }
                    mc_results = monte_carlo_from_trades(profits, n_trades=n_trades, n_trials=1000)
                else:
                    mc_results = {"max_drawdown": None, "ruin_prob": None, "return_distribution": []}

                analysis_results.append({
                    'Strategy': strategy_name,
                    'Trades': n_trades,
                    'Win Rate': f"{win_rate*100:.2f}" if win_rate is not None else "N/A",
                    'Avg Win': f"{avg_win:.2f}" if avg_win is not None else "N/A",
                    'Avg Loss': f"{avg_loss:.2f}" if avg_loss is not None else "N/A",
                    'Kelly Fraction': f"{kelly:.2f}" if kelly is not None else "N/A",
                    'Median Max Drawdown': f"{mc_results['max_drawdown']:.2f}" if mc_results['max_drawdown'] is not None else "N/A",
                    'Ruin Probability': f"{mc_results['ruin_prob']:.2%}" if mc_results['ruin_prob'] is not None else "N/A",
                    'Sample Returns': mc_results['return_distribution'][:10]
                })
            st.session_state.analysis_results = analysis_results
            st.session_state.df_analysis = pd.DataFrame(analysis_results)
            st.rerun()
        else:
            st.info("Click to run Position Sizing & Monte Carlo Risk Analysis (may take time).")

else:
    st.info("No strategies available for analysis.")

st.caption("Manage your strategy portfolio, download set files, and run portfolio analytics. For advanced risk tools, contact admin.")