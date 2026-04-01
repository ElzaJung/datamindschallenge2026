"""
Phase 1, Step 2 — Menu Feature/Retire Matrix
Keyword-extracts menu item mentions from raw Google reviews, cross-references
with avg sentiment and relative profit to produce a 2×2 decision matrix.

Axes:
  x = mention frequency (how often customers talk about it)
  y = avg sentiment of reviews mentioning the item
  bubble size = relative profit tier (from Products sheet coffee type ranking)

Quadrants:
  Top-right (high mentions, high sentiment)  → FEATURE (upsell, promote)
  Top-left  (low mentions, high sentiment)   → HIDDEN GEM (increase visibility)
  Bottom-right (high mentions, low sentiment) → FIX (customers care but are unhappy)
  Bottom-left (low mentions, low sentiment)  → RETIRE (low interest, low satisfaction)
"""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

# ── Load raw reviews ─────────────────────────────────────────────────────────
REVIEW_FILES = {
    "Fahrenheit Coffee": "output/reviews_Fahrenheit_Coffee_1000_reviews.xlsx",
    "Dineen Coffee Co.": "output/reviews_Dineen_Coffee_Co_1000_reviews.xlsx",
    "Cafe Landwer":      "output/reviews_Cafe_Landwer_1000_reviews.xlsx",
}

dfs = []
for cafe, path in REVIEW_FILES.items():
    df = pd.read_excel(path, header=2)
    df["Restaurant Name"] = cafe
    dfs.append(df)

reviews = pd.concat(dfs, ignore_index=True)
reviews = reviews.dropna(subset=["Review Text"])

# ── VADER sentiment per review ───────────────────────────────────────────────
analyzer = SentimentIntensityAnalyzer()
reviews["sentiment_score"] = reviews["Review Text"].apply(
    lambda t: analyzer.polarity_scores(str(t))["compound"]
)

# ── Menu item keyword dictionary ─────────────────────────────────────────────
# Items with >= 5 mentions in the corpus. Grouped into categories for the
# profit mapping. Keywords are matched case-insensitively in review text.
MENU_ITEMS = {
    # Drinks — coffee
    "latte":         {"category": "coffee", "type": "Arabica"},
    "espresso":      {"category": "coffee", "type": "Arabica"},
    "cappuccino":    {"category": "coffee", "type": "Arabica"},
    "americano":     {"category": "coffee", "type": "Robusta"},
    "flat white":    {"category": "coffee", "type": "Arabica"},
    "mocha":         {"category": "coffee", "type": "Excelsa"},
    "drip coffee":   {"category": "coffee", "type": "Robusta"},
    "cold brew":     {"category": "coffee", "type": "Arabica"},
    "iced coffee":   {"category": "coffee", "type": "Robusta"},
    "macchiato":     {"category": "coffee", "type": "Arabica"},
    # Drinks — non-coffee
    "matcha":        {"category": "specialty", "type": "Liberica"},
    "chai":          {"category": "specialty", "type": "Excelsa"},
    "hot chocolate":  {"category": "specialty", "type": "Excelsa"},
    "tea":           {"category": "specialty", "type": "Robusta"},
    # Food
    "croissant":     {"category": "food", "type": "Excelsa"},
    "sandwich":      {"category": "food", "type": "Excelsa"},
    "muffin":        {"category": "food", "type": "Excelsa"},
    "cookie":        {"category": "food", "type": "Robusta"},
    "cake":          {"category": "food", "type": "Excelsa"},
    "salad":         {"category": "food", "type": "Liberica"},
    "eggs":          {"category": "food", "type": "Excelsa"},
    "shakshuka":     {"category": "food", "type": "Liberica"},
    "pita":          {"category": "food", "type": "Robusta"},
    "waffle":        {"category": "food", "type": "Excelsa"},
    "pancake":       {"category": "food", "type": "Excelsa"},
    "falafel":       {"category": "food", "type": "Liberica"},
    "pastry":        {"category": "food", "type": "Excelsa"},
    "toast":         {"category": "food", "type": "Robusta"},
}

# Relative profit tiers from Products sheet (avg margin %)
PROFIT_TIER = {"Liberica": 4, "Excelsa": 3, "Arabica": 2, "Robusta": 1}
PROFIT_LABELS = {4: "High", 3: "Med-High", 2: "Medium", 1: "Low"}

# ── Extract mentions per review ──────────────────────────────────────────────
results = []
text_lower = reviews["Review Text"].str.lower()

for item, meta in MENU_ITEMS.items():
    mask = text_lower.str.contains(item, na=False, regex=False)
    n_mentions = mask.sum()
    if n_mentions < 3:
        continue

    avg_sent = reviews.loc[mask, "sentiment_score"].mean()

    # Per-café breakdown
    per_cafe = reviews.loc[mask].groupby("Restaurant Name").agg(
        mentions=("Review Text", "count"),
        avg_sentiment=("sentiment_score", "mean"),
    )

    results.append({
        "item": item,
        "category": meta["category"],
        "mentions": n_mentions,
        "avg_sentiment": round(avg_sent, 3),
        "profit_tier": PROFIT_TIER[meta["type"]],
        "profit_label": PROFIT_LABELS[PROFIT_TIER[meta["type"]]],
        "per_cafe": per_cafe.to_dict("index"),
    })

menu_df = pd.DataFrame(results).sort_values("mentions", ascending=False).reset_index(drop=True)

# ── Per-café analysis + individual bubble charts ─────────────────────────────
CAFES = ["Fahrenheit Coffee", "Dineen Coffee Co.", "Cafe Landwer"]
CAT_COLORS = {"coffee": "#8B4513", "specialty": "#2E8B57", "food": "#DAA520"}
MIN_MENTIONS = 2  # minimum mentions to include an item for a given café

def classify(row, med_mentions, med_sentiment):
    high_mention = row["mentions"] >= med_mentions
    high_sent = row["avg_sentiment"] >= med_sentiment
    if high_mention and high_sent:
        return "FEATURE"
    elif not high_mention and high_sent:
        return "HIDDEN GEM"
    elif high_mention and not high_sent:
        return "FIX"
    else:
        return "RETIRE"

fig, axes = plt.subplots(1, 3, figsize=(22, 8), sharey=True)
fig.suptitle("Menu Feature / Retire Matrix — Per Café\nMention Frequency × Sentiment × Relative Profit",
             fontsize=14, fontweight="bold", y=1.03)

for ax, cafe in zip(axes, CAFES):
    # Build this café's item table
    cafe_items = []
    for _, row in menu_df.iterrows():
        cafe_data = row["per_cafe"].get(cafe)
        if cafe_data and cafe_data["mentions"] >= MIN_MENTIONS:
            cafe_items.append({
                "item": row["item"],
                "category": row["category"],
                "mentions": cafe_data["mentions"],
                "avg_sentiment": round(cafe_data["avg_sentiment"], 3),
                "profit_tier": row["profit_tier"],
                "profit_label": row["profit_label"],
            })

    cafe_df = pd.DataFrame(cafe_items).sort_values("mentions", ascending=False)
    if cafe_df.empty:
        ax.set_title(f"{cafe}\n(insufficient data)")
        continue

    # Café-specific medians for quadrant lines
    med_mentions = cafe_df["mentions"].median()
    med_sentiment = cafe_df["avg_sentiment"].median()
    cafe_df["quadrant"] = cafe_df.apply(
        classify, axis=1, med_mentions=med_mentions, med_sentiment=med_sentiment
    )

    # Print table
    print(f"{'=' * 72}")
    print(f"  {cafe}")
    print(f"  Median mentions: {med_mentions:.0f}  |  Median sentiment: {med_sentiment:.3f}")
    print(f"{'=' * 72}")
    print(f"  {'Item':<16} {'Mentions':>8} {'Sentiment':>10} {'Profit':>10} {'Action':>12}")
    print(f"  {'-' * 58}")
    for _, r in cafe_df.iterrows():
        print(f"  {r['item']:<16} {r['mentions']:>8} {r['avg_sentiment']:>10.3f} "
              f"{r['profit_label']:>10} {r['quadrant']:>12}")
    print()

    for quad in ["FEATURE", "HIDDEN GEM", "FIX", "RETIRE"]:
        items = cafe_df[cafe_df["quadrant"] == quad]
        if items.empty:
            continue
        print(f"  {quad}:")
        for _, r in items.iterrows():
            print(f"    {r['item']:<16} ({r['mentions']} mentions, "
                  f"sentiment {r['avg_sentiment']:.2f}, profit: {r['profit_label']})")
    print()

    # Plot bubble chart
    colors = [CAT_COLORS[r["category"]] for _, r in cafe_df.iterrows()]
    sizes = [r["profit_tier"] * 120 for _, r in cafe_df.iterrows()]

    ax.scatter(
        cafe_df["mentions"], cafe_df["avg_sentiment"],
        s=sizes, c=colors, alpha=0.7, edgecolors="black", linewidth=0.5,
    )

    for _, r in cafe_df.iterrows():
        ax.annotate(
            r["item"], (r["mentions"], r["avg_sentiment"]),
            textcoords="offset points", xytext=(6, 4), fontsize=7, fontweight="bold",
        )

    ax.axvline(med_mentions, color="gray", linestyle="--", alpha=0.5)
    ax.axhline(med_sentiment, color="gray", linestyle="--", alpha=0.5)

    # Quadrant labels
    x_min, x_max = ax.get_xlim()
    y_min, y_max = ax.get_ylim()
    pad = 0.015
    ax.text(x_max * 0.82, y_max - pad, "FEATURE", fontsize=9, fontweight="bold",
            color="green", alpha=0.6, ha="center")
    ax.text(x_min + (med_mentions - x_min) * 0.35, y_max - pad, "HIDDEN GEM", fontsize=9,
            fontweight="bold", color="blue", alpha=0.6, ha="center")
    ax.text(x_max * 0.82, y_min + pad, "FIX", fontsize=9, fontweight="bold",
            color="red", alpha=0.6, ha="center")
    ax.text(x_min + (med_mentions - x_min) * 0.35, y_min + pad, "RETIRE", fontsize=9,
            fontweight="bold", color="gray", alpha=0.6, ha="center")

    ax.set_title(cafe, fontsize=11, fontweight="bold")
    ax.set_xlabel("Mention Frequency", fontsize=10)
    if ax == axes[0]:
        ax.set_ylabel("Average Sentiment Score", fontsize=10)

# Shared legend on the last axis
cat_handles = [mpatches.Patch(color=c, label=l.title()) for l, c in CAT_COLORS.items()]
size_handles = [plt.scatter([], [], s=tier * 120, c="gray", alpha=0.5,
                            edgecolors="black", linewidth=0.5, label=label)
                for tier, label in sorted(PROFIT_LABELS.items())]
leg1 = axes[2].legend(handles=cat_handles, title="Category", loc="lower right",
                      fontsize=8, title_fontsize=9)
axes[2].add_artist(leg1)
axes[2].legend(handles=size_handles, title="Relative Profit", loc="lower left",
               fontsize=8, title_fontsize=9, labelspacing=1.2)

plt.tight_layout()
plt.savefig("menu_matrix.png", dpi=150, bbox_inches="tight")
plt.show()
print("\nSaved: menu_matrix.png")
