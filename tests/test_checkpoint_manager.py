"""
Tests for checkpoint manager - batch processing checkpoint system.
Following TDD: These tests are written BEFORE implementation.
"""

import pytest
import tempfile
import os
from datetime import datetime
from pathlib import Path


class TestCheckpointManager:
    """Test suite for CheckpointManager class."""

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
    def checkpoint_manager(self, temp_db_path):
        """Create a CheckpointManager instance for testing."""
        from src.batch.checkpoint_manager import CheckpointManager
        return CheckpointManager(temp_db_path)

    def test_create_checkpoint_manager(self, temp_db_path):
        """Test that CheckpointManager can be instantiated."""
        from src.batch.checkpoint_manager import CheckpointManager
        manager = CheckpointManager(temp_db_path)
        assert manager is not None
        assert manager.db_path == temp_db_path

    def test_create_new_run(self, checkpoint_manager):
        """Test creating a new scraping run."""
        run_id = checkpoint_manager.create_run(
            chain_id="rewe",
            total_stores=1000,
            batch_size=100
        )

        assert run_id is not None
        assert run_id.startswith("rewe_")
        assert len(run_id) > 10  # Should include timestamp

        # Verify run details can be retrieved
        run = checkpoint_manager.get_run(run_id)
        assert run['chain_id'] == "rewe"
        assert run['total_stores'] == 1000
        assert run['batch_size'] == 100
        assert run['stores_processed'] == 0
        assert run['stores_failed'] == 0
        assert run['status'] == 'running'

    def test_save_checkpoint(self, checkpoint_manager):
        """Test saving a checkpoint during scraping."""
        run_id = checkpoint_manager.create_run(
            chain_id="denns",
            total_stores=500,
            batch_size=50
        )

        # Save checkpoint after batch 1
        checkpoint_manager.save_checkpoint(
            run_id=run_id,
            batch_index=1,
            stores_processed=50,
            stores_failed=2,
            state={'current_page': 1, 'last_store_id': 'denns_123'}
        )

        # Verify checkpoint was saved
        run = checkpoint_manager.get_run(run_id)
        assert run['stores_processed'] == 50
        assert run['stores_failed'] == 2
        assert run['current_batch'] == 1
        assert run['state']['current_page'] == 1
        assert run['state']['last_store_id'] == 'denns_123'

    def test_resume_from_checkpoint(self, checkpoint_manager):
        """Test resuming a scraping run from a checkpoint."""
        # Create initial run and save checkpoint
        run_id = checkpoint_manager.create_run(
            chain_id="alnatura",
            total_stores=150,
            batch_size=25
        )

        checkpoint_manager.save_checkpoint(
            run_id=run_id,
            batch_index=2,
            stores_processed=50,
            stores_failed=0,
            state={'cities_completed': ['Berlin', 'Munich']}
        )

        # Resume from checkpoint
        resume_data = checkpoint_manager.resume_run(run_id)

        assert resume_data is not None
        assert resume_data['run_id'] == run_id
        assert resume_data['chain_id'] == 'alnatura'
        assert resume_data['batch_index'] == 2
        assert resume_data['stores_processed'] == 50
        assert resume_data['state']['cities_completed'] == ['Berlin', 'Munich']

    def test_resume_nonexistent_run(self, checkpoint_manager):
        """Test that resuming a nonexistent run returns None."""
        resume_data = checkpoint_manager.resume_run("fake_run_id_123")
        assert resume_data is None

    def test_complete_run(self, checkpoint_manager):
        """Test marking a run as completed."""
        run_id = checkpoint_manager.create_run(
            chain_id="tegut",
            total_stores=300,
            batch_size=50
        )

        # Process all stores
        checkpoint_manager.save_checkpoint(
            run_id=run_id,
            batch_index=6,
            stores_processed=300,
            stores_failed=5,
            state={}
        )

        # Mark as complete
        checkpoint_manager.complete_run(
            run_id=run_id,
            total_processed=300,
            total_failed=5
        )

        # Verify status is completed
        run = checkpoint_manager.get_run(run_id)
        assert run['status'] == 'completed'
        assert run['stores_processed'] == 300
        assert run['stores_failed'] == 5
        assert run['completed_at'] is not None

    def test_fail_run(self, checkpoint_manager):
        """Test marking a run as failed."""
        run_id = checkpoint_manager.create_run(
            chain_id="globus",
            total_stores=100,
            batch_size=20
        )

        # Simulate failure
        error_message = "Network timeout after 3 retries"
        checkpoint_manager.fail_run(
            run_id=run_id,
            error_message=error_message,
            stores_processed=40,
            stores_failed=10
        )

        # Verify status is failed
        run = checkpoint_manager.get_run(run_id)
        assert run['status'] == 'failed'
        assert run['error_message'] == error_message
        assert run['stores_processed'] == 40
        assert run['stores_failed'] == 10

    def test_list_runs_by_chain(self, checkpoint_manager):
        """Test listing all runs for a specific chain."""
        # Create multiple runs
        run1 = checkpoint_manager.create_run("rewe", 1000, 100)
        run2 = checkpoint_manager.create_run("rewe", 1000, 100)
        run3 = checkpoint_manager.create_run("denns", 500, 50)

        # Get REWE runs
        rewe_runs = checkpoint_manager.list_runs(chain_id="rewe")

        assert len(rewe_runs) == 2
        assert all(run['chain_id'] == 'rewe' for run in rewe_runs)

        # Get all runs
        all_runs = checkpoint_manager.list_runs()
        assert len(all_runs) == 3

    def test_get_latest_run(self, checkpoint_manager):
        """Test getting the latest run for a chain."""
        # Create multiple runs with delays to ensure ordering
        run1 = checkpoint_manager.create_run("alnatura", 150, 25)
        checkpoint_manager.complete_run(run1, 150, 0)

        run2 = checkpoint_manager.create_run("alnatura", 150, 25)

        # Latest should be run2
        latest = checkpoint_manager.get_latest_run("alnatura")
        assert latest['run_id'] == run2
        assert latest['status'] == 'running'

    def test_cleanup_old_runs(self, checkpoint_manager):
        """Test cleaning up old completed runs."""
        # Create and complete multiple runs for the SAME chain
        for i in range(5):
            run_id = checkpoint_manager.create_run("test_chain", 100, 10)
            checkpoint_manager.complete_run(run_id, 100, 0)

        # Keep only 3 most recent per chain
        deleted = checkpoint_manager.cleanup_old_runs(keep_recent=3)

        assert deleted == 2
        remaining = checkpoint_manager.list_runs()
        assert len(remaining) == 3

    def test_checkpoint_with_large_state(self, checkpoint_manager):
        """Test saving checkpoint with large state object."""
        run_id = checkpoint_manager.create_run("test", 1000, 100)

        # Large state with nested data
        large_state = {
            'processed_ids': [f"store_{i}" for i in range(100)],
            'failed_ids': [f"failed_{i}" for i in range(10)],
            'metadata': {
                'states_completed': ['State1', 'State2', 'State3'],
                'api_calls': 350,
                'errors': [
                    {'store_id': 'x', 'error': 'timeout'},
                    {'store_id': 'y', 'error': 'invalid response'}
                ]
            }
        }

        checkpoint_manager.save_checkpoint(
            run_id=run_id,
            batch_index=1,
            stores_processed=100,
            stores_failed=10,
            state=large_state
        )

        # Verify state can be retrieved
        run = checkpoint_manager.get_run(run_id)
        assert len(run['state']['processed_ids']) == 100
        assert len(run['state']['failed_ids']) == 10
        assert run['state']['metadata']['api_calls'] == 350

    def test_concurrent_checkpoints(self, checkpoint_manager):
        """Test that multiple chains can save checkpoints concurrently."""
        run1 = checkpoint_manager.create_run("chain1", 100, 10)
        run2 = checkpoint_manager.create_run("chain2", 200, 20)

        # Save checkpoints for both runs
        checkpoint_manager.save_checkpoint(run1, 1, 10, 0, {})
        checkpoint_manager.save_checkpoint(run2, 1, 20, 0, {})

        # Both should be retrievable
        r1 = checkpoint_manager.get_run(run1)
        r2 = checkpoint_manager.get_run(run2)

        assert r1['stores_processed'] == 10
        assert r2['stores_processed'] == 20

    def test_get_progress_percentage(self, checkpoint_manager):
        """Test calculating progress percentage."""
        run_id = checkpoint_manager.create_run("test", 1000, 100)
        checkpoint_manager.save_checkpoint(run_id, 3, 300, 10, {})

        progress = checkpoint_manager.get_progress(run_id)

        assert progress['percentage'] == 30.0  # 300/1000
        assert progress['stores_processed'] == 300
        assert progress['stores_failed'] == 10
        assert progress['stores_remaining'] == 700

    def test_estimate_time_remaining(self, checkpoint_manager):
        """Test ETA calculation based on progress."""
        import time

        run_id = checkpoint_manager.create_run("test", 1000, 100)

        # Simulate processing with time delay
        time.sleep(0.1)  # Small delay to simulate work
        checkpoint_manager.save_checkpoint(run_id, 1, 100, 0, {})

        eta = checkpoint_manager.estimate_time_remaining(run_id)

        assert eta is not None
        assert eta['estimated_seconds'] > 0
        assert eta['stores_per_second'] > 0
