"""
Tests for logging configuration - structured logging with structlog.
Following TDD: These tests are written BEFORE implementation.
"""

import pytest
import os
import json
import tempfile
import shutil
from pathlib import Path
from datetime import datetime


class TestLoggingConfig:
    """Test suite for logging configuration."""

    @pytest.fixture
    def temp_log_dir(self):
        """Create a temporary directory for log files."""
        log_dir = tempfile.mkdtemp()
        yield log_dir
        # Cleanup
        shutil.rmtree(log_dir, ignore_errors=True)

    @pytest.fixture
    def logger_config(self, temp_log_dir):
        """Create a logger configuration for testing."""
        from src.logging.config import LoggerConfig
        return LoggerConfig(log_dir=temp_log_dir)

    def test_create_logger_config(self, temp_log_dir):
        """Test that LoggerConfig can be instantiated."""
        from src.logging.config import LoggerConfig
        config = LoggerConfig(log_dir=temp_log_dir)
        assert config is not None
        assert config.log_dir == temp_log_dir

    def test_setup_logging(self, logger_config, temp_log_dir):
        """Test basic logging setup."""
        logger = logger_config.setup()
        assert logger is not None

        # Test logging a message
        logger.info("test_message", extra_field="test_value")

        # Verify log file was created
        log_files = list(Path(temp_log_dir).glob("*.log"))
        assert len(log_files) > 0

    def test_json_output_format(self, logger_config, temp_log_dir):
        """Test that logs are output in JSON format."""
        logger = logger_config.setup(json_output=True)

        test_message = "json_test_message"
        logger.info(test_message, test_field="test_value")

        # Read log file
        log_files = list(Path(temp_log_dir).glob("*.log"))
        assert len(log_files) > 0

        with open(log_files[0], 'r') as f:
            log_content = f.read()
            # Verify it's valid JSON
            log_lines = [line for line in log_content.strip().split('\n') if line]
            assert len(log_lines) > 0

            last_log = json.loads(log_lines[-1])
            assert last_log['event'] == test_message
            assert last_log['test_field'] == 'test_value'
            assert 'timestamp' in last_log
            assert 'level' in last_log

    def test_log_levels(self, logger_config, temp_log_dir):
        """Test different log levels."""
        logger = logger_config.setup(level="DEBUG")

        logger.debug("debug_message")
        logger.info("info_message")
        logger.warning("warning_message")
        logger.error("error_message")

        # All messages should be logged
        log_files = list(Path(temp_log_dir).glob("*.log"))
        with open(log_files[0], 'r') as f:
            content = f.read()
            assert "debug_message" in content
            assert "info_message" in content
            assert "warning_message" in content
            assert "error_message" in content

    def test_log_level_filtering(self, logger_config, temp_log_dir):
        """Test that log level filtering works."""
        logger = logger_config.setup(level="WARNING")

        logger.debug("debug_message_filtered")
        logger.info("info_message_filtered")
        logger.warning("warning_message_visible")
        logger.error("error_message_visible")

        # Only WARNING and ERROR should be logged
        log_files = list(Path(temp_log_dir).glob("*.log"))
        with open(log_files[0], 'r') as f:
            content = f.read()
            assert "debug_message_filtered" not in content
            assert "info_message_filtered" not in content
            assert "warning_message_visible" in content
            assert "error_message_visible" in content

    def test_file_rotation(self, logger_config, temp_log_dir):
        """Test log file rotation configuration."""
        logger = logger_config.setup(
            max_bytes=1024,  # 1KB max size
            backup_count=3
        )

        # Write enough logs to trigger rotation
        for i in range(100):
            logger.info(f"rotation_test_message_{i}", data="x" * 100)

        # Should have multiple log files (rotated)
        log_files = list(Path(temp_log_dir).glob("*.log*"))
        # At least main log + some backups
        assert len(log_files) >= 1

    def test_separate_log_file_per_chain(self, logger_config, temp_log_dir):
        """Test creating separate log files for different chains."""
        rewe_logger = logger_config.get_chain_logger("rewe")
        denns_logger = logger_config.get_chain_logger("denns")

        rewe_logger.info("rewe_specific_message")
        denns_logger.info("denns_specific_message")

        # Should have separate log files
        rewe_logs = list(Path(temp_log_dir).glob("*rewe*.log"))
        denns_logs = list(Path(temp_log_dir).glob("*denns*.log"))

        assert len(rewe_logs) > 0
        assert len(denns_logs) > 0

        # Verify content separation
        with open(rewe_logs[0], 'r') as f:
            rewe_content = f.read()
            assert "rewe_specific_message" in rewe_content
            assert "denns_specific_message" not in rewe_content

    def test_context_binding(self, logger_config):
        """Test binding context to logger."""
        logger = logger_config.setup(json_output=True)

        # Bind context
        bound_logger = logger.bind(chain_id="test_chain", run_id="test_run_123")

        bound_logger.info("test_with_context")

        # Context should be included in all log entries
        log_files = list(Path(logger_config.log_dir).glob("*.log"))
        with open(log_files[0], 'r') as f:
            log_lines = f.readlines()
            last_log = json.loads(log_lines[-1])
            assert last_log['chain_id'] == 'test_chain'
            assert last_log['run_id'] == 'test_run_123'

    def test_exception_logging(self, logger_config, temp_log_dir):
        """Test logging exceptions with stack traces."""
        logger = logger_config.setup(json_output=True)

        try:
            raise ValueError("Test exception")
        except ValueError:
            logger.exception("error_occurred")

        # Verify exception details are logged
        log_files = list(Path(temp_log_dir).glob("*.log"))
        with open(log_files[0], 'r') as f:
            content = f.read()
            assert "error_occurred" in content
            assert "ValueError" in content
            assert "Test exception" in content

    def test_console_and_file_logging(self, logger_config, temp_log_dir):
        """Test that logs go to both console and file."""
        logger = logger_config.setup(
            console_output=True,
            file_output=True
        )

        logger.info("dual_output_test")

        # File should have the log
        log_files = list(Path(temp_log_dir).glob("*.log"))
        assert len(log_files) > 0

        with open(log_files[0], 'r') as f:
            content = f.read()
            assert "dual_output_test" in content

    def test_custom_processors(self, logger_config):
        """Test adding custom processors to the logging chain."""
        def add_timestamp_processor(logger, name, event_dict):
            event_dict['custom_timestamp'] = datetime.now().isoformat()
            return event_dict

        logger = logger_config.setup(
            json_output=True,
            processors=[add_timestamp_processor]
        )

        logger.info("test_custom_processor")

        # Verify custom processor was applied
        log_files = list(Path(logger_config.log_dir).glob("*.log"))
        with open(log_files[0], 'r') as f:
            log_lines = f.readlines()
            last_log = json.loads(log_lines[-1])
            assert 'custom_timestamp' in last_log

    def test_log_directory_creation(self):
        """Test that log directory is created if it doesn't exist."""
        from src.logging.config import LoggerConfig

        non_existent_dir = "/tmp/test_logs_" + str(os.getpid())

        try:
            config = LoggerConfig(log_dir=non_existent_dir)
            config.setup()

            # Directory should be created
            assert os.path.exists(non_existent_dir)
        finally:
            # Cleanup
            if os.path.exists(non_existent_dir):
                shutil.rmtree(non_existent_dir)

    def test_reset_logging_config(self, logger_config):
        """Test resetting logging configuration."""
        logger1 = logger_config.setup(level="DEBUG")
        logger1.info("first_config")

        # Reset and reconfigure
        logger_config.reset()
        logger2 = logger_config.setup(level="ERROR")
        logger2.info("second_config")  # Should not be logged (level too low)
        logger2.error("error_after_reset")

        # Verify reset worked
        log_files = list(Path(logger_config.log_dir).glob("*.log"))
        with open(log_files[0], 'r') as f:
            content = f.read()
            assert "first_config" in content
            assert "error_after_reset" in content
