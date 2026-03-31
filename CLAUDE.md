# Datathon Project — Café Analytics Platform
Laurier Data Minds Datathon. Deadline: March 31 2026, 11:59 PM.
Category: Consumer Analytics. Judges: Sun Life data science employees.
Presentation: ~10 minutes, slides + live demo. 15 hours remaining.

## Team
2-3 people, one primary contributor (me).

## Data sources
1. `Café Google Review Analysis.ipynb` — 3,000 Google reviews, 3 Toronto cafés (groupmate's — do not modify)
2. `datasets-xlsx/Coffee Shop Data.xlsx` — Kaggle café dataset (Orders, Customers, Products)
3. `generate_synthetic_pos.py` — generates `synthetic_pos_reviews.csv`
4. `synthetic_pos_reviews.csv` — 5,000 rows of merged POS + review data (seed=42)
   **Frame as:** "simulated POS data, representative of what a café owner connects
   to the platform." Fully defensible in judge Q&A.

## Synthetic data columns
transaction_date, hour_of_day, day_of_week, product_ordered, unit_price,
profit, loyalty_customer, quantity, total_sale, Restaurant Name,
Review Date, Rating, sentiment_score, sentiment_label, topic_label,
tag_meal_type, tag_order_type

## What's been built

### Notebook (groupmate's — do not modify)
- Text cleaning → `Review Text Clean`
- Tag extraction → `tag_*` columns
- VADER sentiment → `sentiment_score`, `sentiment_label`
- BERTopic topic modeling → `topic_id`, `topic_label`
- Competitor gap heatmap (sentiment × topic × café)
- Rating trend over time with linear regression per café
- Topic → star rating driver table
- Notebook ends mid-thought — dead-end cells at the end

### Standalone scripts (my work)
- `generate_synthetic_pos.py` → `synthetic_pos_reviews.csv` (5,000 rows)
- `promotion_timing.py` → underperforming windows per café + 2 heatmap PNGs
- `staffing_recommendation.py` → staffing tiers per café + 3 PNGs
- `loyalty_analysis.py` → loyalty segment comparison + 2 PNGs
- `menu_matrix.py` → feature/retire quadrant matrix + 1 PNG

## Key existing findings
- Fahrenheit: rating declining (slope=-0.0048, p=0.000) — statistically significant
- Dineen: 25.1% of reviews in "poor service & strict rules" topic
- "Overall coffee experience" topic: +23.8pp more in 5-star vs 1/2-star reviews
- "Poor service & strict rules": -41.2pp (most negative driver by far)
- `promotion_timing.py` identifies underperforming time windows (bottom-quartile
  revenue hour/day slots per café). This is valid — transaction volume patterns
  are defensible from the synthetic data.
- **Margin caveat:** The `profit` column comes from the Kaggle Products sheet,
  which models wholesale bean retail (6–13% margins by coffee type). Real café
  margins on prepared drinks are 60–80%. These margins cannot support claims
  about discount viability or absolute profitability. However, the *relative*
  ranking (Liberica 13% > Excelsa 11% > Arabica 9% > Robusta 6%) is useful
  for product mix comparisons in Step 2 (menu matrix) and Step 4 (loyalty).
  Do not use margins to answer "should we discount?" — that requires price
  elasticity data (volume response to price changes) which doesn't exist here.

## What still needs to be built (PRIORITY ORDER)

### Phase 1 — ✅ COMPLETE
1. **Underperforming windows analysis** ✅ DONE (`promotion_timing.py`)
   Identifies lowest-revenue hour/day windows per café using transaction volume.
   No margin or discount analysis — the script only finds low-traffic periods.
   What the café does about those windows (staffing, marketing, menu changes)
   is informed by Steps 2–4, not prescribed here.

2. **Menu feature/retire matrix** ✅ DONE (`menu_matrix.py`)
   Keyword-extracts 27 menu items from raw review text, computes mention
   frequency × avg sentiment × relative profit tier. Classifies each item
   into quadrants: FEATURE, HIDDEN GEM, FIX, RETIRE.
   Key findings per café:
   - Fahrenheit: espresso + cappuccino = stars; latte in FIX (high volume,
     lower sentiment); cold brew = hidden gem
   - Dineen: latte dominates (137 mentions) but sentiment only 0.57 (FIX);
     croissant + sandwich strongest food; flat white/hot chocolate → RETIRE
   - Landwer: shakshuka is clear differentiator (44 mentions, 0.78 sent,
     high profit); pita/waffle/falafel/pancake = hidden gems
   Profit axis uses Kaggle wholesale ranking (relative only, not absolute).
   Output: menu_matrix.png + per-café breakdown to stdout.

3. **Staffing recommendation** ✅ DONE (`staffing_recommendation.py`)
   Transaction volume heatmap (hour × day) per café, normalized to staffing
   tiers (2–5 staff) using quartile thresholds (Q25=9, Q50=15, Q75=24 txns/hr).
   Linear regression on hourly demand: all 3 cafés show statistically significant
   declining volume through the day (p<0.001, R²≈0.70–0.75). Outputs: staffing
   table per café per day + weekly staff-hours summary (~336–340 hrs/week).
   Outputs: staffing_volume_heatmap.png, staffing_recommendation_heatmap.png,
   staffing_demand_curve.png.

### Phase 2 — High value
4. **Loyalty segment analysis** ✅ DONE (`loyalty_analysis.py`)
   Platform capability demo. Splits loyal/non-loyal, compares avg transaction,
   sentiment, visit frequency with t-tests. Demo data shows no significant
   differences (expected — loyalty is randomly assigned in generator). Script
   is transparent about this and frames the output as "what this analysis
   enables with real loyalty data." Includes LTV framework section mapping to
   Sun Life language (retention, churn risk, segmentation).
   Outputs: loyalty_segment_comparison.png, loyalty_visit_patterns.png.

5. **LLM insight card** — pass the 3 outputs above to Claude API
   (claude-sonnet-4-20250514, max_tokens=1000). Prompt for a 3-bullet executive
   summary per café. This is the "AI layer" of the product.

6. **Streamlit dashboard** — 5 tabs:
   - Overview (avg ratings, sentiment dist., revenue summary)
   - Reviews Over Time (existing chart)
   - Topic Map (competitor gap heatmap)
   - Sales Intelligence (traffic windows, menu matrix, staffing table)  ← NEW
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
- Data-Driven Thinking → underperforming-windows analysis + staffing
  optimization use real transaction patterns (Steps 1-3). Margin analysis
  is framed as a platform capability, not a claim about these cafés.
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
- Margin caveat: The profit column is from a Kaggle wholesale bean dataset
  (6–13% margins). Real café prepared-drink margins are 60–80%. Do NOT
  present absolute margin numbers as findings. Relative product profitability
  (Liberica > Excelsa > Arabica > Robusta) is valid for menu mix comparisons.
  Never claim the data can answer "should we discount?" — that requires price
  elasticity data which we don't have.

## Decision log — what we investigated and why we changed course
1. **"Price sensitivity" via low revenue × low sentiment** — originally the plan
   was to cross-reference low-revenue windows with sentiment to find "price-
   sensitive" customers. Rejected: low revenue = low foot traffic, not price
   sensitivity. Sentiment measures review tone, not willingness to respond to
   discounts. No causal link established. Reframed to "underperforming windows"
   (defensible) without the price-sensitivity claim (not defensible).
2. **"Promotions aren't viable because margins are 8.5%"** — margin analysis
   showed Kaggle product margins of 6–13%, too thin for discounts. But the
   margins come from the Kaggle Products sheet which models wholesale bean
   retail, not prepared café drinks (real margins: 60–80%). The margin finding
   is an artifact of the source data, not a real insight.
3. **"Can margins absorb a discount?" is the wrong question anyway** — even with
   real margins, knowing there's room to cut price doesn't tell you whether a
   promotion would be profitable. That requires price elasticity data: does a
   10% discount drive enough incremental volume to offset the per-unit loss?
   Are new buyers incremental or would they have paid full price? Does a
   discounted customer return at full price later? None of this exists in the
   data. Removed the margin/discount analysis from promotion_timing.py entirely.
4. **Margins are still useful for relative product profitability** — the ranking
   (Liberica 13% > Excelsa 11% > Arabica 9% > Robusta 6%) is valid for the
   menu feature/retire matrix (Step 2) and loyalty analysis (Step 4), where
   the question is "which products are comparatively more profitable" not
   "can we afford to discount."
5. **What IS defensible from promotion_timing.py:** underperforming-windows
   identification (bottom-quartile revenue hour/day slots per café) uses
   transaction volume patterns which are valid from the synthetic data.
   The staffing recommendation (Step 3) is similarly margin-independent
   and the strongest operational output.

## Tech stack
Python, Jupyter, pandas, VADER, BERTopic, matplotlib/seaborn, Streamlit,
Claude API (claude-sonnet-4-20250514, $50 budget).