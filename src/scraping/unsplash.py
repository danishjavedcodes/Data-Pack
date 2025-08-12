import os
import time
import random
from pathlib import Path
from typing import List, Optional, Dict
from urllib.parse import urlparse, urlunparse, quote

import httpx
from selectolax.parser import HTMLParser

from src.utils.io import download_image
from src.utils.db import Database

class UnsplashScraper:
    """Specialized scraper for Unsplash using httpx and selectolax."""
    
    def __init__(self, timeout: int = 30, max_retries: int = 3):
        self.timeout = timeout
        self.max_retries = max_retries
        self.client = httpx.Client(
            timeout=timeout,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }
        )
        
        # Words to exclude from URLs
        self.exclude_words = ["data:", "profile", "premium", "avatar", "logo", "icon"]
    
    def __del__(self):
        """Clean up the HTTP client."""
        if hasattr(self, 'client'):
            self.client.close()
    
    def get_search_url(self, query: str, page: int = 1) -> str:
        """Generate Unsplash search URL."""
        return f"https://unsplash.com/s/photos/{quote(query)}?page={page}"
    
    def extract_image_urls(self, url: str) -> List[str]:
        """Extract image URLs from Unsplash page using selectolax."""
        try:
            print(f"Fetching: {url}")
            resp = self.client.get(url)
            
            if resp.status_code != 200:
                print(f"Error getting response: {resp.status_code}")
                return []
            
            tree = HTMLParser(resp.text)
            
            # Multiple selectors to catch different image loading patterns
            selectors = [
                "figure a img[srcset]",
                "img[srcset*='images.unsplash.com']",
                "a[href*='/photos/'] img[srcset]",
                "img[src*='images.unsplash.com']",
                "figure img[srcset]",
                "[data-test='photo-card'] img[srcset]"
            ]
            
            all_images = []
            for selector in selectors:
                images = tree.css(selector)
                all_images.extend(images)
                if images:
                    print(f"Found {len(images)} images with selector: {selector}")
            
            # Remove duplicates while preserving order
            seen = set()
            unique_images = []
            for img in all_images:
                if img not in seen:
                    seen.add(img)
                    unique_images.append(img)
            
            filtered_urls = []
            
            for img in unique_images:
                # Try srcset first
                srcset = img.attrs.get("srcset", "")
                if srcset:
                    urls = srcset.split(", ")
                    for u in urls:
                        if any(exclude_word in u.lower() for exclude_word in self.exclude_words):
                            continue
                        
                        # Extract URL from srcset entry (format: "url width")
                        url_part = u.split(" ")[0]
                        if url_part.startswith("http"):
                            parsed_url = urlparse(url_part)
                            clean_url = urlunparse((
                                parsed_url.scheme, 
                                parsed_url.netloc, 
                                parsed_url.path, 
                                '', '', ''
                            ))
                            if clean_url not in filtered_urls:
                                filtered_urls.append(clean_url)
                
                # Fallback to src attribute
                src = img.attrs.get("src", "")
                if src and src.startswith("http") and "images.unsplash.com" in src:
                    if not any(exclude_word in src.lower() for exclude_word in self.exclude_words):
                        parsed_url = urlparse(src)
                        clean_url = urlunparse((
                            parsed_url.scheme, 
                            parsed_url.netloc, 
                            parsed_url.path, 
                            '', '', ''
                        ))
                        if clean_url not in filtered_urls:
                            filtered_urls.append(clean_url)
            
            print(f"Extracted {len(filtered_urls)} unique image URLs")
            return filtered_urls
            
        except Exception as e:
            print(f"Error extracting URLs from {url}: {e}")
            return []
    
    def download_images(self, urls: List[str], dest_dir: Path, min_size: int = 512) -> List[Dict]:
        """Download images and return info about successful downloads."""
        successful_downloads = []
        
        for i, url in enumerate(urls):
            try:
                print(f"Downloading {i+1}/{len(urls)}: {url}")
                
                # Use the existing download_image function
                result = download_image(url, dest_dir, self.timeout, min_size)
                if result:
                    successful_downloads.append({
                        "url": url,
                        "local_path": result["local_path"],
                        "width": result["width"],
                        "height": result["height"],
                        "format": result["format"]
                    })
                    print(f"✓ Downloaded: {result['local_path']}")
                else:
                    print(f"✗ Failed to download: {url}")
                
                # Rate limiting
                if i < len(urls) - 1:  # Don't sleep after the last download
                    time.sleep(random.uniform(0.5, 1.5))
                    
            except Exception as e:
                print(f"Error downloading {url}: {e}")
                continue
        
        return successful_downloads
    
    def scrape_query(self, query: str, max_pages: int, target_per_page: int, 
                    dest_dir: Path, db: Database, min_size: int = 512) -> List[int]:
        """Scrape Unsplash for a given query."""
        new_ids = []
        
        for page in range(1, max_pages + 1):
            try:
                print(f"\n--- Scraping page {page} for query: '{query}' ---")
                
                # Get search URL
                search_url = self.get_search_url(query, page)
                
                # Extract image URLs
                urls = self.extract_image_urls(search_url)
                
                if not urls:
                    print(f"No images found on page {page}")
                    continue
                
                # Limit URLs per page
                urls = urls[:target_per_page]
                
                # Download images
                downloaded = self.download_images(urls, dest_dir, min_size)
                
                # Add to database
                for img_info in downloaded:
                    img_id = db.upsert_image({
                        "source": "unsplash",
                        "query": query,
                        "url": img_info["url"],
                        "local_path": img_info["local_path"],
                        "processed_path": None,
                        "width": img_info["width"],
                        "height": img_info["height"],
                        "format": img_info["format"],
                        "hash": None,
                        "type": None,
                        "prompt": None,
                        "flags": None,
                    })
                    if img_id:
                        new_ids.append(img_id)
                
                print(f"Page {page}: Downloaded {len(downloaded)} images")
                
                # Rate limiting between pages
                if page < max_pages:
                    wait_time = random.uniform(2, 5)
                    print(f"Waiting {wait_time:.1f} seconds before next page...")
                    time.sleep(wait_time)
                
            except Exception as e:
                print(f"Error scraping page {page}: {e}")
                continue
        
        print(f"\nUnsplash scraping complete. Downloaded {len(new_ids)} new images.")
        return new_ids
