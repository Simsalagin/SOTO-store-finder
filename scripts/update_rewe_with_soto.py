#!/usr/bin/env python3
"""Script to scrape all REWE stores with SOTO product availability checking."""

import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.scrapers.rewe import REWEScraper
from src.storage.database import Database

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main execution function."""
    logger.info("=" * 80)
    logger.info("REWE Store Scraper with SOTO Availability Checking")
    logger.info("=" * 80)

    # Initialize scraper with SOTO checking enabled
    logger.info("Initializing REWE scraper with SOTO availability checking...")
    scraper = REWEScraper(check_soto_availability=True)

    # Scrape stores
    logger.info("Starting scrape (this will take a while due to SOTO checks)...")
    logger.info("Scraping all 16 German states...")
    stores = scraper.scrape()

    logger.info(f"Successfully scraped {len(stores)} stores")

    # Count stores with SOTO
    stores_with_soto = sum(1 for s in stores if s.has_soto_products is True)
    stores_without_soto = sum(1 for s in stores if s.has_soto_products is False)
    stores_unknown = sum(1 for s in stores if s.has_soto_products is None)

    logger.info("=" * 80)
    logger.info("SOTO Availability Summary:")
    logger.info(f"  Stores with SOTO products: {stores_with_soto}")
    logger.info(f"  Stores without SOTO products: {stores_without_soto}")
    logger.info(f"  Stores with unknown status: {stores_unknown}")
    logger.info("=" * 80)

    # Save to database
    logger.info("Saving to database...")
    db = Database()
    saved_count = db.save_stores(stores)
    logger.info(f"Saved/updated {saved_count} stores")

    # Show database stats
    stats = db.get_statistics()
    logger.info("")
    logger.info("Database Statistics:")
    logger.info(f"  Total stores: {stats['total_stores']}")
    logger.info(f"  REWE stores: {stats['chains'].get('rewe', 0)}")

    logger.info("=" * 80)
    logger.info("Complete!")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
