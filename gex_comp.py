# core GEX calculation funcs. no I/O.
# take a DataFrame of option contracts in, return daily GEX values out

#  defines per-contract dollar gamma using the standard formula
#  gamma times open interest times 100 times spot squared times 0.01
# aggregates contract-level dollar gamma into a daily per-ticker GEX time series.
#  rolling z-score anomalies
import pandas as pd
import numpy as np

def compute_dollar_gamma(df: pd.DataFrame, spot_col: str = "spot") -> pd.Series:
    """
    compute per-contract dollar gamma
    DollarGamma = gamma * oi * 100 * spot^2 * 0.01
    
    interpretation: dollars of underlying that dealers must trade
    to stay hedged on this contract, per 1% move in the underlying.
    """
    # takes DataFrame of options and returns a Series of dollar gamma values
    # the atomic unit of GEX

    dollar_gamma = (
        # per-share gamma from OptionMetrics
        df["gamma"]                
        # number of contracts outstanding
        * df["open_interest"]      
        # shares per contract
        * 100                      
        # spot price squared converts to $ per 1% move
        * df[spot_col] ** 2        
        # scaling so result reads as "$ hedged per 1% move"
        * 0.01                    
    )
    # multiplication of the formula's pieces
    return dollar_gamma

# signs the dollar gamma based on call/put
def apply_dealer_sign(df: pd.DataFrame, dollar_gamma: pd.Series) -> pd.Series:
    """
    apply dealer sign convention: dealers long calls, short puts.
    
    calls contribute +dollar_gamma (dealers long -> positive gamma)
    puts contribute -dollar_gamma (dealers short -> negative gamma)
    """

    signed = np.where(
        df["cp_flag"] == "C",     
        dollar_gamma,          
        -dollar_gamma         
    )

    # wrap the numpy array back into pandas Series
    return pd.Series(signed, index=df.index, name="signed_dollar_gamma")

# Roll up the contract-level data to daily per-ticker GEX
def compute_ticker_gex(df: pd.DataFrame, spot_col: str = "spot") -> pd.DataFrame:
    """
    Aggregate per-contract signed dollar gamma -> daily per-ticker GEX
    
    Input:  DataFrame with one row per contract per day
    Output: DataFrame with one row per ticker per day, containing GEX
    """

    df = df.copy()

    # Add the per-contract dollar gamma column.
    df["dollar_gamma"] = compute_dollar_gamma(df, spot_col=spot_col)

    df["signed_dollar_gamma"] = apply_dealer_sign(df, df["dollar_gamma"])

    # group by (ticker, date) then sum signed dollar gamma across all contracts in each group
    gex_daily = (
        df.groupby(["ticker", "date"])["signed_dollar_gamma"]
          .sum()
          .reset_index()
          .rename(columns={"signed_dollar_gamma": "gex"})
    )

    return gex_daily


def compute_anomalies(gex_df: pd.DataFrame,
                      level_window: int = 60,
                      vol_window: int = 10) -> pd.DataFrame:
    """
    Compute z-score anomalies on the GEX series.
    
    z_level: how unusual is today's GEX vs. its trailing 60-day distribution
    z_vol:   how unusual is today's GEX volatility vs. its own 60-day distribution
    """

    df = gex_df.copy().sort_values(["ticker", "date"]).reset_index(drop=True)
    # sort by ticker then date, ascending

    df["gex_60d_mean"] = (
        df.groupby("ticker")["gex"]
          .transform(lambda x: x.rolling(level_window, min_periods=level_window // 2).mean())
    )
    # 60-day rolling mean of GEX, computed within each ticker

    df["gex_60d_std"] = (
        df.groupby("ticker")["gex"]
          .transform(lambda x: x.rolling(level_window, min_periods=level_window // 2).std())
    )
    # 60-day rolling standard deviation of GEX, per ticker

    df["z_level"] = (df["gex"] - df["gex_60d_mean"]) / df["gex_60d_std"]
    # Z-score of today's GEX vs. its trailing 60-day distribution

    df["gex_10d_vol"] = (
        df.groupby("ticker")["gex"]
          .transform(lambda x: x.rolling(vol_window, min_periods=vol_window // 2).std())
    )
    # 10-day rolling stdev of GEX itself

    df["gex_10d_vol_60d_mean"] = (
        df.groupby("ticker")["gex_10d_vol"]
          .transform(lambda x: x.rolling(level_window, min_periods=level_window // 2).mean())
    )
    df["gex_10d_vol_60d_std"] = (
        df.groupby("ticker")["gex_10d_vol"]
          .transform(lambda x: x.rolling(level_window, min_periods=level_window // 2).std())
    )
    # 60-day mean and stdev of the 10-day GEX vol

    df["z_vol"] = (df["gex_10d_vol"] - df["gex_10d_vol_60d_mean"]) / df["gex_10d_vol_60d_std"]
    # Z-score of recent GEX volatility vs. own history
    return df


if __name__ == "__main__":
    print("Self-test with synthetic data...")

    fake = pd.DataFrame({
        "ticker": ["SPY"] * 4,
        "date": pd.to_datetime(["2024-01-02"] * 4),
        "cp_flag": ["C", "C", "P", "P"],
        "strike_price": [470000, 480000, 470000, 460000],
        "gamma": [0.015, 0.012, 0.014, 0.010],
        "open_interest": [10000, 8000, 12000, 6000],
        "spot": [475.0, 475.0, 475.0, 475.0],
    })
    result = compute_ticker_gex(fake)
    print("Per-ticker GEX:")
    print(result)