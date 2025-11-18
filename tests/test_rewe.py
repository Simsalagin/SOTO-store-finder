"""Test script for REWE scraper."""

from src.scrapers.rewe import REWEScraper
from src.storage.database import Database


def main():
    """Test the REWE scraper and save to database."""
    print("=" * 60)
    print("Testing REWE Scraper")
    print("=" * 60)

    # Initialize scraper
    print("\n1. Initializing scraper...")
    scraper = REWEScraper()
    assert scraper.chain_id == 'rewe'
    assert scraper.chain_name == 'REWE'
    print("   ✓ Scraper initialized")

    # Scrape stores
    print("\n2. Scraping stores from API...")
    print("   (This may take 10-15 minutes - searching ~1,000 postal codes)")
    stores = scraper.scrape()

    print(f"\n   ✓ Found {len(stores)} stores")
    assert len(stores) > 2500, f"Expected > 2500 stores, got {len(stores)}"
    assert all(store.chain_id == 'rewe' for store in stores)

    # Validate store structure
    print("\n3. Validating store structure...")
    for store in stores[:5]:  # Check first 5 stores
        assert store.store_id, "Store must have store_id"
        assert store.name, "Store must have name"
        assert store.street, "Store must have street"
        assert store.postal_code, "Store must have postal_code"
        assert store.city, "Store must have city"
        assert store.country_code == 'DE', "Store must be in Germany"
        assert store.latitude is not None, "Store must have latitude"
        assert store.longitude is not None, "Store must have longitude"
        assert 47 <= store.latitude <= 55, f"Invalid latitude for Germany: {store.latitude}"
        assert 5 <= store.longitude <= 16, f"Invalid longitude for Germany: {store.longitude}"
    print("   ✓ Store structure valid")

    # Show sample stores
    print("\n4. Sample stores:")
    for i, store in enumerate(stores[:3], 1):
        print(f"\n   Store #{i}:")
        print(f"   - ID: {store.store_id}")
        print(f"   - Name: {store.name}")
        print(f"   - Company: {store.name}")  # REWE shows company name
        print(f"   - Address: {store.street}, {store.postal_code} {store.city}")
        print(f"   - Coordinates: {store.latitude}, {store.longitude}")
        if store.opening_hours:
            print(f"   - Opening hours: {len(store.opening_hours)} days")

    # Test Germany-only filter
    print("\n5. Checking country filter...")
    non_de_stores = [s for s in stores if s.country_code != 'DE']
    print(f"   - All stores in DE: {len(non_de_stores) == 0}")
    assert len(non_de_stores) == 0, "All stores should be in Germany"

    # Initialize database
    print("\n6. Initializing database...")
    db = Database()

    # Save to database
    print("7. Saving stores to database...")
    saved_count = db.save_stores(stores)
    print(f"   ✓ Saved/updated {saved_count} stores")

    # Show statistics
    print("\n8. Database statistics:")
    stats = db.get_statistics()
    print(f"   - Total stores: {stats['total_stores']}")
    print(f"   - Active stores: {stats['active_stores']}")
    print(f"   - Chains: {stats['chains']}")

    # Test retrieval
    print("\n9. Testing retrieval of REWE stores:")
    rewe_stores = db.get_stores(chain_id='rewe')
    print(f"   - REWE stores in DB: {len(rewe_stores)}")
    assert len(rewe_stores) >= len(stores), "All scraped stores should be in database"

    print("\n" + "=" * 60)
    print("✓ Test completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    main()
