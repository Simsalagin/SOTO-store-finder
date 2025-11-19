"""
Correlation context manager for tracking requests across log entries.
"""

import uuid
from typing import Optional
import structlog
from contextlib import contextmanager


class CorrelationContext:
    """
    Context manager for binding correlation IDs to structured logs.

    Usage:
        with CorrelationContext(run_id="abc123", chain_id="rewe"):
            logger.info("processing")  # Will include run_id and chain_id
    """

    def __init__(
        self,
        run_id: Optional[str] = None,
        chain_id: Optional[str] = None,
        **extra_context
    ):
        """
        Initialize correlation context.

        Args:
            run_id: Unique run identifier (auto-generated if not provided)
            chain_id: Chain identifier
            **extra_context: Additional context to bind
        """
        self.run_id = run_id or self._generate_run_id()
        self.chain_id = chain_id
        self.extra_context = extra_context
        self._context_token = None

    def _generate_run_id(self) -> str:
        """Generate a unique run ID."""
        return f"run_{uuid.uuid4().hex[:12]}"

    def __enter__(self):
        """Enter correlation context and bind IDs to logger."""
        context = {'run_id': self.run_id}
        if self.chain_id:
            context['chain_id'] = self.chain_id
        context.update(self.extra_context)

        # Bind context to structlog
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(**context)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit correlation context and clear bindings."""
        structlog.contextvars.clear_contextvars()
        return False
