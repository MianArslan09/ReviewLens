# scraper.py — Daraz Review Scraper for ReviewLens
import cloudscraper
import re
import time
import json
import os
 
 
def extract_item_id(url: str):
    """Extract item ID from a Daraz product URL.
    Tries two regex patterns to handle different URL formats.
    """
    # Primary pattern: /products/name-iXXXXXX-sXXXXXX.html
    match = re.search(r'-i(\d+)-s\d+\.html', url)
    if match:
        return match.group(1)
 
    # Fallback pattern: /iXXXXXX. (shorter URL formats)
    match = re.search(r'/i(\d+)\.', url)
    if match:
        return match.group(1)
 
    # Return None instead of raising — caller decides what to do
    return None
 
 
def scrape_daraz_reviews(product_url: str, max_pages: int = 3):
    """Scrape reviews from a Daraz product URL.
    Returns list of dicts: [{'reviewer':..., 'rating':..., 'text':...}]
    Falls back to cached data automatically if live scraping fails.
    """
    item_id = extract_item_id(product_url)
    if not item_id:
        raise ValueError(
            'Could not extract item ID. Make sure URL is like: '
            'https://www.daraz.pk/products/name-iXXXX-sXXXX.html'
        )
 
    # ── Cloudscraper with Chrome fingerprint to bypass Cloudflare ──
    scraper = cloudscraper.create_scraper(
        browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False}
    )
    all_reviews = []
 
    for page in range(1, max_pages + 1):
        # ── Daraz review API endpoint ──
        # pageNo (not pageNum), pageSize=20 matches Daraz API spec
        url = (
            f'https://my.daraz.pk/pdp/review/getReviewList'
            f'?itemId={item_id}&pageSize=20&pageNo={page}'
        )
 
        try:
            response = scraper.get(url, timeout=20)
 
            if response.status_code != 200:
                print(f'Page {page} returned status {response.status_code}')
                break
 
            data = response.json()
 
            # ── JSON key is 'model' (NOT 'result') in Daraz API ──
            items = data.get('model', {}).get('items', [])
            if not items:
                break  # No more pages
 
            for item in items:
                text     = item.get('reviewContent', '').strip()
                rating   = item.get('rating', 0)
                reviewer = item.get('reviewer', 'Anonymous')
 
                if text:  # Only add non-empty reviews
                    all_reviews.append({
                        'reviewer': reviewer,
                        'rating':   rating,
                        'text':     text
                    })
 
            time.sleep(1)  # Polite crawl delay — 1 second between pages
 
        except Exception as e:
            print(f'Error on page {page}: {e}')
            break
 
    # ── Inline cache fallback (inside scraper — no dependency on main.py) ──
    if not all_reviews:
        cache_file = os.path.join(
            os.path.dirname(__file__), 'cache', 'cached_default.json'
        )
        if os.path.exists(cache_file):
            print('Live scraping failed — falling back to cached data')
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
 
    print(f'Scraped {len(all_reviews)} reviews from Daraz')
    return all_reviews
 
 
# ── Standalone test block ──
# Run: python scraper.py  to test the scraper independently
if __name__ == '__main__':
    test_url = input('Paste a Daraz product URL: ')
    reviews = scrape_daraz_reviews(test_url, max_pages=2)
    print(f'\nGot {len(reviews)} reviews\n')
    for r in reviews[:3]:
        print(f'- [{r["rating"]}/5] {r["reviewer"]}: {r["text"][:80]}...')
