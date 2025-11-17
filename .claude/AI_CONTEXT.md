# SOTO Store Finder - AI Assistant Context

## Quick Reference

### Tech Stack
| Component | Technology | Version |
|-----------|-----------|---------|
| Language | Python | 3.8+ |
| Web Scraping | requests, lxml, BeautifulSoup | 2.32.3, 5.3.0, 4.12.3 |
| Browser Automation | Playwright | 1.49.1 |
| Database | SQLAlchemy (SQLite) | 2.0.36 |
| API Server | Flask | 3.1.0 |
| Frontend | Leaflet.js | 1.9.4 |
| Testing | pytest | 8.3.4 |
| Linting | ruff, mypy | 0.8.4, 1.13.0 |

### Current Chain Status
| Chain ID | Stores | Scraper Type | Active |
|----------|--------|--------------|--------|
| `denns` | 591 | API (JSON) | ✅ |
| `tegut` | 312 | HTML (lxml) | ✅ |
| `alnatura` | 150 | HTML (lxml) | ✅ |
| `globus` | 61 | Playwright | ✅ |
| `biocompany` | 59 | Uberall API | ✅ |
| `vollcorner` | 18 | HTML (BeautifulSoup) | ✅ |
| **Total** | **1,191** | - | - |

### Key File Paths
```
/Users/martingugel/Repos/SOTO-store-finder/
├── src/scrapers/base.py          # BaseScraper abstract class + Store dataclass
├── src/scrapers/{chain}.py       # Chain-specific scrapers
├── src/storage/database.py       # SQLAlchemy models + Database class
├── src/geocoding/validator.py    # Coordinate validation (OSM)
├── scripts/update_stores.py      # Main orchestrator (config-driven)
├── config/chains.json            # Chain configuration
├── data/stores.db                # SQLite database
├── api/server.py                 # Flask API
├── api/export_geojson.py         # Generate frontend/stores.geojson
├── frontend/index.html           # Leaflet.js map
├── frontend/stores.geojson       # Generated from database
└── tests/test_{module}.py        # pytest test files
```

---

## Architecture Patterns

### 1. BaseScraper Pattern (MANDATORY)

**All scrapers MUST inherit from `BaseScraper` and implement `scrape()` method.**

```python
# src/scrapers/base.py
from abc import ABC, abstractmethod
from typing import List, Optional
from dataclasses import dataclass

@dataclass
class Store:
    """Store data structure - use this exact structure"""
    chain_id: str           # e.g., 'denns', 'alnatura'
    store_id: str           # unique ID from chain
    name: str
    street: str
    postal_code: str
    city: str
    country_code: str       # ISO code, e.g., 'DE'
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    opening_hours: Optional[Dict] = None  # JSON-serializable dict
    services: Optional[List[str]] = None
    scraped_at: Optional[datetime] = None  # Auto-set by __post_init__

class BaseScraper(ABC):
    def __init__(self, chain_id: str, chain_name: str, validate_coordinates: bool = True):
        self.chain_id = chain_id
        self.chain_name = chain_name
        self.validate_coordinates = validate_coordinates

    @abstractmethod
    def scrape(self) -> List[Store]:
        """Implement scraping logic here"""
        pass

    def validate_store(self, store: Store) -> bool:
        """Validates required fields"""
        pass

    def validate_and_fix_coordinates(self, store: Store) -> Store:
        """Auto-validates coordinates with OSM, auto-fixes if possible"""
        pass

    def filter_country(self, stores: List[Store], country_code: str = 'DE') -> List[Store]:
        """Filter stores by country"""
        pass
```

### 2. Scraper Implementation Example

```python
# src/scrapers/newchain.py
import logging
import requests
from typing import List
from .base import BaseScraper, Store

logger = logging.getLogger(__name__)  # ALWAYS use logger, NEVER print()

class NewChainScraper(BaseScraper):
    API_URL = "https://example.com/api/stores"

    def __init__(self):
        super().__init__(chain_id="newchain", chain_name="New Chain")

    def scrape(self) -> List[Store]:
        logger.info(f"Scraping {self.chain_name} stores...")

        response = requests.get(self.API_URL, timeout=30)
        response.raise_for_status()

        data = response.json()
        stores = []

        for item in data['stores']:
            store = Store(
                chain_id=self.chain_id,
                store_id=item['id'],
                name=item['name'],
                street=item['address']['street'],
                postal_code=item['address']['zip'],
                city=item['address']['city'],
                country_code=item['address']['country'],
                latitude=float(item['lat']) if item.get('lat') else None,
                longitude=float(item['lon']) if item.get('lon') else None,
            )

            if self.validate_store(store):
                # Auto-validate/fix coordinates
                store = self.validate_and_fix_coordinates(store)
                stores.append(store)

        # Filter for Germany only
        return self.filter_country(stores, 'DE')
```

### 3. Database Architecture

**SQLAlchemy ORM with automatic CRUD operations:**

```python
# src/storage/database.py
from sqlalchemy import create_engine, Column, String, Float, DateTime, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

class StoreModel(Base):
    __tablename__ = "stores"

    id = Column(String, primary_key=True)  # Format: {chain_id}_{store_id}
    chain_id = Column(String, nullable=False, index=True)
    store_id = Column(String, nullable=False)
    name = Column(String, nullable=False)
    street = Column(String, nullable=False)
    postal_code = Column(String, nullable=False)
    city = Column(String, nullable=False, index=True)
    country_code = Column(String, nullable=False, default='DE')
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    phone = Column(String, nullable=True)
    email = Column(String, nullable=True)
    website = Column(String, nullable=True)
    opening_hours = Column(JSON, nullable=True)
    services = Column(JSON, nullable=True)
    scraped_at = Column(DateTime, nullable=False, default=datetime.now)
    updated_at = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)
    is_active = Column(String, nullable=False, default='true')

class Database:
    def save_stores(self, stores: List[Store]) -> int:
        """Upsert stores (update if exists, insert if new)"""
        pass
```

**Key behaviors:**
- Composite ID: `{chain_id}_{store_id}` (e.g., `denns_12345`)
- Automatic upsert: Updates existing stores, inserts new ones
- Soft delete: `is_active` field ('true', 'false', 'closed')
- Auto-timestamps: `scraped_at`, `updated_at`

### 4. Config-Driven Architecture

**All chain configuration in `config/chains.json`:**

```json
{
  "chains": [
    {
      "id": "newchain",
      "name": "New Chain",
      "website": "https://www.newchain.com",
      "scraper_type": "all_stores",
      "priority": 7,
      "active": true
    }
  ]
}
```

**Orchestrator automatically loads scrapers:**

```python
# scripts/update_stores.py
def get_scraper_for_chain(chain_id: str):
    scraper_map = {
        'denns': 'src.scrapers.denns.DennsScraper',
        'newchain': 'src.scrapers.newchain.NewChainScraper',  # Add here
    }
    # Dynamically imports and instantiates scraper
```

### 5. Coordinate Validation

**Automatic validation on every scrape:**

- Uses OpenStreetMap Nominatim API to validate coordinates
- Checks if coordinates match the address (street, postal_code, city)
- Auto-fixes common issues:
  - Swapped lat/lon
  - Incorrect coordinates
  - Missing coordinates (geocodes from address)
- Logs all validation results
- Confidence score: 0.0 - 1.0 (warns if < 0.8)

**Triggered automatically by `validate_and_fix_coordinates()` in BaseScraper**

---

## Coding Standards

### 1. Logging (CRITICAL)

```python
# ✅ CORRECT - Always use logging
import logging
logger = logging.getLogger(__name__)

logger.info(f"Scraped {len(stores)} stores")
logger.warning(f"Missing coordinates for {store.name}")
logger.error(f"Failed to scrape: {error}", exc_info=True)

# ❌ WRONG - NEVER use print()
print(f"Scraped {len(stores)} stores")  # NEVER DO THIS
```

### 2. Type Hints

```python
# ✅ Required on all public methods
def scrape(self) -> List[Store]:
    pass

def _parse_store(self, data: Dict) -> Optional[Store]:
    pass

# ❌ Not required on private helpers (but recommended)
def _clean_string(s):
    pass
```

### 3. Error Handling

```python
# ✅ Fail gracefully, log errors
try:
    stores = scraper.scrape()
except Exception as e:
    logger.error(f"Scraping failed: {e}", exc_info=True)
    return []

# ✅ Validate data
if not store.latitude or not store.longitude:
    logger.warning(f"Missing coordinates for {store.name}")
```

### 4. Scraper Patterns

**Pattern A: API-based (recommended when available)**
```python
response = requests.get(API_URL, timeout=30)
response.raise_for_status()
data = response.json()
```

**Pattern B: Static HTML (requests + lxml)**
```python
from lxml import html
response = requests.get(URL)
tree = html.fromstring(response.content)
stores = tree.xpath('//div[@class="store"]')
```

**Pattern C: Dynamic JavaScript (Playwright)**
```python
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.goto(URL)
    page.wait_for_selector('.store-list')
```

---

## Development Methodology

### Test-Driven Development (TDD) - MANDATORY

**All new features and scrapers MUST follow TDD approach:**

#### Red-Green-Refactor Cycle

```
1. RED    → Write a failing test first
2. GREEN  → Write minimal code to make it pass
3. REFACTOR → Clean up code while keeping tests green
```

#### TDD Workflow for New Scraper

**Step 1: RED - Write failing test**
```python
# tests/test_newchain.py
import pytest
from src.scrapers.newchain import NewChainScraper
from src.scrapers.base import Store

class TestNewChainScraper:
    def test_scraper_exists(self):
        """Test that scraper can be instantiated"""
        scraper = NewChainScraper()
        assert scraper.chain_id == 'newchain'
        assert scraper.chain_name == 'New Chain'

    def test_scrape_returns_stores(self):
        """Test that scraper returns stores"""
        scraper = NewChainScraper()
        stores = scraper.scrape()

        assert isinstance(stores, list)
        assert len(stores) > 0
        assert all(isinstance(s, Store) for s in stores)

# Run: pytest tests/test_newchain.py -v
# Result: FAILS (scraper doesn't exist yet)
```

**Step 2: GREEN - Implement minimal code**
```python
# src/scrapers/newchain.py
from .base import BaseScraper, Store
import logging

logger = logging.getLogger(__name__)

class NewChainScraper(BaseScraper):
    def __init__(self):
        super().__init__(chain_id="newchain", chain_name="New Chain")

    def scrape(self) -> List[Store]:
        logger.info("Scraping New Chain stores...")
        # Minimal implementation to pass test
        return []

# Run: pytest tests/test_newchain.py -v
# Result: PASSES (but returns empty list)
```

**Step 3: Add more tests for actual data**
```python
# tests/test_newchain.py
def test_stores_have_required_fields(self):
    """Test that stores have all required fields"""
    scraper = NewChainScraper()
    stores = scraper.scrape()

    for store in stores:
        assert store.chain_id == 'newchain'
        assert store.store_id
        assert store.name
        assert store.street
        assert store.postal_code
        assert store.city
        assert store.country_code == 'DE'

# Run: pytest tests/test_newchain.py::test_stores_have_required_fields -v
# Result: FAILS (stores list is empty or missing fields)
```

**Step 4: Implement actual scraping logic**
```python
# src/scrapers/newchain.py
def scrape(self) -> List[Store]:
    logger.info("Scraping New Chain stores...")

    response = requests.get(self.API_URL, timeout=30)
    response.raise_for_status()

    data = response.json()
    stores = []

    for item in data['stores']:
        store = Store(
            chain_id=self.chain_id,
            store_id=item['id'],
            name=item['name'],
            street=item['address']['street'],
            postal_code=item['address']['zip'],
            city=item['address']['city'],
            country_code='DE',
            latitude=float(item['lat']) if item.get('lat') else None,
            longitude=float(item['lon']) if item.get('lon') else None,
        )

        if self.validate_store(store):
            store = self.validate_and_fix_coordinates(store)
            stores.append(store)

    return self.filter_country(stores, 'DE')

# Run: pytest tests/test_newchain.py -v
# Result: PASSES (all tests green)
```

**Step 5: REFACTOR - Clean up and optimize**
```python
# Refactor: Extract parsing logic
def _parse_store(self, item: Dict) -> Optional[Store]:
    """Parse a single store from API response"""
    try:
        return Store(
            chain_id=self.chain_id,
            store_id=item['id'],
            name=item['name'],
            # ... rest of fields
        )
    except KeyError as e:
        logger.error(f"Missing field in store data: {e}")
        return None

def scrape(self) -> List[Store]:
    logger.info("Scraping New Chain stores...")

    response = requests.get(self.API_URL, timeout=30)
    response.raise_for_status()

    data = response.json()
    stores = []

    for item in data['stores']:
        store = self._parse_store(item)
        if store and self.validate_store(store):
            store = self.validate_and_fix_coordinates(store)
            stores.append(store)

    return self.filter_country(stores, 'DE')

# Run: pytest tests/test_newchain.py -v
# Result: STILL PASSES (refactored code, tests still green)
```

### Iterative Development Style

**Build incrementally, test continuously:**

#### Iteration 1: Basic Structure
```bash
# Goal: Scraper exists and returns empty list
1. Write test for scraper instantiation
2. Create scraper class inheriting from BaseScraper
3. Run tests → GREEN

# Commit: "Add NewChain scraper skeleton"
```

#### Iteration 2: Fetch Data
```bash
# Goal: Scraper fetches data from API
1. Write test expecting non-empty list
2. Add API call logic
3. Run tests → GREEN

# Commit: "Add API data fetching to NewChain scraper"
```

#### Iteration 3: Parse Store Data
```bash
# Goal: Parse stores with required fields
1. Write test validating Store fields
2. Implement parsing logic
3. Run tests → GREEN

# Commit: "Parse NewChain stores with all required fields"
```

#### Iteration 4: Add Coordinate Validation
```bash
# Goal: Validate and fix coordinates
1. Write test for coordinate presence
2. Add validate_and_fix_coordinates() call
3. Run tests → GREEN

# Commit: "Add coordinate validation to NewChain scraper"
```

#### Iteration 5: Error Handling
```bash
# Goal: Handle API errors gracefully
1. Write test for API timeout/errors
2. Add try-catch and error logging
3. Run tests → GREEN

# Commit: "Add error handling to NewChain scraper"
```

### Benefits of TDD + Iterative Approach

**For AI Assistants:**
- ✅ Clear success criteria at each step
- ✅ Immediate feedback (tests pass/fail)
- ✅ Prevents scope creep
- ✅ Documents expected behavior
- ✅ Catches regressions early

**For the Project:**
- ✅ High test coverage (by design)
- ✅ Refactoring confidence (tests verify behavior)
- ✅ Better code design (testable = modular)
- ✅ Living documentation (tests show usage)
- ✅ Easier debugging (isolated failures)

### TDD Rules for AI Assistants

**MANDATORY:**
1. **NEVER write implementation before tests** - Always write failing test first
2. **ALWAYS run tests after each change** - Verify RED → GREEN → still GREEN
3. **COMMIT after each GREEN** - Small, tested commits
4. **REFACTOR only when GREEN** - Never refactor with failing tests

**Workflow:**
```bash
# 1. Write test
vim tests/test_newchain.py

# 2. Run test (should FAIL)
pytest tests/test_newchain.py -v
# Expected: FAILED

# 3. Write minimal code
vim src/scrapers/newchain.py

# 4. Run test (should PASS)
pytest tests/test_newchain.py -v
# Expected: PASSED

# 5. Commit
git add tests/test_newchain.py src/scrapers/newchain.py
git commit -m "Add NewChain scraper basic functionality (RED→GREEN)"

# 6. Add next test, repeat
```

### When to Use TDD

**ALWAYS use TDD for:**
- ✅ New scrapers
- ✅ New features
- ✅ Bug fixes (write failing test first, then fix)
- ✅ Refactoring (ensure tests pass before and after)

**Optional for:**
- ⚠️ Quick experiments (but add tests before committing)
- ⚠️ Prototype code (but TDD before merging)

### Example: TDD for Bug Fix

```bash
# Bug report: "denns scraper returns stores with swapped coordinates"

# 1. Write failing test that reproduces bug
def test_coordinates_not_swapped():
    """Test that coordinates are correct (lat in valid range)"""
    scraper = DennsScraper()
    stores = scraper.scrape()

    for store in stores:
        # Germany latitude: ~47-55°N
        assert 47 <= store.latitude <= 55, f"Invalid latitude for {store.name}"
        # Germany longitude: ~6-15°E
        assert 6 <= store.longitude <= 15, f"Invalid longitude for {store.name}"

# Run: pytest tests/test_denns.py::test_coordinates_not_swapped -v
# Result: FAILS (coordinates are swapped)

# 2. Fix the bug
# src/scrapers/denns.py
# Before:
store.latitude = lon  # BUG: swapped
store.longitude = lat

# After:
store.latitude = lat  # FIXED
store.longitude = lon

# 3. Run test again
# pytest tests/test_denns.py::test_coordinates_not_swapped -v
# Result: PASSES

# 4. Run all tests to ensure no regression
# pytest tests/test_denns.py -v
# Result: ALL PASS

# 5. Commit
git commit -m "Fix swapped coordinates in denns scraper"
```

---

## Common Tasks

### Task 1: Add New Chain

**Step-by-step guide:**

```bash
# 1. Add to config/chains.json
{
  "id": "newchain",
  "name": "New Chain",
  "website": "https://www.newchain.com",
  "scraper_type": "all_stores",
  "priority": 7,
  "active": true
}

# 2. Create scraper
touch src/scrapers/newchain.py

# 3. Implement scraper (see example above)

# 4. Register in update_stores.py
# Add to scraper_map dict in get_scraper_for_chain()

# 5. Test scraper
python scripts/update_stores.py --chain newchain

# 6. Verify in database
sqlite3 data/stores.db "SELECT COUNT(*) FROM stores WHERE chain_id = 'newchain';"

# 7. Export to GeoJSON
python api/export_geojson.py

# 8. Update README.md status table
# Update store counts and add new chain row
```

### Task 2: Debug Scraper Returning 0 Stores

```bash
# 1. Enable debug logging
export LOG_LEVEL=DEBUG
python scripts/update_stores.py --chain <chain>

# 2. Check if website structure changed
# Manually visit the store locator page
# Compare HTML/JSON structure with scraper code

# 3. Test individual components
# Create temporary test file:
python -c "
from src.scrapers.denns import DennsScraper
scraper = DennsScraper()
stores = scraper.scrape()
print(f'Found {len(stores)} stores')
print(stores[0] if stores else 'No stores found')
"

# 4. Check network issues
curl -I <API_URL>
```

### Task 3: Fix Coordinate Issues

```bash
# 1. Check validation logs
grep "Invalid coordinates" logs/scraper.log

# 2. Run validator manually
cd src/geocoding
python validator.py

# 3. Check specific store in database
sqlite3 data/stores.db "
SELECT name, latitude, longitude, city
FROM stores
WHERE chain_id = 'denns'
AND latitude IS NOT NULL
LIMIT 5;
"

# 4. Re-run scraper with validation enabled
python scripts/update_stores.py --chain denns
```

### Task 4: Update Existing Scraper

```bash
# 1. Create feature branch
git checkout -b fix/update-denns-scraper

# 2. Modify scraper
# Edit src/scrapers/denns.py

# 3. Test changes
pytest tests/test_denns.py -v
python scripts/update_stores.py --chain denns

# 4. Verify data quality
sqlite3 data/stores.db "
SELECT COUNT(*),
       SUM(CASE WHEN latitude IS NOT NULL THEN 1 ELSE 0 END) as with_coords
FROM stores
WHERE chain_id = 'denns';
"

# 5. Create PR (see Git Workflow below)
```

### Task 5: Run Tests

```bash
# All tests
pytest tests/ -v

# Specific scraper
pytest tests/test_denns.py -v

# With coverage
pytest --cov=src tests/

# Single test function
pytest tests/test_denns.py::test_scrape_stores -v

# Debug mode
pytest tests/test_denns.py -v -s  # -s shows print/log output
```

---

## Git Workflow & Branch Strategy

### MANDATORY for Features

```bash
# 1. Create feature branch
git checkout -b feature/add-newchain-scraper

# 2. Make changes, commit regularly
git add src/scrapers/newchain.py config/chains.json
git commit -m "Add NewChain scraper with API integration"

# 3. Test thoroughly
pytest tests/test_newchain.py -v
python scripts/update_stores.py --chain newchain

# 4. Update documentation
# - README.md (status table)
# - config/chains.json (already done)

# 5. Push and create PR
git push -u origin feature/add-newchain-scraper
gh pr create --title "Add NewChain scraper" --body "..."

# 6. Wait for human approval

# 7. After approval: merge
git checkout main
git merge feature/add-newchain-scraper
git push origin main
```

### Branch Naming Convention

- `feature/` - New scrapers, new features
- `fix/` - Bug fixes
- `refactor/` - Code refactoring
- `docs/` - Documentation updates
- `test/` - Test additions/fixes

### Exception: Direct to Main

**Only for:**
- Typos in documentation
- Minor formatting fixes
- Small config tweaks

**Everything else REQUIRES a feature branch + PR + human approval**

---

## Testing Requirements

### 1. Test Structure

```python
# tests/test_newchain.py
import pytest
from src.scrapers.newchain import NewChainScraper
from src.scrapers.base import Store

class TestNewChainScraper:
    def test_scrape_returns_stores(self):
        """Test that scraper returns list of Store objects"""
        scraper = NewChainScraper()
        stores = scraper.scrape()

        assert isinstance(stores, list)
        assert len(stores) > 0
        assert all(isinstance(s, Store) for s in stores)

    def test_store_validation(self):
        """Test that all stores have required fields"""
        scraper = NewChainScraper()
        stores = scraper.scrape()

        for store in stores:
            assert store.chain_id == 'newchain'
            assert store.store_id
            assert store.name
            assert store.street
            assert store.postal_code
            assert store.city
            assert store.country_code

    def test_coordinates_present(self):
        """Test that stores have coordinates"""
        scraper = NewChainScraper()
        stores = scraper.scrape()

        for store in stores:
            assert store.latitude is not None
            assert store.longitude is not None
            assert -90 <= store.latitude <= 90
            assert -180 <= store.longitude <= 180
```

### 2. Mocking External Requests

```python
import responses
from src.scrapers.newchain import NewChainScraper

@responses.activate
def test_scraper_handles_api_response():
    """Test scraper with mocked API response"""
    responses.add(
        responses.GET,
        'https://example.com/api/stores',
        json={'stores': [...]},
        status=200
    )

    scraper = NewChainScraper()
    stores = scraper.scrape()

    assert len(stores) == 5
```

### 3. Testing Standards

- **MUST:** Test successful scraping
- **MUST:** Validate Store dataclass structure
- **SHOULD:** Test error handling
- **SHOULD:** Mock HTTP requests (for faster tests)
- **OPTIONAL:** Test coordinate validation (already tested in base)

---

## Critical Rules

**NEVER violate these rules:**

1. **NEVER use `print()`** - Always use `logger.info/warning/error()`
2. **ALWAYS inherit from `BaseScraper`** - Never create standalone scraper functions
3. **NEVER hardcode chain data** - Use `config/chains.json`
4. **ALWAYS validate coordinates** - Use `validate_and_fix_coordinates()`
5. **ALWAYS test before committing** - Run pytest
6. **ALWAYS update documentation** - README.md, chains.json when adding chains
7. **ALWAYS use feature branch for features** - Never commit features directly to main
8. **ALWAYS ask before merging to main** - Get human approval first

---

## Debugging Quick Wins

### Scraper returns 0 stores
```bash
# Website structure likely changed
# 1. Check recent commits for patterns
git log --oneline src/scrapers/<chain>.py

# 2. Enable debug logging
export LOG_LEVEL=DEBUG

# 3. Test URL manually
curl -I <URL>
```

### Coordinate validation failing
```bash
# 1. Check validator logs
grep "Invalid coordinates" logs/*.log

# 2. Disable validation temporarily for debugging
scraper = NewChainScraper()
scraper.validate_coordinates = False
stores = scraper.scrape()
```

### Database locked
```bash
# Close all connections
pkill -f "python.*server.py"
pkill -f "sqlite3"

# Check for file locks
lsof data/stores.db
```

### Playwright timeout
```bash
# Reinstall with system dependencies
playwright install --with-deps chromium

# Increase timeout in scraper
page.wait_for_selector('.store-list', timeout=60000)
```

### Import errors
```bash
# Ensure PYTHONPATH is set
export PYTHONPATH=/Users/martingugel/Repos/SOTO-store-finder
python scripts/update_stores.py
```

---

## Development Environment

### Setup
```bash
# 1. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt
playwright install chromium

# 3. Test installation
python scripts/update_stores.py --chain denns
```

### Key Commands
```bash
# Update all chains
python scripts/update_stores.py

# Update specific chain
python scripts/update_stores.py --chain denns

# Export GeoJSON
python api/export_geojson.py

# Run API server
cd api && python server.py

# Run tests
pytest tests/ -v

# Code quality
ruff check .
mypy src/
```

---

## Deployment

**Frontend auto-deploys to GitHub Pages:**

```bash
# 1. Update stores
python scripts/update_stores.py

# 2. Export GeoJSON
python api/export_geojson.py

# 3. Commit and push (triggers GitHub Actions)
git add frontend/stores.geojson
git commit -m "Update store data"
git push origin main

# 4. Check deployment
# https://simsalagin.github.io/SOTO-store-finder/
```

**Workflow:** `.github/workflows/deploy.yml`

---

## AI Assistant Self-Check

**Before starting work:**
- [ ] Am I on a feature branch? (if adding features)
- [ ] Do I understand the BaseScraper pattern?
- [ ] Have I checked config/chains.json?
- [ ] Do I know which files I need to modify?

**Before committing:**
- [ ] Did I use logging instead of print()?
- [ ] Does my code follow BaseScraper pattern?
- [ ] Did I test my changes with pytest?
- [ ] Did I update README.md status table? (if adding chain)
- [ ] Did I update config/chains.json? (if adding chain)
- [ ] Did I validate coordinates?

**Before merging to main:**
- [ ] Am I on a feature branch?
- [ ] Have I pushed and created a PR?
- [ ] Did I ask for human approval?
- [ ] Are all tests passing?
- [ ] Is documentation updated?

---

## Quick File Reference

**To understand architecture:**
- [src/scrapers/base.py](../src/scrapers/base.py) - BaseScraper + Store dataclass
- [src/storage/database.py](../src/storage/database.py) - Database models
- [scripts/update_stores.py](../scripts/update_stores.py) - Orchestrator

**To see implementation examples:**
- [src/scrapers/denns.py](../src/scrapers/denns.py) - API-based scraper
- [src/scrapers/biocompany.py](../src/scrapers/biocompany.py) - Uberall API
- [src/scrapers/globus.py](../src/scrapers/globus.py) - Playwright scraper

**Configuration:**
- [config/chains.json](../config/chains.json) - Chain configuration
- [requirements.txt](../requirements.txt) - Dependencies

**Human docs:**
- [README.md](../README.md) - Human-focused documentation

---

**End of AI Context** | Token count: ~5000 | For updates: edit [.claude/AI_CONTEXT.md](.claude/AI_CONTEXT.md)
