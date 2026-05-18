# Data Dictionary

**Project:** Dealer Hedging Pressure & Dark Pool Order Flow
**Author:** El
**Last updated:** 2026-05-01

This document defines every variable, its source, frequency, units, and computation method. All downstream pipeline code should match the specifications below.

---

## 1. Universe Variables

These define which tickers are studied and how they are grouped.

| Variable | Description | Source | Type | Notes |
|---|---|---|---|---|
| `ticker` | Primary stock ticker symbol | datahub.io S&P 500 list | string | Wikipedia-format (uses `.` for share class, e.g. `BRK.B`) |
| `company_name` | Company legal name | datahub.io S&P 500 list | string | |
| `gics_sector` | GICS sector classification (11 categories) | datahub.io S&P 500 list | string | Industrials, Financials, Information Technology, Health Care, Consumer Discretionary, Consumer Staples, Utilities, Real Estate, Materials, Communication Services, Energy |
| `gics_sub_industry` | GICS sub-industry classification | datahub.io S&P 500 list | string | Finer-grained classification, used for robustness checks only |
| `optionmetrics_ticker` | Ticker format for OptionMetrics queries | derived | string | Same as `ticker` |
| `finra_ticker` | Ticker format for FINRA ATS data queries | derived | string | Replaces `.` with `-` (e.g. `BRK.B` → `BRK-B`) |
| `snapshot_date` | Date the universe was snapshotted | system | date | All tickers frozen at this date for the full study |

**Universe size:** 503 tickers (includes multi-class shares like GOOG/GOOGL, FOX/FOXA, NWS/NWSA).

---

## 2. Raw Options Data

Pulled from OptionMetrics IvyDB US via WRDS.

| Variable | Description | Frequency | Units | Notes |
|---|---|---|---|---|
| `secid` | OptionMetrics security ID | static | int | Internal join key |
| `date` | Trading date | daily | date | |
| `cp_flag` | Call/Put indicator | daily | char | 'C' = call, 'P' = put |
| `strike_price` | Strike price | daily | USD | Per share |
| `exdate` | Expiration date | daily | date | |
| `open_interest` | Open interest | daily | contracts | One contract = 100 shares |
| `gamma` | Per-share gamma (from IvyDB) | daily | dimensionless | Computed by OptionMetrics off implied vol surface |
| `impl_volatility` | Implied volatility | daily | decimal | Used by OptionMetrics for gamma calculation |
| `close` | Underlying spot price at close | daily | USD | Joined from CRSP via WRDS |

---

## 3. Computed GEX Variables

Derived in the project pipeline.

| Variable | Description | Frequency | Units | Formula / Notes |
|---|---|---|---|---|
| `dollar_gamma_contract` | Dollar gamma contribution of a single contract | daily | USD per 1% move | `gamma * open_interest * 100 * spot^2 * 0.01` |
| `signed_dollar_gamma` | Dealer-signed dollar gamma | daily | USD per 1% move | `+dollar_gamma_contract` for calls, `−dollar_gamma_contract` for puts (dealer convention: long calls, short puts) |
| `gex_ticker` | Per-ticker daily GEX | daily | USD per 1% move | Sum of `signed_dollar_gamma` over all contracts in chain on that date |
| `gex_sector` | Per-sector daily GEX | daily | USD per 1% move | Sum of `gex_ticker` over all tickers in sector |

**Validation:** `gex_ticker` for SPX must match published SpotGamma/SqueezeMetrics SPX GEX values in sign and order of magnitude before pipeline is approved for downstream use.

---

## 4. Anomaly Variables

Computed per sector (and per ticker for granular analysis).

| Variable | Description | Frequency | Units | Formula / Notes |
|---|---|---|---|---|
| `gex_60d_mean` | 60-day rolling mean of GEX | daily | USD per 1% move | Trailing window |
| `gex_60d_std` | 60-day rolling stdev of GEX | daily | USD per 1% move | Trailing window |
| `z_level` | Level anomaly z-score | daily | dimensionless | `(gex - gex_60d_mean) / gex_60d_std` |
| `gex_10d_realized_vol` | 10-day rolling stdev of GEX | daily | USD per 1% move | Short-window vol |
| `z_vol` | Volatility anomaly z-score | daily | dimensionless | Z-score of `gex_10d_realized_vol` against its own 60-day history |

**Anomaly threshold:** `\|z\| > 2` flags an anomalous observation. `z_level` is the primary signal; `z_vol` is a secondary signal / robustness check.

---

## 5. ATS (Dependent) Variables

Pulled from FINRA ATS Transparency dataset (`ATS_W_SMBL`).

| Variable | Description | Frequency | Units | Notes |
|---|---|---|---|---|
| `week_ending` | Reporting week end date (Friday) | weekly | date | Tier 1 NMS stocks reported with 2-week lag |
| `ats_volume_ticker` | ATS share volume per ticker per week | weekly | shares | Summed across all ATSs |
| `ats_trades_ticker` | ATS trade count per ticker per week | weekly | trade count | |
| `total_volume_ticker` | Total weekly volume (all venues) | weekly | shares | From CRSP via WRDS, used for normalization |
| `ats_share_ticker` | Normalized ATS share | weekly | decimal | `ats_volume_ticker / total_volume_ticker` |
| `ats_volume_sector` | ATS volume aggregated to sector | weekly | shares | Sum across tickers in sector |
| `ats_share_sector` | Sector-level normalized ATS share | weekly | decimal | `ats_volume_sector / total_volume_sector` |

---

## 6. Aligned Panel (Final Modeling Table)

The merged table that goes into all regressions.

| Variable | Description | Frequency | Units | Notes |
|---|---|---|---|---|
| `sector` | GICS sector | weekly | string | Panel grouping variable |
| `week_ending` | Friday of week | weekly | date | Index variable |
| `gex_sector_eow` | End-of-week sector GEX | weekly | USD per 1% move | Friday close value |
| `z_level_lag1` | Level anomaly, lagged 1 week | weekly | dimensionless | Predictor in regression |
| `z_vol_lag1` | Volatility anomaly, lagged 1 week | weekly | dimensionless | Secondary predictor |
| `ats_share_sector` | Sector-normalized ATS share | weekly | decimal | Dependent variable |
| `vix_eow` | VIX index end-of-week | weekly | index points | Control variable |
| `total_volume_sector` | Total sector trading volume | weekly | shares | Control variable |

---

## 7. Scope Notes

**Sample period:** January 2020 – April 2026.
**Granularity:** Both per-ticker and per-sector analysis.
**Survivorship bias:** Universe is current S&P 500 constituents; not point-in-time. Acknowledged as limitation.
**Frequency alignment:** Daily GEX → weekly via Friday end-of-week value. Predictors lagged one week to align with FINRA's 2-week reporting delay.
