import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as graph_objects
from plotly.subplots import make_subplots
import os
from dotenv import load_dotenv
load_dotenv()
from datetime import datetime
import re
import matplotlib.pyplot as plt
import subprocess
import sys

# Anthropic API for diagnostic feature
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

ANTHROPIC_API_KEY = (
    st.secrets.get("ANTHROPIC_API_KEY")
    or os.environ.get("ANTHROPIC_API_KEY")
    or os.environ.get("MAC_ANTHROPIC_API_KEY")
)

# Set page config
st.set_page_config(page_title="Cafe Review Analysis Dashboard", layout="wide")

# ------------------------------------------------------------------------------
# Data Loading & Processing
# ------------------------------------------------------------------------------

@st.cache_data
def load_data():
    base_path = "output"
    
    all_dfs = []
    # Dynamic loading from output folder
    if os.path.exists(base_path):
        for file in os.listdir(base_path):
            if file.endswith((".xlsx", ".csv")):
                path = os.path.join(base_path, file)
                try:
                    if file.endswith(".csv"):
                        df_temp = pd.read_csv(path)
                    else:
                        df_temp = pd.read_excel(path, header=2)
                    
                    # Ensure columns exist
                    if 'Restaurant Name' not in df_temp.columns:
                        # Try to guess from filename if possible
                        df_temp['Restaurant Name'] = file.split('_')[1].replace('_', ' ') if '_' in file else "Unknown"
                    
                    if 'Category' not in df_temp.columns:
                        df_temp['Category'] = 'Cafe'
                        
                    all_dfs.append(df_temp)
                except Exception as e:
                    st.warning(f"Failed to load {file}: {e}")
            
    if not all_dfs:
        return pd.DataFrame()
        
    df = pd.concat(all_dfs, ignore_index=True)
    
    # Cleaning Review Date
    df['Review Date'] = pd.to_datetime(df['Review Date'], errors='coerce')
    df = df.dropna(subset=['Review Date'])
    
    # Extracting numeric Rating
    def clean_rating(val):
        if pd.isna(val): return None
        # Extract first digit from "5 ★★★★★" or similar
        match = re.search(r'(\d)', str(val))
        return int(match.group(1)) if match else None
        
    df['Rating_Filtered'] = df['Rating'].apply(clean_rating)
    # Fill NA with mean if some are missing or just drop
    df = df.dropna(subset=['Rating_Filtered'])
    
    # Got it from the notebook
    topic_map = {
        'Coffee Experience': ['coffee', 'taste', 'beans', 'espresso', 'latte', 'cappuccino', 'flat white', 'americano'],
        'Staff & Service': ['service', 'staff', 'friendly', 'barista', 'rude', 'knowledgeable', 'waitress', 'help', 'hospitality'],
        'Food & Brunch': ['food', 'breakfast', 'brunch', 'shakshuka', 'sandwich', 'pancake', 'toast', 'eggs', 'bacon', 'avocado'],
        'Vibe & Seating': ['atmosphere', 'space', 'seating', 'cozy', 'loud', 'vibe', 'interior', 'busy', 'decor', 'music'],
        'Wait & Lines': ['wait', 'line', 'lineup', 'busy', 'crowded', 'queue', 'slow', 'fast'],
        'Pastries & Bakery': ['pastry', 'croissant', 'cookie', 'cake', 'muffin', 'baked', 'bakery', 'scone'],
    }
    
    def assign_topic(text):
        if not isinstance(text, str): return "General"
        text = text.lower()
        for topic, keywords in topic_map.items():
            if any(kw in text for kw in keywords):
                return topic
        return "General Experience"
        
    df['assigned_topic'] = df['Review Text'].apply(assign_topic)
    
    # Sentiment Heuristic (if vader isn't present or for speed)
    try:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
        analyzer = SentimentIntensityAnalyzer()
        df['sentiment_score'] = df['Review Text'].apply(lambda x: analyzer.polarity_scores(str(x))['compound'])
    except ImportError:
        # Fallback heuristic based on rating
        df['sentiment_score'] = (df['Rating_Filtered'] - 3) / 2
        
    return df

with st.spinner("Initializing Dashboard..."):
    df = load_data()

if df.empty:
    st.error("Missing data. Please ensure the 'output/' directory contains the cafe review Excel files.")
    st.stop()

# ------------------------------------------------------------------------------
# Rating Change Detection & Diagnostic Functions
# ------------------------------------------------------------------------------

def detect_rating_changes(agg_trend, threshold=0.3):
    """Detect significant month-over-month rating changes per café."""
    changes = []
    for cafe in agg_trend['Restaurant Name'].unique():
        cafe_data = agg_trend[agg_trend['Restaurant Name'] == cafe].sort_values('Period')
        if len(cafe_data) < 2:
            continue
        cafe_data = cafe_data.reset_index(drop=True)
        for i in range(1, len(cafe_data)):
            prev = cafe_data.iloc[i - 1]
            curr = cafe_data.iloc[i]
            change = curr['Rating_Filtered'] - prev['Rating_Filtered']
            if abs(change) >= threshold:
                changes.append({
                    'Cafe': cafe,
                    'Period': curr['Period'],
                    'Prev Period': prev['Period'],
                    'Previous Rating': round(prev['Rating_Filtered'], 2),
                    'New Rating': round(curr['Rating_Filtered'], 2),
                    'Change': round(change, 2),
                    'Direction': 'DROP' if change < 0 else 'SPIKE',
                    'Reviews': int(curr['Reviews']),
                })
    if not changes:
        return pd.DataFrame()
    return pd.DataFrame(changes).sort_values('Change', key=abs, ascending=False).reset_index(drop=True)


DIAGNOSTIC_SYSTEM_PROMPT = """You are a cafe operations analyst reviewing Google reviews. You are blunt, specific, and never vague.

RULES:
1. Every claim MUST cite at least one specific review by quoting the exact text in quotation marks.
2. Use exact numbers: "rating dropped from 4.41 to 2.00" not "ratings declined significantly."
3. If fewer than 5 text reviews exist, state: "Insufficient review text for confident diagnosis. Only N reviews contain text."
4. Never say "consider improving" or "there may be issues." State what the reviews explicitly say.
5. Never speculate about causes not mentioned in the reviews.
6. Do not start with any greeting, preamble, or "Great question." Get straight to the analysis.

OUTPUT FORMAT (follow strictly):

## What Changed
[1 sentence with exact rating numbers and date range]

## Top Causes
1. **[Specific cause from reviews]** (N reviews mention this)
   > "[exact quote from a review]" — [reviewer name], [date]
2. **[Specific cause from reviews]** (N reviews mention this)
   > "[exact quote from a review]" — [reviewer name], [date]
3. **[Specific cause from reviews]** (N reviews mention this)
   > "[exact quote from a review]" — [reviewer name], [date]

## Evidence Strength
[How many reviews with text support this diagnosis vs. total reviews in the period? Is this conclusive or anecdotal? State the numbers.]

## Blind Spots
[What this data does NOT tell you. Be specific: missing data, time gaps, topics not covered by reviews.]

Maximum 400 words."""


@st.cache_data(ttl=3600, show_spinner=False)
def get_diagnostic(cafe_name, period_start_str, period_end_str, rating_before,
                   rating_after, change_value, reviews_list, user_context=""):
    """Call Claude API to diagnose a rating change using the actual reviews."""
    if not ANTHROPIC_AVAILABLE or not ANTHROPIC_API_KEY:
        return "Error: Anthropic SDK not available or API key not set."

    text_reviews = [r for r in reviews_list if r['text'] and str(r['text']).strip() and str(r['text']).lower() != 'nan']
    n_text = len(text_reviews)
    n_total = len(reviews_list)

    if n_text < 3:
        return f"**Insufficient data.** Only {n_text} reviews with text found in this period (minimum 3 required). Try expanding the date range."

    # Format reviews for the prompt
    formatted = []
    for r in text_reviews[:300]:  # safety cap
        formatted.append(f"[{r['date']}] {r['rating']}★ — \"{r['text']}\" — {r['author']}")
    reviews_block = "\n".join(formatted)

    sparsity_note = ""
    if n_text < 10:
        sparsity_note = f"\nNOTE: Only {n_text} reviews with text. Flag low confidence in your Evidence Strength section."

    context_section = ""
    if user_context.strip():
        context_section = f"\nADDITIONAL CONTEXT FROM CAFE OWNER:\n{user_context.strip()}"

    user_message = f"""Analyze this rating change for {cafe_name}:

PERIOD: {period_start_str} to {period_end_str}
RATING CHANGE: {rating_before:.2f} → {rating_after:.2f} ({change_value:+.2f})
TOTAL REVIEWS IN PERIOD: {n_total} ({n_text} with text)
{sparsity_note}{context_section}

REVIEWS:
{reviews_block}"""

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=800,
        system=DIAGNOSTIC_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )
    return response.content[0].text

# ------------------------------------------------------------------------------
# Sidebar
# ------------------------------------------------------------------------------

st.sidebar.title("Dashboard Control")

# Cafe Selection
cafes = sorted(df['Restaurant Name'].unique())
selected_cafes = st.sidebar.multiselect("Select Cafes", cafes, default=cafes)

# Category Selection
cats = sorted(df['Category'].unique().tolist())
selected_cats = st.sidebar.multiselect("Select Categories", cats, default=cats)

# Topic Selection
topics = ["All Topics"] + sorted(df['assigned_topic'].unique().tolist())
# Using st.pills for a modern interactive look
selected_topic = st.sidebar.pills("Selected Topic Perspective", topics, default="All Topics")

# Date range selection
min_date = df['Review Date'].min().to_pydatetime()
max_date = df['Review Date'].max().to_pydatetime()
date_range = st.sidebar.date_input("Filter by Date Range", [min_date, max_date], min_value=min_date, max_value=max_date)

# Apply filters
filtered_df = df[
    (df['Restaurant Name'].isin(selected_cafes)) &
    (df['Category'].isin(selected_cats))
]
if len(date_range) == 2:
    start_date, end_date = date_range
    filtered_df = filtered_df[(filtered_df['Review Date'].dt.date >= start_date) & 
                             (filtered_df['Review Date'].dt.date <= end_date)]

# ------------------------------------------------------------------------------
# Dashboard Title
# ------------------------------------------------------------------------------

st.title("Business Insights Dashboard")
st.caption(f"Analyzing {len(filtered_df)} reviews across {len(selected_cafes)} cafes.")

# ------------------------------------------------------------------------------
# Topic View
# ------------------------------------------------------------------------------

topic_df = filtered_df if selected_topic == "All Topics" else filtered_df[filtered_df['assigned_topic'] == selected_topic]

# Metrics
col1, col2 = st.columns(2)

# Global averages for deltas
global_avg_rating = filtered_df['Rating_Filtered'].mean()
global_avg_count = filtered_df.groupby('Restaurant Name').size().mean()

m_count = len(topic_df)
m_rating = topic_df['Rating_Filtered'].mean()
m_sentiment = topic_df['sentiment_score'].mean()

with col1:
    with st.container(border=True):
        st.metric("Total Volume", f"{m_count}", delta=f"{m_count - int(global_avg_count)} vs benchmark")

with col2:
    with st.container(border=True):
        st.metric("Avg Rating", f"{m_rating:.1f} ★", delta=f"{m_rating - global_avg_rating:.2f} vs avg")

share_data = topic_df.groupby('Restaurant Name').size().reset_index(name='Reviews')
share_fig = px.bar(
    share_data, 
    x='Reviews', y='Restaurant Name', 
    orientation='h',
    color='Restaurant Name',
    color_discrete_sequence=px.colors.qualitative.Bold,
    text_auto=True,
    template="plotly_white"
)
share_fig.update_layout(showlegend=False, height=300, margin=dict(l=0, r=0, t=10, b=0))
st.plotly_chart(share_fig, width='stretch')


# ------------------------------------------------------------------------------
# Trend Over Time
# ------------------------------------------------------------------------------

st.divider()
col_left, col_right = st.columns(2)

with col_left:
    sub_col1, sub_col2 = st.columns([2, 1])
    with sub_col1:
        st.header("How are we trending?")
    with sub_col2:
        time_res = st.selectbox("Granularity", ["Monthly", "Yearly"], index=0)
    freq = 'M' if time_res == "Monthly" else 'Y'

    trend_work = topic_df.copy()
    trend_work['Period'] = trend_work['Review Date'].dt.to_period(freq).dt.to_timestamp()

    agg_trend = trend_work.groupby(['Period', 'Restaurant Name']).agg({
        'Rating_Filtered': 'mean',
        'Review Text': 'count'
    }).reset_index().rename(columns={'Review Text': 'Reviews'})

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    for cafe in selected_cafes:
        c_data = agg_trend[agg_trend['Restaurant Name'] == cafe]
        fig.add_trace(
            graph_objects.Scatter(x=c_data['Period'], y=c_data['Rating_Filtered'], name=f"{cafe} Rating", mode='lines+markers'),
            secondary_y=False
        )
        fig.add_trace(
            graph_objects.Bar(x=c_data['Period'], y=c_data['Reviews'], name=f"{cafe} Vol", opacity=0.2),
            secondary_y=True
        )

    fig.update_layout(
        template="simple_white",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    fig.update_yaxes(title_text="Avg Rating", secondary_y=False, range=[1, 5.2])
    fig.update_yaxes(title_text="Review Volume", secondary_y=True)
    st.plotly_chart(fig, width='stretch')

    # ------------------------------------------------------------------
    # Rating Change Diagnostic (below chart, same column)
    # ------------------------------------------------------------------
    threshold = 0.2 if time_res == "Yearly" else 0.3
    changes_df = detect_rating_changes(agg_trend, threshold=threshold)

    if not changes_df.empty:
        st.subheader("Rating Change Detection")
        st.caption("Significant rating changes detected in the data above. Select one to diagnose with AI.")

        # Format the selectable options
        change_options = []
        for _, row in changes_df.iterrows():
            direction_icon = "📉" if row['Direction'] == 'DROP' else "📈"
            period_str = pd.Timestamp(row['Period']).strftime('%b %Y')
            change_options.append(
                f"{direction_icon} {row['Cafe']}: {row['Previous Rating']:.2f} → {row['New Rating']:.2f} "
                f"({row['Change']:+.2f}) — {period_str} ({row['Reviews']} reviews)"
            )

        selected_change_idx = st.selectbox(
            "Select a rating change to diagnose",
            range(len(change_options)),
            format_func=lambda i: change_options[i],
        )

        selected_change = changes_df.iloc[selected_change_idx]

        user_context = st.text_area(
            "Additional context for the AI (optional)",
            placeholder="e.g., We changed our coffee supplier in August, or We had staff turnover in September...",
            height=80,
        )

        # Check if diagnostic is possible
        can_diagnose = ANTHROPIC_AVAILABLE and ANTHROPIC_API_KEY

        if not can_diagnose:
            st.warning("AI Diagnostic unavailable: set ANTHROPIC_API_KEY or MAC_ANTHROPIC_API_KEY environment variable and install the anthropic package.")

        if st.button("Diagnose This Change", type="primary", disabled=not can_diagnose):
            sel_cafe = selected_change['Cafe']
            sel_period = pd.Timestamp(selected_change['Period'])
            sel_prev_period = pd.Timestamp(selected_change['Prev Period'])

            # Get all reviews in the period range for this café
            period_reviews = topic_df[
                (topic_df['Restaurant Name'] == sel_cafe) &
                (topic_df['Review Date'] >= sel_prev_period) &
                (topic_df['Review Date'] <= sel_period + pd.offsets.MonthEnd(0))
            ].copy()

            reviews_list = []
            for _, rev in period_reviews.iterrows():
                reviews_list.append({
                    'date': rev['Review Date'].strftime('%Y-%m-%d') if pd.notna(rev['Review Date']) else 'Unknown',
                    'rating': rev['Rating_Filtered'] if pd.notna(rev['Rating_Filtered']) else 'N/A',
                    'text': str(rev.get('Review Text', '')) if pd.notna(rev.get('Review Text')) else '',
                    'author': str(rev.get('Author Name', 'Anonymous')) if pd.notna(rev.get('Author Name')) else 'Anonymous',
                })

            n_text = len([r for r in reviews_list if r['text'].strip() and r['text'].lower() != 'nan'])

            with st.spinner(f"Analyzing {len(reviews_list)} reviews ({n_text} with text)..."):
                try:
                    result = get_diagnostic(
                        cafe_name=sel_cafe,
                        period_start_str=sel_prev_period.strftime('%b %Y'),
                        period_end_str=sel_period.strftime('%b %Y'),
                        rating_before=selected_change['Previous Rating'],
                        rating_after=selected_change['New Rating'],
                        change_value=selected_change['Change'],
                        reviews_list=reviews_list,
                        user_context=user_context,
                    )

                    st.divider()
                    direction_label = "Drop" if selected_change['Direction'] == 'DROP' else "Improvement"
                    st.markdown(f"#### Diagnostic: {sel_cafe} — {direction_label}")
                    st.caption(f"Based on {n_text} reviews with text ({len(reviews_list)} total) from {sel_prev_period.strftime('%b %Y')} to {sel_period.strftime('%b %Y')}")

                    if n_text < 10:
                        st.info(f"Low data density: only {n_text} reviews with text. Diagnostic confidence is limited.")

                    st.markdown(result)

                    with st.expander("View raw reviews sent to AI"):
                        review_display = period_reviews[['Review Date', 'Rating_Filtered', 'Review Text', 'Author Name']].copy()
                        review_display = review_display.dropna(subset=['Review Text'])
                        review_display = review_display[review_display['Review Text'].str.strip().str.lower() != 'nan']
                        st.dataframe(review_display, use_container_width=True)

                except Exception as e:
                    st.error(f"API call failed: {e}")

    elif len(agg_trend) > 1:
        st.caption("No significant rating changes detected in the selected period.")

with col_right:
    st.header("In-depth Analysis")
    tab1, tab2, tab3 = st.tabs(["Review Counts", "Average Ratings", "% Share of Voice"])

    def get_matrix(metric):
        if metric == "count":
            return filtered_df.pivot_table(index='assigned_topic', columns='Restaurant Name', values='Review Text', aggfunc='count', fill_value=0)
        elif metric == "rating":
            return filtered_df.pivot_table(index='assigned_topic', columns='Restaurant Name', values='Rating_Filtered', aggfunc='mean', fill_value=0)
        elif metric == "share":
            counts = filtered_df.pivot_table(index='assigned_topic', columns='Restaurant Name', values='Review Text', aggfunc='count', fill_value=0)
            return (counts.div(counts.sum(axis=0), axis=1) * 100).round(1)

    with tab1:
        st.info("**Review Counts**: Measures total interaction volume. Darker blue signifies higher customer engagement in that specific topic.")
        matrix1 = get_matrix("count")
        st.dataframe(matrix1.style.background_gradient(cmap='Blues', axis=1), width='stretch')

    with tab2:
        st.info("**Average Ratings**: Measures quality of experience. Colors range from Red (Lower Ratings / Action Required) to Green (Excellence).")
        matrix2 = get_matrix("rating")
        st.dataframe(matrix2.style.background_gradient(cmap='RdYlGn', axis=1), width='stretch')

    with tab3:
        st.info("**Share of Voice**: Measures the percentage of reviews each cafe captures for a topic. Darker purple indicates market dominance.")
        matrix3 = get_matrix("share")
        st.dataframe(matrix3.style.background_gradient(cmap='Purples', axis=1), width='stretch')



# ------------------------------------------------------------------------------
# Review Explorer
# ------------------------------------------------------------------------------

st.divider()
st.subheader("💬 Review Explorer")
st.write("Click a point on the chart (conceptual) or browse sample reviews below based on filters.")

if not topic_df.empty:
    col_sort1, col_sort2 = st.columns([2, 1])
    with col_sort1:
        sample_size = st.slider("Number of reviews", 1, min(len(topic_df), 50), 3)
    with col_sort2:
        sort_by = st.pills("Sort by", ["Random", "Newest", "High Rating", "Low Rating"], default="Random")
    
    # Apply Sorting
    if sort_by == "Random":
        samples = topic_df.sample(min(sample_size, len(topic_df)))
    elif sort_by == "Newest":
        samples = topic_df.sort_values("Review Date", ascending=False).head(sample_size)
    elif sort_by == "High Rating":
        samples = topic_df.sort_values("Rating_Filtered", ascending=False).head(sample_size)
    elif sort_by == "Low Rating":
        samples = topic_df.sort_values("Rating_Filtered", ascending=True).head(sample_size)
    
    # Display Reviews in a 2-column grid
    review_cols = st.columns(2)
    for i, (_, row) in enumerate(samples.iterrows()):
        col_idx = i % 2
        with review_cols[col_idx]:
            with st.chat_message("user"):
                st.markdown(f"**{row['Restaurant Name']}** — {row['Review Date'].strftime('%b %Y')}")
                st.write(f"\"{row['Review Text']}\"")
                st.caption(f"Rating: {row['Rating_Filtered']}⭐ | Topic: {row['assigned_topic']}")
else:
    st.info("No reviews match your current criteria.")



st.sidebar.divider()
st.sidebar.subheader("🛠️ Admin: Trigger Scraper (Beta)")
refresh_place = st.sidebar.text_input("Cafe Name (Search)", placeholder="e.g. Dineen Coffee Toronto")
refresh_period = st.sidebar.text_input("Period (Shorthand)", value="1m", help="e.g. 1m, 2w, 1y")
refresh_category = st.sidebar.selectbox("Category", ["Cafe", "F&B", "Bar"])

if st.sidebar.button("Start Scraping"):
    if not refresh_place:
        st.sidebar.error("Please enter a place name.")
    else:
        try:
            with st.status(f"Scraping reviews for '{refresh_place}'...", expanded=True) as status:
                st.write("Initializing Playwright...")
                # Run the scraper script
                cmd = [
                    sys.executable, 
                    os.path.join("Review_Scrapper", "google_reviews.py"),
                    "--place", refresh_place,
                    "--period", refresh_period,
                    "--category", refresh_category
                ]
                
                process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                
                # Stream the output to the status block
                for line in process.stdout:
                    st.text(line.strip())
                
                process.wait()
                
                if process.returncode == 0:
                    status.update(label="Scraping Complete! Reloading data...", state="complete", expanded=False)
                    st.cache_data.clear()
                    st.rerun()
                else:
                    status.update(label="Scraping Failed.", state="error")
                    st.sidebar.error("Scraper exited with an error. Check console/status for details.")
        except Exception as e:
            st.sidebar.error(f"Error running scraper: {e}")

st.sidebar.divider()
st.sidebar.caption("Dashboard v1.1 | Data Ducks")

