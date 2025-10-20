"""Test script for denn's Biomarkt scraper."""

from src.scrapers.denns import DennsScraper
from src.storage.database import Database


def main():
    """Test the denn's scraper and save to database."""
    print("=" * 60)
    print("Testing denn's Biomarkt Scraper")
    print("=" * 60)

    # Initialize scraper
    print("\n1. Initializing scraper...")
    scraper = DennsScraper()

    # Scrape stores
    print("2. Scraping stores from API...")
    stores = scraper.scrape()
    print(f"   ✓ Found {len(stores)} stores")

    # Show first 3 stores as examples
    print("\n3. Sample stores:")
    for i, store in enumerate(stores[:3], 1):
        print(f"\n   Store #{i}:")
        print(f"   - Name: {store.name}")
        print(f"   - Address: {store.street}, {store.postal_code} {store.city}")
        print(f"   - Coordinates: {store.latitude}, {store.longitude}")
        print(f"   - Phone: {store.phone}")
        if store.services:
            print(f"   - Services: {', '.join(store.services[:3])}...")
        if store.opening_hours:
            monday = store.opening_hours.get('Montag', {})
            if monday:
                print(f"   - Monday hours: {monday.get('open_from')} - {monday.get('open_until')}")

    # Initialize database
    print("\n4. Initializing database...")
    db = Database()

    # Save to database
    print("5. Saving stores to database...")
    saved_count = db.save_stores(stores)
    print(f"   ✓ Saved/updated {saved_count} stores")

    # Show statistics
    print("\n6. Database statistics:")
    stats = db.get_statistics()
    print(f"   - Total stores: {stats['total_stores']}")
    print(f"   - Active stores: {stats['active_stores']}")
    print(f"   - Chains: {stats['chains']}")

    # Test retrieval
    print("\n7. Testing retrieval (first 3 cities):")
    all_stores = db.get_stores()
    cities = list(set(s.city for s in all_stores))[:3]
    for city in cities:
        city_stores = db.get_stores(city=city)
        print(f"   - {city}: {len(city_stores)} stores")

    print("\n" + "=" * 60)
    print("✓ Test completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    main()
