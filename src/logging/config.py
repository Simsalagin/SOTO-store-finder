"""
Logging configuration with structured logging using structlog.
Provides JSON output, file rotation, and per-chain logging.
"""

import os
import logging
import logging.handlers
from pathlib import Path
from typing import List, Optional, Callable, Any, Dict
import structlog


class LoggerConfig:
    """
    Centralized logging configuration for the application.

    Features:
    - Structured logging with JSON output
    - File rotation with configurable size and backup count
    - Per-chain log files
    - Console and file output
    - Context binding for correlation IDs
    - Custom processors support
    """

    def __init__(self, log_dir: str = "logs"):
        """
        Initialize logger configuration.

        Args:
            log_dir: Directory for log files
        """
        self.log_dir = log_dir
        self._chain_loggers: Dict[str, Any] = {}
        self._configured = False

        # Ensure log directory exists
        Path(self.log_dir).mkdir(parents=True, exist_ok=True)

    def setup(
        self,
        level: str = "INFO",
        json_output: bool = False,
        console_output: bool = True,
        file_output: bool = True,
        max_bytes: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5,
        processors: Optional[List[Callable]] = None
    ) -> Any:
        """
        Set up structured logging with structlog.

        Args:
            level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            json_output: Whether to output logs in JSON format
            console_output: Whether to output to console
            file_output: Whether to output to file
            max_bytes: Maximum size of log file before rotation
            backup_count: Number of backup files to keep
            processors: Additional custom processors

        Returns:
            Configured structlog logger
        """
        # Convert level string to logging level
        numeric_level = getattr(logging, level.upper())

        # Build processor chain
        processor_chain = []

        # Add custom processors first
        if processors:
            processor_chain.extend(processors)

        # Add standard processors
        processor_chain.extend([
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
        ])

        # Add renderer (JSON or console)
        if json_output:
            processor_chain.append(structlog.processors.JSONRenderer())
        else:
            processor_chain.append(structlog.dev.ConsoleRenderer())

        # Configure structlog
        structlog.configure(
            processors=processor_chain,
            wrapper_class=structlog.stdlib.BoundLogger,
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )

        # Configure stdlib logging
        root_logger = logging.getLogger()
        root_logger.setLevel(numeric_level)

        # Remove existing handlers
        root_logger.handlers = []

        # Add console handler
        if console_output:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(numeric_level)
            if json_output:
                formatter = logging.Formatter('%(message)s')
            else:
                formatter = logging.Formatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
                )
            console_handler.setFormatter(formatter)
            root_logger.addHandler(console_handler)

        # Add file handler with rotation
        if file_output:
            log_file = os.path.join(self.log_dir, "application.log")
            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=max_bytes,
                backupCount=backup_count
            )
            file_handler.setLevel(numeric_level)
            formatter = logging.Formatter('%(message)s')
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)

        self._configured = True

        # Return structlog logger
        return structlog.get_logger()

    def get_chain_logger(self, chain_id: str) -> Any:
        """
        Get a logger specific to a chain with its own log file.

        Args:
            chain_id: Chain identifier (e.g., 'rewe', 'denns')

        Returns:
            Structlog logger for the chain
        """
        if chain_id in self._chain_loggers:
            return self._chain_loggers[chain_id]

        # Create stdlib logger for this chain
        stdlib_logger = logging.getLogger(f"chain.{chain_id}")
        stdlib_logger.setLevel(logging.INFO)
        stdlib_logger.propagate = False  # Don't propagate to root

        # Add chain-specific file handler
        log_file = os.path.join(self.log_dir, f"{chain_id}.log")
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5
        )
        file_handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(message)s')
        file_handler.setFormatter(formatter)
        stdlib_logger.addHandler(file_handler)

        # Get structlog logger
        chain_logger = structlog.get_logger(f"chain.{chain_id}")

        # Bind chain_id to all logs
        bound_logger = chain_logger.bind(chain_id=chain_id)

        self._chain_loggers[chain_id] = bound_logger
        return bound_logger

    def reset(self):
        """Reset logging configuration."""
        # Reset structlog
        structlog.reset_defaults()

        # Clear chain loggers
        self._chain_loggers = {}

        # Reset stdlib logging
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            handler.close()
            root_logger.removeHandler(handler)

        self._configured = False
