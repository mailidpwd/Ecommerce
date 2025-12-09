"""Test ScraperAPI scraping only, without Gemini"""
import asyncio
from scraper_api import scrape_product_scraperapi

async def test_scraper():
    url = "https://www.amazon.in/dp/B0CFF2K7C8"
    
    print(f"🧪 Testing ScraperAPI with: {url}")
    print("=" * 60)
    
    try:
        data = await scrape_product_scraperapi(url)
        
        print("\n✅ ScraperAPI SUCCESS!")
        print(f"\nProduct Data:")
        print(f"  Title: {data.get('title')}")
        print(f"  Price: {data.get('price')}")
        print(f"  Image: {data.get('image_url', 'None')[:80]}...")
        print(f"  Rating: {data.get('rating')}")
        print(f"  Specs: {len(data.get('specs', []))} found")
        
        if data.get('specs'):
            print(f"\n  First 3 specs:")
            for spec in data['specs'][:3]:
                print(f"    - {spec}")
        
        print("\n✅ ScraperAPI is working correctly!")
        return data
        
    except Exception as e:
        print(f"\n❌ ScraperAPI FAILED: {str(e)}")
        return None

if __name__ == "__main__":
    asyncio.run(test_scraper())


