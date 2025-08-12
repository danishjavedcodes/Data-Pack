from typing import Dict, Iterable, List, Optional
from pathlib import Path
import re
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

from src.utils.io import download_image, rate_limited_sleep
from src.utils.db import Database

HEADERS = {"User-Agent": "Mozilla/5.0"}

SITE_SEARCH_URLS = {
    "unsplash": lambda q, page: f"https://unsplash.com/s/photos/{quote(q)}?page={page}",
    "pexels": lambda q, page: f"https://www.pexels.com/search/{quote(q)}/?page={page}",
    "pixabay": lambda q, page: f"https://pixabay.com/images/search/{quote(q)}/?pagi={page}",
    "flickr": lambda q, page: f"https://www.flickr.com/search/?text={quote(q)}&page={page}",
    "wallhaven": lambda q, page: f"https://wallhaven.cc/search?q={quote(q)}&page={page}",
}

IMG_SRC_ATTRS = ["src", "data-src", "data-lazy", "data-srcset", "srcset"]


def _extract_img_urls(html: str) -> List[str]:
    soup = BeautifulSoup(html, "lxml")
    urls: List[str] = []
    for img in soup.find_all("img"):
        for attr in IMG_SRC_ATTRS:
            val = img.get(attr)
            if not val:
                continue
            if attr.endswith("srcset"):
                parts = [p.strip() for p in val.split(",") if p.strip()]
                if parts:
                    url = parts[-1].split(" ")[0]
                    urls.append(url)
            else:
                urls.append(val)
    clean: List[str] = []
    for u in urls:
        if not u.lower().startswith("http"):
            continue
        u = re.sub(r"\?.*$", "", u)
        clean.append(u)
    return list(dict.fromkeys(clean))


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
) -> List[int]:
    new_ids: List[int] = []

    def _ingest_url(img_url: str, source: str):
        info = download_image(img_url, dest_dir=paths["raw"], timeout=timeout)
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

    for site in sites:
        if site == "generic_url_list":
            continue
        getter = SITE_SEARCH_URLS.get(site)
        if not getter:
            continue
        fetched = 0
        for page in range(1, max_pages + 1):
            try:
                url = getter(query, page)
                resp = requests.get(url, headers=HEADERS, timeout=timeout)
                if resp.status_code != 200:
                    break
                urls = _extract_img_urls(resp.text)
                for u in urls:
                    if fetched >= target_per_site:
                        break
                    _ingest_url(u, source=site)
                    fetched += 1
                    rate_limited_sleep(rate_limit_per_min)
                if fetched >= target_per_site:
                    break
            except Exception:
                continue

    if generic_urls:
        for page_url in generic_urls:
            try:
                resp = requests.get(page_url, headers=HEADERS, timeout=timeout)
                if resp.status_code != 200:
                    continue
                for u in _extract_img_urls(resp.text):
                    _ingest_url(u, source="generic")
                    rate_limited_sleep(rate_limit_per_min)
            except Exception:
                continue

    return new_ids
