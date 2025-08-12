import streamlit as st
import os

from src.config import ensure_directories, get_paths
from src.utils.db import Database
from src.scraping.common import scrape_query
from src.utils.images import preprocess_images
from src.classify.clip_type import classify_types_for_images
from src.prompts.caption_blip import generate_captions_for_images
from src.qc.duplicates import find_duplicates
from src.dataset.exporter import export_dataset

# Initialize paths and DB
ensure_directories()
paths = get_paths()
db = Database(paths["db_file"])  # creates tables if not exist

# Configure Streamlit for ngrok compatibility
st.set_page_config(
    page_title="TARUMResearch Dataset Builder", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# Add custom CSS for better appearance
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .status-box {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #1f77b4;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<h1 class="main-header">TARUMResearch Dataset Builder</h1>', unsafe_allow_html=True)

# Add info about ngrok if running
if os.environ.get('NGROK_TUNNEL'):
    st.info("🌐 Running via ngrok tunnel - accessible from anywhere!")

page = st.sidebar.radio("Navigation", ["Scrape", "Preprocess", "Create Dataset"])  # 3 steps

if page == "Scrape":
    st.header("1. Scrape")
    st.caption("Demo scrapers. Respect robots.txt and site ToS.")

    sites = st.multiselect(
        "Select sites",
        options=[
            "unsplash", "pexels", "pixabay", "flickr", "wallhaven",
            "generic_url_list"
        ],
        default=["unsplash", "pexels", "pixabay"],
    )

    query = st.text_input("Query/Keyword", value="mountain landscape")
    total_target = st.number_input("Target images per site", min_value=10, max_value=5000, value=100, step=10)
    max_pages = st.slider("Max pages per site", min_value=1, max_value=50, value=5)

    generic_urls_text = st.text_area("Optional: Add page URLs (one per line) for generic scraping")
    generic_urls = [u.strip() for u in generic_urls_text.splitlines() if u.strip()]

    col_a, col_b = st.columns(2)
    with col_a:
        rate_limit = st.number_input("Requests per minute (per site)", min_value=10, max_value=600, value=120)
    with col_b:
        timeout = st.number_input("HTTP timeout (seconds)", min_value=5, max_value=60, value=15)

    if st.button("Start Scraping", type="primary"):
        with st.status("Scraping in progress...", expanded=True) as status:
            new_images = scrape_query(
                sites=sites,
                query=query,
                target_per_site=int(total_target),
                max_pages=int(max_pages),
                rate_limit_per_min=int(rate_limit),
                timeout=int(timeout),
                generic_urls=generic_urls,
                db=db,
                paths=paths,
            )
            status.update(label=f"Downloaded {len(new_images)} new images.")

            st.write("Classifying image types...")
            classify_types_for_images(db=db, image_ids=new_images)
            counts = db.count_by_type()
            st.subheader("Type counts")
            st.dataframe(counts, use_container_width=True)

elif page == "Preprocess":
    st.header("2. Preprocess")

    # Selection controls
    filter_text = st.text_input("Filter by source or query (contains)", value="")
    limit = st.number_input("Max rows to show",  min_value=10, max_value=5000, value=200, step=10)

    rows = db.list_images(filter_text=filter_text, limit=int(limit))
    st.caption(f"Found {len(rows)} records")

    # Build selection UI
    selected_ids = st.multiselect(
        "Select image IDs to preprocess",
        options=[r["id"] for r in rows],
        format_func=lambda rid: f"{rid} | {next((r['source'] for r in rows if r['id']==rid), '?')}"
    )

    st.markdown("---")
    st.subheader("Processing Options")
    col1, col2, col3 = st.columns(3)
    with col1:
        do_resize = st.checkbox("Resize", value=True)
        resize_dim = st.selectbox("Size", options=["1024x1024", "512x512"], index=0)
        width, height = map(int, resize_dim.split("x"))
    with col2:
        fmt = st.selectbox("Format", options=["PNG", "JPEG"], index=1)
        do_enhance = st.checkbox("Enhance (contrast/bri)", value=True)
    with col3:
        do_watermark = st.checkbox("Watermark removal (heuristic)", value=False)

    if st.button("Run Preprocessing", type="primary"):
        with st.status("Preprocessing...", expanded=True) as status:
            processed = preprocess_images(
                db=db,
                image_ids=selected_ids,
                target_size=(width, height) if do_resize else None,
                target_format=fmt,
                enhance=do_enhance,
                remove_watermark=do_watermark,
                paths=paths,
            )
            status.update(label=f"Processed {len(processed)} images")
            st.success("Done")

elif page == "Create Dataset":
    st.header("3. Create Dataset")

    st.subheader("Prompt Generation")
    do_captions = st.checkbox("Generate prompts (BLIP)", value=True)
    batch_size = st.slider("Caption batch size", min_value=2, max_value=32, value=8)

    st.subheader("Quality Control")
    do_dupes = st.checkbox("Detect duplicates (imagehash)", value=True)

    st.subheader("Export")
    formats = st.multiselect("Export formats", options=["csv", "json", "parquet", "hdf5"], default=["csv", "parquet"]) 

    if st.button("Create Dataset", type="primary"):
        with st.status("Creating dataset...", expanded=True) as status:
            if do_captions:
                status.write("Generating captions...")
                ids_missing = db.list_image_ids_missing_prompts()
                generate_captions_for_images(db=db, image_ids=ids_missing, batch_size=int(batch_size))

            if do_dupes:
                status.write("Detecting duplicates...")
                dupes = find_duplicates(db=db)
                status.write(f"Potential duplicates groups: {len(dupes)}")

            status.write("Exporting dataset...")
            export_paths = export_dataset(db=db, paths=paths, formats=formats)
            status.update(label="Dataset created.")

        st.success("Complete")
        st.write({k: str(v) for k, v in export_paths.items()})

# Add footer with ngrok info
if os.environ.get('NGROK_TUNNEL'):
    st.markdown("---")
    st.caption("🌐 Powered by ngrok - Public tunnel active")
