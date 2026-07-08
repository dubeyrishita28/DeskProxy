import streamlit as st
import requests

# Page setup
st.set_page_config(page_title="DeskProxy Dashboard", layout="wide")

# Custom CSS styling
st.markdown("""
    <style>
    .main {background-color: #f9f9f9;}
    h1, h2, h3 {color: #2c3e50;}
    .stButton>button {
        background-color: #3498db;
        color: white;
        border-radius: 8px;
        padding: 0.5em 1em;
    }
    .stButton>button:hover {
        background-color: #2980b9;
    }
    </style>
""", unsafe_allow_html=True)

# Sidebar navigation
st.sidebar.title("Navigation")
choice = st.sidebar.radio("Go to:", ["Home", "Upload", "Search", "Results", "Analytics"])

# Home
if choice == "Home":
    st.title("DeskProxy Dashboard")
    st.write("Elegant Streamlit UI for your FastAPI + Semantic Search project.")
    st.markdown("---")
    st.info("Use the sidebar to navigate between sections.")

# Upload
elif choice == "Upload":
    st.header("Upload Dataset / Config")
    file = st.file_uploader("Upload your dataset or configuration file")
    if file:
        st.success("File uploaded successfully!")
        # You can call backend functions here if needed

# Search
elif choice == "Search":
    st.header("Semantic Search")
    query = st.text_input("Enter your search term")
    if st.button("Run Search"):
        with st.spinner("Searching..."):
            try:
                response = requests.post(
                    "http://127.0.0.1:8000/query",
                    json={"query": query}
                )
                if response.status_code == 200:
                    result = response.json()
                    st.subheader("Search Results")
                    # Display results in expandable cards
                    if isinstance(result, dict):
                        for key, value in result.items():
                            with st.expander(f"{key}"):
                                st.write(value)
                    else:
                        st.write(result)
                else:
                    st.error(f"Backend error: {response.status_code}")
            except Exception as e:
                st.error(f"Connection failed: {e}")

# Results
elif choice == "Results":
    st.header("Processed Results")
    st.info("View or clear cached query results from backend.")

    # Buttons for actions
    col1, col2 = st.columns(2)
    with col1:
        load_btn = st.button("Load Cache Entries")
    with col2:
        purge_btn = st.button("Purge Cache")

    # Load cache entries
    if load_btn:
        with st.spinner("Fetching cache entries..."):
            try:
                response = requests.get("http://127.0.0.1:8000/cache/entries")
                if response.status_code == 200:
                    data = response.json()
                    st.success(f"Total entries: {data.get('total', 0)}")
                    for i, entry in enumerate(data.get("entries", []), start=1):
                        with st.expander(f"Entry {i}: {entry.get('query_text')}"):
                            st.write({
                                "Result": entry.get("result"),
                                "Access Count": entry.get("access_count"),
                                "Created At": entry.get("created_at"),
                                "Last Accessed": entry.get("last_accessed_at"),
                                "Metadata": entry.get("metadata"),
                            })
                else:
                    st.error(f"Backend error: {response.status_code}")
            except Exception as e:
                st.error(f"Connection failed: {e}")

    # Purge cache
    if purge_btn:
        with st.spinner("Purging cache..."):
            try:
                response = requests.delete("http://127.0.0.1:8000/cache")
                if response.status_code == 200:
                    result = response.json()
                    st.success(f"{result.get('message')} ({result.get('deleted_count')} entries removed)")
                else:
                    st.error(f"Backend error: {response.status_code}")
            except Exception as e:
                st.error(f"Connection failed: {e}")


# Analytics
elif choice == "Analytics":
    st.header("Usage Analytics")
    st.info("View aggregated telemetry statistics from backend.")

    if st.button("Load Analytics Summary"):
        with st.spinner("Fetching telemetry summary..."):
            try:
                response = requests.get("http://127.0.0.1:8000/telemetry/summary")
                if response.status_code == 200:
                    data = response.json()
                    st.success("Telemetry summary loaded successfully!")

                    # Display key metrics
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Total Queries", data.get("total_queries", 0))
                    col2.metric("Cache Hits", data.get("cache_hits", 0))
                    col3.metric("Cache Misses", data.get("cache_misses", 0))

                    st.markdown("---")
                    col4, col5, col6 = st.columns(3)
                    col4.metric("Hit Rate (%)", round(data.get("hit_rate_percent", 0), 2))
                    col5.metric("Avg Latency (ms)", round(data.get("average_latency_ms", 0), 2))
                    col6.metric("Avg Similarity Score", round(data.get("average_similarity_score", 0), 3))

                    st.markdown("---")
                    st.subheader("Latency Percentiles")
                    st.write({
                        
                        "P95 Latency (ms)": data.get("p95_latency_ms"),
                        "P99 Latency (ms)": data.get("p99_latency_ms"),
                    })

                    st.markdown("---")
                    st.caption(f"Data window: {data.get('window_start')} → {data.get('window_end')}")
                else:
                    st.error(f"Backend error: {response.status_code}")
            except Exception as e:
                st.error(f"Connection failed: {e}")
