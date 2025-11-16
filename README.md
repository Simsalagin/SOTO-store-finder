# SOTO Store Finder

Automated system for scraping, validating, and visualizing store locations that carry SOTO brand products across German organic supermarket chains.

![Status](https://img.shields.io/badge/stores-1191-brightgreen) ![Chains](https://img.shields.io/badge/chains-6-blue) ![Python](https://img.shields.io/badge/python-3.8+-blue)

## 📑 Table of Contents

- [Quick Start (5 Minutes)](#-quick-start-5-minutes)
- [Current Status](#-current-status)
- [Project Architecture](#️-project-architecture)
  - [Key Components](#key-components)
- [Common Commands](#-common-commands)
- [Development](#-development)
  - [Adding a New Chain](#adding-a-new-chain)
  - [Scraper Patterns](#scraper-patterns)
  - [Git Workflow & Branch Strategy](#git-workflow--branch-strategy)
  - [Database Schema](#database-schema)
- [Testing](#-testing)
- [Key Principles](#-key-principles)
- [Troubleshooting](#-troubleshooting)
- [Documentation Update Checklist](#-documentation-update-checklist)
- [Deployment](#-deployment)
- [Dependencies](#-dependencies)
- [AI Assistant Guidelines](#-ai-assistant-guidelines)
- [License](#-license)
- [Contact](#-contact)

## 🚀 Quick Start (5 Minutes)

```bash
# 1. Clone and setup
git clone <repo-url>
cd SOTO-store-finder
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt
playwright install chromium  # Required for Playwright-based scrapers

# 3. Update stores
python scripts/update_stores.py

# 4. View the map
cd frontend
python -m http.server 8000
# Open http://localhost:8000
```

## 📊 Current Status

| Chain | Stores | Scraper Type | Status |
|-------|--------|--------------|--------|
| denn's Biomarkt | 591 | Custom (requests + lxml) | ✅ Working |
| tegut... | 312 | Custom (requests + lxml) | ✅ Working |
| Alnatura | 150 | Custom (requests + lxml) | ✅ Working |
| Globus | 61 | Playwright (Browser automation) | ✅ Working |
| Bio Company | 59 | Uberall API | ✅ Working |
| VollCorner | 18 | Custom (BeautifulSoup) | ✅ Working |

**Total: 1,191 stores**

**Live Map:** https://simsalagin.github.io/SOTO-store-finder/

## 🏗️ Project Architecture

```
SOTO-store-finder/
├── src/
│   ├── scrapers/          # Store scrapers
│   │   ├── base.py        # BaseScraper abstract class
│   │   ├── denns.py       # denn's scraper
│   │   ├── alnatura.py    # Alnatura scraper
│   │   ├── tegut.py       # tegut scraper
│   │   └── biocompany.py  # Bio Company scraper
│   ├── geocoding/         # Coordinate validation
│   │   └── validator.py   # OSM-based validation
│   └── database/          # Database models
│       └── models.py      # SQLAlchemy models
├── scripts/
│   └── update_stores.py   # Main orchestrator (config-driven)
├── api/
│   ├── server.py          # Flask API server
│   └── export_geojson.py  # GeoJSON generator
├── frontend/              # Interactive map (Leaflet.js)
│   ├── index.html
│   ├── stores.geojson     # Generated from database
│   └── markers/           # Custom chain markers
├── config/
│   └── chains.json        # Chain configuration
├── data/
│   └── stores.db          # SQLite database
└── tests/                 # Test suite
```

### Key Components

- **BaseScraper** (`src/scrapers/base.py`): Abstract base class for all scrapers
- **Orchestrator** (`scripts/update_stores.py`): Config-driven chain management
- **Validator** (`src/geocoding/validator.py`): OSM-based coordinate validation
- **Database** (`src/database/models.py`): SQLAlchemy models (Chain, Store)
- **API** (`api/server.py`): Flask server for dynamic data serving
- **Frontend** (`frontend/`): Leaflet.js map with custom markers

## 📖 Common Commands

```bash
# Update all stores
python scripts/update_stores.py

# Update specific chain
python scripts/update_stores.py --chain denns

# Start API server
cd api
python server.py  # http://localhost:5000

# Export GeoJSON
python api/export_geojson.py

# Run tests
pytest tests/ -v

# Code quality
ruff check .
mypy src/
```

## 🔧 Development

### Adding a New Chain

1. **Add to `config/chains.json`:**
```json
{
  "chain_id": "newchain",
  "name": "New Chain",
  "scraper_module": "newchain",
  "enabled": true,
  "color": "#FF5733"
}
```

2. **Create scraper `src/scrapers/newchain.py`:**
```python
from src.scrapers.base import BaseScraper, Store
import requests
from typing import List

class NewChainScraper(BaseScraper):
    def scrape(self) -> List[Store]:
        stores = []
        # Your scraping logic here
        return stores
```

3. **Test the scraper:**
```bash
python scripts/update_stores.py --chain newchain
```

4. **Verify in database:**
```bash
sqlite3 data/stores.db "SELECT COUNT(*) FROM stores WHERE chain_id = 'newchain';"
```

### Scraper Patterns

**Pattern 1: Static HTML (requests + lxml)**
- Used by: denn's, Alnatura, tegut
- Best for: Server-side rendered store locators
- Fast and reliable

**Pattern 2: API-based (requests)**
- Used by: Bio Company (Uberall API)
- Best for: Chains with public APIs
- Most reliable when available

**Pattern 3: Dynamic JavaScript (Playwright)**
- Used by: Globus (optional)
- Best for: SPAs and AJAX-loaded content
- Slower but handles complex cases

### Git Workflow & Branch Strategy

**MANDATORY for new features:**

```bash
# Create feature branch
git checkout -b feature/add-newchain-scraper

# Make changes, commit regularly
git add .
git commit -m "Add newchain scraper"

# Push and create PR
git push -u origin feature/add-newchain-scraper
gh pr create --title "Add NewChain scraper" --body "..."

# After human approval: merge
git checkout main
git merge feature/add-newchain-scraper
git push origin main
```

**Branch naming:**
- `feature/` - New features
- `fix/` - Bug fixes
- `refactor/` - Code refactoring
- `docs/` - Documentation updates
- `test/` - Test additions

**Exception:** Small fixes (typos, minor docs) can go directly to main.

### Database Schema

```sql
CREATE TABLE chains (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    color TEXT
);

CREATE TABLE stores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chain_id TEXT NOT NULL,
    name TEXT NOT NULL,
    street TEXT,
    postal_code TEXT,
    city TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    opening_hours TEXT,
    coordinates_validated BOOLEAN DEFAULT 0,
    FOREIGN KEY (chain_id) REFERENCES chains(id)
);
```

## 🧪 Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test
pytest tests/test_scrapers.py -v

# With coverage
pytest --cov=src tests/
```

**Testing Standards:**
- All scrapers must have unit tests
- Test both successful and error cases
- Mock external HTTP requests
- Validate data structure and types

## 🎯 Key Principles

### 1. Logging over Print
```python
# ✅ Good
import logging
logger = logging.getLogger(__name__)
logger.info(f"Scraped {len(stores)} stores")

# ❌ Bad
print(f"Scraped {len(stores)} stores")
```

### 2. Use BaseScraper Pattern
```python
# ✅ Good - Inherit from BaseScraper
class NewScraper(BaseScraper):
    def scrape(self) -> List[Store]:
        # Your logic
        pass

# ❌ Bad - Standalone scraper
def scrape_stores():
    # Your logic
    pass
```

### 3. Configuration-Driven
- All chains in `config/chains.json`
- No hardcoded chain data in code
- Enables/disables chains via config

### 4. Coordinate Validation
- Always validate coordinates with OSM
- Catch invalid/swapped coordinates
- Log validation results

## 🐛 Troubleshooting

### Common Issues

**Issue:** Scraper returns 0 stores
```bash
# Solution: Check if website structure changed
# Enable debug logging
export LOG_LEVEL=DEBUG
python scripts/update_stores.py --chain <chain>
```

**Issue:** Playwright timeout
```bash
# Solution: Increase timeout or check network
# Verify playwright installation
playwright install --with-deps chromium
```

**Issue:** Database locked
```bash
# Solution: Close all connections
pkill -f "python.*server.py"
```

**Issue:** Coordinates not validated
```bash
# Solution: Run validator manually
cd src/geocoding
python validator.py
```

## 📋 Documentation Update Checklist

When making changes, update:

| Change Type | Update These Docs |
|-------------|-------------------|
| New chain added | README.md (Status table), chains.json |
| New scraper pattern | README.md (Scraper Patterns section) |
| New dependency | requirements.txt |
| Architecture change | README.md (Project Architecture) |
| New feature/API | README.md (Common Commands) |
| Bug fix | Document in commit message |

## 🚀 Deployment

The frontend is automatically deployed to GitHub Pages:
- **URL:** `https://simsalagin.github.io/SOTO-store-finder/`
- **Trigger:** Push to `main` branch
- **Workflow:** `.github/workflows/deploy.yml`

To deploy manually:
```bash
python api/export_geojson.py
git add frontend/stores.geojson
git commit -m "Update store data"
git push origin main
```

## 📦 Dependencies

Key dependencies (see `requirements.txt` for full list):

- **requests 2.32.3** - HTTP library
- **lxml 5.3.0** - HTML/XML parsing
- **playwright 1.49.1** - Browser automation
- **sqlalchemy 2.0.36** - Database ORM
- **flask 3.1.0** - API server
- **pandas 2.2.3** - Data export
- **geopy 2.4.1** - Geocoding utilities

Dev dependencies:
- **pytest 8.3.4** - Testing framework
- **ruff 0.8.4** - Linter
- **mypy 1.13.0** - Type checker

## 🤖 AI Assistant Guidelines

When working on this project:

1. **Always use feature branches** for new features (except small fixes)
2. **Update documentation** before merging (README, chains.json, etc.)
3. **Follow BaseScraper pattern** for new scrapers
4. **Use logging**, not print statements
5. **Test your changes** with pytest
6. **Validate coordinates** with OSM
7. **Ask before merging** to main branch

**Self-Check Questions:**
- [ ] Am I on a feature branch?
- [ ] Have I updated all relevant documentation?
- [ ] Does my code follow the existing patterns?
- [ ] Have I tested my changes?
- [ ] Did I use logging instead of print?

## 📄 License

This project is licensed under the MIT License.

## 👥 Contact

For questions or contributions, please open an issue or pull request.

---

**Last Updated:** January 2025 | **Total Stores:** 1,191 | **Active Chains:** 6
