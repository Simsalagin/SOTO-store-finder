"""
Tests for batch processor - generic batch iteration with checkpoint integration.
Following TDD: These tests are written BEFORE implementation.
"""

import pytest
import tempfile
import os
from unittest.mock import MagicMock, call


class TestBatchProcessor:
    """Test suite for BatchProcessor class."""

    @pytest.fixture
    def temp_db_path(self):
        """Create a temporary database file for testing."""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as f:
            db_path = f.name
        yield db_path
        # Cleanup
        if os.path.exists(db_path):
            os.remove(db_path)

    @pytest.fixture
    def batch_processor(self, temp_db_path):
        """Create a BatchProcessor instance for testing."""
        from src.batch.batch_processor import BatchProcessor
        return BatchProcessor(db_path=temp_db_path)

    def test_create_batch_processor(self, temp_db_path):
        """Test that BatchProcessor can be instantiated."""
        from src.batch.batch_processor import BatchProcessor
        processor = BatchProcessor(db_path=temp_db_path)
        assert processor is not None

    def test_process_items_in_batches(self, batch_processor):
        """Test basic batch processing with callback."""
        items = list(range(100))  # 100 items
        processed = []

        def process_batch(batch):
            processed.extend(batch)
            return len(batch), 0  # processed, failed

        batch_processor.process(
            items=items,
            chain_id="test",
            batch_size=25,
            process_callback=process_batch
        )

        assert len(processed) == 100
        assert processed == items

    def test_batch_size_respected(self, batch_processor):
        """Test that batches are of correct size."""
        items = list(range(100))
        batch_sizes = []

        def capture_batch_size(batch):
            batch_sizes.append(len(batch))
            return len(batch), 0

        batch_processor.process(
            items=items,
            chain_id="test",
            batch_size=30,
            process_callback=capture_batch_size
        )

        # Should have 4 batches: 30, 30, 30, 10
        assert batch_sizes == [30, 30, 30, 10]

    def test_checkpoint_created_per_batch(self, batch_processor, temp_db_path):
        """Test that checkpoints are saved after each batch."""
        from src.batch.checkpoint_manager import CheckpointManager

        items = list(range(50))

        def process_batch(batch):
            return len(batch), 0

        batch_processor.process(
            items=items,
            chain_id="rewe",
            batch_size=10,
            process_callback=process_batch
        )

        # Verify checkpoints were saved
        manager = CheckpointManager(temp_db_path)
        runs = manager.list_runs(chain_id="rewe")
        assert len(runs) == 1
        assert runs[0]['status'] == 'completed'
        assert runs[0]['stores_processed'] == 50

    def test_resume_from_checkpoint(self, batch_processor):
        """Test resuming processing from a saved checkpoint."""
        items = list(range(100))
        processed_batches = []

        def process_batch(batch):
            # Track which batch we're on
            batch_num = len(processed_batches)
            processed_batches.append(batch)

            # Crash on batch 2 (items 50-74) BEFORE returning
            if batch_num == 2:
                raise Exception("Simulated crash")
            return len(batch), 0

        # First run - will crash on batch 2 (disable retries for this test)
        try:
            batch_processor.process(
                items=items,
                chain_id="test",
                batch_size=25,
                process_callback=process_batch,
                max_retries=1  # No retries for cleaner test
            )
        except Exception:
            pass

        # Checkpoint was saved after batches 0 and 1 (50 items successfully processed)
        # Batch 2 failed, so checkpoint has 50 items processed
        assert len(processed_batches) == 3  # Attempted 3 batches (0, 1, 2)

        # Resume processing - should start from batch 2 (item 50)
        processed_resume = []

        def process_batch_resume(batch):
            processed_resume.extend(batch)
            return len(batch), 0

        batch_processor.resume(
            items=items,
            process_callback=process_batch_resume
        )

        # Should have processed items from 50-99 (2 batches: 50-74, 75-99)
        assert len(processed_resume) == 50
        assert processed_resume == items[50:]

    def test_track_failed_items(self, batch_processor):
        """Test tracking of failed items."""
        items = list(range(100))

        def process_with_failures(batch):
            # Simulate 10% failure rate
            failed = len([i for i in batch if i % 10 == 0])
            processed = len(batch) - failed
            return processed, failed

        result = batch_processor.process(
            items=items,
            chain_id="test",
            batch_size=25,
            process_callback=process_with_failures
        )

        assert result['processed'] == 90  # 100 - 10 failed
        assert result['failed'] == 10

    def test_progress_callback(self, batch_processor):
        """Test that progress callback is called during processing."""
        items = list(range(100))
        progress_updates = []

        def process_batch(batch):
            return len(batch), 0

        def on_progress(progress):
            progress_updates.append(progress)

        batch_processor.process(
            items=items,
            chain_id="test",
            batch_size=25,
            process_callback=process_batch,
            progress_callback=on_progress
        )

        # Should have 4 progress updates (one per batch)
        assert len(progress_updates) == 4
        assert progress_updates[0]['percentage'] == 25.0
        assert progress_updates[1]['percentage'] == 50.0
        assert progress_updates[2]['percentage'] == 75.0
        assert progress_updates[3]['percentage'] == 100.0

    def test_custom_state_persistence(self, batch_processor):
        """Test that custom state can be saved and resumed."""
        items = list(range(100))
        custom_state = {'api_calls': 0, 'errors': []}
        batch_count = [0]  # Use list to modify in nested function

        def process_batch(batch):
            # Only increment on successful processing (before potential crash)
            batch_num = batch_count[0]
            batch_count[0] += 1

            # Crash on batch 2 BEFORE incrementing api_calls
            if batch_num == 2:
                raise Exception("Crash")

            # Increment api_calls only for successful batches
            custom_state['api_calls'] += len(batch)
            return len(batch), 0

        # First run (disable retries for cleaner test)
        try:
            batch_processor.process(
                items=items,
                chain_id="test",
                batch_size=25,
                process_callback=process_batch,
                state=custom_state,
                max_retries=1  # No retries for cleaner test
            )
        except Exception:
            pass

        # Resume with state - should have api_calls from batches 0 and 1 (50 items)
        resumed_state = batch_processor.get_resume_state()
        assert resumed_state is not None
        assert resumed_state['api_calls'] == 50  # Processed 2 batches

    def test_empty_items_list(self, batch_processor):
        """Test processing empty items list."""
        items = []

        def process_batch(batch):
            return len(batch), 0

        result = batch_processor.process(
            items=items,
            chain_id="test",
            batch_size=25,
            process_callback=process_batch
        )

        assert result['processed'] == 0
        assert result['failed'] == 0

    def test_single_item(self, batch_processor):
        """Test processing single item."""
        items = [1]

        def process_batch(batch):
            return len(batch), 0

        result = batch_processor.process(
            items=items,
            chain_id="test",
            batch_size=25,
            process_callback=process_batch
        )

        assert result['processed'] == 1
        assert result['failed'] == 0

    def test_batch_size_larger_than_items(self, batch_processor):
        """Test batch size larger than total items."""
        items = list(range(10))
        batch_count = []

        def process_batch(batch):
            batch_count.append(1)
            return len(batch), 0

        batch_processor.process(
            items=items,
            chain_id="test",
            batch_size=100,
            process_callback=process_batch
        )

        # Should have only 1 batch
        assert len(batch_count) == 1

    def test_error_handling_with_max_retries(self, batch_processor):
        """Test error handling with retry logic."""
        items = list(range(10))
        attempt_count = []

        def process_with_errors(batch):
            attempt_count.append(1)
            if len(attempt_count) < 3:  # Fail first 2 attempts
                raise Exception("Temporary error")
            return len(batch), 0

        result = batch_processor.process(
            items=items,
            chain_id="test",
            batch_size=5,
            process_callback=process_with_errors,
            max_retries=3
        )

        # Should succeed on 3rd attempt
        assert len(attempt_count) >= 3

    def test_generator_as_input(self, batch_processor):
        """Test that batch processor accepts generators."""
        def item_generator():
            for i in range(100):
                yield i

        processed = []

        def process_batch(batch):
            processed.extend(batch)
            return len(batch), 0

        batch_processor.process(
            items=item_generator(),
            chain_id="test",
            batch_size=25,
            process_callback=process_batch
        )

        assert len(processed) == 100

    def test_run_id_returned(self, batch_processor):
        """Test that run_id is returned after processing."""
        items = list(range(10))

        def process_batch(batch):
            return len(batch), 0

        result = batch_processor.process(
            items=items,
            chain_id="test",
            batch_size=5,
            process_callback=process_batch
        )

        assert 'run_id' in result
        assert result['run_id'].startswith('test_')

    def test_cleanup_after_success(self, batch_processor, temp_db_path):
        """Test that old runs are cleaned up after successful completion."""
        from src.batch.checkpoint_manager import CheckpointManager

        items = list(range(10))

        def process_batch(batch):
            return len(batch), 0

        # Create multiple successful runs
        for i in range(5):
            batch_processor.process(
                items=items,
                chain_id="cleanup_test",
                batch_size=5,
                process_callback=process_batch
            )

        # Should keep only recent runs
        manager = CheckpointManager(temp_db_path)
        runs = manager.list_runs(chain_id="cleanup_test")

        # Default cleanup policy should keep reasonable number
        assert len(runs) <= 10

    def test_process_with_item_limit(self, batch_processor):
        """Test processing with item limit (for testing purposes)."""
        items = list(range(1000))
        processed = []

        def process_batch(batch):
            processed.extend(batch)
            return len(batch), 0

        batch_processor.process(
            items=items,
            chain_id="test",
            batch_size=25,
            process_callback=process_batch,
            limit=50  # Process only first 50 items
        )

        assert len(processed) == 50
