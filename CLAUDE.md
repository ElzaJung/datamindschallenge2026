# Datathon Project — Cafe Analytics Platform
Laurier Data Minds Datathon. Deadline: March 31 2026, 11:59 PM.
Category: Consumer Analytics. Judges: Sun Life data science employees.
Presentation: ~10 minutes, slides + live demo.

## Team
2-3 people, everyone contributing. Groupmate wrote the notebook + scraper + original dashboard.

## Critical constraint
**DO NOT modify `Cafe Google Review Analysis.ipynb`.** Groupmate's work. Build new analysis in separate files only.

## Mentor pivot (2026-03-31)
Standalone analysis scripts (revenue heatmaps, staffing tiers, loyalty segments, menu matrix) are **commodity analytics** — a business owner could do this with AI themselves. Not what judges want to see.

**The differentiator is diagnostic intelligence:** detect rating changes over time, cross-reference with reviews from those periods, use Claude API to explain what caused the change and suggest specific operational fixes. Zero vagueness. Zero sycophancy. Feedback must cite actual review quotes.

This is now the centrepiece of the dashboard. Everything else is supporting context.

## Project structure
```
/
├── output/                              <- canonical data (xlsx review files)
├── .streamlit/config.toml
├── streamlit_app.py                     <- MAIN: dashboard + rating change diagnostic
├── Cafe Google Review Analysis.ipynb    <- groupmate's notebook (DO NOT MODIFY)
├── Review_Scrapper/                     <- groupmate's Playwright scraper
├── generate_synthetic_pos.py            <- generates synthetic_pos_reviews.csv
├── synthetic_pos_reviews.csv            <- 5,000 rows merged POS + review data (seed=42)
├── menu_matrix.py + menu_matrix.png     <- per-cafe menu quadrant analysis
├── loyalty_analysis.py + 2 PNGs         <- loyalty segment comparison
├── in-company-analysis/
│   ├── revenue_and_sentiment_analysis/  <- promotion timing script + PNGs
│   └── menu_analysis/                   <- empty
├── staffing_analysis/                   <- staffing recommendation script + PNGs
├── datasets-csv/                        <- empty
├── requirements.txt
└── CLAUDE.md
```

## What's been built

### Rating Change Diagnostic (centrepiece feature, in `streamlit_app.py`)
- `detect_rating_changes()` — computes month-over-month rating diff per cafe, flags |change| >= 0.3
- `DIAGNOSTIC_SYSTEM_PROMPT` — anti-sycophancy rules: must cite quotes, exact numbers, no preamble, blind spots section
- `get_diagnostic()` — cached Claude API call (`claude-sonnet-4-20250514`, max_tokens=800)
  - Sparse data tiers: <3 text reviews = block, 3-9 = caveat, 10+ = full analysis
  - Caps at 300 most recent reviews per API call
- UI: auto-detected changes shown as selectable list below trend chart, "Diagnose This Change" button, results rendered inline
- API key: checks `ANTHROPIC_API_KEY`, falls back to `MAC_ANTHROPIC_API_KEY` (set in `~/.zshrc`)

### Streamlit dashboard (`streamlit_app.py`)
- Groupmate's original v1 dashboard structure (overview, trend charts, topic analysis)
- Loads review data from `output/` xlsx files (header=2 for metadata rows)
- Rating parsed from raw format like `"4  ****"` via regex `.str.extract(r"(\d)")`
- VADER sentiment computed on load
- My additions: rating change detection + diagnostic UI in left column below trend chart

### Notebook (groupmate's — DO NOT MODIFY)
- 3,000 Google reviews across Fahrenheit Coffee, Dineen Coffee Co., Cafe Landwer
- Text cleaning, tag extraction, VADER sentiment, BERTopic topic modeling
- Competitor gap heatmap, rating trend + linear regression, topic-star driver table
- Ends mid-thought (last cells incomplete)

### Standalone analysis scripts (commodity — supporting context only)
- `generate_synthetic_pos.py` -> `synthetic_pos_reviews.csv` (5,000 rows)
- `in-company-analysis/revenue_and_sentiment_analysis/promotion_timing.py` -> underperforming windows + 2 PNGs
- `staffing_analysis/staffing_recommendation.py` -> staffing tiers + 3 PNGs
- `loyalty_analysis.py` -> loyalty segment comparison + 2 PNGs
- `menu_matrix.py` -> per-cafe feature/retire quadrant matrix + 1 PNG

## Key findings
- Fahrenheit: rating declining (slope=-0.0048, p=0.000) — statistically significant
- Dineen: 25.1% of reviews in "poor service & strict rules" topic
- "Poor service & strict rules": -41.2pp (most negative driver)
- Synthetic data is framed as "simulated POS data, representative of what a cafe owner connects"

## What still needs to be done (PRIORITY ORDER)

### Immediate — test and polish diagnostic feature
1. Run Streamlit, verify diagnostic feature works end-to-end with real API calls
2. Test sparse month (Fahrenheit Sep 2025, ~4 reviews) -> sparsity warning
3. Test dense month (Cafe Landwer Aug 2025, ~125 text reviews) -> full diagnostic
4. Test cache: second Diagnose click should be instant
5. Test missing API key -> graceful degradation

### High priority
6. Slide deck — 8 slides max. Problem -> Approach -> Solution -> Impact.
   Slide titles = business insights, not section labels. One chart per slide.
7. Quantify TAM: ~22,000 independent Canadian cafes, ~$300K avg revenue,
   1-star drop = 5-9% revenue loss (Harvard/Yelp study).
8. Churn risk framing: "Fahrenheit's statistically significant rating decline
   means risk of losing their 4.X star rating in X months."

### Differentiators
9. Scalability narrative — scraper takes any Google Maps URL, pipeline is generic,
   any cafe onboarded in 5 minutes.

### Final prep
10. Re-run notebook end-to-end with random_state=42 on BERTopic (ask groupmate).
11. Rehearse: 2min problem, 2min approach, 3min demo (Streamlit), 2min impact, 1min next steps.

## Rubric mapping
- Problem Clarity -> TAM number on slide 1
- Business Impact -> churn risk framing + diagnostic feature
- Feasibility -> working scraper + live Streamlit demo
- Data-Driven Thinking -> rating change detection with statistical backing
- Innovation -> Claude API diagnostic (anti-sycophantic, citation-backed)
- Scalability -> any-cafe onboarding narrative
- Actionability -> diagnostic reports produce specific decisions, not just charts
- Presentation -> deck + rehearsal

## Framing for judges
- Judges are Sun Life DS employees — they think in customer segments, churn risk, retention value
- Core pitch: "Enterprise chains make decisions with data. Now independent cafes can too."
- The diagnostic feature is the product — it's what separates this from every other team's notebook
- Synthetic data: "simulated POS data, representative of what a cafe owner connects to the platform"
- Data gaps: "the full product ingests live POS exports, loyalty data, and Google reviews automatically"
- Web search was cut — review text is ground truth, defensible to judges

## Decision log
1. **Mentor pivot (2026-03-31)** — standalone analysis scripts are commodity analytics.
   Pivoted to rating-change diagnostic feature as the centrepiece. Analysis scripts kept
   as supporting context but are no longer the focus.
2. **Web search cut** — originally considered supplementing with web data. Cut because
   review text is already the ground truth and is defensible to judges.
3. **Hover-based UI rejected** — Plotly hover events can't trigger custom UI in Streamlit.
   Replaced with auto-detect changes + selectable list + button approach.
4. **Anti-sycophancy prompt** — Claude output must cite specific review quotes, use exact
   numbers, never speculate beyond what reviews say. Includes blind spots section.
5. **Sparse data handling** — <3 text reviews blocks API call, 3-9 adds caveat, 10+ full analysis.
   Prevents hallucination on insufficient data.

## Margin caveat
The `profit` column in synthetic data comes from a Kaggle wholesale bean dataset (6-13% margins).
Real cafe prepared-drink margins are 60-80%. Do NOT present absolute margin numbers as findings.
Relative product profitability ranking is valid for menu mix comparisons only.

## Tech stack
Python, Jupyter, pandas, VADER, BERTopic, matplotlib/seaborn, Plotly, Streamlit,
Claude API (claude-sonnet-4-20250514, anthropic SDK, $50 budget).
