"""
Product Scraper for Amazon India and Flipkart
Uses Playwright for reliable scraping
"""

import asyncio
import json
import re
from typing import Dict, Optional, List
from playwright.async_api import async_playwright, Page, Browser
from urllib.parse import urlparse, quote_plus


class ProductScraper:
    """Scrapes product data from Amazon India and Flipkart"""
    
    def __init__(self):
        self.browser: Optional[Browser] = None
        self.user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    
    async def __aenter__(self):
        """Context manager entry - OPTIMIZED FOR SPEED"""
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-accelerated-2d-canvas',
                '--disable-gpu',
                '--disable-software-rasterizer',
                '--disable-extensions',
                '--disable-plugins',
            ]
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        if self.browser:
            await self.browser.close()
    
    def _detect_source(self, url: str) -> str:
        """Detect if URL is Amazon or Flipkart"""
        domain = urlparse(url).netloc.lower()
        if 'amazon' in domain:
            return 'amazon'
        elif 'flipkart' in domain:
            return 'flipkart'
        return 'unknown'
    
    async def _create_page(self) -> Page:
        """Create new page with anti-detection measures - SPEED OPTIMIZED"""
        if not self.browser:
            raise RuntimeError("Browser not initialized")
        
        page = await self.browser.new_page(
            user_agent=self.user_agent,
            viewport={'width': 1920, 'height': 1080}
        )
        
        # SPEED OPTIMIZATION: Block unnecessary resources
        await page.route("**/*.{png,jpg,jpeg,gif,svg,css,font,woff,woff2}", lambda route: route.abort())
        await page.route("**/*{google-analytics,doubleclick,facebook,twitter,analytics}*", lambda route: route.abort())
        
        # Set extra headers
        await page.set_extra_http_headers({
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        })
        
        return page
    
    async def scrape_amazon(self, url: str) -> Dict:
        """Scrape Amazon India product page - SPEED OPTIMIZED"""
        print(f"⚡ Fast-scraping Amazon: {url}")
        
        page = await self._create_page()
        
        try:
            # Navigate to page - FAST MODE (increased timeout for slow pages)
            await page.goto(url, wait_until='domcontentloaded', timeout=20000)
            await asyncio.sleep(0.5)  # Minimal wait for dynamic content
            
            # Extract data using multiple strategies
            data = {}
            
            # 1. Try JSON-LD structured data (most reliable)
            try:
                json_ld = await page.locator('script[type="application/ld+json"]').first.inner_text()
                structured_data = json.loads(json_ld)
                if isinstance(structured_data, list):
                    structured_data = structured_data[0]
                
                data['title'] = structured_data.get('name', '')
                data['image_url'] = structured_data.get('image', '')
                if isinstance(data['image_url'], list):
                    data['image_url'] = data['image_url'][0]
                
                # Extract price
                offers = structured_data.get('offers', {})
                if isinstance(offers, dict):
                    price_str = offers.get('price', '')
                    data['price'] = f"₹{price_str}" if price_str else None
            except:
                pass
            
            # 2. Fallback to CSS selectors
            if not data.get('title'):
                title_selectors = [
                    '#productTitle',
                    'span#productTitle',
                    'h1.product-title'
                ]
                for selector in title_selectors:
                    try:
                        title = await page.locator(selector).first.inner_text()
                        data['title'] = title.strip()
                        break
                    except:
                        continue
            
            if not data.get('image_url'):
                image_selectors = [
                    '#landingImage',
                    '#imgBlkFront',
                    'img[data-old-hires]',
                    'img.a-dynamic-image'
                ]
                for selector in image_selectors:
                    try:
                        img_elem = page.locator(selector).first
                        # Get high-res image
                        data_src = await img_elem.get_attribute('data-old-hires')
                        if not data_src:
                            data_src = await img_elem.get_attribute('src')
                        data['image_url'] = data_src
                        break
                    except:
                        continue
            
            if not data.get('price'):
                price_selectors = [
                    'span.a-price-whole',
                    '.a-price .a-offscreen',
                    '#priceblock_ourprice',
                    '#priceblock_dealprice'
                ]
                for selector in price_selectors:
                    try:
                        price_text = await page.locator(selector).first.inner_text()
                        # Clean price (remove commas, spaces)
                        price_clean = re.sub(r'[^\d.]', '', price_text)
                        if price_clean:
                            data['price'] = f"₹{price_clean}"
                            break
                    except:
                        continue
            
            # Extract rating
            try:
                rating_text = await page.locator('span.a-icon-alt').first.inner_text()
                rating_match = re.search(r'([\d.]+)', rating_text)
                if rating_match:
                    data['rating'] = float(rating_match.group(1))
                
                # Rating count
                rating_count = await page.locator('#acrCustomerReviewText').first.inner_text()
                count_match = re.search(r'([\d,]+)', rating_count)
                if count_match:
                    data['rating_count'] = int(count_match.group(1).replace(',', ''))
            except:
                data['rating'] = None
                data['rating_count'] = None
            
            # Extract specs from feature bullets
            specs = []
            try:
                bullets = page.locator('#feature-bullets li span.a-list-item')
                count = await bullets.count()
                for i in range(min(count, 8)):  # Get up to 8 specs
                    spec_text = await bullets.nth(i).inner_text()
                    spec_clean = spec_text.strip()
                    if spec_clean and len(spec_clean) < 150:
                        specs.append(spec_clean)
            except:
                pass
            
            data['specs'] = specs
            data['source'] = 'amazon'
            data['url'] = url
            
            print(f"✅ Scraped Amazon product: {data.get('title', 'Unknown')[:50]}")
            return data
            
        except Exception as e:
            print(f"❌ Error scraping Amazon: {str(e)}")
            raise
        finally:
            await page.close()
    
    async def scrape_flipkart(self, url: str) -> Dict:
        """Scrape Flipkart product page - SPEED OPTIMIZED"""
        print(f"⚡ Fast-scraping Flipkart: {url}")
        
        page = await self._create_page()
        
        try:
            # Navigate to page - FAST MODE (increased timeout for slow pages)
            await page.goto(url, wait_until='domcontentloaded', timeout=20000)
            await asyncio.sleep(0.5)  # Minimal wait for dynamic content
            
            data = {}
            
            # Extract title
            title_selectors = [
                'span.VU-ZEz',
                'h1.yhB1nd',
                'h1 span'
            ]
            for selector in title_selectors:
                try:
                    title = await page.locator(selector).first.inner_text()
                    data['title'] = title.strip()
                    break
                except:
                    continue
            
            # Extract image
            image_selectors = [
                'img.DByuf4',
                'img[loading="eager"]',
                'div._4WELSP img'
            ]
            for selector in image_selectors:
                try:
                    img = await page.locator(selector).first.get_attribute('src')
                    if img and 'static' not in img:  # Skip static placeholder
                        data['image_url'] = img.replace('128/128', '416/416')  # Get higher res
                        break
                except:
                    continue
            
            # Extract price
            price_selectors = [
                'div.Nx9bqj',
                'div._30jeq3',
                'div._16Jk6d'
            ]
            for selector in price_selectors:
                try:
                    price_text = await page.locator(selector).first.inner_text()
                    price_clean = re.sub(r'[^\d.]', '', price_text)
                    if price_clean:
                        data['price'] = f"₹{price_clean}"
                        break
                except:
                    continue
            
            # Extract rating
            try:
                rating_text = await page.locator('div.XQDdHH').first.inner_text()
                rating_match = re.search(r'([\d.]+)', rating_text)
                if rating_match:
                    data['rating'] = float(rating_match.group(1))
                
                # Rating count
                rating_count_text = await page.locator('span.Wphh3N').first.inner_text()
                count_match = re.search(r'([\d,]+)', rating_count_text)
                if count_match:
                    data['rating_count'] = int(count_match.group(1).replace(',', ''))
            except:
                data['rating'] = None
                data['rating_count'] = None
            
            # Extract specs
            specs = []
            try:
                spec_rows = page.locator('div._6R0wZ6 tr')
                count = await spec_rows.count()
                for i in range(min(count, 8)):
                    try:
                        label = await spec_rows.nth(i).locator('td').nth(0).inner_text()
                        value = await spec_rows.nth(i).locator('td').nth(1).inner_text()
                        spec = f"{label}: {value}".strip()
                        if len(spec) < 150:
                            specs.append(spec)
                    except:
                        continue
            except:
                pass
            
            data['specs'] = specs
            data['source'] = 'flipkart'
            data['url'] = url
            
            print(f"✅ Scraped Flipkart product: {data.get('title', 'Unknown')[:50]}")
            return data
            
        except Exception as e:
            print(f"❌ Error scraping Flipkart: {str(e)}")
            raise
        finally:
            await page.close()
    
    async def scrape_product(self, url: str) -> Dict:
        """Main scraping method - detects source and scrapes accordingly"""
        source = self._detect_source(url)
        
        if source == 'amazon':
            return await self.scrape_amazon(url)
        elif source == 'flipkart':
            return await self.scrape_flipkart(url)
        else:
            raise ValueError(f"Unsupported URL: {url}")


# Example usage
async def main():
    """Test scraper"""
    test_urls = [
        "https://www.amazon.in/dp/B097JMG7ZB",  # Example Amazon URL
        "https://www.flipkart.com/safari-pentagon-hardside/p/itm123"  # Example Flipkart URL
    ]
    
    async with ProductScraper() as scraper:
        for url in test_urls:
            try:
                data = await scraper.scrape_product(url)
                print(f"\n{json.dumps(data, indent=2, ensure_ascii=False)}\n")
            except Exception as e:
                print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())

