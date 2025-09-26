import streamlit as st
import pandas as pd
from db_utils import (
    get_db,
    load_available_strategies,
    get_user_portfolios,
    create_portfolio,
    get_portfolio_strategies,
    add_strategy_to_portfolio,
    remove_strategy_from_portfolio,
    get_portfolio_currency_correlation,
    aggregate_correlation,
)
import config
from session_manager import is_authenticated, sync_streamlit_session

import seaborn as sns
import matplotlib.pyplot as plt

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

session = get_db()

# --- Portfolio Creation & Selection ---
st.subheader("Your Portfolios")

user_portfolios = get_user_portfolios(session, username)
if not user_portfolios:
    st.info("You have no portfolio yet.")
    with st.form("create_portfolio_form"):
        portfolio_name = st.text_input("Portfolio Name", value=f"{username}'s Portfolio")
        description = st.text_area("Description", value="")
        create_btn = st.form_submit_button("Create Portfolio")
        if create_btn and portfolio_name:
            new_portfolio = create_portfolio(session, username, portfolio_name, description)
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
st.subheader("Available Strategies")
available_df = load_available_strategies(session)
max_available_page_size = min(50, len(available_df))
available_page_size = st.number_input(
    "Records per page (Available strategies)", 
    min_value=1, 
    max_value=max_available_page_size if max_available_page_size > 0 else 1, 
    value=min(10, max_available_page_size if max_available_page_size > 0 else 1), 
    step=1
)

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
if not portfolio_df.empty:
    if st.button("Download Portfolio Set Files"):
        st.info("Download feature coming soon.")

    st.markdown("**Currency Correlation Assessment:**")
    corr_df = get_portfolio_currency_correlation(session, portfolio.id, timeframe='H1')
    if not corr_df.empty:
        st.write("#### Pairwise Currency Correlations (H1 timeframe)")
        st.data_editor(
            corr_df,
            width="stretch",
            hide_index=True,
            disabled=True,
            key="corr_table"
        )
        agg = aggregate_correlation(corr_df)
        st.write(f"**Average Correlation:** {agg['average_correlation']:.2f}")
        st.write(f"**Max Correlation:** {agg['max_correlation']:.2f}")
        if agg['high_corr_pairs']:
            st.warning(f"Highly correlated pairs (>0.7): {agg['high_corr_pairs']}")
        st.write("#### Correlation Heatmap")
        heatmap_matrix = corr_df.pivot(index="symbol1", columns="symbol2", values="correlation")
        fig, ax = plt.subplots()
        sns.heatmap(heatmap_matrix, annot=True, fmt=".2f", cmap="coolwarm", ax=ax)
        st.pyplot(fig)
    else:
        st.info("No correlation data found for selected strategies.")

    st.markdown("**Position Sizing & Monte Carlo Risk Analysis:**")
    st.info("Position sizing and risk analytics will be shown here.")

st.caption("Manage your strategy portfolio, download set files, and run portfolio analytics. For advanced risk tools, contact admin.")