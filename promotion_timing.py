"""
Phase 1, Step 1 — Underperforming Time Windows
Uses synthetic_pos_reviews.csv to identify low-traffic hour/day windows per café.
These are periods where the café may want to intervene (staffing, product mix,
marketing) — but this analysis does not prescribe a specific intervention.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

# ── Load data ────────────────────────────────────────────────────────────────
df = pd.read_csv("synthetic_pos_reviews.csv", parse_dates=["transaction_date", "review_date"])

DOW_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
CAFES = df["restaurant_name"].unique()

# ── 1. Revenue heatmap: hour × day per café ──────────────────────────────────
fig, axes = plt.subplots(1, 3, figsize=(20, 6), sharey=True)
fig.suptitle("Hourly Revenue by Day of Week", fontsize=14, fontweight="bold", y=1.02)

for ax, cafe in zip(axes, CAFES):
    cafe_df = df[df["restaurant_name"] == cafe]
    pivot = (
        cafe_df.groupby(["hour_of_day", "day_of_week"])["total_sale"]
        .sum()
        .unstack()
        .reindex(columns=DOW_ORDER)
        .fillna(0)
    )
    sns.heatmap(pivot, annot=True, fmt=".0f", cmap="YlOrRd", ax=ax,
                cbar_kws={"label": "Revenue ($)"})
    ax.set_title(cafe, fontsize=11, fontweight="bold")
    ax.set_ylabel("Hour of Day" if ax == axes[0] else "")
    ax.set_xlabel("Day of Week")

plt.tight_layout()
plt.savefig("promotion_timing_revenue_heatmap.png", dpi=150, bbox_inches="tight")
plt.show()
print("Saved: promotion_timing_revenue_heatmap.png\n")

# ── 2. Sentiment heatmap: hour × day per café ───────────────────────────────
fig2, axes2 = plt.subplots(1, 3, figsize=(20, 6), sharey=True)
fig2.suptitle("Average Sentiment by Hour × Day", fontsize=14, fontweight="bold", y=1.02)

for ax, cafe in zip(axes2, CAFES):
    cafe_df = df[df["restaurant_name"] == cafe]
    pivot = (
        cafe_df.groupby(["hour_of_day", "day_of_week"])["sentiment_score"]
        .mean()
        .unstack()
        .reindex(columns=DOW_ORDER)
        .fillna(0)
    )
    sns.heatmap(pivot, annot=True, fmt=".2f", cmap="RdYlGn", center=0, ax=ax,
                cbar_kws={"label": "Sentiment"})
    ax.set_title(cafe, fontsize=11, fontweight="bold")
    ax.set_ylabel("Hour of Day" if ax == axes2[0] else "")
    ax.set_xlabel("Day of Week")

plt.tight_layout()
plt.savefig("promotion_timing_sentiment_heatmap.png", dpi=150, bbox_inches="tight")
plt.show()
print("Saved: promotion_timing_sentiment_heatmap.png\n")

# ── 3. Identify underperforming windows ──────────────────────────────────────
# Bottom 25% of revenue by hour × day = underperforming slots.
# Group consecutive hours into readable windows.

print("=" * 72)
print("UNDERPERFORMING TIME WINDOWS")
print("=" * 72)

all_recommendations = []

for cafe in CAFES:
    cafe_df = df[df["restaurant_name"] == cafe]

    hourday = (
        cafe_df.groupby(["day_of_week", "hour_of_day"])
        .agg(
            revenue=("total_sale", "sum"),
            transactions=("total_sale", "count"),
            avg_sale=("total_sale", "mean"),
            avg_sentiment=("sentiment_score", "mean"),
        )
        .reset_index()
    )
    hourday["day_of_week"] = pd.Categorical(
        hourday["day_of_week"], categories=DOW_ORDER, ordered=True
    )
    hourday = hourday.sort_values(["day_of_week", "hour_of_day"])

    # Bottom 25% of revenue = underperforming slots
    rev_threshold = hourday["revenue"].quantile(0.25)
    low_rev = hourday[hourday["revenue"] <= rev_threshold].copy()

    # Group consecutive hours into windows
    windows = []
    for day in DOW_ORDER:
        day_slots = low_rev[low_rev["day_of_week"] == day].sort_values("hour_of_day")
        if day_slots.empty:
            continue

        hours = day_slots["hour_of_day"].values
        groups = []
        current_group = [hours[0]]
        for h in hours[1:]:
            if h == current_group[-1] + 1:
                current_group.append(h)
            else:
                groups.append(current_group)
                current_group = [h]
        groups.append(current_group)

        for group in groups:
            window_data = day_slots[day_slots["hour_of_day"].isin(group)]
            windows.append({
                "day": day,
                "start_hour": group[0],
                "end_hour": group[-1] + 1,
                "window": f"{group[0]:02d}:00–{group[-1]+1:02d}:00",
                "total_revenue": window_data["revenue"].sum(),
                "avg_transactions_per_hr": window_data["transactions"].mean(),
                "avg_sentiment": window_data["avg_sentiment"].mean(),
                "hours": len(group),
            })

    windows_df = pd.DataFrame(windows)
    if windows_df.empty:
        continue

    windows_df = windows_df.sort_values("total_revenue").reset_index(drop=True)

    print(f"\n{'─' * 72}")
    print(f"  {cafe}")
    print(f"{'─' * 72}")
    print(f"  Total weekly revenue: ${cafe_df['total_sale'].sum():,.0f}")
    print(f"  Avg transaction: ${cafe_df['total_sale'].mean():.2f}")
    print()

    top_n = min(3, len(windows_df))
    for i in range(top_n):
        w = windows_df.iloc[i]
        print(f"  Window {i+1}: {w['day']} {w['window']} ({w['hours']}h)")
        print(f"    Revenue:      ${w['total_revenue']:,.0f}  (bottom quartile)")
        print(f"    Transactions: ~{w['avg_transactions_per_hr']:.0f}/hour")
        print(f"    Sentiment:    {w['avg_sentiment']:.2f}")
        print()

    top = windows_df.iloc[0]
    rec_text = (
        f"{cafe}: lowest-traffic window is {top['day']}s {top['window']} "
        f"(${top['total_revenue']:,.0f} revenue, "
        f"~{top['avg_transactions_per_hr']:.0f} transactions/hr, "
        f"sentiment {top['avg_sentiment']:.2f})."
    )
    print(f"  ► LOWEST-TRAFFIC WINDOW: {rec_text}")
    all_recommendations.append({"cafe": cafe, "recommendation": rec_text, **top.to_dict()})

# ── 4. Summary ───────────────────────────────────────────────────────────────
print(f"\n{'=' * 72}")
print("SUMMARY — UNDERPERFORMING WINDOWS PER CAFÉ")
print(f"{'=' * 72}")
summary = pd.DataFrame(all_recommendations)[
    ["cafe", "day", "window", "total_revenue", "avg_transactions_per_hr", "avg_sentiment"]
]
summary.columns = ["Café", "Day", "Window", "Revenue ($)", "Txns/hr", "Sentiment"]
print(summary.to_string(index=False))
print()
