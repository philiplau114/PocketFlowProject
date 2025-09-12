import numpy as np
import pandas as pd
from scipy.stats import norm

def kelly_fraction(win_rate, avg_win, avg_loss):
    b = avg_win / abs(avg_loss)
    kelly = win_rate - (1 - win_rate) / b
    return max(0, min(kelly, 1))  # Clamp to [0, 1]

def monte_carlo_simulation(win_rate, avg_win, avg_loss, n_trades=1000, n_trials=5000):
    results = []
    for _ in range(n_trials):
        outcomes = np.random.choice(
            [avg_win, -abs(avg_loss)],
            size=n_trades,
            p=[win_rate, 1-win_rate]
        )
        results.append(np.cumsum(outcomes))
    results = np.array(results)
    max_drawdown = np.max(np.maximum.accumulate(results, axis=1) - results, axis=1)
    ruin_prob = np.mean(np.min(results, axis=1) < -1000)  # Example: Ruin threshold
    return {
        "max_drawdown": float(np.median(max_drawdown)),
        "ruin_prob": float(ruin_prob),
        "return_distribution": results[:, -1].tolist()
    }