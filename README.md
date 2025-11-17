# SOTO Store Finder

Find stores carrying SOTO brand products across German organic supermarket chains. Automated scraping, validation, and interactive map visualization.

![Status](https://img.shields.io/badge/stores-1191-brightgreen) ![Chains](https://img.shields.io/badge/chains-6-blue) ![Python](https://img.shields.io/badge/python-3.8+-blue)

**[Live Map](https://simsalagin.github.io/SOTO-store-finder/)** | **[AI Assistant Context](.claude/AI_CONTEXT.md)**

---

## Features

- 🔄 **Automated scraping** from 6 organic supermarket chains
- 📍 **Coordinate validation** using OpenStreetMap
- 🗺️ **Interactive map** with 1,191 stores
- 🔌 **REST API** for dynamic data access
- 🧪 **Comprehensive tests** with pytest

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

**Total: 1,191 stores** | **Live Map:** [simsalagin.github.io/SOTO-store-finder](https://simsalagin.github.io/SOTO-store-finder/)

---

## Project Structure

```
SOTO-store-finder/
├── src/
│   ├── scrapers/          # Store scrapers
│   │   ├── base.py        # BaseScraper abstract class
│   │   ├── denns.py       # denn's scraper
│   │   ├── alnatura.py    # Alnatura scraper
│   │   ├── tegut.py       # tegut scraper
│   │   ├── biocompany.py  # Bio Company scraper
│   │   ├── vollcorner.py  # VollCorner scraper
│   │   └── globus.py      # Globus scraper
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
│   └── stores.db          # SQLite database
└── tests/                 # Test suite
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
# Access at http://localhost:5000

# Example endpoints:
# GET /api/stores
# GET /api/stores?chain_id=denns
# GET /api/stores?city=Berlin
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
import requests

class NewChainScraper(BaseScraper):
    def __init__(self):
        super().__init__(chain_id="newchain", chain_name="New Chain")

    def scrape(self) -> List[Store]:
        # Your scraping logic
        return stores
```

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
    scraped_at DATETIME,
    updated_at DATETIME,
    is_active TEXT DEFAULT 'true'
);
```

---

## Technology Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| Language | Python | 3.8+ |
| Web Scraping | requests, lxml | 2.32.3, 5.3.0 |
| Browser Automation | Playwright | 1.49.1 |
| Database | SQLAlchemy (SQLite) | 2.0.36 |
| API | Flask | 3.1.0 |
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

- **BaseScraper Pattern**: All scrapers inherit from abstract base class
- **Config-Driven**: Chain configuration in `config/chains.json`
- **Auto-Validation**: Coordinates validated with OpenStreetMap
- **Upsert Strategy**: Database updates existing stores, inserts new ones
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

**Last Updated:** January 2025 | **Total Stores:** 1,191 | **Active Chains:** 6
