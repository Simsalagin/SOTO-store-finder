"""Script to scrape and save all Alnatura stores."""

import logging
from src.scrapers.alnatura import AlnaturaScraper
from src.storage.database import Database

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Scrape all Alnatura stores and save to database."""
    logger.info("=" * 60)
    logger.info("Scraping Alnatura Stores")
    logger.info("=" * 60)

    # Initialize
    scraper = AlnaturaScraper()
    db = Database()

    # Scrape stores (with automatic coordinate validation)
    logger.info("Scraping stores from website...")
    logger.info("This will take approximately 2-3 minutes...")
    stores = scraper.scrape()
    logger.info(f"Successfully scraped {len(stores)} stores")

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
    logger.info("Scraping completed successfully!")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
