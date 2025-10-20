"""Test script for Alnatura scraper."""

from src.scrapers.alnatura import AlnaturaScraper


def main():
    """Test the Alnatura scraper with sample pages."""
    print("=" * 60)
    print("Testing Alnatura Scraper (Sample Pages)")
    print("=" * 60)

    # Initialize scraper
    print("\n1. Initializing scraper...")
    scraper = AlnaturaScraper()

    # Get market URLs
    print("2. Getting market URLs from sitemap...")
    market_urls = scraper._get_market_urls()
    print(f"   ✓ Found {len(market_urls)} market pages")

    # Test first 3 pages
    print("\n3. Testing first 3 market pages:")
    test_urls = market_urls[:3]

    for i, url in enumerate(test_urls, 1):
        print(f"\n   Page {i}: {url}")
        store = scraper._scrape_market_page(url)

        if store:
            print(f"   ✓ Store: {store.name}")
            print(f"     Address: {store.street}, {store.postal_code} {store.city}")
            if store.latitude and store.longitude:
                print(f"     Coordinates: {store.latitude}, {store.longitude}")
            else:
                print(f"     Coordinates: NOT FOUND - will be geocoded")
            if store.phone:
                print(f"     Phone: {store.phone}")
        else:
            print(f"   ✗ Failed to parse")

    print("\n" + "=" * 60)
    print("Sample test completed")
    print("=" * 60)


if __name__ == "__main__":
    main()
