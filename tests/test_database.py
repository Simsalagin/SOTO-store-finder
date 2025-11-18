"""Unit tests for database storage with SOTO product availability tracking."""

import pytest
import tempfile
import os
from datetime import datetime
from src.storage.database import Database, StoreModel
from src.scrapers.base import Store


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.db') as f:
        db_path = f.name

    # Create database
    db = Database(database_path=db_path)

    yield db

    # Cleanup
    os.unlink(db_path)


@pytest.fixture
def sample_store():
    """Create a sample store for testing."""
    return Store(
        chain_id='test_chain',
        store_id='store_001',
        name='Test Store',
        street='Test Street 123',
        postal_code='12345',
        city='Test City',
        country_code='DE',
        latitude=52.5200,
        longitude=13.4050,
        has_soto_products=None  # Will be set in tests
    )


@pytest.fixture
def rewe_store_with_soto():
    """Create a REWE store with SOTO products."""
    return Store(
        chain_id='rewe',
        store_id='762432',
        name='REWE Schmidt',
        street='Schönhauser Allee 80',
        postal_code='10439',
        city='Berlin',
        country_code='DE',
        latitude=52.5437,
        longitude=13.4125,
        has_soto_products=True
    )


@pytest.fixture
def rewe_store_without_soto():
    """Create a REWE store without SOTO products."""
    return Store(
        chain_id='rewe',
        store_id='762433',
        name='REWE Test',
        street='Test Str. 1',
        postal_code='10115',
        city='Berlin',
        country_code='DE',
        latitude=52.5200,
        longitude=13.4050,
        has_soto_products=False
    )


@pytest.fixture
def denns_store():
    """Create a denn's store (assumed to have SOTO)."""
    return Store(
        chain_id='denns',
        store_id='denns_001',
        name="denn's Biomarkt",
        street='Bio Street 1',
        postal_code='80331',
        city='München',
        country_code='DE',
        latitude=48.1351,
        longitude=11.5820,
        has_soto_products=True
    )


class TestDatabaseSchema:
    """Test database schema includes has_soto_products field."""

    def test_store_model_has_soto_field(self):
        """Test that StoreModel has has_soto_products column."""
        assert hasattr(StoreModel, 'has_soto_products')
        column = StoreModel.__table__.columns.get('has_soto_products')
        assert column is not None
        assert column.nullable is True  # Field should be nullable

    def test_store_dataclass_has_soto_field(self):
        """Test that Store dataclass has has_soto_products field."""
        store = Store(
            chain_id='test',
            store_id='001',
            name='Test',
            street='Test St',
            postal_code='12345',
            city='Test City',
            country_code='DE',
            has_soto_products=True
        )
        assert hasattr(store, 'has_soto_products')
        assert store.has_soto_products is True


class TestSaveStoresWithSOTO:
    """Test saving stores with SOTO availability information."""

    def test_save_store_with_soto_true(self, temp_db, rewe_store_with_soto):
        """Test saving a store with has_soto_products=True."""
        count = temp_db.save_stores([rewe_store_with_soto])
        assert count == 1

        # Retrieve and verify
        stores = temp_db.get_stores(chain_id='rewe')
        assert len(stores) == 1
        assert stores[0].has_soto_products is True

    def test_save_store_with_soto_false(self, temp_db, rewe_store_without_soto):
        """Test saving a store with has_soto_products=False."""
        count = temp_db.save_stores([rewe_store_without_soto])
        assert count == 1

        # Retrieve and verify
        stores = temp_db.get_stores(chain_id='rewe')
        assert len(stores) == 1
        assert stores[0].has_soto_products is False

    def test_save_store_with_soto_none(self, temp_db, sample_store):
        """Test saving a store with has_soto_products=None (unknown)."""
        sample_store.has_soto_products = None
        count = temp_db.save_stores([sample_store])
        assert count == 1

        # Retrieve and verify
        stores = temp_db.get_stores(chain_id='test_chain')
        assert len(stores) == 1
        assert stores[0].has_soto_products is None

    def test_save_multiple_stores_mixed_soto(self, temp_db, rewe_store_with_soto,
                                            rewe_store_without_soto, denns_store):
        """Test saving multiple stores with different SOTO availability."""
        stores_to_save = [rewe_store_with_soto, rewe_store_without_soto, denns_store]
        count = temp_db.save_stores(stores_to_save)
        assert count == 3

        # Verify REWE stores
        rewe_stores = temp_db.get_stores(chain_id='rewe')
        assert len(rewe_stores) == 2

        # Check that we have one with SOTO and one without
        soto_flags = sorted([s.has_soto_products for s in rewe_stores])
        assert soto_flags == [False, True]

        # Verify denn's store
        denns_stores = temp_db.get_stores(chain_id='denns')
        assert len(denns_stores) == 1
        assert denns_stores[0].has_soto_products is True


class TestUpdateStoreSOTO:
    """Test updating SOTO availability for existing stores."""

    def test_update_soto_from_none_to_true(self, temp_db, rewe_store_with_soto):
        """Test updating SOTO availability from None to True."""
        # Save initially without SOTO info
        rewe_store_with_soto.has_soto_products = None
        temp_db.save_stores([rewe_store_with_soto])

        # Verify it's None
        stores = temp_db.get_stores(chain_id='rewe')
        assert stores[0].has_soto_products is None

        # Update with SOTO info
        rewe_store_with_soto.has_soto_products = True
        temp_db.save_stores([rewe_store_with_soto])

        # Verify it's updated
        stores = temp_db.get_stores(chain_id='rewe')
        assert len(stores) == 1  # Should still be only one store
        assert stores[0].has_soto_products is True

    def test_update_soto_from_true_to_false(self, temp_db, rewe_store_with_soto):
        """Test updating SOTO availability from True to False."""
        # Save initially with SOTO
        temp_db.save_stores([rewe_store_with_soto])

        # Update without SOTO
        rewe_store_with_soto.has_soto_products = False
        temp_db.save_stores([rewe_store_with_soto])

        # Verify it's updated
        stores = temp_db.get_stores(chain_id='rewe')
        assert len(stores) == 1
        assert stores[0].has_soto_products is False


class TestQueryStoresBySOTO:
    """Test querying stores based on SOTO availability."""

    def test_get_all_stores_with_soto(self, temp_db, rewe_store_with_soto,
                                     rewe_store_without_soto, denns_store):
        """Test retrieving only stores with SOTO products."""
        # Save mixed stores
        temp_db.save_stores([rewe_store_with_soto, rewe_store_without_soto, denns_store])

        # Get all stores
        all_stores = temp_db.get_stores()

        # Filter for SOTO stores
        soto_stores = [s for s in all_stores if s.has_soto_products is True]
        assert len(soto_stores) == 2  # REWE with SOTO + denn's

        # Verify chain IDs
        chain_ids = sorted([s.chain_id for s in soto_stores])
        assert 'denns' in chain_ids
        assert 'rewe' in chain_ids

    def test_count_stores_by_soto_status(self, temp_db, rewe_store_with_soto,
                                        rewe_store_without_soto, denns_store):
        """Test counting stores by SOTO availability status."""
        # Add another store with unknown SOTO status
        unknown_store = Store(
            chain_id='rewe',
            store_id='999999',
            name='REWE Unknown',
            street='Unknown St',
            postal_code='00000',
            city='Unknown',
            country_code='DE',
            has_soto_products=None
        )

        temp_db.save_stores([
            rewe_store_with_soto,
            rewe_store_without_soto,
            denns_store,
            unknown_store
        ])

        all_stores = temp_db.get_stores()

        with_soto = sum(1 for s in all_stores if s.has_soto_products is True)
        without_soto = sum(1 for s in all_stores if s.has_soto_products is False)
        unknown_soto = sum(1 for s in all_stores if s.has_soto_products is None)

        assert with_soto == 2  # REWE with SOTO + denn's
        assert without_soto == 1  # REWE without SOTO
        assert unknown_soto == 1  # REWE unknown


class TestDatabaseStatistics:
    """Test that database statistics work with SOTO field."""

    def test_statistics_with_soto_stores(self, temp_db, rewe_store_with_soto, denns_store):
        """Test that statistics still work correctly with SOTO field."""
        temp_db.save_stores([rewe_store_with_soto, denns_store])

        stats = temp_db.get_statistics()

        assert stats['total_stores'] == 2
        assert stats['active_stores'] == 2
        assert 'rewe' in stats['chains']
        assert 'denns' in stats['chains']
        assert stats['chains']['rewe'] == 1
        assert stats['chains']['denns'] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
