"""
ScraperAPI Integration for Fast & Reliable Product Scraping
Uses premium ScraperAPI service instead of Playwright
Much faster and more reliable than direct scraping
"""

import os
from dotenv import load_dotenv

# Force reload .env file to ensure we get the latest key (override system env vars)
env_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(env_path):
    load_dotenv(dotenv_path=env_path, override=True)
else:
    load_dotenv(override=True)  # Try loading from current directory

import requests
import re
import asyncio
from typing import Dict, Optional
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin

# ScraperAPI Configuration - Optional for local testing
SCRAPERAPI_KEY = os.getenv("SCRAPERAPI_KEY")
if not SCRAPERAPI_KEY:
    print("⚠️  WARNING: SCRAPERAPI_KEY not set - will use fallback mode")
    print("⚠️  Get a free key from: https://www.scraperapi.com/")
    print("⚠️  To set the key, create a .env file in the backend directory with: SCRAPERAPI_KEY=your_key_here")
    SCRAPERAPI_KEY = None  # Allow running without ScraperAPI (fallback mode)
else:
    # Mask the key for security (show first 4 and last 4 chars)
    masked_key = SCRAPERAPI_KEY[:4] + "..." + SCRAPERAPI_KEY[-4:] if len(SCRAPERAPI_KEY) > 8 else "***"
    print(f"✅ ScraperAPI key loaded: {masked_key}")
SCRAPERAPI_ENDPOINT = "http://api.scraperapi.com"


def detect_source(url: str) -> str:
    """Detect if URL is Amazon or Flipkart"""
    domain = urlparse(url).netloc.lower()
    if 'amazon' in domain:
        return 'amazon'
    elif 'flipkart' in domain:
        return 'flipkart'
    return 'unknown'


async def scrape_product_scraperapi(url: str) -> Dict:
    """
    Scrape product using ScraperAPI - FAST & RELIABLE
    
    Benefits:
    - Handles JavaScript automatically
    - Bypasses CAPTCHAs
    - Manages proxies
    - Much faster than Playwright
    """
    if not SCRAPERAPI_KEY:
        print(f"⚠️  ScraperAPI key not available - returning minimal data")
        return {'title': 'Product', 'price': None, 'image_url': '', 'specs': []}
    
    print(f"🚀 Scraping with ScraperAPI: {url}")
    print(f"🔑 Using ScraperAPI key: {SCRAPERAPI_KEY[:4]}...{SCRAPERAPI_KEY[-4:] if SCRAPERAPI_KEY and len(SCRAPERAPI_KEY) > 8 else '***'}")
    
    source = detect_source(url)
    
    try:
        # Call ScraperAPI (run in thread pool to avoid blocking)
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: requests.get(
                SCRAPERAPI_ENDPOINT,
                params={
                    'api_key': SCRAPERAPI_KEY,
                    'url': url,
                    'render': 'true',  # Need JS rendering for product pages (but use short timeout)
                    'country_code': 'in',  # Use India proxies
                    'premium': 'true',  # Use premium proxies for e-commerce
                },
                timeout=12  # 12 second timeout (reduced for faster failure)
            )
        )
        
        if response.status_code != 200:
            error_msg = f"ScraperAPI returned status {response.status_code}"
            # Try to get error details from response
            try:
                error_text = response.text[:300] if response.text else "No error details"
                error_msg += f": {error_text}"
                print(f"❌ ScraperAPI Error Response: {error_text}")
            except:
                pass
            raise Exception(error_msg)
        
        # Parse HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract data based on source
        if source == 'amazon':
            return await scrape_amazon_from_html(soup, url)
        elif source == 'flipkart':
            return await scrape_flipkart_from_html(soup, url)
        else:
            raise ValueError(f"Unsupported source: {source}")
            
    except Exception as e:
        print(f"❌ ScraperAPI error: {str(e)}")
        raise


async def scrape_amazon_from_html(soup: BeautifulSoup, url: str) -> Dict:
    """Extract Amazon product data from HTML"""
    data = {
        'source': 'amazon',
        'url': url,
        'title': None,
        'price': None,
        'image_url': None,
        'rating': None,
        'rating_count': None,
        'specs': []
    }
    
    # Extract title
    title_selectors = [
        '#productTitle',
        'span#productTitle',
        'h1 span#productTitle'
    ]
    for selector in title_selectors:
        element = soup.select_one(selector)
        if element:
            data['title'] = element.get_text().strip()
            break
    
    # Extract image
    image_selectors = [
        '#landingImage',
        '#imgBlkFront',
        'img[data-old-hires]',
        'img.a-dynamic-image'
    ]
    for selector in image_selectors:
        element = soup.select_one(selector)
        if element:
            # Try high-res image first
            img_url = element.get('data-old-hires') or element.get('data-a-dynamic-image') or element.get('src')
            if img_url:
                # If data-a-dynamic-image is JSON, extract first URL
                if img_url.startswith('{'):
                    import json
                    try:
                        img_dict = json.loads(img_url)
                        img_url = list(img_dict.keys())[0] if img_dict else None
                    except:
                        pass
                data['image_url'] = img_url
                break
    
    # Extract price
    price_selectors = [
        'span.a-price-whole',
        '.a-price .a-offscreen',
        '#priceblock_ourprice',
        '#priceblock_dealprice',
        'span.a-price span.a-offscreen'
    ]
    for selector in price_selectors:
        element = soup.select_one(selector)
        if element:
            price_text = element.get_text().strip()
            # Clean price
            price_clean = re.sub(r'[^\d.]', '', price_text)
            if price_clean:
                data['price'] = f"₹{price_clean}"
                break
    
    # Extract rating
    rating_element = soup.select_one('span.a-icon-alt')
    if rating_element:
        rating_text = rating_element.get_text()
        rating_match = re.search(r'([\d.]+)', rating_text)
        if rating_match:
            data['rating'] = float(rating_match.group(1))
    
    # Extract rating count
    rating_count_element = soup.select_one('#acrCustomerReviewText')
    if rating_count_element:
        count_text = rating_count_element.get_text()
        count_match = re.search(r'([\d,]+)', count_text)
        if count_match:
            data['rating_count'] = int(count_match.group(1).replace(',', ''))
    
    # Extract specs from feature bullets (get more detailed specs)
    bullet_points = soup.select('#feature-bullets li span.a-list-item')
    for bullet in bullet_points[:10]:  # Get up to 10 specs for detailed view
        spec_text = bullet.get_text().strip()
        if spec_text and len(spec_text) < 200:  # Allow longer specs
            data['specs'].append(spec_text)
    
    # Also try to get product details from table
    if len(data['specs']) < 5:
        detail_rows = soup.select('.prodDetTable tr, #productDetails_detailBullets_sections1 tr')
        for row in detail_rows[:10]:
            cells = row.select('th, td')
            if len(cells) >= 2:
                label = cells[0].get_text().strip()
                value = cells[1].get_text().strip()
                spec = f"{label}: {value}"
                if len(spec) < 200 and spec not in data['specs']:
                    data['specs'].append(spec)
    
    print(f"✅ Scraped Amazon: {data.get('title', 'Unknown')[:50]}")
    return data


async def scrape_flipkart_from_html(soup: BeautifulSoup, url: str) -> Dict:
    """Extract Flipkart product data from HTML"""
    data = {
        'source': 'flipkart',
        'url': url,
        'title': None,
        'price': None,
        'image_url': None,
        'rating': None,
        'rating_count': None,
        'specs': []
    }
    
    # Extract title
    title_selectors = [
        'span.VU-ZEz',
        'h1.yhB1nd',
        'h1 span.B_NuCI'
    ]
    for selector in title_selectors:
        element = soup.select_one(selector)
        if element:
            data['title'] = element.get_text().strip()
            break
    
    # Extract image
    image_selectors = [
        'img.DByuf4',
        'img[loading="eager"]',
        'div._4WELSP img'
    ]
    for selector in image_selectors:
        element = soup.select_one(selector)
        if element:
            img_url = element.get('src')
            if img_url and 'static' not in img_url:
                # Get higher resolution
                data['image_url'] = img_url.replace('128/128', '416/416')
                break
    
    # Extract price
    price_selectors = [
        'div.Nx9bqj',
        'div._30jeq3',
        'div._16Jk6d'
    ]
    for selector in price_selectors:
        element = soup.select_one(selector)
        if element:
            price_text = element.get_text().strip()
            price_clean = re.sub(r'[^\d.]', '', price_text)
            if price_clean:
                data['price'] = f"₹{price_clean}"
                break
    
    # Extract rating
    rating_element = soup.select_one('div.XQDdHH')
    if rating_element:
        rating_text = rating_element.get_text()
        rating_match = re.search(r'([\d.]+)', rating_text)
        if rating_match:
            data['rating'] = float(rating_match.group(1))
    
    # Extract rating count
    rating_count_element = soup.select_one('span.Wphh3N')
    if rating_count_element:
        count_text = rating_count_element.get_text()
        count_match = re.search(r'([\d,]+)', count_text)
        if count_match:
            data['rating_count'] = int(count_match.group(1).replace(',', ''))
    
    # Extract specs from table (get more detailed specs)
    spec_rows = soup.select('div._6R0wZ6 tr, table.XhzH3c tr')
    for row in spec_rows[:12]:  # Get up to 12 specs for detailed view
        cells = row.select('td')
        if len(cells) >= 2:
            label = cells[0].get_text().strip()
            value = cells[1].get_text().strip()
            spec = f"{label}: {value}"
            if len(spec) < 200:  # Allow longer specs
                data['specs'].append(spec)
    
    print(f"✅ Scraped Flipkart: {data.get('title', 'Unknown')[:50]}")
    return data


async def search_product_scraperapi(product_name: str, source_site: str = 'amazon') -> Optional[Dict]:
    """
    Search for a product using ScraperAPI and return the first result
    Returns product data from search results page
    """
    if not SCRAPERAPI_KEY:
        print(f"⚠️  ScraperAPI key not available - returning fallback for: {product_name}")
        # Return minimal data so app doesn't crash
        return {
            'title': product_name,
            'price': '₹0',
            'image_url': '',
            'url': f"https://www.{source_site}.in/s?k={product_name.replace(' ', '+')}",
            'rating': None,
            'specs': []
        }
    
    print(f"🔍 Searching ScraperAPI for: {product_name} on {source_site}")
    print(f"🔑 Using ScraperAPI key: {SCRAPERAPI_KEY[:4]}...{SCRAPERAPI_KEY[-4:] if SCRAPERAPI_KEY and len(SCRAPERAPI_KEY) > 8 else '***'}")
    
    # Build search URL
    if source_site == 'flipkart':
        search_url = f"https://www.flipkart.com/search?q={product_name.replace(' ', '+')}"
    else:
        search_url = f"https://www.amazon.in/s?k={product_name.replace(' ', '+')}"
    
    try:
        # Call ScraperAPI (run in thread pool to avoid blocking)
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: requests.get(
                SCRAPERAPI_ENDPOINT,
                params={
                    'api_key': SCRAPERAPI_KEY,
                    'url': search_url,
                    'render': 'false',  # No JS rendering for speed
                    'country_code': 'in',
                    'premium': 'true',
                },
                timeout=10  # 10 second timeout for search (faster failure)
            )
        )
        
        if response.status_code != 200:
            error_msg = f"ScraperAPI returned status {response.status_code} for search"
            try:
                error_text = response.text[:300] if response.text else "No error details"
                error_msg += f": {error_text}"
                print(f"❌ ScraperAPI Search Error: {error_text}")
            except:
                pass
            print(f"⚠️  {error_msg}")
            return None
        
        # Parse HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract first product from search results
        if source_site == 'amazon':
            return await extract_first_amazon_search_result(soup, product_name)
        else:
            return await extract_first_flipkart_search_result(soup, product_name)
            
    except Exception as e:
        print(f"❌ ScraperAPI search error: {str(e)}")
        return None


async def extract_first_amazon_search_result(soup: BeautifulSoup, product_name: str) -> Optional[Dict]:
    """Extract first product from Amazon search results with brand matching validation"""
    # Find all product cards in search results
    product_cards = soup.select('div[data-component-type="s-search-result"]')
    
    if not product_cards:
        # Try alternative selectors
        product_cards = soup.select('div.s-result-item[data-asin]')
    
    if not product_cards:
        print(f"⚠️  No products found in Amazon search results")
        return None
    
    # Extract brand name from search query (first word usually)
    search_brand = product_name.split()[0].lower() if product_name else ""
    print(f"🔍 Looking for brand/keyword: '{search_brand}' in search results")
    
    # Try to find a card that matches the search query (brand name)
    first_product = None
    best_match_score = 0
    
    for card in product_cards[:6]:  # Check first 6 cards for best match (reduced from 10 for speed)
        # Check if this card has data-asin (direct product link)
        asin = card.get('data-asin')
        if asin and len(asin) == 10:
            # Check if it has a title
            title_elem = card.select_one('h2 a span, h2 span')
            if title_elem:
                title = title_elem.get_text().strip()
                title_lower = title.lower()
                
                # Calculate match score
                match_score = 0
                
                # Check if brand name appears in title
                if search_brand and search_brand in title_lower:
                    match_score += 10
                    print(f"✅ Found brand match '{search_brand}' in: {title[:60]}")
                
                # Check if other keywords from search appear in title
                search_words = set(product_name.lower().split())
                title_words = set(title_lower.split())
                common_words = search_words & title_words
                match_score += len(common_words)
                
                # Take the card with highest match score
                if match_score > best_match_score:
                    best_match_score = match_score
                    first_product = card
                    print(f"✅ Better match found (score {match_score}): ASIN {asin}, {title[:50]}")
                
                # If we found a strong brand match, use it immediately
                if match_score >= 10:
                    break
    
    # Warn if match quality is poor
    if first_product and best_match_score < 5:
        print(f"⚠️  WARNING: Low match score ({best_match_score}) for search '{product_name}'")
        print(f"⚠️  Search result may not accurately match query - recommend manual verification")
    
    # Fallback: use first card with title even if no brand match
    if not first_product:
        print(f"⚠️  No brand match found for '{search_brand}' - using first available result")
        for card in product_cards[:5]:
            title_check = card.select_one('h2 a span, h2 span')
            if title_check and title_check.get_text().strip():
                asin = card.get('data-asin')
                if asin and len(asin) == 10:
                    first_product = card
                    print(f"⚠️  Using first card with ASIN (no brand match)")
                    break
    
    if not first_product:
        print(f"❌ Could not find any valid product card")
        first_product = product_cards[0]  # Last resort fallback
    
    data = {
        'source': 'amazon',
        'title': None,
        'price': None,
        'image_url': None,
        'rating': None,
        'rating_count': None,
        'specs': [],
        'url': None
    }
    
    # Extract title
    title_elem = first_product.select_one('h2 a span, h2 span')
    if title_elem:
        data['title'] = title_elem.get_text().strip()
    
    # Extract link - try multiple selectors to find product page URL
    link_elem = None
    href = None
    
    # Method 1: Extract ASIN from data-asin attribute (most reliable)
    asin = first_product.get('data-asin')
    if asin and len(asin) == 10:
        # Direct ASIN found - build URL directly
        data['url'] = f"https://www.amazon.in/dp/{asin}"
        print(f"✅ Found ASIN from data attribute: {asin}")
        href = data['url']  # Set href for image extraction
    else:
        # Method 2: Find direct product links with /dp/ ASIN
        direct_product_links = first_product.select('a[href*="/dp/"]')
        
        href = None
        if direct_product_links:
            # Found direct product link(s) - use the first one
            for link in direct_product_links:
                href = link.get('href')
                if href and '/dp/' in href and href != '#':
                    print(f"✅ Found direct /dp/ link: {href[:80]}")
                    break
                href = None
        
        # Method 3: Try title link (and verify it has /dp/)
        if not href:
            title_link = first_product.select_one('h2 a')
            if title_link:
                href = title_link.get('href')
                if href and '/dp/' not in href:
                    # Title link doesn't have /dp/ - not useful
                    print(f"⚠️  Title link has no /dp/: {href[:80]}")
                    href = None
                elif href:
                    print(f"✅ Found product link via title: {href[:80]}")
    
    # Extract clean ASIN and build direct product URL
    if href and href != '#':
        # Clean URL - remove tracking parameters and ensure it's a direct product link
        if href.startswith('/'):
            href = f"https://www.amazon.in{href}"
        
        # Extract ASIN from URL (10-character alphanumeric code)
        # Amazon product URLs: /dp/ASIN or /gp/product/ASIN
        asin_match = re.search(r'/(?:dp|gp/product)/([A-Z0-9]{10})', href)
        
        if asin_match:
            asin = asin_match.group(1)
            # Build clean direct product URL
            data['url'] = f"https://www.amazon.in/dp/{asin}"
            print(f"✅ Extracted direct product URL with ASIN {asin}")
        else:
            # No valid ASIN found - this link is not usable
            print(f"⚠️  No ASIN found in link: {href[:100]}")
            data['url'] = None
    else:
        print(f"⚠️  No product link found in search results")
        data['url'] = None
    
    # Extract image
    img_elem = first_product.select_one('img.s-image')
    if img_elem:
        data['image_url'] = img_elem.get('src') or img_elem.get('data-src')
    
    # Extract price (try multiple selectors)
    price_selectors = [
        'span.a-price-whole',  # Most common
        '.a-price .a-offscreen',  # Alternative
        'span.a-price span.a-offscreen',  # Nested
        'span.a-color-price',  # Another alternative
        '.a-price[data-a-size] .a-offscreen',  # With size attribute
    ]
    for selector in price_selectors:
        price_elem = first_product.select_one(selector)
        if price_elem:
            price_text = price_elem.get_text().strip()
            # Extract price number
            price_clean = re.sub(r'[^\d.,]', '', price_text)
            # Remove extra commas/dots
            price_clean = price_clean.replace(',', '')
            if price_clean and '.' in price_clean:
                # Keep only first decimal point
                parts = price_clean.split('.')
                price_clean = parts[0] + '.' + parts[1] if len(parts) > 1 else parts[0]
            if price_clean and float(price_clean) > 0:
                # Format as integer if no decimals
                if '.' in price_clean and price_clean.split('.')[1] == '00':
                    price_clean = price_clean.split('.')[0]
                data['price'] = f"₹{price_clean}"
                break
    
    # Extract rating
    rating_elem = first_product.select_one('span.a-icon-alt')
    if rating_elem:
        rating_text = rating_elem.get_text()
        rating_match = re.search(r'([\d.]+)', rating_text)
        if rating_match:
            data['rating'] = float(rating_match.group(1))
    
    # Extract rating count (try multiple selectors)
    rating_count_selectors = [
        'span[aria-label*="ratings"]',  # More specific selector
        'a.a-link-normal span.a-size-base',
        'span.a-size-base.s-underline-text'
    ]
    for selector in rating_count_selectors:
        rating_count_elem = first_product.select_one(selector)
        if rating_count_elem:
            count_text = rating_count_elem.get_text()
            # Look for number followed by "ratings" or "reviews"
            count_match = re.search(r'([\d,]+)\s*(?:rating|review)', count_text, re.IGNORECASE)
            if not count_match:
                # Fallback to any number (but avoid prices - check for ₹ symbol)
                if '₹' not in count_text:
                    count_match = re.search(r'([\d,]+)', count_text)
            
            if count_match:
                try:
                    count_val = int(count_match.group(1).replace(',', ''))
                    # Sanity check: rating count should be reasonable (< 1 million usually)
                    if count_val < 1000000:
                        data['rating_count'] = count_val
                        break
                except:
                    pass
    
    # Extract specs from TITLE (already has features!) - FASTER & FREE
    title = data.get('title', '')
    if title:
        # Split title by commas and extract features
        parts = title.split(',')
        for part in parts:
            part = part.strip()
            # Extract specific patterns
            # RAM/Storage
            if re.search(r'\d+\s*GB\s+(RAM|Storage|SSD|HDD)', part, re.IGNORECASE):
                if part not in data['specs'] and len(part) < 50:
                    data['specs'].append(part)
            # Processor
            elif re.search(r'(Intel|AMD|Ryzen|Core)\s+i?\d+', part, re.IGNORECASE):
                if part not in data['specs'] and len(part) < 60:
                    data['specs'].append(part)
            # Display
            elif re.search(r'\d+(\.\d+)?["\']?\s*(inch|cm|FHD|HD|Display)', part, re.IGNORECASE):
                if part not in data['specs'] and len(part) < 50:
                    data['specs'].append(part)
            # Battery
            elif re.search(r'\d+\s*(mAh|WHR|Wh)\s*Battery', part, re.IGNORECASE):
                if part not in data['specs'] and len(part) < 50:
                    data['specs'].append(part)
            # Weight
            elif re.search(r'\d+(\.\d+)?\s*(kg|Kg|KG)', part, re.IGNORECASE):
                if part not in data['specs'] and len(part) < 30:
                    data['specs'].append(part)
            # Operating System
            elif re.search(r'(Windows|Win|macOS|Linux|Chrome OS)\s*\d*', part, re.IGNORECASE):
                if part not in data['specs'] and len(part) < 40:
                    data['specs'].append(part)
            # Office/Software
            elif 'Office' in part or 'M365' in part:
                if part not in data['specs'] and len(part) < 40:
                    data['specs'].append(part)
            # Graphics
            elif re.search(r'(Graphics|GPU|iGPU|Intel UHD|NVIDIA|AMD)', part, re.IGNORECASE):
                if part not in data['specs'] and len(part) < 50:
                    data['specs'].append(part)
            # General features (>10 chars, <80 chars, has useful info)
            elif len(part) > 10 and len(part) < 80 and any(c.isdigit() or c.isupper() for c in part):
                if part not in data['specs']:
                    data['specs'].append(part)
    
    # Skip purchase indicators like "10K+ bought" - user doesn't want this
    # Only extract actual product features, not popularity metrics
    
    print(f"✅ Found Amazon product: {data.get('title', 'Unknown')[:50]} | Price: {data.get('price', 'N/A')} | Specs: {len(data.get('specs', []))}")
    return data


async def extract_first_flipkart_search_result(soup: BeautifulSoup, product_name: str) -> Optional[Dict]:
    """Extract first product from Flipkart search results"""
    # Find first product card
    product_cards = soup.select('div._1AtVbE, div[data-id]')
    
    if not product_cards:
        print(f"⚠️  No products found in Flipkart search results")
        return None
    
    # Get first product
    first_product = product_cards[0]
    
    data = {
        'source': 'flipkart',
        'title': None,
        'price': None,
        'image_url': None,
        'rating': None,
        'rating_count': None,
        'specs': [],
        'url': None
    }
    
    # Extract title
    title_elem = first_product.select_one('a.IRpwTa, a.s1Q9rs, div._4rR01T')
    if title_elem:
        data['title'] = title_elem.get_text().strip()
    
    # PRIORITY: Find direct product links with /p/ first
    direct_product_links = first_product.select('a[href*="/p/"]')
    
    href = None
    if direct_product_links:
        # Found direct product link(s) - use the first one
        for link in direct_product_links:
            href = link.get('href')
            if href and '/p/' in href and href != '#' and not href.startswith('#'):
                print(f"✅ Found direct /p/ link: {href[:80]}")
                break
            href = None
    
    # Fallback: try other selectors only if no direct /p/ link found
    if not href:
        selectors = [
            'a.IRpwTa',  # Common product link
            'a.s1Q9rs',  # Alternative
        ]
        
        for selector in selectors:
            link_elem = first_product.select_one(selector)
            if link_elem:
                href = link_elem.get('href')
                # Must contain /p/ to be valid
                if href and '/p/' in href and href != '#':
                    print(f"✅ Found product link via '{selector}': {href[:80]}")
                    break
                href = None
    
    # Extract clean Flipkart product URL
    if href and href != '#' and '/p/' in href:
        # Clean URL - ensure it's a direct product link
        if href.startswith('/'):
            href = f"https://www.flipkart.com{href}"
        
        # Extract clean product URL (remove tracking & query params)
        # Flipkart product URLs: /p/product-name/pid
        url_parts = href.split('?')
        base_url = url_parts[0]
        
        # Ensure it's a valid /p/ URL
        if '/p/' in base_url and not '/search' in base_url:
            data['url'] = base_url
            print(f"✅ Extracted direct Flipkart product URL: {data['url']}")
        else:
            print(f"⚠️  Link doesn't look like a Flipkart product URL: {href}")
            data['url'] = None
    else:
        print(f"⚠️  No direct /p/ product link found")
        data['url'] = None
    
    # Extract image
    img_elem = first_product.select_one('img._396cs4, img._2r_T1I')
    if img_elem:
        img_url = img_elem.get('src') or img_elem.get('data-src')
        if img_url:
            # Get higher resolution
            data['image_url'] = img_url.replace('128/128', '416/416')
    
    # Extract price
    price_elem = first_product.select_one('div._30jeq3, div._25b18c')
    if price_elem:
        price_text = price_elem.get_text().strip()
        price_clean = re.sub(r'[^\d.]', '', price_text)
        if price_clean:
            data['price'] = f"₹{price_clean}"
    
    # Extract rating
    rating_elem = first_product.select_one('div._3LWZlK')
    if rating_elem:
        rating_text = rating_elem.get_text()
        rating_match = re.search(r'([\d.]+)', rating_text)
        if rating_match:
            data['rating'] = float(rating_match.group(1))
    
    # Extract rating count
    rating_count_elem = first_product.select_one('span._2_R_DZ')
    if rating_count_elem:
        count_text = rating_count_elem.get_text()
        count_match = re.search(r'([\d,]+)', count_text)
        if count_match:
            data['rating_count'] = int(count_match.group(1).replace(',', ''))
    
    # Extract specs from TITLE (already has features!) - FASTER & FREE
    title = data.get('title', '')
    if title:
        # Parse title for specifications
        spec_indicators = [
            r'with\s+(.+?)(?:,|$)',
            r'featuring\s+(.+?)(?:,|$)',
            r'(\d+(?:dB|ms|hrs?|W|mAh|GB|MP|inch|mm)[\w\s]*?)(?:,|$)',
            r',\s*([^,]{10,80}?)(?:,|$)',
        ]
        
        for pattern in spec_indicators:
            matches = re.findall(pattern, title, re.IGNORECASE)
            for match in matches[:8]:
                spec = match.strip()
                if spec and len(spec) > 5 and len(spec) < 100:
                    spec = re.sub(r'\s+', ' ', spec)
                    if spec not in data['specs'] and not spec.startswith('₹'):
                        data['specs'].append(spec)
    
    print(f"✅ Found Flipkart product: {data.get('title', 'Unknown')[:50]} | Specs: {len(data.get('specs', []))}")
    return data


