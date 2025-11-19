"""
Progress tracking with ETA estimation and visual progress bars.
"""

import time
from typing import Optional, Callable, Dict, Any
from datetime import datetime
import structlog


class ProgressTracker:
    """
    Track progress with ETA estimation and optional visual progress bar.

    Features:
    - Percentage calculation
    - ETA estimation based on current rate
    - Visual progress bar
    - Success/failure tracking
    - Integration with structured logging
    """

    def __init__(
        self,
        total: int,
        description: str = "",
        bar_width: int = 40,
        mode: str = "bar",
        callback: Optional[Callable[[Dict], None]] = None,
        logger: Optional[Any] = None
    ):
        """
        Initialize progress tracker.

        Args:
            total: Total number of items to process
            description: Description of the task
            bar_width: Width of progress bar in characters
            mode: Display mode ('bar', 'percentage', 'text')
            callback: Optional callback function called on updates
            logger: Optional structured logger for progress logging
        """
        self.total = total
        self.description = description
        self.bar_width = bar_width
        self.mode = mode
        self.callback = callback
        self.logger = logger or structlog.get_logger()

        self.current = 0
        self.failed = 0
        self.successful = 0
        self.start_time = time.time()

    @property
    def percentage(self) -> float:
        """Calculate current completion percentage."""
        if self.total == 0:
            return 0.0
        percentage = (self.current / self.total) * 100
        return min(percentage, 100.0)  # Cap at 100%

    def update(self, current: int, failed: int = 0):
        """
        Update progress to a specific value.

        Args:
            current: Current number of items processed
            failed: Number of failed items (optional)
        """
        self.current = current
        self.failed = failed
        self.successful = current - failed

        # Call callback if provided
        if self.callback:
            self.callback(self.get_summary())

        # Log progress if logger provided
        if self.logger:
            self.logger.info(
                "progress_update",
                description=self.description,
                current=self.current,
                total=self.total,
                percentage=round(self.percentage, 2),
                failed=self.failed
            )

    def increment(self, amount: int = 1, failed: int = 0):
        """
        Increment progress by a specified amount.

        Args:
            amount: Amount to increment by (default: 1)
            failed: Number of failed items in this increment
        """
        self.update(self.current + amount, self.failed + failed)

    def estimate_remaining(self) -> Optional[Dict[str, float]]:
        """
        Estimate remaining time based on current progress rate.

        Returns:
            Dictionary with estimated_seconds and items_per_second,
            or None if cannot estimate
        """
        elapsed = time.time() - self.start_time

        if elapsed == 0 or self.current == 0:
            return None

        items_per_second = self.current / elapsed
        remaining_items = self.total - self.current

        if items_per_second == 0:
            return None

        estimated_seconds = remaining_items / items_per_second

        return {
            'estimated_seconds': estimated_seconds,
            'items_per_second': items_per_second,
            'remaining_items': remaining_items
        }

    def get_rate(self) -> float:
        """Get current processing rate (items per second)."""
        elapsed = time.time() - self.start_time
        if elapsed == 0:
            return 0.0
        return self.current / elapsed

    def get_progress_bar(self) -> str:
        """
        Generate ASCII progress bar.

        Returns:
            String representation of progress bar
        """
        filled_width = int(self.bar_width * (self.current / max(self.total, 1)))
        empty_width = self.bar_width - filled_width

        bar = '█' * filled_width + '░' * empty_width
        percentage_str = f"{self.percentage:.1f}%"

        # Add description if provided
        if self.description:
            return f"[{self.description}] {bar} {percentage_str} ({self.current}/{self.total})"
        else:
            return f"{bar} {percentage_str} ({self.current}/{self.total})"

    def display(self) -> str:
        """
        Display progress based on configured mode.

        Returns:
            Formatted progress string
        """
        if self.mode == "bar":
            return self.get_progress_bar()
        elif self.mode == "percentage":
            return f"{self.percentage:.1f}% ({self.current}/{self.total})"
        else:  # text mode
            return f"{self.current}/{self.total} items processed"

    def is_complete(self) -> bool:
        """Check if processing is complete."""
        return self.current >= self.total

    def get_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive progress summary.

        Returns:
            Dictionary with all progress metrics
        """
        elapsed = time.time() - self.start_time
        eta = self.estimate_remaining()

        summary = {
            'description': self.description,
            'total': self.total,
            'current': self.current,
            'successful': self.successful,
            'failed': self.failed,
            'percentage': round(self.percentage, 2),
            'elapsed_seconds': round(elapsed, 2),
            'is_complete': self.is_complete()
        }

        if eta:
            summary['estimated_remaining_seconds'] = round(eta['estimated_seconds'], 2)
            summary['items_per_second'] = round(eta['items_per_second'], 2)

        return summary

    def __enter__(self):
        """Enter context manager."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager and log final summary."""
        if self.logger:
            self.logger.info(
                "progress_complete",
                **self.get_summary()
            )
        return False

    def __str__(self) -> str:
        """String representation."""
        return self.display()
