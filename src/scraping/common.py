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

# Try to import the specialized Unsplash API scraper
try:
    from src.scraping.unsplash import UnsplashAPIScraper
    UNSPLASH_API_AVAILABLE = True
except ImportError:
    UNSPLASH_API_AVAILABLE = False
    print("Warning: Unsplash API scraper not available")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
    "DNT": "1",
    "Sec-CH-UA": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
    "Sec-CH-UA-Mobile": "?0",
    "Sec-CH-UA-Platform": '"Windows"',
}

# Rotating User Agents for anti-detection
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
]

# API headers for modern sites
API_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "X-Requested-With": "XMLHttpRequest",
}

# Only Unsplash configuration for now
SITE_CONFIGS = {
    "unsplash": {
        "use_api": True,
        "api_scraper": True
    }
}

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
    
    # Only support Unsplash for now
    if "unsplash" not in sites:
        print("Only Unsplash is currently supported. Please select Unsplash.")
        return new_ids
    
    if not UNSPLASH_API_AVAILABLE:
        print("Unsplash API scraper not available. Please check the installation.")
        return new_ids
    
    print("Using Unsplash API scraper...")
    
    try:
        # Initialize Unsplash API scraper
        unsplash_scraper = UnsplashAPIScraper(timeout=timeout)
        
        # Calculate target per page (API max is 30)
        target_per_page = min(target_per_site // max_pages, 30)
        if target_per_page < 1:
            target_per_page = 1
        
        # Scrape using the API
        unsplash_ids = unsplash_scraper.scrape_query(
            query=query,
            max_pages=max_pages,
            target_per_page=target_per_page,
            dest_dir=paths["raw"],
            db=db,
            min_size=min_size
        )
        
        new_ids.extend(unsplash_ids)
        print(f"Unsplash API scraping completed: {len(unsplash_ids)} images")
        
    except Exception as e:
        print(f"Error with Unsplash API scraper: {e}")
    
    print(f"Scraping complete. Downloaded {len(new_ids)} new images.")
    return new_ids
