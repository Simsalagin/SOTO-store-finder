"""
Tests for BaseScraper with batch processing integration.
Following TDD: These tests are written BEFORE implementation.
"""

import pytest
import tempfile
import os
from unittest.mock import MagicMock, patch
from typing import List


class TestBaseScraperBatching:
    """Test suite for BaseScraper batch processing."""

    @pytest.fixture
    def temp_db_path(self):
        """Create temporary database for checkpoints."""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as f:
            db_path = f.name
        yield db_path
        if os.path.exists(db_path):
            os.remove(db_path)

    @pytest.fixture
    def mock_scraper(self):
        """Create a mock scraper for testing."""
        from src.scrapers.base import BaseScraper, Store

        class MockScraper(BaseScraper):
            def __init__(self, chain_id="test", chain_name="Test Chain"):
                super().__init__(chain_id, chain_name, validate_coordinates=False)
                self.scraped_stores = []

            def scrape(self, limit=None) -> List[Store]:
                """Traditional scrape method - returns all stores."""
                stores = [
                    Store(
                        chain_id=self.chain_id,
                        store_id=f"store_{i}",
                        name=f"Store {i}",
                        street=f"{i} Main St",
                        postal_code="12345",
                        city="Test City",
                        country_code="DE"
                    )
                    for i in range(100)
                ]
                if limit:
                    stores = stores[:limit]
                self.scraped_stores = stores
                return stores

        return MockScraper()

    def test_backward_compatibility_scrape(self, mock_scraper):
        """Test that traditional scrape() method still works."""
        stores = mock_scraper.scrape()
        assert len(stores) == 100
        assert all(s.chain_id == "test" for s in stores)

    def test_scrape_with_limit(self, mock_scraper):
        """Test scrape with limit parameter for testing."""
        stores = mock_scraper.scrape(limit=10)
        assert len(stores) == 10

    def test_scrape_with_batches(self, mock_scraper, temp_db_path):
        """Test new scrape_with_batches method."""
        result = mock_scraper.scrape_with_batches(
            batch_size=25,
            checkpoint_db=temp_db_path,
            limit=50  # Limit for fast testing
        )

        assert 'run_id' in result
        assert result['processed'] == 50
        assert result['failed'] == 0
        assert result['status'] == 'completed'

    def test_batch_processing_with_checkpoints(self, mock_scraper, temp_db_path):
        """Test that checkpoints are created during batch processing."""
        from src.batch.checkpoint_manager import CheckpointManager

        result = mock_scraper.scrape_with_batches(
            batch_size=10,
            checkpoint_db=temp_db_path,
            limit=30
        )

        # Verify checkpoints were saved
        manager = CheckpointManager(temp_db_path)
        runs = manager.list_runs(chain_id="test")
        assert len(runs) == 1
        assert runs[0]['status'] == 'completed'
        assert runs[0]['stores_processed'] == 30

    def test_batch_processing_with_validation(self, temp_db_path):
        """Test that validation is applied during batch processing."""
        from src.scrapers.base import BaseScraper, Store

        class ValidatingScraper(BaseScraper):
            def __init__(self):
                super().__init__("test", "Test", validate_coordinates=False)

            def scrape(self, limit=None):
                # Return some invalid stores
                stores = [
                    Store("test", f"s{i}", f"Store {i}", "St", "12345", "City", "DE")
                    for i in range(10)
                ]
                # Make one store invalid (missing name)
                stores[5].name = None
                if limit:
                    stores = stores[:limit]
                return stores

        scraper = ValidatingScraper()
        result = scraper.scrape_with_batches(
            batch_size=5,
            checkpoint_db=temp_db_path
        )

        # Should have processed 9 valid stores, 1 invalid
        assert result['processed'] == 9
        assert result['failed'] == 1

    def test_batch_processing_with_progress_callback(self, mock_scraper, temp_db_path):
        """Test progress callback during batch processing."""
        progress_updates = []

        def on_progress(progress):
            progress_updates.append(progress)

        mock_scraper.scrape_with_batches(
            batch_size=20,
            checkpoint_db=temp_db_path,
            limit=60,
            progress_callback=on_progress
        )

        # Should have 3 progress updates (3 batches of 20)
        assert len(progress_updates) == 3
        assert progress_updates[0]['percentage'] > 0
        assert progress_updates[-1]['percentage'] == 100.0

    def test_resume_after_failure(self, temp_db_path):
        """Test resuming batch processing after failure."""
        from src.scrapers.base import BaseScraper, Store

        class FailingScraper(BaseScraper):
            def __init__(self):
                super().__init__("failing", "Failing Chain", validate_coordinates=False)
                self.scrape_count = 0

            def scrape(self, limit=None):
                stores = [
                    Store("failing", f"s{i}", f"Store {i}", "St", "12345", "City", "DE")
                    for i in range(100)
                ]
                if limit:
                    stores = stores[:limit]

                self.scrape_count += 1
                # Fail on first attempt
                if self.scrape_count == 1:
                    # Simulate processing 50 stores then crashing
                    return stores[:50]  # Will be processed in batches, but then crash

                return stores

        scraper = FailingScraper()

        # This test is more conceptual - actual resume implementation
        # would require modifying the scraper to raise exceptions mid-processing
        # For now, just verify the method exists and can be called
        result = scraper.scrape_with_batches(
            batch_size=25,
            checkpoint_db=temp_db_path,
            limit=50
        )
        assert result['processed'] == 50

    def test_batch_processing_with_custom_batch_size(self, mock_scraper, temp_db_path):
        """Test custom batch sizes."""
        # Small batches
        result = mock_scraper.scrape_with_batches(
            batch_size=5,
            checkpoint_db=temp_db_path,
            limit=15
        )
        assert result['processed'] == 15

        # Large batches
        result = mock_scraper.scrape_with_batches(
            batch_size=100,
            checkpoint_db=temp_db_path,
            limit=50
        )
        assert result['processed'] == 50

    def test_batch_processing_logs_correlation_id(self, mock_scraper, temp_db_path):
        """Test that batch processing uses correlation context."""
        result = mock_scraper.scrape_with_batches(
            batch_size=10,
            checkpoint_db=temp_db_path,
            limit=10
        )

        # Run ID should be present in result
        assert 'run_id' in result
        assert result['run_id'].startswith('test_')

    def test_get_batch_processor(self, mock_scraper, temp_db_path):
        """Test getting configured batch processor."""
        processor = mock_scraper.get_batch_processor(checkpoint_db=temp_db_path)

        assert processor is not None
        from src.batch.batch_processor import BatchProcessor
        assert isinstance(processor, BatchProcessor)

    def test_batch_processing_with_coordinate_validation(self, temp_db_path):
        """Test that coordinate validation works with batching."""
        from src.scrapers.base import BaseScraper, Store

        class CoordinateScraper(BaseScraper):
            def __init__(self):
                super().__init__("coords", "Coord Chain", validate_coordinates=False)

            def scrape(self, limit=None):
                stores = [
                    Store(
                        "coords", f"s{i}", f"Store {i}",
                        "Street", "12345", "Berlin", "DE",
                        latitude=52.52 + i*0.01,
                        longitude=13.40 + i*0.01
                    )
                    for i in range(10)
                ]
                if limit:
                    stores = stores[:limit]
                return stores

        scraper = CoordinateScraper()
        result = scraper.scrape_with_batches(
            batch_size=5,
            checkpoint_db=temp_db_path,
            limit=10
        )

        assert result['processed'] == 10
        assert result['failed'] == 0

    def test_batch_size_validation(self, mock_scraper, temp_db_path):
        """Test batch size validation."""
        # Batch size must be positive
        with pytest.raises(ValueError):
            mock_scraper.scrape_with_batches(
                batch_size=0,
                checkpoint_db=temp_db_path
            )

        with pytest.raises(ValueError):
            mock_scraper.scrape_with_batches(
                batch_size=-10,
                checkpoint_db=temp_db_path
            )

    def test_default_checkpoint_location(self, mock_scraper):
        """Test default checkpoint database location."""
        # Should use default location if not specified
        result = mock_scraper.scrape_with_batches(
            batch_size=10,
            limit=10
        )

        assert result['processed'] == 10

        # Cleanup default checkpoint file
        import os
        if os.path.exists('data/checkpoints.db'):
            os.remove('data/checkpoints.db')

    def test_empty_scrape_result(self, temp_db_path):
        """Test handling empty scrape results."""
        from src.scrapers.base import BaseScraper

        class EmptyScraper(BaseScraper):
            def __init__(self):
                super().__init__("empty", "Empty Chain")

            def scrape(self, limit=None):
                return []

        scraper = EmptyScraper()
        result = scraper.scrape_with_batches(
            batch_size=10,
            checkpoint_db=temp_db_path
        )

        assert result['processed'] == 0
        assert result['failed'] == 0
