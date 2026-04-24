import os
import sys
import logging
import requests
from typing import Dict, Any, Optional

try:
    import browser_cookie3
except ImportError:
    browser_cookie3 = None

logger = logging.getLogger("SmartSocialFetch")

class SmartSocialFetcher:
    """
    A modern social data fetcher that uses existing browser cookies 
    to bypass login blocks and guest-token failures.
    """
    def __init__(self):
        self.session = requests.Session()
        self._load_cookies()

    def _load_cookies(self):
        if not browser_cookie3:
            logger.warning("browser_cookie3 not installed. Cannot use browser cookies.")
            return
        
        try:
            # Automatically identify and load cookies from the primary browser
            # browser_cookie3.load() picks the best one available (Chrome, Firefox, Edge, etc.)
            self.session.cookies = browser_cookie3.load()
            logger.info("Successfully loaded browser cookies for automated fetching.")
        except Exception as e:
            logger.error(f"Failed to auto-load browser cookies: {e}")

    def fetch_profile(self, platform: str, identifier: str) -> Optional[str]:
        """
        Fetches public/private profile data using browser context.
        """
        platform = platform.lower()
        
        # Mapping platforms to their base URLs
        urls = {
            "twitter": f"https://x.com/{identifier.lstrip('@')}",
            "x": f"https://x.com/{identifier.lstrip('@')}",
            "facebook": f"https://www.facebook.com/{identifier}",
            "instagram": f"https://www.instagram.com/{identifier.lstrip('@')}/",
            "github": f"https://github.com/{identifier}",
        }
        
        url = urls.get(platform)
        if not url:
            return None

        logger.info(f"Smart-fetching {platform} profile: {url}")
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        }

        try:
            response = self.session.get(url, headers=headers, timeout=15)
            if response.status_code == 200:
                # Return a snippet of the page or use a simple heuristic to extract text
                # In a real scenario, we'd use BeautifulSoup here.
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Extract meta description or bio-like sections
                bio = ""
                meta_desc = soup.find("meta", {"name": "description"})
                if meta_desc:
                    bio = meta_desc.get("content", "")
                
                # Get some text content
                text_content = soup.get_text(separator=' ', strip=True)[:2000]
                
                return f"[{platform.upper()}_SMART_FETCH]\nURL: {url}\nSummary: {bio}\nRaw Excerpt: {text_content}"
            else:
                logger.warning(f"Failed to fetch {platform} (Status: {response.status_code})")
                return None
        except Exception as e:
            logger.error(f"Error during smart fetch for {platform}: {e}")
            return None

import subprocess

def quick_fetch(data: Dict[str, str]) -> str:
    """Helper for Start.py to run all fetches in one go."""
    fetcher = SmartSocialFetcher()
    results = []
    
    # Path to legacy scripts
    fetch_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "SocialFetch")

    for plat, ident in data.items():
        if not ident or plat == "email": continue
        
        # Method 1: Smart Fetch (Cookies)
        res = fetcher.fetch_profile(plat, ident)
        if res:
            results.append(res)
        
        # Method 2: Legacy Script Fallback (Subprocess)
        script_path = os.path.join(fetch_dir, f"{plat}.py")
        if os.path.exists(script_path):
            logger.info(f"Running legacy fallback for {plat}...")
            try:
                # Use current python interpreter
                legacy_res = subprocess.run(
                    [sys.executable, script_path, ident], 
                    capture_output=True, text=True, timeout=30
                )
                if legacy_res.returncode == 0 and legacy_res.stdout.strip():
                    results.append(f"[{plat.upper()}_LEGACY_FETCH]\n{legacy_res.stdout.strip()}")
            except Exception as e:
                logger.error(f"Legacy fetch failed for {plat}: {e}")

    return "\n\n".join(results)
