"""Main script to update all store data with validation."""

import json
import logging
from pathlib import Path
from src.storage.database import Database

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_chains_config():
    """Load chains configuration from JSON file."""
    config_path = Path(__file__).parent.parent / 'config' / 'chains.json'
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_scraper_for_chain(chain_id: str):
    """
    Get scraper instance for a given chain ID.

    Args:
        chain_id: Chain identifier (e.g., 'denns', 'alnatura', 'tegut')

    Returns:
        Scraper instance or None if not implemented
    """
    scraper_map = {
        'denns': 'src.scrapers.denns.DennsScraper',
        'alnatura': 'src.scrapers.alnatura.AlnaturaScraper',
        'tegut': 'src.scrapers.tegut.TegutScraper',
        'vollcorner': 'src.scrapers.vollcorner.VollcornerScraper',
    }

    scraper_class_path = scraper_map.get(chain_id)
    if not scraper_class_path:
        return None

    # Dynamically import the scraper
    module_path, class_name = scraper_class_path.rsplit('.', 1)
    try:
        module = __import__(module_path, fromlist=[class_name])
        scraper_class = getattr(module, class_name)
        return scraper_class()
    except (ImportError, AttributeError) as e:
        logger.warning(f"Could not load scraper for {chain_id}: {e}")
        return None


def update_chain_stores(chain_config: dict, db: Database) -> dict:
    """
    Update stores for a specific chain.

    Args:
        chain_config: Chain configuration from chains.json
        db: Database instance

    Returns:
        Dictionary with update statistics
    """
    chain_id = chain_config['id']
    chain_name = chain_config['name']

    logger.info("=" * 60)
    logger.info(f"Updating {chain_name} Stores")
    logger.info("=" * 60)

    # Get scraper
    scraper = get_scraper_for_chain(chain_id)
    if not scraper:
        logger.warning(f"Scraper not implemented for {chain_name} - skipping")
        return {'chain': chain_name, 'status': 'not_implemented', 'stores': 0}

    try:
        # Scrape stores (with automatic coordinate validation)
        logger.info("Scraping stores...")
        stores = scraper.scrape()
        logger.info(f"Found {len(stores)} stores")

        # Save to database
        logger.info("Saving stores to database...")
        saved_count = db.save_stores(stores)
        logger.info(f"Saved/updated {saved_count} stores")

        return {
            'chain': chain_name,
            'status': 'success',
            'stores': saved_count
        }

    except Exception as e:
        logger.error(f"Error updating {chain_name}: {e}", exc_info=True)
        return {
            'chain': chain_name,
            'status': 'error',
            'stores': 0,
            'error': str(e)
        }


def main():
    """Main update function for all chains."""
    logger.info("Starting store update process...")

    # Load configuration
    config = load_chains_config()
    chains = config['chains']

    # Filter active chains and sort by priority
    active_chains = [c for c in chains if c.get('active', False)]
    active_chains.sort(key=lambda x: x.get('priority', 999))

    logger.info(f"Found {len(active_chains)} active chains to update")

    # Initialize database
    db = Database()

    # Update each chain
    results = []
    for chain in active_chains:
        # Skip product_check type chains for now
        if chain.get('scraper_type') == 'product_check':
            logger.info(f"Skipping {chain['name']} (product_check type not yet implemented)")
            continue

        result = update_chain_stores(chain, db)
        results.append(result)

    # Show final statistics
    logger.info("=" * 60)
    logger.info("UPDATE SUMMARY")
    logger.info("=" * 60)

    for result in results:
        status_icon = "✓" if result['status'] == 'success' else "✗"
        logger.info(f"{status_icon} {result['chain']}: {result['stores']} stores ({result['status']})")

    stats = db.get_statistics()
    logger.info("")
    logger.info("Database Statistics:")
    logger.info(f"  Total stores: {stats['total_stores']}")
    logger.info(f"  Active stores: {stats['active_stores']}")
    logger.info(f"  By chain:")
    for chain_id, count in stats['chains'].items():
        logger.info(f"    - {chain_id}: {count}")

    logger.info("=" * 60)
    logger.info("Update completed!")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
