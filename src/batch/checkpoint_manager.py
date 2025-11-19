"""
Checkpoint manager for batch processing with resume capability.
Stores scraping progress in SQLite database to enable recovery from failures.
"""

import sqlite3
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class CheckpointManager:
    """
    Manages checkpoints for batch scraping operations.

    Features:
    - Create scraping runs with unique IDs
    - Save checkpoints after each batch
    - Resume from last checkpoint on failure
    - Track progress and calculate ETA
    - Clean up old completed runs
    """

    def __init__(self, db_path: str):
        """
        Initialize checkpoint manager.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._ensure_database_exists()

    def _ensure_database_exists(self):
        """Create database and tables if they don't exist."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS scraping_progress (
                    run_id TEXT PRIMARY KEY,
                    chain_id TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    last_checkpoint TEXT,
                    current_batch INTEGER DEFAULT 0,
                    total_stores INTEGER NOT NULL,
                    batch_size INTEGER NOT NULL,
                    stores_processed INTEGER DEFAULT 0,
                    stores_failed INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'running',
                    error_message TEXT,
                    state TEXT,
                    created_at TEXT NOT NULL
                )
            """)

            # Create index for faster lookups
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_chain_status
                ON scraping_progress(chain_id, status)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_started_at
                ON scraping_progress(started_at DESC)
            """)

            conn.commit()
            logger.debug(f"Checkpoint database initialized at {self.db_path}")
        finally:
            conn.close()

    def create_run(
        self,
        chain_id: str,
        total_stores: int,
        batch_size: int
    ) -> str:
        """
        Create a new scraping run.

        Args:
            chain_id: ID of the chain being scraped
            total_stores: Total number of stores to scrape
            batch_size: Number of stores per batch

        Returns:
            Unique run ID
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        run_id = f"{chain_id}_{timestamp}"

        now = datetime.now().isoformat()

        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO scraping_progress
                (run_id, chain_id, started_at, total_stores, batch_size,
                 state, created_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'running')
            """, (run_id, chain_id, now, total_stores, batch_size,
                  json.dumps({}), now))
            conn.commit()

            logger.info(f"Created scraping run: {run_id} ({total_stores} stores, "
                       f"batch size {batch_size})")
            return run_id
        finally:
            conn.close()

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """
        Get run details.

        Args:
            run_id: Run ID

        Returns:
            Dictionary with run details or None if not found
        """
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT run_id, chain_id, started_at, completed_at,
                       last_checkpoint, current_batch, total_stores, batch_size,
                       stores_processed, stores_failed, status, error_message, state
                FROM scraping_progress
                WHERE run_id = ?
            """, (run_id,))

            row = cursor.fetchone()
            if not row:
                return None

            return {
                'run_id': row[0],
                'chain_id': row[1],
                'started_at': row[2],
                'completed_at': row[3],
                'last_checkpoint': row[4],
                'current_batch': row[5],
                'total_stores': row[6],
                'batch_size': row[7],
                'stores_processed': row[8],
                'stores_failed': row[9],
                'status': row[10],
                'error_message': row[11],
                'state': json.loads(row[12]) if row[12] else {}
            }
        finally:
            conn.close()

    def save_checkpoint(
        self,
        run_id: str,
        batch_index: int,
        stores_processed: int,
        stores_failed: int,
        state: Dict[str, Any]
    ):
        """
        Save a checkpoint for the current run.

        Args:
            run_id: Run ID
            batch_index: Current batch number
            stores_processed: Total stores processed so far
            stores_failed: Total stores failed so far
            state: Arbitrary state dictionary to persist
        """
        now = datetime.now().isoformat()

        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE scraping_progress
                SET last_checkpoint = ?,
                    current_batch = ?,
                    stores_processed = ?,
                    stores_failed = ?,
                    state = ?
                WHERE run_id = ?
            """, (now, batch_index, stores_processed, stores_failed,
                  json.dumps(state), run_id))
            conn.commit()

            logger.debug(f"Checkpoint saved: {run_id} - Batch {batch_index}, "
                        f"{stores_processed} processed, {stores_failed} failed")
        finally:
            conn.close()

    def resume_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """
        Resume a scraping run from its last checkpoint.

        Args:
            run_id: Run ID to resume

        Returns:
            Resume data dictionary or None if run doesn't exist
        """
        run = self.get_run(run_id)
        if not run:
            logger.warning(f"Cannot resume run {run_id}: not found")
            return None

        if run['status'] == 'completed':
            logger.info(f"Run {run_id} already completed")
            return None

        logger.info(f"Resuming run {run_id} from batch {run['current_batch']}, "
                   f"{run['stores_processed']} stores processed")

        return {
            'run_id': run['run_id'],
            'chain_id': run['chain_id'],
            'batch_index': run['current_batch'],
            'stores_processed': run['stores_processed'],
            'stores_failed': run['stores_failed'],
            'total_stores': run['total_stores'],
            'batch_size': run['batch_size'],
            'state': run['state']
        }

    def complete_run(
        self,
        run_id: str,
        total_processed: int,
        total_failed: int
    ):
        """
        Mark a run as completed.

        Args:
            run_id: Run ID
            total_processed: Final count of processed stores
            total_failed: Final count of failed stores
        """
        now = datetime.now().isoformat()

        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE scraping_progress
                SET status = 'completed',
                    completed_at = ?,
                    stores_processed = ?,
                    stores_failed = ?
                WHERE run_id = ?
            """, (now, total_processed, total_failed, run_id))
            conn.commit()

            logger.info(f"Run completed: {run_id} - {total_processed} processed, "
                       f"{total_failed} failed")
        finally:
            conn.close()

    def fail_run(
        self,
        run_id: str,
        error_message: str,
        stores_processed: int,
        stores_failed: int
    ):
        """
        Mark a run as failed.

        Args:
            run_id: Run ID
            error_message: Error description
            stores_processed: Count of stores processed before failure
            stores_failed: Count of stores that failed
        """
        now = datetime.now().isoformat()

        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE scraping_progress
                SET status = 'failed',
                    completed_at = ?,
                    error_message = ?,
                    stores_processed = ?,
                    stores_failed = ?
                WHERE run_id = ?
            """, (now, error_message, stores_processed, stores_failed, run_id))
            conn.commit()

            logger.error(f"Run failed: {run_id} - {error_message}")
        finally:
            conn.close()

    def list_runs(self, chain_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List all runs, optionally filtered by chain.

        Args:
            chain_id: Optional chain ID to filter by

        Returns:
            List of run dictionaries
        """
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()

            if chain_id:
                cursor.execute("""
                    SELECT run_id, chain_id, started_at, completed_at, status,
                           stores_processed, stores_failed, total_stores
                    FROM scraping_progress
                    WHERE chain_id = ?
                    ORDER BY started_at DESC
                """, (chain_id,))
            else:
                cursor.execute("""
                    SELECT run_id, chain_id, started_at, completed_at, status,
                           stores_processed, stores_failed, total_stores
                    FROM scraping_progress
                    ORDER BY started_at DESC
                """)

            runs = []
            for row in cursor.fetchall():
                runs.append({
                    'run_id': row[0],
                    'chain_id': row[1],
                    'started_at': row[2],
                    'completed_at': row[3],
                    'status': row[4],
                    'stores_processed': row[5],
                    'stores_failed': row[6],
                    'total_stores': row[7]
                })

            return runs
        finally:
            conn.close()

    def get_latest_run(self, chain_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the most recent run for a chain.

        Args:
            chain_id: Chain ID

        Returns:
            Run dictionary or None
        """
        runs = self.list_runs(chain_id)
        return runs[0] if runs else None

    def cleanup_old_runs(self, keep_recent: int = 10) -> int:
        """
        Delete old completed runs, keeping only the most recent ones.

        Args:
            keep_recent: Number of recent runs to keep per chain

        Returns:
            Number of runs deleted
        """
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()

            # Get runs to delete (keep N most recent per chain)
            cursor.execute("""
                SELECT run_id
                FROM (
                    SELECT run_id, chain_id, started_at,
                           ROW_NUMBER() OVER (
                               PARTITION BY chain_id
                               ORDER BY started_at DESC
                           ) as rn
                    FROM scraping_progress
                    WHERE status = 'completed'
                )
                WHERE rn > ?
            """, (keep_recent,))

            runs_to_delete = [row[0] for row in cursor.fetchall()]

            if runs_to_delete:
                placeholders = ','.join('?' * len(runs_to_delete))
                cursor.execute(f"""
                    DELETE FROM scraping_progress
                    WHERE run_id IN ({placeholders})
                """, runs_to_delete)
                conn.commit()

                logger.info(f"Cleaned up {len(runs_to_delete)} old runs")

            return len(runs_to_delete)
        finally:
            conn.close()

    def get_progress(self, run_id: str) -> Dict[str, Any]:
        """
        Calculate progress percentage for a run.

        Args:
            run_id: Run ID

        Returns:
            Dictionary with progress metrics
        """
        run = self.get_run(run_id)
        if not run:
            return {}

        total = run['total_stores']
        processed = run['stores_processed']
        failed = run['stores_failed']
        remaining = total - processed

        percentage = (processed / total * 100) if total > 0 else 0

        return {
            'percentage': round(percentage, 2),
            'stores_processed': processed,
            'stores_failed': failed,
            'stores_remaining': remaining,
            'total_stores': total
        }

    def estimate_time_remaining(self, run_id: str) -> Optional[Dict[str, Any]]:
        """
        Estimate time remaining based on current progress.

        Args:
            run_id: Run ID

        Returns:
            Dictionary with ETA metrics or None if can't calculate
        """
        run = self.get_run(run_id)
        if not run or not run['started_at']:
            return None

        # Parse timestamps
        start_time = datetime.fromisoformat(run['started_at'])
        current_time = datetime.now()

        elapsed_seconds = (current_time - start_time).total_seconds()

        if elapsed_seconds == 0 or run['stores_processed'] == 0:
            return None

        # Calculate rate
        stores_per_second = run['stores_processed'] / elapsed_seconds
        stores_remaining = run['total_stores'] - run['stores_processed']

        estimated_seconds = stores_remaining / stores_per_second if stores_per_second > 0 else 0

        return {
            'estimated_seconds': round(estimated_seconds, 2),
            'stores_per_second': round(stores_per_second, 2),
            'elapsed_seconds': round(elapsed_seconds, 2)
        }
