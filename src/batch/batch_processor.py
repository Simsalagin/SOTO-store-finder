"""
Generic batch processor with checkpoint/resume capability.
Processes items in batches with progress tracking and error recovery.
"""

import logging
from typing import Callable, Iterable, Dict, Any, Optional, Tuple
from .checkpoint_manager import CheckpointManager

logger = logging.getLogger(__name__)


class BatchProcessor:
    """
    Generic batch processor with checkpoint integration.

    Features:
    - Process items in configurable batch sizes
    - Automatic checkpointing after each batch
    - Resume from last checkpoint on failure
    - Progress callbacks for monitoring
    - Retry logic for transient failures
    - Support for generators and lists
    """

    def __init__(self, db_path: str):
        """
        Initialize batch processor.

        Args:
            db_path: Path to checkpoint database
        """
        self.checkpoint_manager = CheckpointManager(db_path)
        self._current_run_id = None
        self._resume_state = None

    def process(
        self,
        items: Iterable[Any],
        chain_id: str,
        batch_size: int,
        process_callback: Callable[[list], Tuple[int, int]],
        progress_callback: Optional[Callable[[Dict], None]] = None,
        state: Optional[Dict[str, Any]] = None,
        max_retries: int = 3,
        limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Process items in batches with checkpointing.

        Args:
            items: Iterable of items to process
            chain_id: Identifier for this processing chain
            batch_size: Number of items per batch
            process_callback: Function to process each batch.
                Should return (processed_count, failed_count)
            progress_callback: Optional callback for progress updates
            state: Optional custom state to persist
            max_retries: Maximum retry attempts for failed batches
            limit: Optional limit on total items to process (for testing)

        Returns:
            Dictionary with run_id, processed count, failed count
        """
        # Convert to list if generator
        if hasattr(items, '__iter__') and not isinstance(items, (list, tuple)):
            items = list(items)

        # Apply limit if specified
        if limit is not None:
            items = items[:limit]

        total_items = len(items)

        # Create run
        run_id = self.checkpoint_manager.create_run(
            chain_id=chain_id,
            total_stores=total_items,
            batch_size=batch_size
        )
        self._current_run_id = run_id

        logger.info(f"Starting batch processing: {run_id} "
                   f"({total_items} items, batch size {batch_size})")

        total_processed = 0
        total_failed = 0
        current_state = state or {}

        try:
            # Process in batches
            for batch_index in range(0, total_items, batch_size):
                batch_end = min(batch_index + batch_size, total_items)
                batch = items[batch_index:batch_end]
                batch_num = batch_index // batch_size

                # Process batch with retries
                processed, failed = self._process_batch_with_retry(
                    batch=batch,
                    process_callback=process_callback,
                    max_retries=max_retries,
                    batch_num=batch_num
                )

                total_processed += processed
                total_failed += failed

                # Save checkpoint
                self.checkpoint_manager.save_checkpoint(
                    run_id=run_id,
                    batch_index=batch_num,
                    stores_processed=total_processed,
                    stores_failed=total_failed,
                    state=current_state
                )

                # Call progress callback
                if progress_callback:
                    progress = {
                        'batch': batch_num,
                        'processed': total_processed,
                        'failed': total_failed,
                        'total': total_items,
                        'percentage': round((total_processed + total_failed) / total_items * 100, 2)
                    }
                    progress_callback(progress)

                logger.debug(f"Batch {batch_num} complete: {processed} processed, "
                            f"{failed} failed")

            # Mark as completed
            self.checkpoint_manager.complete_run(
                run_id=run_id,
                total_processed=total_processed,
                total_failed=total_failed
            )

            logger.info(f"Processing complete: {run_id} - {total_processed} processed, "
                       f"{total_failed} failed")

            # Store state for potential resume
            self._resume_state = current_state

            return {
                'run_id': run_id,
                'processed': total_processed,
                'failed': total_failed,
                'status': 'completed'
            }

        except Exception as e:
            # Mark as failed
            error_message = str(e)
            self.checkpoint_manager.fail_run(
                run_id=run_id,
                error_message=error_message,
                stores_processed=total_processed,
                stores_failed=total_failed
            )

            logger.error(f"Processing failed: {run_id} - {error_message}")

            # Store state for resume
            self._resume_state = current_state

            raise

    def _process_batch_with_retry(
        self,
        batch: list,
        process_callback: Callable,
        max_retries: int,
        batch_num: int
    ) -> Tuple[int, int]:
        """
        Process a batch with retry logic.

        Args:
            batch: Batch of items to process
            process_callback: Processing function
            max_retries: Maximum retry attempts
            batch_num: Batch number for logging

        Returns:
            Tuple of (processed_count, failed_count)
        """
        last_error = None

        for attempt in range(max_retries):
            try:
                processed, failed = process_callback(batch)
                return processed, failed

            except Exception as e:
                last_error = e
                logger.warning(f"Batch {batch_num} failed (attempt {attempt + 1}/{max_retries}): {e}")

                if attempt < max_retries - 1:
                    # Exponential backoff
                    import time
                    delay = 2 ** attempt
                    time.sleep(delay)

        # All retries exhausted
        logger.error(f"Batch {batch_num} failed after {max_retries} attempts: {last_error}")
        raise last_error

    def resume(
        self,
        items: Iterable[Any],
        process_callback: Callable[[list], Tuple[int, int]],
        progress_callback: Optional[Callable[[Dict], None]] = None,
        run_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Resume processing from last checkpoint.

        Args:
            items: Full list of items (will skip already processed)
            process_callback: Processing function
            progress_callback: Optional progress callback
            run_id: Optional specific run to resume (defaults to last failed)

        Returns:
            Dictionary with run results
        """
        # Get run to resume
        if run_id:
            resume_data = self.checkpoint_manager.resume_run(run_id)
        elif self._current_run_id:
            resume_data = self.checkpoint_manager.resume_run(self._current_run_id)
        else:
            raise ValueError("No run_id specified and no current run to resume")

        if not resume_data:
            raise ValueError("Cannot resume: run not found or already completed")

        # Convert to list if generator
        if hasattr(items, '__iter__') and not isinstance(items, (list, tuple)):
            items = list(items)

        # Calculate where to resume from
        start_index = resume_data['stores_processed'] + resume_data['stores_failed']
        remaining_items = items[start_index:]

        logger.info(f"Resuming run {resume_data['run_id']} from item {start_index} "
                   f"({len(remaining_items)} items remaining)")

        # Continue processing
        total_processed = resume_data['stores_processed']
        total_failed = resume_data['stores_failed']
        batch_size = resume_data['batch_size']
        current_state = resume_data['state']
        run_id = resume_data['run_id']

        try:
            for batch_index in range(0, len(remaining_items), batch_size):
                batch_end = min(batch_index + batch_size, len(remaining_items))
                batch = remaining_items[batch_index:batch_end]
                batch_num = resume_data['batch_index'] + 1 + (batch_index // batch_size)

                # Process batch
                processed, failed = process_callback(batch)
                total_processed += processed
                total_failed += failed

                # Save checkpoint
                self.checkpoint_manager.save_checkpoint(
                    run_id=run_id,
                    batch_index=batch_num,
                    stores_processed=total_processed,
                    stores_failed=total_failed,
                    state=current_state
                )

                # Call progress callback
                if progress_callback:
                    progress = {
                        'batch': batch_num,
                        'processed': total_processed,
                        'failed': total_failed,
                        'total': resume_data['total_stores'],
                        'percentage': round((total_processed + total_failed) /
                                          resume_data['total_stores'] * 100, 2)
                    }
                    progress_callback(progress)

            # Mark as completed
            self.checkpoint_manager.complete_run(
                run_id=run_id,
                total_processed=total_processed,
                total_failed=total_failed
            )

            logger.info(f"Resume complete: {run_id} - {total_processed} processed, "
                       f"{total_failed} failed")

            return {
                'run_id': run_id,
                'processed': total_processed,
                'failed': total_failed,
                'status': 'completed'
            }

        except Exception as e:
            # Mark as failed
            self.checkpoint_manager.fail_run(
                run_id=run_id,
                error_message=str(e),
                stores_processed=total_processed,
                stores_failed=total_failed
            )
            raise

    def get_resume_state(self) -> Optional[Dict[str, Any]]:
        """
        Get the last saved state for resuming.

        Returns:
            State dictionary or None
        """
        return self._resume_state
