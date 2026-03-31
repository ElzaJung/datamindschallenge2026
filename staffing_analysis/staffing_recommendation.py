"""
Phase 1, Step 3 — Staffing Recommendation
Uses synthetic_pos_reviews.csv transaction volume (hour × day) to recommend
staffing levels per café. Includes linear regression on hourly demand for
statistical analysis.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats

# ── Load data ────────────────────────────────────────────────────────────────
df = pd.read_csv("../synthetic_pos_reviews.csv", parse_dates=["transaction_date"])

DOW_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
CAFES = sorted(df["restaurant_name"].unique())
HOURS = list(range(7, 21))  # 7 AM – 8 PM

# ── 1. Transaction volume heatmap: hour × day per café ───────────────────────
fig, axes = plt.subplots(1, 3, figsize=(20, 6), sharey=True)
fig.suptitle("Transaction Volume by Hour × Day of Week",
             fontsize=14, fontweight="bold", y=1.02)

volume_pivots = {}
for ax, cafe in zip(axes, CAFES):
    cafe_df = df[df["restaurant_name"] == cafe]
    pivot = (
        cafe_df.groupby(["hour_of_day", "day_of_week"])
        .size()
        .unstack()
        .reindex(index=HOURS, columns=DOW_ORDER)
        .fillna(0)
    )
    volume_pivots[cafe] = pivot
    sns.heatmap(pivot, annot=True, fmt=".0f", cmap="YlOrRd", ax=ax,
                cbar_kws={"label": "Transactions"})
    ax.set_title(cafe, fontsize=11, fontweight="bold")
    ax.set_ylabel("Hour of Day" if ax == axes[0] else "")
    ax.set_xlabel("Day of Week")

plt.tight_layout()
plt.savefig("staffing_volume_heatmap.png", dpi=150, bbox_inches="tight")
plt.show()
print("Saved: staffing_volume_heatmap.png\n")

# ── 2. Map transaction volume → staffing tiers ──────────────────────────────
# Tiers based on transactions per hour. Thresholds derived from the data
# distribution across all cafés.

all_counts = []
for cafe in CAFES:
    cafe_df = df[df["restaurant_name"] == cafe]
    counts = (
        cafe_df.groupby(["day_of_week", "hour_of_day"])
        .size()
        .reset_index(name="txn_count")
    )
    counts["restaurant_name"] = cafe
    all_counts.append(counts)

all_counts_df = pd.concat(all_counts, ignore_index=True)

# Use quartiles to set staffing thresholds
q25 = all_counts_df["txn_count"].quantile(0.25)
q50 = all_counts_df["txn_count"].quantile(0.50)
q75 = all_counts_df["txn_count"].quantile(0.75)

print("=" * 72)
print("STAFFING TIER THRESHOLDS (based on transaction volume distribution)")
print("=" * 72)
print(f"  Q25 = {q25:.0f} txns/hr | Q50 = {q50:.0f} txns/hr | Q75 = {q75:.0f} txns/hr")
print()
print(f"  Tier 2 (min staff):  ≤ {q25:.0f} transactions/hour")
print(f"  Tier 3 (moderate):   {q25:.0f}–{q50:.0f} transactions/hour")
print(f"  Tier 4 (busy):       {q50:.0f}–{q75:.0f} transactions/hour")
print(f"  Tier 5 (peak):       > {q75:.0f} transactions/hour")
print()


def txn_to_staff(txn_count):
    if txn_count <= q25:
        return 2
    elif txn_count <= q50:
        return 3
    elif txn_count <= q75:
        return 4
    else:
        return 5


# ── 3. Staffing table per café ───────────────────────────────────────────────
print("=" * 72)
print("RECOMMENDED STAFFING TABLES")
print("=" * 72)

staffing_pivots = {}
for cafe in CAFES:
    cafe_counts = all_counts_df[all_counts_df["restaurant_name"] == cafe].copy()
    cafe_counts["staff"] = cafe_counts["txn_count"].apply(txn_to_staff)

    pivot = (
        cafe_counts.pivot_table(
            index="hour_of_day", columns="day_of_week",
            values="staff", aggfunc="first"
        )
        .reindex(index=HOURS, columns=DOW_ORDER)
        .fillna(2)
        .astype(int)
    )
    staffing_pivots[cafe] = pivot

    print(f"\n{'─' * 72}")
    print(f"  {cafe}")
    print(f"{'─' * 72}")
    print(pivot.to_string())
    print()

# ── 4. Staffing heatmap ─────────────────────────────────────────────────────
fig2, axes2 = plt.subplots(1, 3, figsize=(20, 6), sharey=True)
fig2.suptitle("Recommended Staffing Levels (2–5 staff)",
              fontsize=14, fontweight="bold", y=1.02)

for ax, cafe in zip(axes2, CAFES):
    sns.heatmap(staffing_pivots[cafe], annot=True, fmt="d",
                cmap="YlOrRd", vmin=2, vmax=5, ax=ax,
                cbar_kws={"label": "Staff"})
    ax.set_title(cafe, fontsize=11, fontweight="bold")
    ax.set_ylabel("Hour of Day" if ax == axes2[0] else "")
    ax.set_xlabel("Day of Week")

plt.tight_layout()
plt.savefig("staffing_recommendation_heatmap.png", dpi=150, bbox_inches="tight")
plt.show()
print("Saved: staffing_recommendation_heatmap.png\n")

# ── 5. Linear regression: hourly demand trend ───────────────────────────────
# For each café, regress transaction count on hour_of_day (aggregated across
# all days) to model the daily demand curve. This quantifies the peak/trough
# pattern and provides a statistical test (slope, p-value, R²).

print("=" * 72)
print("LINEAR REGRESSION — HOURLY DEMAND CURVE PER CAFÉ")
print("=" * 72)

fig3, axes3 = plt.subplots(1, 3, figsize=(18, 5), sharey=True)
fig3.suptitle("Hourly Demand Curve with Linear Trend",
              fontsize=14, fontweight="bold", y=1.02)

for ax, cafe in zip(axes3, CAFES):
    cafe_df = df[df["restaurant_name"] == cafe]

    # Transaction count per hour (summed across all days and weeks)
    hourly = cafe_df.groupby("hour_of_day").size().reindex(HOURS, fill_value=0)

    x = np.array(hourly.index)
    y = hourly.values

    slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)

    ax.bar(x, y, color="steelblue", alpha=0.7, label="Transactions")
    ax.plot(x, intercept + slope * x, color="red", linewidth=2,
            label=f"Trend (slope={slope:.1f}, R²={r_value**2:.2f})")
    ax.set_title(cafe, fontsize=11, fontweight="bold")
    ax.set_xlabel("Hour of Day")
    if ax == axes3[0]:
        ax.set_ylabel("Total Transactions")
    ax.legend(fontsize=8)
    ax.set_xticks(x)

    print(f"\n  {cafe}:")
    print(f"    slope     = {slope:.2f} transactions/hour")
    print(f"    intercept = {intercept:.1f}")
    print(f"    R²        = {r_value**2:.3f}")
    print(f"    p-value   = {p_value:.4f}")
    print(f"    std_err   = {std_err:.2f}")

    if p_value < 0.05:
        direction = "declining" if slope < 0 else "increasing"
        print(f"    → Statistically significant {direction} trend (p < 0.05)")
    else:
        print(f"    → No statistically significant linear trend (p = {p_value:.3f})")

plt.tight_layout()
plt.savefig("staffing_demand_curve.png", dpi=150, bbox_inches="tight")
plt.show()
print("\nSaved: staffing_demand_curve.png\n")

# ── 6. Summary: staff-hours per day ─────────────────────────────────────────
print("=" * 72)
print("SUMMARY — TOTAL STAFF-HOURS PER DAY")
print("=" * 72)

for cafe in CAFES:
    daily_hours = staffing_pivots[cafe].sum()
    print(f"\n  {cafe}:")
    for day in DOW_ORDER:
        print(f"    {day:12s}: {daily_hours[day]:2d} staff-hours")
    print(f"    {'WEEKLY TOTAL':12s}: {daily_hours.sum():2d} staff-hours")
