# SOTO Store Finder

Find stores carrying SOTO brand products across German organic supermarket chains. Automated scraping, validation, and interactive map visualization.

![Status](https://img.shields.io/badge/stores-1191-brightgreen) ![Chains](https://img.shields.io/badge/chains-7-blue) ![Python](https://img.shields.io/badge/python-3.8+-blue) ![Tests](https://img.shields.io/badge/tests-87-success)

**[Live Map](https://simsalagin.github.io/SOTO-store-finder/)** | **[AI Assistant Context](.claude/AI_CONTEXT.md)**

---

## Features

- 🔄 **Automated scraping** from 7 organic/mainstream supermarket chains
- 📍 **Coordinate validation** using OpenStreetMap
- 🗺️ **Interactive map** with 1,191 stores
- 🎯 **SOTO availability tracking** - Only shows stores carrying SOTO products
- 🔌 **REST API** for dynamic data access
- 🧪 **Comprehensive tests** with pytest (87 tests, 100% pass rate)
- ⚡ **Batch processing** with checkpoints - recover from failures
- 📊 **Structured logging** with JSON output and correlation IDs
- 🚀 **Fast testing** - test scraping in seconds instead of hours

---

## Quick Start

```bash
# 1. Setup
git clone <repo-url>
cd SOTO-store-finder
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium

# 2. Update stores
python scripts/update_stores.py

# 3. View map
cd frontend && python -m http.server 8000
# Open http://localhost:8000
```

---

## Current Status

| Chain | Stores | Scraper Type | Status |
|-------|--------|--------------|--------|
| denn's Biomarkt | 591 | API (JSON) | ✅ |
| tegut | 312 | HTML (lxml) | ✅ |
| Alnatura | 150 | HTML (lxml) | ✅ |
| Globus | 61 | Playwright | ✅ |
| Bio Company | 59 | Uberall API | ✅ |
| VollCorner | 18 | BeautifulSoup | ✅ |
| REWE | 0* | curl_cffi + API | ✅ |

**Total: 1,191 stores** | **Live Map:** [simsalagin.github.io/SOTO-store-finder](https://simsalagin.github.io/SOTO-store-finder/)

*REWE scraper implemented with SOTO product availability checking via API (opt-in)

---

## Project Structure

```
SOTO-store-finder/
├── src/
│   ├── scrapers/          # Store scrapers
│   │   ├── base.py        # BaseScraper (with batch processing)
│   │   ├── rewe.py        # REWE scraper
│   │   ├── denns.py       # denn's scraper
│   │   ├── alnatura.py    # Alnatura scraper
│   │   ├── tegut.py       # tegut scraper
│   │   ├── biocompany.py  # Bio Company scraper
│   │   ├── vollcorner.py  # VollCorner scraper
│   │   └── globus.py      # Globus scraper
│   ├── batch/             # Batch processing (NEW)
│   │   ├── checkpoint_manager.py  # Checkpoint system
│   │   └── batch_processor.py     # Batch iteration engine
│   ├── logging/           # Structured logging (NEW)
│   │   ├── config.py      # Logger configuration
│   │   ├── correlation.py # Correlation context
│   │   └── progress.py    # Progress tracking
│   ├── storage/           # Database models
│   │   └── database.py    # SQLAlchemy models
│   └── geocoding/         # Coordinate validation
│       └── validator.py   # OSM-based validation
├── scripts/
│   └── update_stores.py   # Main orchestrator
├── api/
│   ├── server.py          # Flask API server
│   └── export_geojson.py  # GeoJSON generator
├── frontend/              # Interactive map
│   ├── index.html         # Leaflet.js map
│   ├── stores.geojson     # Generated from database
│   └── markers/           # Custom chain markers
├── config/
│   └── chains.json        # Chain configuration
├── data/
│   ├── stores.db          # SQLite database
│   └── checkpoints.db     # Batch processing checkpoints (NEW)
└── tests/                 # Test suite (87 tests)
```

---

## Usage

### Update Stores

```bash
# Update all chains
python scripts/update_stores.py

# Update specific chain
python scripts/update_stores.py --chain denns
```

### Start API Server

```bash
cd api
python server.py
# Access at http://localhost:8001

# Available endpoints:
# GET /api/stores - JSON array of all stores
# GET /api/stores/geojson - GeoJSON format for mapping
```

### Export GeoJSON

```bash
python api/export_geojson.py
# Generates frontend/stores.geojson
```

### Run Tests

```bash
# All tests
pytest tests/ -v

# Specific scraper
pytest tests/test_denns.py -v

# With coverage
pytest --cov=src tests/
```

### Batch Processing & Fast Testing (NEW)

**Fast testing with limit parameter:**
```python
from src.scrapers.rewe import REWEScraper

# Test with just 10 stores instead of all ~3000
scraper = REWEScraper(states=["Berlin"], check_soto_availability=False)
stores = scraper.scrape(limit=10)  # Takes ~5 seconds instead of 60 minutes
```

**Batch processing with checkpoints:**
```python
# Process with automatic checkpointing (recovers from crashes)
result = scraper.scrape_with_batches(
    batch_size=100,              # Checkpoint every 100 stores
    limit=50,                    # Limit for testing
    checkpoint_db="data/checkpoints.db",
    progress_callback=lambda p: print(f"{p['percentage']:.1f}% complete")
)

# Result:
# {
#     'run_id': 'rewe_20250119_160530',
#     'processed': 50,
#     'failed': 0,
#     'status': 'completed'
# }
```

**Resume from checkpoint after failure:**
```python
from src.batch import BatchProcessor

processor = BatchProcessor(db_path="data/checkpoints.db")
processor.resume(items=all_stores, process_callback=process_fn)
```

**Structured logging with correlation:**
```python
from src.logging import LoggerConfig, CorrelationContext
import structlog

# Setup structured logging
config = LoggerConfig(log_dir="logs")
logger = config.setup(json_output=True, level="INFO")

# Use correlation context for request tracing
with CorrelationContext(run_id="scrape_001", chain_id="rewe"):
    logger.info("scraping_started", total_stores=100)
    # All logs in this block will have run_id and chain_id
```

**Progress tracking:**
```python
from src.logging import ProgressTracker

with ProgressTracker(total=1000, description="Scraping stores") as tracker:
    for i in range(1000):
        # ... process store ...
        tracker.increment()
        # Output: [Scraping stores] ████████░░ 40% (400/1000)
```

---

## Adding a New Chain

**Quick guide** ([detailed AI guide here](.claude/AI_CONTEXT.md#task-1-add-new-chain)):

1. **Add to config:**
```json
// config/chains.json
{
  "id": "newchain",
  "name": "New Chain",
  "website": "https://www.newchain.com",
  "scraper_type": "all_stores",
  "priority": 7,
  "active": true
}
```

2. **Create scraper:**
```python
# src/scrapers/newchain.py
from .base import BaseScraper, Store
from typing import List, Optional
import requests

class NewChainScraper(BaseScraper):
    def __init__(self):
        super().__init__(chain_id="newchain", chain_name="New Chain")

    def scrape(self, limit: Optional[int] = None) -> List[Store]:
        # Your scraping logic
        stores = fetch_all_stores()  # Your implementation

        # Apply limit for testing
        if limit:
            stores = stores[:limit]

        return stores
```

**Note:** All scrapers automatically inherit `scrape_with_batches()` from BaseScraper!

3. **Register in orchestrator:**
```python
# scripts/update_stores.py
scraper_map = {
    'newchain': 'src.scrapers.newchain.NewChainScraper',
    # ...
}
```

4. **Test and verify:**
```bash
python scripts/update_stores.py --chain newchain
sqlite3 data/stores.db "SELECT COUNT(*) FROM stores WHERE chain_id = 'newchain';"
```

5. **Update this README** (status table above)

---

## Troubleshooting

### Scraper returns 0 stores
```bash
# Website structure likely changed - enable debug logging
export LOG_LEVEL=DEBUG
python scripts/update_stores.py --chain <chain>
```

### Playwright timeout
```bash
# Reinstall with system dependencies
playwright install --with-deps chromium
```

### Database locked
```bash
# Close all connections
pkill -f "python.*server.py"
```

### Import errors
```bash
# Set PYTHONPATH
export PYTHONPATH=/path/to/SOTO-store-finder
python scripts/update_stores.py
```

---

## Deployment

Frontend auto-deploys to GitHub Pages on push to `main`:

```bash
# 1. Update stores
python scripts/update_stores.py

# 2. Export GeoJSON
python api/export_geojson.py

# 3. Commit and push
git add frontend/stores.geojson
git commit -m "Update store data"
git push origin main

# GitHub Actions will deploy to:
# https://simsalagin.github.io/SOTO-store-finder/
```

Workflow: [.github/workflows/deploy.yml](.github/workflows/deploy.yml)

---

## Database Schema

```sql
CREATE TABLE stores (
    id TEXT PRIMARY KEY,           -- Format: {chain_id}_{store_id}
    chain_id TEXT NOT NULL,
    store_id TEXT NOT NULL,
    name TEXT NOT NULL,
    street TEXT NOT NULL,
    postal_code TEXT NOT NULL,
    city TEXT NOT NULL,
    country_code TEXT DEFAULT 'DE',
    latitude REAL,
    longitude REAL,
    phone TEXT,
    email TEXT,
    website TEXT,
    opening_hours JSON,            -- JSON structure
    services JSON,                 -- JSON array
    has_soto_products BOOLEAN,     -- NULL=unknown, TRUE=has SOTO, FALSE=no SOTO
    scraped_at DATETIME,
    updated_at DATETIME,
    is_active TEXT DEFAULT 'true'
);
```

**SOTO Availability:**
- **REWE stores**: Checked via product search API (opt-in with `check_soto_availability=True`)
- **Other chains**: Assumed to carry SOTO (`has_soto_products=True`)
- **Frontend**: Only displays stores where `has_soto_products=True`

---

## Technology Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| Language | Python | 3.8+ |
| Web Scraping | requests, lxml, curl_cffi | 2.32.3, 5.3.0, latest |
| Browser Automation | Playwright | 1.55.0 |
| Database | SQLAlchemy (SQLite) | 2.0.36 |
| Logging | structlog | 24.4.0 |
| API | http.server (stdlib) | - |
| Frontend | Leaflet.js | 1.9.4 |
| Testing | pytest | 8.3.4 |

Full dependencies: [requirements.txt](requirements.txt)

---

## Contributing

Contributions welcome! Please:

1. Create a feature branch (`git checkout -b feature/your-feature`)
2. Write tests for your changes
3. Ensure all tests pass (`pytest tests/ -v`)
4. Update documentation
5. Submit a pull request

**Code Style:**
- Use logging, not print statements
- Follow [PEP 8](https://pep8.org/)
- Type hints on public methods
- Inherit from `BaseScraper` for scrapers

---

## Architecture Principles

- **BaseScraper Pattern**: All scrapers inherit from abstract base class with built-in batch processing
- **Batch Processing**: Checkpoint every N stores - recover from failures without data loss
- **Structured Logging**: JSON logs with correlation IDs for request tracing
- **Config-Driven**: Chain configuration in `config/chains.json`
- **Auto-Validation**: Coordinates validated with OpenStreetMap
- **Upsert Strategy**: Database updates existing stores, inserts new ones
- **Fast Testing**: `limit` parameter enables testing with small datasets (seconds vs hours)
- **No Hardcoding**: All chain data lives in configuration files

For detailed architecture and AI assistant context: [.claude/AI_CONTEXT.md](.claude/AI_CONTEXT.md)

---

## License

MIT License - see [LICENSE](LICENSE) for details

---

## Contact

For questions or issues:
- Open an [issue](https://github.com/Simsalagin/SOTO-store-finder/issues)
- Submit a [pull request](https://github.com/Simsalagin/SOTO-store-finder/pulls)

---

**Last Updated:** January 2025 | **Total Stores:** 1,191 | **Active Chains:** 7 | **Tests:** 87
