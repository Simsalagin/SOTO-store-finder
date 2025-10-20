"""Main script to update all store data with validation."""

import logging
from src.scrapers.denns import DennsScraper
from src.storage.database import Database

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def update_denns_stores():
    """Update denn's Biomarkt stores with coordinate validation."""
    logger.info("=" * 60)
    logger.info("Updating denn's Biomarkt Stores")
    logger.info("=" * 60)

    # Initialize
    scraper = DennsScraper()
    db = Database()

    # Scrape stores (with automatic coordinate validation)
    logger.info("Scraping stores from API...")
    stores = scraper.scrape()
    logger.info(f"Found {len(stores)} stores")

    # Save to database
    logger.info("Saving stores to database...")
    saved_count = db.save_stores(stores)
    logger.info(f"Saved/updated {saved_count} stores")

    # Show statistics
    stats = db.get_statistics()
    logger.info("Database statistics:")
    logger.info(f"  Total stores: {stats['total_stores']}")
    logger.info(f"  Active stores: {stats['active_stores']}")
    logger.info(f"  By chain: {stats['chains']}")

    logger.info("=" * 60)
    logger.info("Update completed successfully!")
    logger.info("=" * 60)


def main():
    """Main update function for all chains."""
    try:
        update_denns_stores()
        # Future: Add other chains here
        # update_alnatura_stores()
        # update_tegut_stores()
        # etc.
    except Exception as e:
        logger.error(f"Update failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
