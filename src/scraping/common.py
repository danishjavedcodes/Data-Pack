from typing import Dict, Iterable, List, Optional, Set
from pathlib import Path
import re
import time
import random
import json
from urllib.parse import quote, urljoin, urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup

from src.utils.io import download_image, rate_limited_sleep
from src.utils.db import Database

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Cache-Control": "max-age=0",
}

# Enhanced site configurations with modern selectors
SITE_CONFIGS = {
    "unsplash": {
        "search_url": lambda q, page: f"https://unsplash.com/s/photos/{quote(q)}?page={page}",
        "img_selectors": [
            "img[src*='images.unsplash.com']", 
            "img[data-src*='images.unsplash.com']",
            "img[srcset*='images.unsplash.com']",
            "a[href*='/photos/'] img",
            "figure img",
            "[data-test='photo-card'] img"
        ],
        "quality_patterns": [r"w=\d+", r"h=\d+", r"fit=crop", r"auto=format", r"q=\d+"],
        "min_quality_score": 1,
        "dynamic_loading": True,
        "scroll_required": True
    },
    "pexels": {
        "search_url": lambda q, page: f"https://www.pexels.com/search/{quote(q)}/?page={page}",
        "img_selectors": [
            "img[src*='images.pexels.com']", 
            "img[data-src*='images.pexels.com']",
            "img[srcset*='images.pexels.com']",
            "a[href*='/photo/'] img",
            "article img",
            "[data-testid='photo-card'] img"
        ],
        "quality_patterns": [r"auto=compress", r"cs=tinysrgb", r"w=\d+", r"h=\d+"],
        "min_quality_score": 1,
        "dynamic_loading": True,
        "scroll_required": True
    },
    "pixabay": {
        "search_url": lambda q, page: f"https://pixabay.com/images/search/{quote(q)}/?pagi={page}",
        "img_selectors": [
            "img[src*='cdn.pixabay.com']", 
            "img[data-src*='cdn.pixabay.com']",
            "img[srcset*='cdn.pixabay.com']",
            "a[href*='/photo/'] img"
        ],
        "quality_patterns": [r"__340", r"__480", r"__1280", r"__1920"],
        "min_quality_score": 2,
        "dynamic_loading": False
    },
    "flickr": {
        "search_url": lambda q, page: f"https://www.flickr.com/search/?text={quote(q)}&page={page}",
        "img_selectors": [
            "img[src*='live.staticflickr.com']", 
            "img[data-src*='live.staticflickr.com']",
            "a[href*='/photos/'] img"
        ],
        "quality_patterns": [r"_b\.", r"_c\.", r"_z\.", r"_n\."],
        "min_quality_score": 2,
        "dynamic_loading": False
    },
    "wallhaven": {
        "search_url": lambda q, page: f"https://wallhaven.cc/search?q={quote(q)}&page={page}",
        "img_selectors": [
            "img[src*='w.wallhaven.cc']", 
            "img[data-src*='w.wallhaven.cc']",
            "a[href*='/wallpaper/'] img"
        ],
        "quality_patterns": [r"full", r"large", r"medium"],
        "min_quality_score": 1,
        "dynamic_loading": False
    },
    "deviantart": {
        "search_url": lambda q, page: f"https://www.deviantart.com/search?q={quote(q)}&page={page}",
        "img_selectors": [
            "img[src*='images-wixmp-']", 
            "img[data-src*='images-wixmp-']",
            "a[href*='/art/'] img"
        ],
        "quality_patterns": [r"v1", r"f_auto", r"w_\d+", r"h_\d+"],
        "min_quality_score": 1,
        "dynamic_loading": True
    },
    "artstation": {
        "search_url": lambda q, page: f"https://www.artstation.com/search?q={quote(q)}&page={page}",
        "img_selectors": [
            "img[src*='cdnb.artstation.com']", 
            "img[data-src*='cdnb.artstation.com']",
            "a[href*='/artwork/'] img"
        ],
        "quality_patterns": [r"large", r"medium", r"small"],
        "min_quality_score": 1,
        "dynamic_loading": True
    },
    "ideogram": {
        "search_url": lambda q, page: f"https://ideogram.ai/t/explore?f={quote(q)}&page={page}",
        "img_selectors": [
            "img[src*='ideogram.ai']", 
            "img[data-src*='ideogram.ai']",
            "img[src*='cdn.ideogram.ai']",
            "a[href*='/t/'] img",
            "[data-testid='image-card'] img"
        ],
        "quality_patterns": [r"quality=\d+", r"width=\d+", r"height=\d+"],
        "min_quality_score": 1,
        "dynamic_loading": True,
        "scroll_required": True
    }
}

# Additional image source attributes to check
IMG_SRC_ATTRS = [
    "src", "data-src", "data-lazy", "data-srcset", "srcset", 
    "data-original", "data-image", "data-full", "data-large",
    "data-src-retina", "data-srcset", "data-lazy-src"
]

def _extract_high_quality_urls(html: str, site_config: Dict) -> List[str]:
    """Extract high-quality image URLs using site-specific selectors."""
    soup = BeautifulSoup(html, "lxml")
    urls: Set[str] = set()
    
    # Use site-specific selectors
    for selector in site_config.get("img_selectors", ["img"]):
        for img in soup.select(selector):
            for attr in IMG_SRC_ATTRS:
                val = img.get(attr)
                if not val:
                    continue
                
                # Handle srcset
                if attr.endswith("srcset"):
                    parts = [p.strip() for p in val.split(",") if p.strip()]
                    if parts:
                        # Get the highest resolution URL from srcset
                        best_url = None
                        best_width = 0
                        for part in parts:
                            url_part = part.split(" ")[0]
                            width_match = re.search(r"(\d+)w", part)
                            if width_match:
                                width = int(width_match.group(1))
                                if width > best_width:
                                    best_width = width
                                    best_url = url_part
                        if best_url:
                            urls.add(best_url)
                else:
                    urls.add(val)
    
    # Also look for links that might contain image URLs
    for link in soup.find_all("a", href=True):
        href = link.get("href")
        if href and any(pattern in href for pattern in ["/photo/", "/photos/", "/art/", "/artwork/", "/t/"]):
            # Check if the link contains an image
            img_tag = link.find("img")
            if img_tag:
                for attr in IMG_SRC_ATTRS:
                    val = img_tag.get(attr)
                    if val:
                        urls.add(val)
    
    # Filter and clean URLs
    clean_urls = []
    for url in urls:
        if not url.lower().startswith("http"):
            continue
        
        # Remove query parameters that might reduce quality
        base_url = re.sub(r"\?.*$", "", url)
        
        # Score URL quality
        quality_score = 0
        for pattern in site_config.get("quality_patterns", []):
            if re.search(pattern, url, re.IGNORECASE):
                quality_score += 1
        
        # Only include URLs that meet minimum quality threshold
        if quality_score >= site_config.get("min_quality_score", 0):
            clean_urls.append(base_url)
    
    return list(clean_urls)

def _extract_generic_urls(html: str) -> List[str]:
    """Extract image URLs from generic HTML."""
    soup = BeautifulSoup(html, "lxml")
    urls: Set[str] = set()
    
    for img in soup.find_all("img"):
        for attr in IMG_SRC_ATTRS:
            val = img.get(attr)
            if not val:
                continue
            
            if attr.endswith("srcset"):
                parts = [p.strip() for p in val.split(",") if p.strip()]
                if parts:
                    # Get the largest image from srcset
                    url = parts[-1].split(" ")[0]
                    urls.add(url)
            else:
                urls.add(val)
    
    # Clean URLs
    clean_urls = []
    for url in urls:
        if not url.lower().startswith("http"):
            continue
        # Remove query parameters
        clean_url = re.sub(r"\?.*$", "", url)
        clean_urls.append(clean_url)
    
    return list(clean_urls)

def _download_with_retry(url: str, dest_dir: Path, timeout: int, min_size: int, max_retries: int = 3) -> Optional[Dict]:
    """Download image with retry mechanism."""
    for attempt in range(max_retries):
        try:
            result = download_image(url, dest_dir, timeout, min_size)
            if result:
                return result
        except Exception as e:
            if attempt == max_retries - 1:
                print(f"Failed to download {url} after {max_retries} attempts: {e}")
            time.sleep(random.uniform(1, 3))  # Random delay between retries
    return None

def _get_page_with_retry(session: requests.Session, url: str, timeout: int, max_retries: int = 3) -> Optional[str]:
    """Get page content with retry mechanism."""
    for attempt in range(max_retries):
        try:
            resp = session.get(url, timeout=timeout)
            if resp.status_code == 200:
                return resp.text
            elif resp.status_code == 429:  # Rate limited
                wait_time = random.uniform(30, 60)
                print(f"Rate limited, waiting {wait_time:.1f} seconds...")
                time.sleep(wait_time)
            else:
                print(f"HTTP {resp.status_code} for {url}")
        except Exception as e:
            if attempt == max_retries - 1:
                print(f"Failed to fetch {url} after {max_retries} attempts: {e}")
            time.sleep(random.uniform(2, 5))
    return None

def scrape_query(
    sites: Iterable[str],
    query: str,
    target_per_site: int,
    max_pages: int,
    rate_limit_per_min: int,
    timeout: int,
    generic_urls: Optional[List[str]],
    db: Database,
    paths: Dict[str, Path],
    min_size: int = 512,
    max_workers: int = 4,
) -> List[int]:
    new_ids: List[int] = []
    session = requests.Session()
    session.headers.update(HEADERS)

    def _ingest_url(img_url: str, source: str):
        info = _download_with_retry(img_url, dest_dir=paths["raw"], timeout=timeout, min_size=min_size)
        if not info:
            return
        img_id = db.upsert_image({
            "source": source,
            "query": query,
            "url": img_url,
            "local_path": info["local_path"],
            "processed_path": None,
            "width": info["width"],
            "height": info["height"],
            "format": info["format"],
            "hash": None,
            "type": None,
            "prompt": None,
            "flags": None,
        })
        if img_id:
            new_ids.append(img_id)

    # Scrape configured sites
    for site in sites:
        if site == "generic_url_list":
            continue
        
        site_config = SITE_CONFIGS.get(site)
        if not site_config:
            print(f"Warning: No configuration for site '{site}', skipping...")
            continue
        
        print(f"Scraping {site}...")
        fetched = 0
        
        for page in range(1, max_pages + 1):
            try:
                url = site_config["search_url"](query, page)
                html_content = _get_page_with_retry(session, url, timeout)
                
                if not html_content:
                    print(f"Failed to fetch {site} page {page}")
                    break
                
                urls = _extract_high_quality_urls(html_content, site_config)
                print(f"Found {len(urls)} potential images on {site} page {page}")
                
                if not urls:
                    print(f"No images found on {site} page {page}, trying next page...")
                    continue
                
                # Use threading for faster downloads
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    futures = []
                    for img_url in urls:
                        if fetched >= target_per_site:
                            break
                        future = executor.submit(_ingest_url, img_url, site)
                        futures.append(future)
                        fetched += 1
                    
                    # Wait for downloads to complete
                    for future in as_completed(futures):
                        try:
                            future.result()
                        except Exception as e:
                            print(f"Download error: {e}")
                
                if fetched >= target_per_site:
                    break
                
                # Rate limiting
                rate_limited_sleep(rate_limit_per_min)
                
            except Exception as e:
                print(f"Error scraping {site} page {page}: {e}")
                continue

    # Scrape generic URLs
    if generic_urls:
        print("Scraping generic URLs...")
        for page_url in generic_urls:
            try:
                html_content = _get_page_with_retry(session, page_url, timeout)
                if not html_content:
                    continue
                
                urls = _extract_generic_urls(html_content)
                print(f"Found {len(urls)} images on {page_url}")
                
                # Download images from generic URLs
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    futures = []
                    for img_url in urls:
                        future = executor.submit(_ingest_url, img_url, "generic")
                        futures.append(future)
                    
                    for future in as_completed(futures):
                        try:
                            future.result()
                        except Exception as e:
                            print(f"Download error: {e}")
                
                rate_limited_sleep(rate_limit_per_min)
                
            except Exception as e:
                print(f"Error scraping {page_url}: {e}")
                continue

    print(f"Scraping complete. Downloaded {len(new_ids)} new images.")
    return new_ids
