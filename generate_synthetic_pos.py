"""
Synthetic POS + Review data generator for Café Analytics Platform.
Combines Google Review data with Coffee Shop Products to simulate a
real POS-integrated platform. Seed: random_state=42.
"""

import numpy as np
import pandas as pd
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

rng = np.random.default_rng(42)

# ── 1. Load raw review data ──────────────────────────────────────────────────
REVIEW_FILES = {
    "Fahrenheit Coffee":  "output/reviews_Fahrenheit_Coffee_1000_reviews.xlsx",
    "Dineen Coffee Co.":  "output/reviews_Dineen_Coffee_Co_1000_reviews.xlsx",
    "Cafe Landwer":       "output/reviews_Cafe_Landwer_1000_reviews.xlsx",
}

dfs = []
for cafe, path in REVIEW_FILES.items():
    df = pd.read_excel(path, header=2)
    df["Restaurant Name"] = cafe
    dfs.append(df)

reviews = pd.concat(dfs, ignore_index=True)

# Parse dates — some are strings like "2026-03-25", some may be datetimes
reviews["Review Date"] = pd.to_datetime(reviews["Review Date"], errors="coerce")
reviews = reviews.dropna(subset=["Review Date"])

# Clean Rating: strip star characters, coerce to int
reviews["Rating"] = (
    reviews["Rating"]
    .astype(str)
    .str.extract(r"(\d)")[0]
    .astype(float)
    .astype("Int64")
)
reviews = reviews.dropna(subset=["Rating"])
reviews["Rating"] = reviews["Rating"].astype(int)

# ── 2. VADER sentiment ───────────────────────────────────────────────────────
analyzer = SentimentIntensityAnalyzer()

def vader_score(text):
    if pd.isna(text) or str(text).strip() == "":
        return 0.0
    return analyzer.polarity_scores(str(text))["compound"]

print("Running VADER on review text…")
reviews["sentiment_score"] = reviews["Review Text"].apply(vader_score)
reviews["sentiment_label"] = reviews["sentiment_score"].apply(
    lambda s: "positive" if s >= 0.05 else ("negative" if s <= -0.05 else "neutral")
)

# ── 3. Synthetic topic labels (BERTopic-style, matched to known findings) ────
TOPIC_POOL = [
    "Overall coffee experience",
    "Poor service & strict rules",
    "Atmosphere & ambience",
    "Food & pastry quality",
    "Price & value",
    "Wait time & efficiency",
    "Specialty drinks",
    "Loyalty & regulars",
]

# Weight topics per café to mirror known findings
TOPIC_WEIGHTS = {
    "Fahrenheit Coffee":  [0.35, 0.10, 0.15, 0.12, 0.10, 0.08, 0.07, 0.03],
    "Dineen Coffee Co.":  [0.20, 0.25, 0.15, 0.10, 0.08, 0.10, 0.07, 0.05],
    "Cafe Landwer":       [0.30, 0.08, 0.18, 0.16, 0.10, 0.06, 0.08, 0.04],
}

topic_labels = []
for _, row in reviews.iterrows():
    weights = TOPIC_WEIGHTS[row["Restaurant Name"]]
    topic_labels.append(rng.choice(TOPIC_POOL, p=weights))
reviews["topic_label"] = topic_labels

# ── 4. Synthetic tag columns ─────────────────────────────────────────────────
MEAL_TYPES   = ["Breakfast", "Lunch", "Brunch", "Afternoon snack", None]
ORDER_TYPES  = ["Dine-in", "Take out", "Delivery", None]
MEAL_WEIGHTS  = [0.30, 0.25, 0.20, 0.15, 0.10]
ORDER_WEIGHTS = [0.45, 0.40, 0.05, 0.10]

reviews["tag_meal_type"]  = rng.choice(MEAL_TYPES,  size=len(reviews), p=MEAL_WEIGHTS)
reviews["tag_order_type"] = rng.choice(ORDER_TYPES, size=len(reviews), p=ORDER_WEIGHTS)

# ── 5. Review volume ratios → row budget ─────────────────────────────────────
TOTAL_ROWS = 5_000
cafe_counts = reviews["Restaurant Name"].value_counts()
cafe_ratios = cafe_counts / cafe_counts.sum()

row_budget = (cafe_ratios * TOTAL_ROWS).round().astype(int)
# Adjust rounding so sum == 5000
diff = TOTAL_ROWS - row_budget.sum()
row_budget.iloc[0] += diff
print("Row budget per café:", row_budget.to_dict())

# ── 6. Products sheet ────────────────────────────────────────────────────────
products = pd.read_excel("output/Coffee Shop Data.xlsx", sheet_name="Products")

# Map short codes to full names
COFFEE_TYPE_MAP = {"Ara": "Arabica", "Exc": "Excelsa", "Lib": "Liberica", "Rob": "Robusta"}
ROAST_TYPE_MAP  = {"L": "Light", "M": "Medium", "D": "Dark"}

products["Coffee Type Name"] = products["Coffee Type"].map(COFFEE_TYPE_MAP)
products["Roast Type Name"]  = products["Roast Type"].map(ROAST_TYPE_MAP)
products["product_label"] = (
    products["Coffee Type Name"] + " " +
    products["Roast Type Name"]  + " " +
    products["Size"].astype(str) + "kg"
)

# Product weights: latte-ish (Arabica/Excelsa) > cappuccino-ish (Robusta) > other
COFFEE_WEIGHTS = {"Arabica": 0.40, "Excelsa": 0.25, "Robusta": 0.20, "Liberica": 0.15}
products["type_weight"] = products["Coffee Type Name"].map(COFFEE_WEIGHTS)

# Within each coffee type, weight smaller sizes more (typical café behaviour)
SIZE_WEIGHT_MAP = {0.2: 0.35, 0.5: 0.30, 1.0: 0.20, 2.5: 0.15}
products["size_weight"] = products["Size"].map(SIZE_WEIGHT_MAP)
products["product_weight"] = products["type_weight"] * products["size_weight"]
products["product_weight"] /= products["product_weight"].sum()  # normalise

# ── 7. Hour-of-day distribution (realistic café peaks) ───────────────────────
HOURS = list(range(7, 21))  # 7 AM – 8 PM
# Peaks: 7-10 AM, 12-1 PM, 3-4 PM; troughs: mid-morning, early afternoon
HOUR_WEIGHTS_RAW = [
    9, 12, 11, 8,   # 7, 8, 9, 10
    5, 4,           # 11, 12  (wait—12 should be a peak)
    8, 6,           # 12, 13  ← lunch peak
    4, 3,           # 14, 15
    6, 5,           # 15, 16  ← afternoon
    3, 2,           # 17, 18
]
# Redefine cleanly
HOUR_WEIGHTS_RAW = {
    7: 9, 8: 14, 9: 12, 10: 8,   # morning peak
    11: 5,
    12: 9, 13: 7,                 # lunch peak
    14: 4, 15: 6, 16: 5,          # afternoon dip / mini-peak
    17: 4, 18: 3, 19: 2, 20: 2,   # evening
}
hw_arr = np.array([HOUR_WEIGHTS_RAW[h] for h in HOURS], dtype=float)
hw_arr /= hw_arr.sum()

# ── 8. Generate rows per café ────────────────────────────────────────────────
output_rows = []

for cafe, n_rows in row_budget.items():
    cafe_reviews = reviews[reviews["Restaurant Name"] == cafe].reset_index(drop=True)

    # Sample transaction dates uniformly across the café's date range,
    # weighted by day-of-week (weekends busier) — avoids artificial
    # correlation with review_date column.
    date_min = cafe_reviews["Review Date"].min()
    date_max = cafe_reviews["Review Date"].max()
    date_range_days = (date_max - date_min).days
    DOW_WEIGHTS = {"Monday": 0.7, "Tuesday": 0.7, "Wednesday": 1.0,
                   "Thursday": 1.0, "Friday": 1.2, "Saturday": 1.4, "Sunday": 1.4}
    random_days = rng.integers(0, date_range_days, size=n_rows * 3)
    candidates = date_min + pd.to_timedelta(random_days, unit="D")
    dow_weights_arr = np.array([DOW_WEIGHTS[d] for d in pd.DatetimeIndex(candidates).day_name()])
    dow_weights_arr /= dow_weights_arr.sum()
    chosen_idx = rng.choice(len(candidates), size=n_rows, replace=False, p=dow_weights_arr)
    tx_dates = pd.Series(candidates[chosen_idx]).reset_index(drop=True)

    hours = rng.choice(HOURS, size=n_rows, p=hw_arr)

    # transaction_date = normalized date + hour offset (normalize strips any
    # time component from the date before adding hours)
    tx_datetimes = tx_dates.dt.normalize() + pd.to_timedelta(hours, unit="h")

    # Sample products
    prod_indices = rng.choice(
        len(products), size=n_rows, p=products["product_weight"].values
    )
    chosen_products = products.iloc[prod_indices].reset_index(drop=True)

    # Quantity
    qty = rng.choice([1, 2, 3], size=n_rows, p=[0.80, 0.15, 0.05])

    # Loyalty card
    loyalty = rng.choice(["Yes", "No"], size=n_rows, p=[0.30, 0.70])

    # Sample review metadata to attach (not a join — independent sampling)
    review_sample = cafe_reviews.sample(
        n=n_rows, replace=True, random_state=42
    ).reset_index(drop=True)

    chunk = pd.DataFrame({
        "restaurant_name":   cafe,
        "transaction_date":  tx_datetimes.values,
        "hour_of_day":       hours,
        "day_of_week":       pd.DatetimeIndex(tx_datetimes).day_name(),
        # Review-side columns
        "review_date":       review_sample["Review Date"].values,
        "rating":            review_sample["Rating"].values,
        "sentiment_score":   review_sample["sentiment_score"].values,
        "sentiment_label":   review_sample["sentiment_label"].values,
        "topic_label":       review_sample["topic_label"].values,
        "tag_meal_type":     review_sample["tag_meal_type"].values,
        "tag_order_type":    review_sample["tag_order_type"].values,
        # POS-side columns
        "product_ordered":   chosen_products["product_label"].values,
        "coffee_type":       chosen_products["Coffee Type Name"].values,
        "roast_type":        chosen_products["Roast Type Name"].values,
        "size_kg":           chosen_products["Size"].values,
        "unit_price":        chosen_products["Unit Price"].values,
        "profit":            chosen_products["Profit"].values,
        "loyalty_customer":  loyalty,
        "quantity":          qty,
        "total_sale":        (chosen_products["Unit Price"].values * qty).round(2),
        "total_profit":      (chosen_products["Profit"].values * qty).round(4),
    })
    output_rows.append(chunk)

df_final = pd.concat(output_rows, ignore_index=True)
df_final["transaction_date"] = pd.to_datetime(df_final["transaction_date"])
df_final["review_date"]      = pd.to_datetime(df_final["review_date"])

# ── 9. Save ───────────────────────────────────────────────────────────────────
out_path = "synthetic_pos_reviews.csv"
df_final.to_csv(out_path, index=False)
print(f"\nSaved → {out_path}  ({df_final.shape[0]:,} rows × {df_final.shape[1]} cols)")

# ── 10. Sanity checks ─────────────────────────────────────────────────────────
print("\n═══ SHAPE & DTYPES ═══")
print(df_final.shape)
print(df_final.dtypes.to_string())

print("\n═══ SAMPLE (3 rows) ═══")
print(df_final.head(3)[["restaurant_name","transaction_date","hour_of_day",
                         "product_ordered","unit_price","total_sale",
                         "loyalty_customer","rating","sentiment_label"]].to_string())

DOW_ORDER = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]

print("\n═══ AVG DAILY SALES BY DAY_OF_WEEK ═══")
dow_stats = (
    df_final.groupby("day_of_week")["total_sale"]
    .agg(["mean", "sum", "count"])
    .rename(columns={"mean": "avg_sale", "sum": "total_rev", "count": "transactions"})
    .reindex(DOW_ORDER)
    .round(2)
)
print(dow_stats.to_string())

print("\n═══ TOP 5 PRODUCTS BY TOTAL REVENUE ═══")
top5 = (
    df_final.groupby("product_ordered")["total_sale"]
    .sum()
    .sort_values(ascending=False)
    .head(5)
    .reset_index()
    .rename(columns={"total_sale": "total_revenue"})
)
top5["total_revenue"] = top5["total_revenue"].round(2)
print(top5.to_string(index=False))

print("\n═══ CAFÉ DISTRIBUTION ═══")
print(df_final["restaurant_name"].value_counts())
