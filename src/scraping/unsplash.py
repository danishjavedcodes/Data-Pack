import os
import time
import random
from pathlib import Path
from typing import List, Optional, Dict
from urllib.parse import quote

import httpx

from src.utils.io import download_image
from src.utils.db import Database

class UnsplashAPIScraper:
    """Official Unsplash API scraper using their documented endpoints."""
    
    def __init__(self, access_key: str = None, timeout: int = 30):
        self.timeout = timeout
        self.base_url = "https://api.unsplash.com"
        
        # Use demo access key if none provided
        self.access_key = access_key or "DEMO_KEY"
        
        # API headers as per documentation
        self.headers = {
            "Authorization": f"Client-ID {self.access_key}",
            "Accept-Version": "v1",
            "User-Agent": "TARUMResearch-DatasetBuilder/1.0"
        }
        
        # Rate limiting info
        self.rate_limit_remaining = 50  # Demo limit
        self.rate_limit_reset = None
        
        # Initialize client
        self.client = httpx.Client(
            timeout=timeout,
            headers=self.headers,
            follow_redirects=True
        )
    
    def __del__(self):
        """Clean up the HTTP client."""
        if hasattr(self, 'client'):
            self.client.close()
    
    def _handle_rate_limits(self, response: httpx.Response):
        """Handle rate limiting based on response headers."""
        if 'X-Ratelimit-Remaining' in response.headers:
            self.rate_limit_remaining = int(response.headers['X-Ratelimit-Remaining'])
            print(f"Rate limit remaining: {self.rate_limit_remaining}")
        
        if 'X-Ratelimit-Reset' in response.headers:
            self.rate_limit_reset = int(response.headers['X-Ratelimit-Reset'])
    
    def search_photos(self, query: str, page: int = 1, per_page: int = 30, 
                     order_by: str = "relevant") -> Optional[Dict]:
        """
        Search photos using the official Unsplash API.
        
        Args:
            query: Search term
            page: Page number (default: 1)
            per_page: Number of items per page (max: 30)
            order_by: Sort order (relevant, latest, oldest)
        """
        try:
            # Check rate limit
            if self.rate_limit_remaining <= 0:
                print("Rate limit exceeded. Waiting for reset...")
                if self.rate_limit_reset:
                    wait_time = max(0, self.rate_limit_reset - time.time())
                    if wait_time > 0:
                        print(f"Waiting {wait_time:.0f} seconds for rate limit reset...")
                        time.sleep(wait_time)
            
            # Build API URL
            url = f"{self.base_url}/search/photos"
            params = {
                "query": query,
                "page": page,
                "per_page": min(per_page, 30),  # API max is 30
                "order_by": order_by
            }
            
            print(f"Searching Unsplash API: {url} with params {params}")
            
            response = self.client.get(url, params=params)
            
            # Handle rate limits
            self._handle_rate_limits(response)
            
            if response.status_code == 200:
                data = response.json()
                print(f"API Response: Found {len(data.get('results', []))} photos")
                return data
            elif response.status_code == 403:
                print("403 Forbidden - Check your access key")
                return None
            elif response.status_code == 429:
                print("429 Too Many Requests - Rate limit exceeded")
                return None
            else:
                print(f"API Error: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"Error searching photos: {e}")
            return None
    
    def extract_image_urls(self, api_response: Dict) -> List[str]:
        """Extract image URLs from API response."""
        urls = []
        
        if not api_response or 'results' not in api_response:
            return urls
        
        for photo in api_response['results']:
            if 'urls' in photo:
                # Use 'regular' size for good quality (1080px width)
                # You can also use 'full' for maximum quality
                if 'regular' in photo['urls']:
                    urls.append(photo['urls']['regular'])
                elif 'full' in photo['urls']:
                    urls.append(photo['urls']['full'])
        
        print(f"Extracted {len(urls)} image URLs from API response")
        return urls
    
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
                
                # Rate limiting between downloads
                if i < len(urls) - 1:  # Don't sleep after the last download
                    time.sleep(random.uniform(1, 2))
                    
            except Exception as e:
                print(f"Error downloading {url}: {e}")
                continue
        
        return successful_downloads
    
    def scrape_query(self, query: str, max_pages: int, target_per_page: int, 
                    dest_dir: Path, db: Database, min_size: int = 512) -> List[int]:
        """Scrape Unsplash for a given query using the official API."""
        new_ids = []
        
        for page in range(1, max_pages + 1):
            try:
                print(f"\n--- Scraping page {page} for query: '{query}' ---")
                
                # Search photos via API
                api_response = self.search_photos(
                    query=query,
                    page=page,
                    per_page=target_per_page,
                    order_by="relevant"
                )
                
                if not api_response:
                    print(f"Failed to get API response for page {page}")
                    continue
                
                # Extract image URLs
                urls = self.extract_image_urls(api_response)
                
                if not urls:
                    print(f"No images found on page {page}")
                    continue
                
                # Download images
                downloaded = self.download_images(urls, dest_dir, min_size)
                
                # Add to database
                for img_info in downloaded:
                    img_id = db.upsert_image({
                        "source": "unsplash_api",
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
                    wait_time = random.uniform(2, 4)
                    print(f"Waiting {wait_time:.1f} seconds before next page...")
                    time.sleep(wait_time)
                
            except Exception as e:
                print(f"Error scraping page {page}: {e}")
                continue
        
        print(f"\nUnsplash API scraping complete. Downloaded {len(new_ids)} new images.")
        return new_ids
