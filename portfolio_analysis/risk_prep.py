import pandas as pd

def calculate_kelly_allocation(deposit, kelly_fraction):
    """Return full and half Kelly allocations for a given deposit."""
    full_kelly = deposit * kelly_fraction
    half_kelly = full_kelly / 2
    return {'full_kelly': full_kelly, 'half_kelly': half_kelly}

def calculate_pip_value(pair, lot_size=0.01, account_currency='USD'):
    """
    Simplified pip value calculation for major/minor pairs.
    For more accuracy, use broker API or online calculators.
    """
    # Example for AUDCHF (pip = 0.0001, quote currency = CHF)
    pip = 0.0001
    # Assuming 100,000 units per 1 lot
    units = lot_size * 100_000
    pip_value = units * pip
    # If account currency is quote currency, this is correct.
    # Otherwise, conversion with current fx rate needed.
    # For now, just return pip_value as is (user should verify)
    return pip_value

def prepare_strategy_data(set_file_content, strategy_stats, deposit, kelly_fraction, pair, lot_size=0.01, account_currency='USD'):
    """
    Return all info needed for prompt/LLM/UI for one strategy.
    strategy_stats: dict with keys like 'kelly_fraction', 'mean_return', etc.
    """
    kelly_alloc = calculate_kelly_allocation(deposit, kelly_fraction)
    pip_value = calculate_pip_value(pair, lot_size, account_currency)
    return {
        'set_file': set_file_content,
        'kelly_allocation': kelly_alloc,
        'kelly_fraction': kelly_fraction,
        'deposit': deposit,
        'pair': pair,
        'pip_value_per_001': pip_value,
        'lot_size': lot_size,
        'account_currency': account_currency,
        'stats': strategy_stats
    }

def prepare_portfolio_data(strategies, deposit, account_currency='USD'):
    """
    strategies: list of dict, each with keys:
      - 'set_file_content'
      - 'strategy_stats' (must include 'kelly_fraction')
      - 'pair' (e.g. 'AUDCHF')
      - 'lot_size' (optional, default 0.01)
    Returns: list of dicts, one per strategy, ready for prompt/UI/LLM
    """
    prepared = []
    for strat in strategies:
        d = prepare_strategy_data(
            set_file_content=strat['set_file_content'],
            strategy_stats=strat['strategy_stats'],
            deposit=deposit,
            kelly_fraction=strat['strategy_stats']['kelly_fraction'],
            pair=strat['pair'],
            lot_size=strat.get('lot_size', 0.01),
            account_currency=account_currency
        )
        prepared.append(d)
    return prepared