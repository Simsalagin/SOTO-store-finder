"""Main script to update all store data with validation."""

import argparse
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


def get_scraper_for_chain(chain_id: str, check_soto: bool = False):
    """
    Get scraper instance for a given chain ID.

    Args:
        chain_id: Chain identifier (e.g., 'denns', 'alnatura', 'tegut')
        check_soto: Whether to check SOTO product availability (REWE only)

    Returns:
        Scraper instance or None if not implemented
    """
    scraper_map = {
        'denns': 'src.scrapers.denns.DennsScraper',
        'alnatura': 'src.scrapers.alnatura.AlnaturaScraper',
        'tegut': 'src.scrapers.tegut.TegutScraper',
        'vollcorner': 'src.scrapers.vollcorner.VollcornerScraper',
        'globus': 'src.scrapers.globus.GlobusScraper',
        'biocompany': 'src.scrapers.biocompany.BioCompanyScraper',
        'rewe': 'src.scrapers.rewe.REWEScraper',
    }

    scraper_class_path = scraper_map.get(chain_id)
    if not scraper_class_path:
        return None

    # Dynamically import the scraper
    module_path, class_name = scraper_class_path.rsplit('.', 1)
    try:
        module = __import__(module_path, fromlist=[class_name])
        scraper_class = getattr(module, class_name)

        # Special handling for REWE with SOTO checking
        if chain_id == 'rewe' and check_soto:
            logger.info("Enabling SOTO product availability checking for REWE")
            return scraper_class(check_soto_availability=True)
        else:
            return scraper_class()
    except (ImportError, AttributeError) as e:
        logger.warning(f"Could not load scraper for {chain_id}: {e}")
        return None


def update_chain_stores(chain_config: dict, db: Database, limit: int = None, batch_size: int = 100, check_soto: bool = False) -> dict:
    """
    Update stores for a specific chain using batch processing.

    Args:
        chain_config: Chain configuration from chains.json
        db: Database instance
        limit: Maximum number of stores to process (None for all)
        batch_size: Number of stores to process per batch (default: 100)
        check_soto: Whether to check SOTO product availability (REWE only)

    Returns:
        Dictionary with update statistics
    """
    chain_id = chain_config['id']
    chain_name = chain_config['name']

    logger.info("=" * 60)
    logger.info(f"Updating {chain_name} Stores")
    logger.info("=" * 60)

    # Get scraper
    scraper = get_scraper_for_chain(chain_id, check_soto=check_soto)
    if not scraper:
        logger.warning(f"Scraper not implemented for {chain_name} - skipping")
        return {'chain': chain_name, 'status': 'not_implemented', 'stores': 0}

    try:
        # Check if scraper supports incremental batch processing
        if hasattr(scraper, '_generate_batches'):
            # USE NEW INCREMENTAL BATCH PROCESSING
            logger.info("Using incremental batch processing with GeoJSON updates...")
            from api.export_geojson import update_geojson_incremental

            total_processed = 0
            total_failed = 0
            batch_count = 0

            # Process batches as they're scraped
            for batch in scraper._generate_batches(batch_size=batch_size, limit=limit):
                batch_count += 1
                logger.info(f"[{chain_name}] Batch {batch_count}: Fetched {len(batch)} stores")

                # Validate stores
                logger.info(f"[{chain_name}] Batch {batch_count}: Validating stores...")
                valid_stores = []
                for store in batch:
                    if scraper.validate_store(store):
                        valid_stores.append(store)
                        total_processed += 1
                    else:
                        total_failed += 1
                        logger.warning(f"[{chain_name}] Invalid store: {store.name} - missing required fields")

                # Save to database
                if valid_stores:
                    logger.info(f"[{chain_name}] Batch {batch_count}: Saving {len(valid_stores)} stores to database...")
                    db.save_stores(valid_stores)
                    logger.info(f"[{chain_name}] Batch {batch_count}: Saved ✓")

                    # Update GeoJSON incrementally (stores visible on map immediately!)
                    logger.info(f"[{chain_name}] Batch {batch_count}: Updating GeoJSON...")
                    update_geojson_incremental(valid_stores)
                    logger.info(f"[{chain_name}] Batch {batch_count}: GeoJSON updated (+{len(valid_stores)} stores) ✓")

                # Check limit
                if limit and total_processed >= limit:
                    logger.info(f"Reached limit of {limit} stores")
                    break

            logger.info(f"Incremental processing completed: {total_processed} processed, {total_failed} failed")

            return {
                'chain': chain_name,
                'status': 'success',
                'stores': total_processed,
                'processed': total_processed,
                'failed': total_failed
            }

        else:
            # FALLBACK: Use old batch processing for scrapers without _generate_batches
            logger.info("Scraping stores (old method)...")
            stores = scraper.scrape(limit=limit)
            logger.info(f"Found {len(stores)} stores")

            # Process in batches with checkpointing
            from src.batch import BatchProcessor
            from api.export_geojson import update_geojson_incremental
            from pathlib import Path

            # Ensure data directory exists
            Path("data").mkdir(exist_ok=True)
            processor = BatchProcessor(db_path="data/checkpoints.db")

            # Progress callback to show updates
            def progress_callback(progress: dict):
                logger.info(
                    f"Progress: {progress['processed']}/{progress['total']} stores "
                    f"({progress['percentage']:.1f}%) - "
                    f"batch {progress['batch']}, failed: {progress['failed']}"
                )

            # Batch processing callback to validate and save stores
            def process_batch(batch):
                """Validate and save a batch of stores."""
                processed = 0
                failed = 0

                # Validate stores
                valid_stores = []
                for store in batch:
                    if scraper.validate_store(store):
                        valid_stores.append(store)
                        processed += 1
                    else:
                        failed += 1
                        logger.warning(f"Invalid store: {store.name} - missing required fields")

                # Save valid stores to database
                if valid_stores:
                    db.save_stores(valid_stores)

                    # Update GeoJSON incrementally
                    update_geojson_incremental(valid_stores)
                    logger.info(f"  Updated stores.geojson (+{len(valid_stores)} stores)")

                return processed, failed

            # Process with batch processing and checkpointing
            logger.info(f"Processing {len(stores)} stores in batches (batch_size={batch_size})...")
            result = processor.process(
                items=stores,
                chain_id=chain_id,
                batch_size=batch_size,
                process_callback=process_batch,
                progress_callback=progress_callback
            )

            logger.info(f"Batch processing completed: {result['status']}")
            logger.info(f"Run ID: {result['run_id']}")

            return {
                'chain': chain_name,
                'status': 'success',
                'stores': result['processed'],
                'run_id': result.get('run_id'),
                'processed': result['processed'],
                'failed': result['failed']
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
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Update store data for grocery chains')
    parser.add_argument('--chain', type=str, help='Only update specific chain (e.g., rewe, denns)')
    parser.add_argument('--limit', type=int, help='Limit number of stores to process per chain')
    parser.add_argument('--batch-size', type=int, default=100, help='Batch size for processing (default: 100)')
    parser.add_argument('--check-soto', action='store_true', help='Check SOTO product availability (REWE only)')
    args = parser.parse_args()

    logger.info("Starting store update process...")

    # Load configuration
    config = load_chains_config()
    chains = config['chains']

    # Filter active chains and sort by priority
    active_chains = [c for c in chains if c.get('active', False)]

    # Filter by specific chain if requested
    if args.chain:
        active_chains = [c for c in active_chains if c['id'] == args.chain]
        if not active_chains:
            logger.error(f"Chain '{args.chain}' not found or not active")
            return

    active_chains.sort(key=lambda x: x.get('priority', 999))

    logger.info(f"Found {len(active_chains)} active chains to update")
    if args.limit:
        logger.info(f"Limiting to {args.limit} stores per chain")
    logger.info(f"Batch size: {args.batch_size}")
    if args.check_soto:
        logger.info("SOTO product availability checking: ENABLED")

    # Initialize database
    db = Database()

    # Update each chain
    results = []
    for chain in active_chains:
        # Skip product_check type chains for now
        if chain.get('scraper_type') == 'product_check':
            logger.info(f"Skipping {chain['name']} (product_check type not yet implemented)")
            continue

        result = update_chain_stores(chain, db, limit=args.limit, batch_size=args.batch_size, check_soto=args.check_soto)
        results.append(result)

    # Show final statistics
    logger.info("=" * 60)
    logger.info("UPDATE SUMMARY")
    logger.info("=" * 60)

    for result in results:
        status_icon = "✓" if result['status'] == 'success' else "✗"
        base_msg = f"{status_icon} {result['chain']}: {result['stores']} stores ({result['status']})"

        # Add batch processing details if available
        if 'run_id' in result:
            base_msg += f" [run_id: {result['run_id'][:8]}...]"
        if 'processed' in result and 'failed' in result:
            base_msg += f" [processed: {result['processed']}, failed: {result['failed']}]"

        logger.info(base_msg)

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
