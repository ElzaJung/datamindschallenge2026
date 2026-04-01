"""
Phase 2, Step 4 — Loyalty Segment Analysis (Platform Capability Demo)
Demonstrates how the platform would segment loyal vs. non-loyal customers
when a café connects real loyalty program data. The loyalty_customer column
in the demo data is randomly assigned (30/70 split) with no built-in
behavioral differences — results here illustrate the analysis structure,
not real findings.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats

# ── Load data ────────────────────────────────────────────────────────────────
df = pd.read_csv("synthetic_pos_reviews.csv", parse_dates=["transaction_date"])

DOW_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
CAFES = sorted(df["restaurant_name"].unique())

# ── 1. Segment comparison table ──────────────────────────────────────────────
print("=" * 72)
print("LOYALTY SEGMENT ANALYSIS — PLATFORM CAPABILITY DEMO")
print("=" * 72)
print("  NOTE: loyalty_customer is randomly assigned in the demo data.")
print("  With real loyalty program data, these metrics would reveal actual")
print("  behavioral differences between segments.")
print()

for cafe in CAFES:
    cafe_df = df[df["restaurant_name"] == cafe]
    loyal = cafe_df[cafe_df["loyalty_customer"] == "Yes"]
    non_loyal = cafe_df[cafe_df["loyalty_customer"] == "No"]

    print(f"{'─' * 72}")
    print(f"  {cafe}")
    print(f"{'─' * 72}")
    print(f"  {'Metric':<30s} {'Loyal':>10s} {'Non-Loyal':>10s} {'Delta':>10s}")
    print(f"  {'─'*30} {'─'*10} {'─'*10} {'─'*10}")

    metrics = [
        ("Customers", len(loyal), len(non_loyal)),
        ("% of transactions", f"{len(loyal)/len(cafe_df)*100:.1f}%",
         f"{len(non_loyal)/len(cafe_df)*100:.1f}%"),
        ("Avg transaction ($)", loyal["total_sale"].mean(), non_loyal["total_sale"].mean()),
        ("Avg quantity", loyal["quantity"].mean(), non_loyal["quantity"].mean()),
        ("Avg sentiment", loyal["sentiment_score"].mean(), non_loyal["sentiment_score"].mean()),
        ("Total revenue ($)", loyal["total_sale"].sum(), non_loyal["total_sale"].sum()),
    ]

    for name, lval, nlval in metrics:
        if isinstance(lval, str):
            print(f"  {name:<30s} {lval:>10s} {nlval:>10s} {'':>10s}")
        elif isinstance(lval, (int, np.integer)):
            print(f"  {name:<30s} {lval:>10,d} {nlval:>10,d} {lval - nlval:>+10,d}")
        else:
            print(f"  {name:<30s} {lval:>10.2f} {nlval:>10.2f} {lval - nlval:>+10.2f}")
    print()

    # Statistical test: is there a difference in avg transaction value?
    t_stat, p_val = stats.ttest_ind(loyal["total_sale"], non_loyal["total_sale"])
    print(f"  t-test (avg transaction): t={t_stat:.3f}, p={p_val:.3f}")
    if p_val < 0.05:
        print(f"  → Statistically significant difference (p < 0.05)")
    else:
        print(f"  → No significant difference (p = {p_val:.3f}) — expected with demo data")
    print()

# ── 2. Visualization: segment comparison ────────────────────────────────────
fig, axes = plt.subplots(1, 3, figsize=(18, 5))
fig.suptitle("Loyalty Segment Comparison — Platform Demo",
             fontsize=14, fontweight="bold", y=1.02)

for ax, cafe in zip(axes, CAFES):
    cafe_df = df[df["restaurant_name"] == cafe]
    segment_stats = cafe_df.groupby("loyalty_customer").agg(
        avg_sale=("total_sale", "mean"),
        avg_sentiment=("sentiment_score", "mean"),
        transaction_count=("total_sale", "count"),
    ).reindex(["Yes", "No"])

    x = np.arange(3)
    width = 0.35
    vals_loyal = [
        segment_stats.loc["Yes", "avg_sale"],
        segment_stats.loc["Yes", "avg_sentiment"] * 10,  # scale for visibility
        segment_stats.loc["Yes", "transaction_count"] / 100,  # scale
    ]
    vals_non = [
        segment_stats.loc["No", "avg_sale"],
        segment_stats.loc["No", "avg_sentiment"] * 10,
        segment_stats.loc["No", "transaction_count"] / 100,
    ]

    bars1 = ax.bar(x - width/2, vals_loyal, width, label="Loyal", color="steelblue")
    bars2 = ax.bar(x + width/2, vals_non, width, label="Non-Loyal", color="lightcoral")
    ax.set_title(cafe, fontsize=11, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(["Avg Sale ($)", "Sentiment (×10)", "Txns (÷100)"])
    ax.legend(fontsize=8)

plt.tight_layout()
plt.savefig("loyalty_segment_comparison.png", dpi=150, bbox_inches="tight")
plt.show()
print("Saved: loyalty_segment_comparison.png\n")

# ── 3. Visit frequency by day of week ────────────────────────────────────────
fig2, axes2 = plt.subplots(1, 3, figsize=(18, 5))
fig2.suptitle("Visit Patterns by Loyalty Status — Platform Demo",
              fontsize=14, fontweight="bold", y=1.02)

for ax, cafe in zip(axes2, CAFES):
    cafe_df = df[df["restaurant_name"] == cafe]
    dow_loyalty = (
        cafe_df.groupby(["day_of_week", "loyalty_customer"])
        .size()
        .unstack(fill_value=0)
        .reindex(DOW_ORDER)
    )
    dow_loyalty.plot(kind="bar", ax=ax, color=["lightcoral", "steelblue"])
    ax.set_title(cafe, fontsize=11, fontweight="bold")
    ax.set_xlabel("Day of Week")
    ax.set_ylabel("Transactions")
    ax.legend(["No", "Yes"], title="Loyal", fontsize=8)
    ax.tick_params(axis="x", rotation=45)

plt.tight_layout()
plt.savefig("loyalty_visit_patterns.png", dpi=150, bbox_inches="tight")
plt.show()
print("Saved: loyalty_visit_patterns.png\n")

# ── 4. LTV framing ──────────────────────────────────────────────────────────
print("=" * 72)
print("LTV FRAMEWORK — WHAT THIS ANALYSIS ENABLES WITH REAL DATA")
print("=" * 72)
print("""
  With real loyalty program data connected, this analysis would answer:

  1. RETENTION VALUE
     How much more does a loyal customer spend per visit?
     What is the revenue at risk if loyal customers churn?

  2. VISIT FREQUENCY
     Do loyal customers visit more often? On which days?
     Can staffing/promotions be timed to loyal customer patterns?

  3. SATISFACTION GAP
     Do loyal customers have higher or lower sentiment?
     Are loyal customers more forgiving of service issues?

  4. PRODUCT PREFERENCES
     Do loyal customers buy higher-margin products?
     Can product recommendations be personalized by segment?

  For Sun Life context: this maps directly to customer segmentation,
  lifetime value modeling, and churn risk assessment — the same
  frameworks used in insurance retention analysis.
""")
