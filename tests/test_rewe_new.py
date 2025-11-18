"""Pytest tests for REWE scraper using marketSearch API."""

import pytest
from src.scrapers.rewe import REWEScraper
from src.scrapers.base import Store


class TestREWEScraper:
    """Tests for REWEScraper class."""

    def test_scraper_initialization(self):
        """Test that scraper can be instantiated."""
        scraper = REWEScraper()
        assert scraper.chain_id == 'rewe'
        assert scraper.chain_name == 'REWE'

    def test_scrape_returns_stores(self):
        """Test that scraper returns list of Store objects."""
        # Test with just 2 small states for speed
        scraper = REWEScraper(states=["Bremen", "Hamburg"])
        stores = scraper.scrape()

        assert isinstance(stores, list)
        assert len(stores) > 0
        assert all(isinstance(s, Store) for s in stores)

    def test_store_has_required_fields(self):
        """Test that stores have all required fields."""
        scraper = REWEScraper(states=["Bremen"])
        stores = scraper.scrape()

        # Test first store
        store = stores[0]
        assert store.chain_id == 'rewe'
        assert store.store_id
        assert store.name
        assert store.street
        assert store.postal_code
        assert store.city
        assert store.country_code == 'DE'

    def test_stores_have_coordinates(self):
        """Test that stores have valid coordinates."""
        scraper = REWEScraper(states=["Bremen"])
        stores = scraper.scrape()

        # Check first 5 stores
        for store in stores[:5]:
            assert store.latitude is not None, f"Store {store.name} missing latitude"
            assert store.longitude is not None, f"Store {store.name} missing longitude"

            # Germany latitude: ~47-55°N, longitude: ~5-16°E
            assert 47 <= store.latitude <= 55, f"Invalid latitude for {store.name}: {store.latitude}"
            assert 5 <= store.longitude <= 16, f"Invalid longitude for {store.name}: {store.longitude}"

    def test_stores_count_subset(self):
        """Test that we get a reasonable number of stores from subset."""
        scraper = REWEScraper(states=["Bremen", "Hamburg"])
        stores = scraper.scrape()

        # Bremen + Hamburg should have at least 100 stores combined
        assert len(stores) > 100, f"Expected > 100 stores from Bremen + Hamburg, got {len(stores)}"

    def test_no_duplicate_stores(self):
        """Test that there are no duplicate stores."""
        scraper = REWEScraper(states=["Bremen"])
        stores = scraper.scrape()

        store_ids = [s.store_id for s in stores]
        assert len(store_ids) == len(set(store_ids)), "Found duplicate store IDs"

    def test_all_stores_in_germany(self):
        """Test that all stores are in Germany."""
        scraper = REWEScraper(states=["Bremen"])
        stores = scraper.scrape()

        assert all(s.country_code == 'DE' for s in stores), "All stores should be in Germany"
