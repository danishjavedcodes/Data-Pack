import streamlit as st
from pathlib import Path
from typing import List, Dict, Any, Optional
from PIL import Image
import pandas as pd

from .db import Database


def display_image_grid(images: List[Dict[str, Any]], cols: int = 4, max_display: int = 20):
    """Display a grid of images with their metadata."""
    if not images:
        st.info("No images found.")
        return
    
    # Limit display to prevent overwhelming the UI
    display_images = images[:max_display]
    if len(images) > max_display:
        st.warning(f"Showing first {max_display} images out of {len(images)} total.")
    
    # Create columns for the grid
    cols_list = st.columns(cols)
    
    for idx, img_data in enumerate(display_images):
        col_idx = idx % cols
        with cols_list[col_idx]:
            try:
                # Try to load and display the image
                img_path = img_data.get("processed_path") or img_data.get("local_path")
                if img_path and Path(img_path).exists():
                    img = Image.open(img_path)
                    st.image(img, caption=f"ID: {img_data.get('id', 'N/A')}", use_column_width=True)
                    
                    # Display metadata
                    st.caption(f"Size: {img_data.get('width', 'N/A')}x{img_data.get('height', 'N/A')}")
                    st.caption(f"Type: {img_data.get('type', 'unknown')}")
                    st.caption(f"Source: {img_data.get('source', 'N/A')}")
                    
                    if img_data.get('prompt'):
                        st.caption(f"Prompt: {img_data['prompt'][:50]}...")
                else:
                    st.error(f"Image not found: {img_path}")
            except Exception as e:
                st.error(f"Error loading image {img_data.get('id', 'N/A')}: {str(e)}")


def display_image_data_table(images: List[Dict[str, Any]]):
    """Display image data in a table format."""
    if not images:
        st.info("No images found.")
        return
    
    # Prepare data for display
    display_data = []
    for img in images:
        display_data.append({
            "ID": img.get("id"),
            "Source": img.get("source"),
            "Query": img.get("query"),
            "Size": f"{img.get('width', 'N/A')}x{img.get('height', 'N/A')}",
            "Type": img.get("type", "unknown"),
            "Format": img.get("format", "N/A"),
            "Has Prompt": "Yes" if img.get("prompt") else "No",
            "Processed": "Yes" if img.get("processed_path") else "No",
        })
    
    df = pd.DataFrame(display_data)
    st.dataframe(df, use_container_width=True)


def display_image_details(img_data: Dict[str, Any]):
    """Display detailed information about a single image."""
    col1, col2 = st.columns([1, 2])
    
    with col1:
        try:
            img_path = img_data.get("processed_path") or img_data.get("local_path")
            if img_path and Path(img_path).exists():
                img = Image.open(img_path)
                st.image(img, caption=f"Image ID: {img_data.get('id')}", use_column_width=True)
            else:
                st.error("Image file not found")
        except Exception as e:
            st.error(f"Error loading image: {str(e)}")
    
    with col2:
        st.subheader("Image Details")
        
        # Basic info
        st.write(f"**ID:** {img_data.get('id')}")
        st.write(f"**Source:** {img_data.get('source')}")
        st.write(f"**Query:** {img_data.get('query')}")
        st.write(f"**Dimensions:** {img_data.get('width')} x {img_data.get('height')}")
        st.write(f"**Format:** {img_data.get('format')}")
        st.write(f"**Type:** {img_data.get('type', 'unknown')}")
        
        # URLs
        if img_data.get('url'):
            st.write(f"**Original URL:** {img_data.get('url')}")
        
        # File paths
        if img_data.get('local_path'):
            st.write(f"**Local Path:** {img_data.get('local_path')}")
        if img_data.get('processed_path'):
            st.write(f"**Processed Path:** {img_data.get('processed_path')}")
        
        # Prompt
        if img_data.get('prompt'):
            st.subheader("Generated Prompt")
            st.write(img_data.get('prompt'))
        
        # Hash
        if img_data.get('hash'):
            st.write(f"**Hash:** {img_data.get('hash')[:20]}...")


def get_image_stats(db: Database) -> Dict[str, Any]:
    """Get statistics about the image database."""
    stats = {}
    
    # Total counts
    total_images = db.list_images(limit=1000000)
    stats['total'] = len(total_images)
    
    # By type
    type_counts = db.count_by_type()
    stats['by_type'] = {row['type']: row['n'] for row in type_counts}
    
    # By source
    sources = {}
    for img in total_images:
        source = img.get('source', 'unknown')
        sources[source] = sources.get(source, 0) + 1
    stats['by_source'] = sources
    
    # Processed vs raw
    processed = sum(1 for img in total_images if img.get('processed_path'))
    stats['processed'] = processed
    stats['raw_only'] = stats['total'] - processed
    
    # With prompts
    with_prompts = sum(1 for img in total_images if img.get('prompt'))
    stats['with_prompts'] = with_prompts
    stats['without_prompts'] = stats['total'] - with_prompts
    
    return stats
