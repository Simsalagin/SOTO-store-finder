"""Base scraper class for all store chain scrapers."""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Callable, Any, Tuple
from dataclasses import dataclass
from datetime import datetime
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class Store:
    """Represents a single store location."""

    chain_id: str  # e.g., 'denns', 'alnatura'
    store_id: str  # unique ID from the chain
    name: str
    street: str
    postal_code: str
    city: str
    country_code: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    opening_hours: Optional[Dict] = None
    services: Optional[List[str]] = None
    has_soto_products: Optional[bool] = None  # True=has SOTO, False=no SOTO, None=unknown
    scraped_at: Optional[datetime] = None

    def __post_init__(self):
        """Set scraped_at timestamp."""
        if self.scraped_at is None:
            self.scraped_at = datetime.now()


class BaseScraper(ABC):
    """Abstract base class for all store scrapers."""

    def __init__(self, chain_id: str, chain_name: str, validate_coordinates: bool = True):
        """
        Initialize the scraper.

        Args:
            chain_id: Unique identifier for the chain (e.g., 'denns')
            chain_name: Display name of the chain (e.g., "denn's Biomarkt")
            validate_coordinates: Whether to validate coordinates (default: True)
        """
        self.chain_id = chain_id
        self.chain_name = chain_name
        self.validate_coordinates = validate_coordinates
        self._validator = None

    @abstractmethod
    def scrape(self, limit: Optional[int] = None) -> List[Store]:
        """
        Scrape all stores for this chain.

        Args:
            limit: Optional limit on number of stores to scrape (for testing)

        Returns:
            List of Store objects
        """
        pass

    def filter_country(self, stores: List[Store], country_code: str = 'DE') -> List[Store]:
        """
        Filter stores by country code.

        Args:
            stores: List of stores to filter
            country_code: ISO country code (default: 'DE' for Germany)

        Returns:
            Filtered list of stores
        """
        return [store for store in stores if store.country_code == country_code]

    def validate_store(self, store: Store) -> bool:
        """
        Validate that a store has all required fields.

        Args:
            store: Store to validate

        Returns:
            True if valid, False otherwise
        """
        required_fields = ['chain_id', 'store_id', 'name', 'street', 'postal_code', 'city']
        return all(getattr(store, field, None) for field in required_fields)

    def validate_and_fix_coordinates(self, store: Store) -> Store:
        """
        Validate and potentially fix store coordinates.

        Args:
            store: Store to validate

        Returns:
            Store with validated/fixed coordinates
        """
        if not self.validate_coordinates:
            return store

        # Skip if no coordinates provided
        if store.latitude is None or store.longitude is None:
            logger.warning(f"Store {store.name} has no coordinates, attempting geocoding")
            store = self._geocode_store(store)
            return store

        # Initialize validator if needed
        if self._validator is None:
            from ..geocoding.validator import CoordinateValidator
            self._validator = CoordinateValidator()

        # Validate coordinates
        validation = self._validator.validate_coordinates(
            latitude=store.latitude,
            longitude=store.longitude,
            street=store.street,
            postal_code=store.postal_code,
            city=store.city,
            country_code=store.country_code
        )

        # Log validation results
        if not validation['valid']:
            logger.warning(
                f"Invalid coordinates for {store.name}: {', '.join(validation['issues'])}"
            )

            # Attempt to fix
            new_lat, new_lon, was_fixed = self._validator.validate_and_fix(
                latitude=store.latitude,
                longitude=store.longitude,
                street=store.street,
                postal_code=store.postal_code,
                city=store.city,
                country_code=store.country_code
            )

            if was_fixed:
                logger.info(
                    f"Fixed coordinates for {store.name}: "
                    f"({store.latitude}, {store.longitude}) -> ({new_lat}, {new_lon})"
                )
                store.latitude = new_lat
                store.longitude = new_lon

        elif validation['confidence'] < 0.8:
            logger.warning(
                f"Low confidence ({validation['confidence']:.2f}) for {store.name}: "
                f"{', '.join(validation['issues'])}"
            )

        return store

    def _geocode_store(self, store: Store) -> Store:
        """Geocode a store that has no coordinates."""
        from ..geocoding.geocoder import Geocoder

        geocoder = Geocoder()
        coords = geocoder.geocode_address(
            street=store.street,
            postal_code=store.postal_code,
            city=store.city,
            country_code=store.country_code
        )

        if coords:
            store.latitude, store.longitude = coords
            logger.info(f"Geocoded {store.name}: {coords}")
        else:
            logger.error(f"Failed to geocode {store.name}")

        return store

    def get_batch_processor(self, checkpoint_db: Optional[str] = None):
        """
        Get a configured batch processor for this scraper.

        Args:
            checkpoint_db: Path to checkpoint database (default: data/checkpoints.db)

        Returns:
            Configured BatchProcessor instance
        """
        from ..batch import BatchProcessor

        if checkpoint_db is None:
            # Ensure data directory exists
            Path("data").mkdir(exist_ok=True)
            checkpoint_db = "data/checkpoints.db"

        return BatchProcessor(db_path=checkpoint_db)

    def scrape_with_batches(
        self,
        batch_size: int = 100,
        checkpoint_db: Optional[str] = None,
        progress_callback: Optional[Callable[[Dict], None]] = None,
        limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Scrape stores with batch processing, checkpointing, and progress tracking.

        This method provides:
        - Automatic checkpointing every N stores (prevents data loss)
        - Resume capability after failures
        - Progress tracking with ETA
        - Correlation IDs for log tracing

        Args:
            batch_size: Number of stores to process per batch (default: 100)
            checkpoint_db: Path to checkpoint database
            progress_callback: Optional callback for progress updates
            limit: Optional limit on total stores (for testing)

        Returns:
            Dictionary with run_id, processed count, failed count, status

        Raises:
            ValueError: If batch_size is invalid
        """
        from ..batch import BatchProcessor
        from ..logging import CorrelationContext, ProgressTracker
        import structlog

        # Validate batch_size
        if batch_size <= 0:
            raise ValueError(f"batch_size must be positive, got {batch_size}")

        # Get all stores from traditional scrape method
        logger.info(f"Starting batch scrape for {self.chain_name}")
        stores = self.scrape(limit=limit)
        logger.info(f"Retrieved {len(stores)} stores from {self.chain_name}")

        # Setup batch processor
        processor = self.get_batch_processor(checkpoint_db)

        # Process stores in batches with correlation context
        with CorrelationContext(chain_id=self.chain_id) as ctx:
            struct_logger = structlog.get_logger()

            struct_logger.info(
                "batch_scrape_started",
                chain=self.chain_name,
                total_stores=len(stores),
                batch_size=batch_size
            )

            # Define batch processing callback
            def process_batch(batch: List[Store]) -> Tuple[int, int]:
                """Process a batch of stores (validate and count)."""
                processed = 0
                failed = 0

                for store in batch:
                    # Validate store
                    if self.validate_store(store):
                        processed += 1
                    else:
                        failed += 1
                        logger.warning(
                            f"Invalid store: {store.name} - missing required fields"
                        )

                return processed, failed

            # Execute batch processing
            result = processor.process(
                items=stores,
                chain_id=self.chain_id,
                batch_size=batch_size,
                process_callback=process_batch,
                progress_callback=progress_callback
            )

            struct_logger.info(
                "batch_scrape_complete",
                **result
            )

            return result
