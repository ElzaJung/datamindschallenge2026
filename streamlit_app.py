import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as graph_objects
from plotly.subplots import make_subplots
import os
from datetime import datetime
import re
import matplotlib.pyplot as plt
import subprocess
import sys

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
    
    # Simple Topic Classification based on the Notebook's Topics
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
st.plotly_chart(share_fig, use_container_width=True)


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
    st.plotly_chart(fig, use_container_width=True)

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
        st.dataframe(matrix1.style.background_gradient(cmap='Blues', axis=1), use_container_width=True)

    with tab2:
        st.info("**Average Ratings**: Measures quality of experience. Colors range from Red (Lower Ratings / Action Required) to Green (Excellence).")
        matrix2 = get_matrix("rating")
        st.dataframe(matrix2.style.background_gradient(cmap='RdYlGn', axis=1), use_container_width=True)

    with tab3:
        st.info("**Share of Voice**: Measures the percentage of reviews each cafe captures for a topic. Darker purple indicates market dominance.")
        matrix3 = get_matrix("share")
        st.dataframe(matrix3.style.background_gradient(cmap='Purples', axis=1), use_container_width=True)



# ------------------------------------------------------------------------------
# Review Explorer
# ------------------------------------------------------------------------------

st.divider()
st.subheader("💬 Review Explorer")
st.write("Click a point on the chart (conceptual) or browse sample reviews below based on filters.")

if not topic_df.empty:
    sample_size = st.slider("Samples to audit", 1, 10, 3)
    samples = topic_df.sample(min(sample_size, len(topic_df)))
    
    for _, row in samples.iterrows():
        with st.chat_message("user"):
            st.markdown(f"**{row['Restaurant Name']}** — {row['Review Date'].strftime('%b %Y')}")
            st.write(f"\"{row['Review Text']}\"")
            st.caption(f"Rating: {row['Rating_Filtered']}⭐ | Topic Categorization: {row['assigned_topic']}")
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

