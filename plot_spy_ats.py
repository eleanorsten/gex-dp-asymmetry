import pandas as pd
import matplotlib.pyplot as plt


df = pd.read_csv("spy_ats_data.csv", parse_dates=["weekStartDate"])

print(f"Loaded {len(df)} rows from {df['weekStartDate'].min().date()} to {df['weekStartDate'].max().date()}")


fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

axes[0].plot(df["weekStartDate"], df["totalWeeklyShareQuantity"] / 1e6,
             color="#1f4e79", linewidth=1.2)

axes[0].set_title("SPY Weekly ATS Share Volume", fontsize=13, fontweight="bold")

axes[0].set_ylabel("Weekly volume (millions of shares)", fontsize=10)

axes[0].grid(True, alpha=0.3)



axes[1].plot(df["weekStartDate"], df["totalWeeklyTradeCount"] / 1e3,
             color="#8b3a3a", linewidth=1.2)

axes[1].set_title("SPY Weekly ATS Trade Count", fontsize=13, fontweight="bold")
axes[1].set_ylabel("Weekly trade count (thousands)", fontsize=10)
axes[1].set_xlabel("Week", fontsize=10)

axes[1].grid(True, alpha=0.3)



fig.suptitle("SPY Dark Pool Activity (FINRA ATS Transparency)", fontsize=15, fontweight="bold", y=1.00)

plt.tight_layout()



plt.savefig("spy_ats_overview.png", dpi=150, bbox_inches="tight")

print("Saved chart to spy_ats_overview.png")