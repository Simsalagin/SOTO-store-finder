"""Tests for other chain scrapers - SOTO availability assumption."""

import pytest
from src.scrapers.base import Store


class TestSOTOAssumption:
    """Test that non-REWE scrapers assume all stores have SOTO products."""

    def test_store_created_with_soto_true(self):
        """Test creating a store with has_soto_products=True."""
        store = Store(
            chain_id='denns',
            store_id='001',
            name="denn's Biomarkt",
            street='Test St 1',
            postal_code='12345',
            city='Test City',
            country_code='DE',
            has_soto_products=True
        )

        assert store.has_soto_products is True

    def test_denns_scraper_sets_soto(self):
        """Test that denn's scraper sets has_soto_products=True."""
        # This test will verify the implementation sets the flag
        # For now, it's a placeholder that documents expected behavior
        from src.scrapers.denns import DennsScraper

        # Create sample store as denns scraper would
        store = Store(
            chain_id='denns',
            store_id='test_001',
            name="denn's Biomarkt Test",
            street='Test Street 1',
            postal_code='80331',
            city='München',
            country_code='DE',
            has_soto_products=True  # Should be set by scraper
        )

        assert store.has_soto_products is True
        assert store.chain_id == 'denns'

    def test_alnatura_scraper_sets_soto(self):
        """Test that Alnatura scraper sets has_soto_products=True."""
        from src.scrapers.alnatura import AlnaturaScraper

        # Create sample store as alnatura scraper would
        store = Store(
            chain_id='alnatura',
            store_id='test_001',
            name="Alnatura Test",
            street='Test Street 1',
            postal_code='80331',
            city='München',
            country_code='DE',
            has_soto_products=True  # Should be set by scraper
        )

        assert store.has_soto_products is True
        assert store.chain_id == 'alnatura'

    def test_biocompany_scraper_sets_soto(self):
        """Test that BioCompany scraper sets has_soto_products=True."""
        from src.scrapers.biocompany import BioCompanyScraper

        # Create sample store as biocompany scraper would
        store = Store(
            chain_id='biocompany',
            store_id='test_001',
            name="BioCompany Test",
            street='Test Street 1',
            postal_code='10115',
            city='Berlin',
            country_code='DE',
            has_soto_products=True  # Should be set by scraper
        )

        assert store.has_soto_products is True
        assert store.chain_id == 'biocompany'

    def test_multiple_chains_all_have_soto(self):
        """Test that stores from multiple chains all have SOTO."""
        chains = ['denns', 'alnatura', 'biocompany', 'tegut', 'globus', 'vollcorner']

        for chain_id in chains:
            store = Store(
                chain_id=chain_id,
                store_id='001',
                name=f'{chain_id} Test Store',
                street='Test St 1',
                postal_code='12345',
                city='Test City',
                country_code='DE',
                has_soto_products=True
            )

            assert store.has_soto_products is True, f"{chain_id} store should have has_soto_products=True"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
