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

import seaborn as sns
import matplotlib.pyplot as plt

st.set_page_config(page_title="Portfolio Management", layout="wide")
st.title("💼 Portfolio Management")

# --- AUTH CHECK ---
username = st.session_state.get("username")
user_role = st.session_state.get("user_role")
if not username or not user_role or user_role == "Guest":
    st.warning("You must be logged in as a Trader to view this page.")
    st.stop()

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
if not portfolio_df.empty:
    st.dataframe(portfolio_df[["set_file_name", "symbol", "net_profit", "weighted_score", "win_rate"]], use_container_width=True)
    with st.expander("Remove strategies from portfolio"):
        remove_ids = st.multiselect(
            "Select strategies to remove",
            portfolio_df["metric_id"].tolist(),
            format_func=lambda x: portfolio_df[portfolio_df["metric_id"]==x]["set_file_name"].values[0]
        )
        if st.button("Remove Selected"):
            for metric_id in remove_ids:
                remove_strategy_from_portfolio(session, portfolio.id, metric_id)
            st.success("Removed selected strategies.")
            st.rerun()
else:
    st.info("Your portfolio is empty. Add strategies below.")

st.markdown("---")
# --- Available Strategies to Add ---
st.subheader("Available Strategies")
available_df = load_available_strategies(session)
if not available_df.empty:
    # Exclude those already in portfolio
    available_df = available_df[
        ~available_df["metric_id"].isin(
            portfolio_df["metric_id"] if not portfolio_df.empty else []
        )
    ]
    st.dataframe(available_df, use_container_width=True)
    add_ids = st.multiselect(
        "Select strategies to add",
        available_df["metric_id"].tolist(),
        format_func=lambda x: available_df[available_df["metric_id"]==x]["set_file_name"].values[0]
    )
    if st.button("Add Selected"):
        for metric_id in add_ids:
            add_strategy_to_portfolio(session, portfolio.id, metric_id)
        st.success("Added selected strategies to portfolio.")
        st.rerun()
else:
    st.info("No strategies available for portfolio.")

st.markdown("---")
# --- Portfolio Analysis & Tools ---
st.subheader("Portfolio Analysis & Tools")
if not portfolio_df.empty:
    # Example: Download all set files in portfolio
    if st.button("Download Portfolio Set Files"):
        # Placeholder: In real app, bundle files and serve
        st.info("Download feature coming soon.")

    # --- Currency Correlation Assessment ---
    st.markdown("**Currency Correlation Assessment:**")
    corr_df = get_portfolio_currency_correlation(session, portfolio.id, timeframe='H1')
    if not corr_df.empty:
        st.write("#### Pairwise Currency Correlations (H1 timeframe)")
        st.dataframe(corr_df, use_container_width=True)
        agg = aggregate_correlation(corr_df)
        st.write(f"**Average Correlation:** {agg['average_correlation']:.2f}")
        st.write(f"**Max Correlation:** {agg['max_correlation']:.2f}")
        if agg['high_corr_pairs']:
            st.warning(f"Highly correlated pairs (>0.7): {agg['high_corr_pairs']}")
        # --- Heatmap Visualization ---
        st.write("#### Correlation Heatmap")
        # Pivot to symmetric matrix for heatmap
        heatmap_matrix = corr_df.pivot(index="symbol1", columns="symbol2", values="correlation")
        fig, ax = plt.subplots()
        sns.heatmap(heatmap_matrix, annot=True, fmt=".2f", cmap="coolwarm", ax=ax)
        st.pyplot(fig)
    else:
        st.info("No correlation data found for selected strategies.")

    # --- Position sizing & Monte Carlo risk assessment ---
    st.markdown("**Position Sizing & Monte Carlo Risk Analysis:**")
    st.info("Position sizing and risk analytics will be shown here.")

st.caption("Manage your strategy portfolio, download set files, and run portfolio analytics. For advanced risk tools, contact admin.")