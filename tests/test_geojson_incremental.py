"""
Tests for incremental GeoJSON export functionality.
Following TDD: These tests are written BEFORE implementation.
"""

import pytest
import json
import tempfile
import os
from pathlib import Path


class TestIncrementalGeoJSONExport:
    """Test suite for incremental GeoJSON updates."""

    @pytest.fixture
    def temp_geojson_path(self):
        """Create temporary GeoJSON file."""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.geojson', mode='w') as f:
            geojson_path = f.name
        yield geojson_path
        if os.path.exists(geojson_path):
            os.remove(geojson_path)

    @pytest.fixture
    def sample_stores(self):
        """Create sample store data."""
        from src.scrapers.base import Store
        return [
            Store(
                chain_id="test",
                store_id="store_1",
                name="Test Store 1",
                street="1 Main St",
                postal_code="12345",
                city="Test City",
                country_code="DE",
                latitude=52.52,
                longitude=13.40
            ),
            Store(
                chain_id="test",
                store_id="store_2",
                name="Test Store 2",
                street="2 Main St",
                postal_code="12345",
                city="Test City",
                country_code="DE",
                latitude=52.53,
                longitude=13.41
            )
        ]

    def test_create_new_geojson_file(self, temp_geojson_path, sample_stores):
        """Test creating GeoJSON file from scratch."""
        from api.export_geojson import update_geojson_incremental

        # Remove file to ensure clean state
        if os.path.exists(temp_geojson_path):
            os.remove(temp_geojson_path)

        # Update with initial stores
        update_geojson_incremental(sample_stores, output_path=temp_geojson_path)

        # Verify file exists
        assert os.path.exists(temp_geojson_path)

        # Verify content
        with open(temp_geojson_path) as f:
            geojson = json.load(f)

        assert geojson['type'] == 'FeatureCollection'
        assert len(geojson['features']) == 2
        assert geojson['features'][0]['properties']['store_id'] == 'store_1'
        assert geojson['features'][1]['properties']['store_id'] == 'store_2'

    def test_append_new_stores_to_existing_file(self, temp_geojson_path, sample_stores):
        """Test appending new stores to existing GeoJSON file."""
        from api.export_geojson import update_geojson_incremental
        from src.scrapers.base import Store

        # Create initial file with 2 stores
        update_geojson_incremental(sample_stores[:1], output_path=temp_geojson_path)

        # Verify initial state
        with open(temp_geojson_path) as f:
            geojson = json.load(f)
        assert len(geojson['features']) == 1

        # Add one more store
        new_store = Store(
            chain_id="test",
            store_id="store_3",
            name="Test Store 3",
            street="3 Main St",
            postal_code="12345",
            city="Test City",
            country_code="DE",
            latitude=52.54,
            longitude=13.42
        )

        update_geojson_incremental([new_store], output_path=temp_geojson_path)

        # Verify updated state
        with open(temp_geojson_path) as f:
            geojson = json.load(f)

        assert len(geojson['features']) == 2
        store_ids = [f['properties']['store_id'] for f in geojson['features']]
        assert 'store_1' in store_ids
        assert 'store_3' in store_ids

    def test_update_existing_store(self, temp_geojson_path, sample_stores):
        """Test updating an existing store in GeoJSON file."""
        from api.export_geojson import update_geojson_incremental
        from src.scrapers.base import Store

        # Create initial file
        update_geojson_incremental(sample_stores[:1], output_path=temp_geojson_path)

        # Update the same store with new data
        updated_store = Store(
            chain_id="test",
            store_id="store_1",  # Same ID
            name="Updated Store Name",  # Changed name
            street="1 Main St",
            postal_code="12345",
            city="Test City",
            country_code="DE",
            latitude=52.52,
            longitude=13.40
        )

        update_geojson_incremental([updated_store], output_path=temp_geojson_path)

        # Verify store was updated, not duplicated
        with open(temp_geojson_path) as f:
            geojson = json.load(f)

        assert len(geojson['features']) == 1  # Still only 1 store
        assert geojson['features'][0]['properties']['name'] == 'Updated Store Name'

    def test_batch_update_mixed_new_and_existing(self, temp_geojson_path, sample_stores):
        """Test batch update with mix of new and existing stores."""
        from api.export_geojson import update_geojson_incremental
        from src.scrapers.base import Store

        # Create initial file with store_1
        update_geojson_incremental(sample_stores[:1], output_path=temp_geojson_path)

        # Batch update: update store_1 and add store_2
        updated_store_1 = Store(
            chain_id="test",
            store_id="store_1",
            name="Updated Store 1",
            street="1 Main St",
            postal_code="12345",
            city="Test City",
            country_code="DE",
            latitude=52.52,
            longitude=13.40
        )

        update_geojson_incremental([updated_store_1, sample_stores[1]], output_path=temp_geojson_path)

        # Verify
        with open(temp_geojson_path) as f:
            geojson = json.load(f)

        assert len(geojson['features']) == 2
        names = [f['properties']['name'] for f in geojson['features']]
        assert 'Updated Store 1' in names
        assert 'Test Store 2' in names

    def test_preserve_other_chains_stores(self, temp_geojson_path):
        """Test that updating one chain preserves stores from other chains."""
        from api.export_geojson import update_geojson_incremental
        from src.scrapers.base import Store

        # Add stores from chain A
        chain_a_stores = [
            Store("chain_a", "a1", "Store A1", "St", "12345", "City", "DE", 52.52, 13.40),
            Store("chain_a", "a2", "Store A2", "St", "12345", "City", "DE", 52.53, 13.41)
        ]
        update_geojson_incremental(chain_a_stores, output_path=temp_geojson_path)

        # Add stores from chain B
        chain_b_stores = [
            Store("chain_b", "b1", "Store B1", "St", "12345", "City", "DE", 52.54, 13.42)
        ]
        update_geojson_incremental(chain_b_stores, output_path=temp_geojson_path)

        # Verify both chains exist
        with open(temp_geojson_path) as f:
            geojson = json.load(f)

        assert len(geojson['features']) == 3
        chain_ids = [f['properties']['chain_id'] for f in geojson['features']]
        assert chain_ids.count('chain_a') == 2
        assert chain_ids.count('chain_b') == 1

    def test_store_with_has_soto_products(self, temp_geojson_path):
        """Test that has_soto_products field is included in GeoJSON."""
        from api.export_geojson import update_geojson_incremental
        from src.scrapers.base import Store

        store_with_soto = Store(
            chain_id="rewe",
            store_id="rewe_1",
            name="REWE Store with SOTO",
            street="1 Main St",
            postal_code="12345",
            city="Berlin",
            country_code="DE",
            latitude=52.52,
            longitude=13.40,
            has_soto_products=True
        )

        store_without_soto = Store(
            chain_id="rewe",
            store_id="rewe_2",
            name="REWE Store without SOTO",
            street="2 Main St",
            postal_code="12345",
            city="Berlin",
            country_code="DE",
            latitude=52.53,
            longitude=13.41,
            has_soto_products=False
        )

        update_geojson_incremental([store_with_soto, store_without_soto], output_path=temp_geojson_path)

        # Verify has_soto_products is in GeoJSON
        with open(temp_geojson_path) as f:
            geojson = json.load(f)

        assert len(geojson['features']) == 2

        # Find stores by ID
        soto_store = next(f for f in geojson['features'] if f['properties']['store_id'] == 'rewe_1')
        no_soto_store = next(f for f in geojson['features'] if f['properties']['store_id'] == 'rewe_2')

        assert soto_store['properties']['has_soto_products'] is True
        assert no_soto_store['properties']['has_soto_products'] is False

    def test_empty_batch_does_not_clear_file(self, temp_geojson_path, sample_stores):
        """Test that updating with empty batch preserves existing stores."""
        from api.export_geojson import update_geojson_incremental

        # Create initial file
        update_geojson_incremental(sample_stores, output_path=temp_geojson_path)

        # Update with empty batch
        update_geojson_incremental([], output_path=temp_geojson_path)

        # Verify stores still exist
        with open(temp_geojson_path) as f:
            geojson = json.load(f)

        assert len(geojson['features']) == 2

    def test_coordinates_format(self, temp_geojson_path, sample_stores):
        """Test that coordinates are in [lon, lat] format (GeoJSON standard)."""
        from api.export_geojson import update_geojson_incremental

        update_geojson_incremental(sample_stores[:1], output_path=temp_geojson_path)

        with open(temp_geojson_path) as f:
            geojson = json.load(f)

        feature = geojson['features'][0]
        coords = feature['geometry']['coordinates']

        # GeoJSON format: [longitude, latitude]
        assert coords[0] == 13.40  # longitude
        assert coords[1] == 52.52  # latitude

    def test_unique_store_key_format(self, temp_geojson_path):
        """Test that store uniqueness is based on chain_id + store_id."""
        from api.export_geojson import update_geojson_incremental
        from src.scrapers.base import Store

        # Add store from chain A with ID "1"
        store_a = Store("chain_a", "1", "Store A", "St", "12345", "City", "DE", 52.52, 13.40)
        update_geojson_incremental([store_a], output_path=temp_geojson_path)

        # Add store from chain B with same ID "1" (should be separate)
        store_b = Store("chain_b", "1", "Store B", "St", "12345", "City", "DE", 52.53, 13.41)
        update_geojson_incremental([store_b], output_path=temp_geojson_path)

        # Verify both stores exist (different chains, same store_id)
        with open(temp_geojson_path) as f:
            geojson = json.load(f)

        assert len(geojson['features']) == 2

    def test_json_formatting(self, temp_geojson_path, sample_stores):
        """Test that JSON output is properly formatted with indentation."""
        from api.export_geojson import update_geojson_incremental

        update_geojson_incremental(sample_stores[:1], output_path=temp_geojson_path)

        # Read raw file content
        with open(temp_geojson_path) as f:
            content = f.read()

        # Verify it's indented (contains newlines and spaces)
        assert '\n' in content
        assert '  ' in content  # 2-space indentation
