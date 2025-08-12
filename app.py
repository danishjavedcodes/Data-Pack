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
from src.utils.display import display_image_grid, display_image_data_table, display_image_details, get_image_stats

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

page = st.sidebar.radio("Navigation", ["Scrape", "Preprocess", "Create Dataset", "View Images"])  # 4 steps

if page == "Scrape":
    st.header("1. Scrape")
    st.caption("Enhanced scrapers with quality filtering and retry mechanisms.")

    # Enhanced site selection with descriptions
    st.subheader("Select Image Sources")
    
    # Only Unsplash is supported for now
    st.info("""
    **Currently Supported:**
    - **Unsplash** (Official API) - High-quality free stock photos
    
    **Coming Soon:**
    - Pexels, Pixabay, Flickr, and other sites will be added back
    """)
    
    # Simplified site selection
    sites = st.multiselect(
        "Select Image Sources",
        options=["unsplash"],
        default=["unsplash"],
        help="Currently only Unsplash is supported using their official API"
    )
    
    if not sites:
        st.warning("Please select Unsplash to continue.")
    
    st.markdown("---")
    
    # Search configuration
    st.subheader("Search Configuration")
    query = st.text_input("Query/Keyword", value="portrait", help="Search term for images (e.g., 'portrait', 'landscape', 'people')")
    
    col_a, col_b = st.columns(2)
    with col_a:
        total_target = st.number_input("Target images per site", min_value=10, max_value=5000, value=100, step=10)
    with col_b:
        max_pages = st.slider("Max pages per site", min_value=1, max_value=50, value=5)

    # Generic URLs
    generic_urls_text = st.text_area(
        "Optional: Add specific page URLs (one per line)", 
        placeholder="https://example.com/gallery\nhttps://another-site.com/photos",
        help="Direct URLs to scrape images from"
    )
    generic_urls = [u.strip() for u in generic_urls_text.splitlines() if u.strip()]

    # Enhanced scraping options
    st.subheader("Advanced Options")
    col_a, col_b, col_c, col_d = st.columns(4)
    with col_a:
        rate_limit = st.number_input("Requests per minute (per site)", min_value=10, max_value=600, value=120)
    with col_b:
        timeout = st.number_input("HTTP timeout (seconds)", min_value=5, max_value=60, value=15)
    with col_c:
        min_size = st.number_input("Minimum image size (px)", min_value=100, max_value=2048, value=512, step=64)
        st.caption("Images smaller than this will be filtered out")
    with col_d:
        max_workers = st.number_input("Max concurrent downloads", min_value=1, max_value=10, value=4, step=1)
        st.caption("Higher values = faster but may trigger rate limits")

    # Quality info
    st.info("""
    **Unsplash API Features:**
    - 🎯 **Official API** - Uses Unsplash's documented search endpoint
    - 🔄 **Rate limit handling** - Respects API limits automatically
    - ⚡ **High-quality images** - Gets 1080px width images by default
    - 🛡️ **Reliable access** - No more 403 errors or blocking
    - 📊 **Structured data** - Clean JSON responses with metadata
    - 🌐 **Proper attribution** - Follows Unsplash guidelines
    """)
    
    # API key information
    st.success("""
    **Unsplash API Access:**
    - **Production Mode**: Using your API key (5000 requests/hour)
    - **Application**: TARUM (ID: 790856)
    - **Rate Limits**: 5000/hour (Production limit)
    - **No 403 Errors**: Official API access prevents blocking
    """)
    
    # Instructions for getting API key
    with st.expander("🔑 API Key Information"):
        st.markdown("""
        **Current Setup:**
        - **Application ID**: 790856
        - **Access Key**: IDIRKPCHUQLvHbPXkJ4nN3BVduzGLYXUq_FC-PsYkp8
        - **Status**: Production mode active
        
        **Benefits:**
        - 5000 requests per hour (vs 50 in demo)
        - Stable and reliable access
        - Full API features available
        """)
    
    # Remove the 403 error section since we're using the official API

    if st.button("Start Scraping", type="primary", disabled=len(sites) == 0):
        with st.status("Scraping in progress...", expanded=True) as status:
            status.write("Initializing enhanced scraper...")
            
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
                min_size=int(min_size),
                max_workers=int(max_workers),
            )
            status.update(label=f"Downloaded {len(new_images)} new images (≥{min_size}px).")

            if new_images:
                status.write("Classifying image types...")
                classify_types_for_images(db=db, image_ids=new_images)
                counts = db.count_by_type()
                st.subheader("Type counts")
                st.dataframe(counts, use_container_width=True)
            else:
                st.warning("No images were downloaded. Try adjusting your search terms or minimum size.")

elif page == "Preprocess":
    st.header("2. Preprocess")

    # Selection controls
    filter_text = st.text_input("Filter by source or query (contains)", value="")
    limit = st.number_input("Max rows to show",  min_value=10, max_value=5000, value=200, step=10)

    rows = db.list_images(filter_text=filter_text, limit=int(limit))
    st.caption(f"Found {len(rows)} records")

    # Build selection UI
    st.subheader("Image Selection")
    
    # Add select all option
    col1, col2 = st.columns([3, 1])
    with col1:
        selected_ids = st.multiselect(
            "Select image IDs to preprocess",
            options=[r["id"] for r in rows],
            format_func=lambda rid: f"{rid} | {next((r['source'] for r in rows if r['id']==rid), '?')}"
        )
    with col2:
        if st.button("Select All", type="secondary"):
            selected_ids = [r["id"] for r in rows]
            st.rerun()
    
    st.caption(f"Selected {len(selected_ids)} out of {len(rows)} images")

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

elif page == "View Images":
    st.header("4. View Images")
    
    # Get statistics
    stats = get_image_stats(db)
    
    # Display summary stats
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Images", stats['total'])
    with col2:
        st.metric("Processed", stats['processed'])
    with col3:
        st.metric("With Prompts", stats['with_prompts'])
    with col4:
        st.metric("Raw Only", stats['raw_only'])
    
    # Filter options
    st.subheader("Filter Options")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        view_type = st.selectbox("View Type", ["All", "Raw Only", "Processed Only", "With Prompts", "Without Prompts"])
    with col2:
        image_type = st.selectbox("Image Type", ["All"] + list(stats['by_type'].keys()))
    with col3:
        source_filter = st.selectbox("Source", ["All"] + list(stats['by_source'].keys()))
    
    # Apply filters
    filter_text = st.text_input("Search by query or source (contains)", value="")
    limit = st.number_input("Max images to display", min_value=10, max_value=100, value=20, step=5)
    
    # Get filtered images
    all_images = db.list_images(filter_text=filter_text, limit=10000)
    
    # Apply additional filters
    filtered_images = []
    for img in all_images:
        # View type filter
        if view_type == "Raw Only" and img.get('processed_path'):
            continue
        if view_type == "Processed Only" and not img.get('processed_path'):
            continue
        if view_type == "With Prompts" and not img.get('prompt'):
            continue
        if view_type == "Without Prompts" and img.get('prompt'):
            continue
        
        # Image type filter
        if image_type != "All" and img.get('type') != image_type:
            continue
        
        # Source filter
        if source_filter != "All" and img.get('source') != source_filter:
            continue
        
        filtered_images.append(img)
    
    st.caption(f"Showing {len(filtered_images)} images")
    
    # Display options
    display_mode = st.radio("Display Mode", ["Grid View", "Table View", "Single Image"])
    
    if display_mode == "Grid View":
        cols = st.slider("Columns", min_value=2, max_value=6, value=4)
        display_image_grid(filtered_images, cols=cols, max_display=limit)
    
    elif display_mode == "Table View":
        display_image_data_table(filtered_images[:limit])
    
    elif display_mode == "Single Image":
        if filtered_images:
            selected_id = st.selectbox(
                "Select Image ID",
                options=[img['id'] for img in filtered_images],
                format_func=lambda x: f"ID {x} - {next((img['source'] for img in filtered_images if img['id']==x), 'Unknown')}"
            )
            
            selected_image = next((img for img in filtered_images if img['id'] == selected_id), None)
            if selected_image:
                display_image_details(selected_image)
        else:
            st.info("No images match the current filters.")

# Add footer with ngrok info
if os.environ.get('NGROK_TUNNEL'):
    st.markdown("---")
    st.caption("🌐 Powered by ngrok - Public tunnel active")
