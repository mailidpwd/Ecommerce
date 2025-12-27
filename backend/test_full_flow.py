"""
Test the full recommendation flow with a real product URL
"""
import asyncio
import sys
import os

# Fix Windows console encoding
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Add backend to path
sys.path.insert(0, os.path.dirname(__file__))

async def test_full_flow():
    """Test the complete recommendation flow"""
    print("="*60)
    print("TESTING FULL RECOMMENDATION FLOW")
    print("="*60)
    
    # Import after path setup
    from main import get_recommendations, RecommendRequest
    
    # Test with a real Amazon product URL
    test_url = "https://www.amazon.in/dp/B08N5WRWNW"
    test_share_text = None  # You can add share text here if needed
    
    print(f"\n📥 Test Request:")
    print(f"   URL: {test_url}")
    print(f"   Share Text: {test_share_text or 'None'}")
    
    request = RecommendRequest(
        url=test_url,
        share_text=test_share_text,
        device="test",
        refresh=False
    )
    
    try:
        print(f"\n🚀 Starting recommendation request...")
        result = await get_recommendations(request)
        
        print(f"\n✅ SUCCESS!")
        print(f"   Found {len(result.alternatives)} alternatives")
        for idx, alt in enumerate(result.alternatives[:3], 1):
            print(f"\n   Product {idx}:")
            print(f"      Title: {alt.title[:60]}")
            print(f"      Price: {alt.price_estimate}")
            print(f"      Has Image: {bool(alt.image_url)}")
            print(f"      URL: {alt.source_url[:60]}...")
        
        return True
    except Exception as e:
        print(f"\n❌ FAILED!")
        print(f"   Error: {str(e)}")
        print(f"   Type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_full_flow())
    sys.exit(0 if success else 1)

