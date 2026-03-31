# Datathon Project — Café Analytics Platform
Laurier Data Minds Datathon. Deadline: March 31 2026, 11:59 PM.
Category: Consumer Analytics. Judges: Sun Life data science employees.
Presentation: ~10 minutes, slides + live demo. 15 hours remaining.

## Team
2-3 people, one primary contributor (me).

## Data sources
1. `Cafe__Google_Review_Analysis.ipynb` — 3,000 Google reviews, 3 Toronto cafés
2. `Coffee_Shop_Data.xlsx` — Kaggle café dataset (Orders, Customers, Products)
3. `generate_synthetic_pos.py` — generates `synthetic_pos_reviews.csv`
4. `synthetic_pos_reviews.csv` — 5,000 rows of merged POS + review data (seed=42)
   **Frame as:** "simulated POS data, representative of what a café owner connects
   to the platform." Fully defensible in judge Q&A.

## Synthetic data columns
transaction_date, hour_of_day, day_of_week, product_ordered, unit_price,
profit, loyalty_customer, quantity, total_sale, Restaurant Name,
Review Date, Rating, sentiment_score, sentiment_label, topic_label,
tag_meal_type, tag_order_type

## What's been built (notebook)
- Text cleaning → `Review Text Clean`
- Tag extraction → `tag_*` columns
- VADER sentiment → `sentiment_score`, `sentiment_label`
- BERTopic topic modeling → `topic_id`, `topic_label`
- Competitor gap heatmap (sentiment × topic × café)
- Rating trend over time with linear regression per café
- Topic → star rating driver table
- **NOTEBOOK ENDS MID-THOUGHT** — needs Phase 1 cells added

## Key existing findings
- Fahrenheit: rating declining (slope=-0.0048, p=0.000) — statistically significant
- Dineen: 25.1% of reviews in "poor service & strict rules" topic
- "Overall coffee experience" topic: +23.8pp more in 5-star vs 1/2-star reviews
- "Poor service & strict rules": -41.2pp (most negative driver by far)

## What still needs to be built (PRIORITY ORDER)

### Phase 1 — Critical (do first, use synthetic_pos_reviews.csv not proxies)
1. **Promotion timing** — use `hour_of_day` + `day_of_week` + `total_sale` from
   synthetic data. Find lowest revenue hour/day per café. Cross with sentiment_score
   to find when customers are most price-sensitive. Output: specific day + hour window
   recommendation per café with supporting revenue numbers. 
   NO LONGER a review volume proxy — use actual transaction data.

2. **Menu feature/retire matrix** — 3-axis output:
   - x: mention frequency (keyword extract from reviews)
   - y: avg sentiment_score for reviews mentioning that item
   - z (bubble size or color): profit from Products sheet via product_ordered
   Top-right + high margin = FEATURE. Low sentiment + low margin = RETIRE.
   This is now a proper business decision tool, not just an NLP output.

3. **Staffing recommendation** — use `hour_of_day` + `day_of_week` + `total_sale`
   from synthetic data. Plot transaction volume heatmap (hour × day). Normalize to
   staffing tiers (2–5 staff). Add linear regression for the Statistical Analysis
   rubric box. Output: staffing table per café per day.
   NO LONGER a review volume proxy — use actual transaction data.

### Phase 2 — High value
4. **Loyalty segment analysis** — split `loyalty_customer` yes/no. Compare avg
   `total_sale`, visit frequency, sentiment_score. Frame as LTV and churn risk
   language for Sun Life judges. This is a free win from the Kaggle data.

5. **LLM insight card** — pass the 3 outputs above to Claude API
   (claude-sonnet-4-20250514, max_tokens=1000). Prompt for a 3-bullet executive
   summary per café. This is the "AI layer" of the product.

6. **Streamlit dashboard** — 5 tabs:
   - Overview (avg ratings, sentiment dist., revenue summary)
   - Reviews Over Time (existing chart)
   - Topic Map (competitor gap heatmap)
   - Sales Intelligence (hourly heatmap, menu matrix, staffing table)  ← NEW
   - Recommendations (LLM insight cards)
   Pre-load synthetic_pos_reviews.csv. No live scraping needed for demo.

7. **Slide deck** — 8 slides max. Problem → Approach → Solution → Impact.
   Slide titles must be business insights not section labels. One chart per slide.

### Phase 3 — Differentiators
8. **Quantify the problem** — ~22,000 independent Canadian cafés, ~$300K avg
   revenue, 1-star drop = 5-9% revenue loss (Harvard/Yelp study). Put on Impact slide.

9. **Churn risk framing** — "Fahrenheit has a statistically significant rating
   decline (slope=-0.0048, p<0.001). Without intervention, at risk of losing their
   4.X star rating in X months." Sun Life judges model risk for a living.

10. **Scalability narrative** — scraper takes any Google Maps URL + any POS CSV.
    Pipeline is generic. Any café onboarded in 5 minutes.

### Phase 4 — Final 2 hours
11. Re-run notebook end-to-end with random_state=42 on BERTopic, clear outputs first.
12. Rehearse: 2min problem, 2min approach, 3min demo (Streamlit), 2min impact, 1min next steps.

## Rubric mapping
- Problem Clarity → TAM number on slide 1
- Business Impact → loyalty LTV + churn risk framing (Steps 4, 9)
- Feasibility → working scraper + live Streamlit demo
- Data-Driven Thinking → 3 insight cells with real transaction data (Steps 1-3)
- Innovation → LLM insight cards + 3-source data fusion (Steps 4, 5)
- Scalability → any-café onboarding narrative (Step 10)
- Actionability → recommendation outputs + next steps slide
- Presentation → deck (Step 7) + rehearsal (Step 12)

## Framing for judges
- Synthetic data: "simulated POS data, representative of what a café owner
  connects to the platform"
- Data gaps: "the full product ingests live POS exports, loyalty program data,
  and Google reviews automatically"
- Sun Life language: retention, LTV, churn risk, customer segmentation
- Core pitch: "Enterprise chains make decisions with data. Now independent
  cafés can too."

## Tech stack
Python, Jupyter, pandas, VADER, BERTopic, matplotlib/seaborn, Streamlit,
Claude API (claude-sonnet-4-20250514, $50 budget).