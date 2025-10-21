# AI Assistant Guide for SOTO Store Finder

**Purpose:** This document serves as a comprehensive guide for AI coding assistants (Claude Code, GitHub Copilot, etc.) working on the SOTO Store Finder project. Read this at the start of every session to understand the project structure, coding standards, and best practices.

---

## 📋 Project Overview

### What This Project Does
SOTO Store Finder is an automated system that:
1. **Scrapes** store location data from various German supermarket chains
2. **Validates** geographic coordinates using OpenStreetMap
3. **Stores** data in a SQLite database with SQLAlchemy ORM
4. **Exports** to GeoJSON for visualization
5. **Displays** stores on an interactive Leaflet.js map
6. **Deploys** automatically to GitHub Pages

### Current State (2025-10-21)
- **3 chains implemented:** denn's Biomarkt (590), Alnatura (150), tegut (314)
- **Total stores:** 1,054 validated locations
- **Architecture:** Modular, config-driven, production-ready
- **Deployment:** Live at https://simsalagin.github.io/SOTO-store-finder/

---

## 🏗️ Architecture Overview

### Core Design Principles

1. **Configuration-Driven Design**
   - All chains defined in `config/chains.json`
   - Easy to enable/disable chains without code changes
   - Priority-based processing

2. **Inheritance-Based Scrapers**
   - All scrapers inherit from `BaseScraper`
   - Consistent validation and coordinate fixing
   - Standardized error handling

3. **Separation of Concerns**
   - `/src/scrapers/` - Data acquisition
   - `/src/geocoding/` - Location validation
   - `/src/storage/` - Data persistence
   - `/src/export/` - Data transformation
   - `/api/` - Data serving
   - `/frontend/` - Visualization

4. **Fail-Safe Operations**
   - Coordinate validation with automatic correction
   - Graceful handling of missing data
   - Continue processing if one chain fails

---

## 📁 Project Structure

```
SOTO-store-finder/
├── src/
│   ├── scrapers/         # Chain-specific scrapers
│   │   ├── base.py       # Abstract base class (IMPORTANT!)
│   │   ├── denns.py      # JSON API scraper
│   │   ├── alnatura.py   # HTML scraper
│   │   └── tegut.py      # JSON-LD + HTML scraper
│   ├── geocoding/        # Location validation
│   │   ├── geocoder.py   # OSM forward geocoding
│   │   └── validator.py  # Coordinate validation logic
│   ├── storage/          # Database layer
│   │   └── database.py   # SQLAlchemy models & operations
│   └── export/           # Data export
│       └── geojson.py    # GeoJSON generation
├── api/                  # REST API server
│   ├── server.py         # HTTP endpoints
│   └── export_geojson.py # Export utility
├── frontend/             # Web interface
│   ├── index.html        # Leaflet map
│   └── images/           # Logos and markers
├── scripts/              # Utility scripts
│   └── update_stores.py  # Main orchestrator (IMPORTANT!)
├── config/
│   └── chains.json       # Chain definitions (IMPORTANT!)
├── tests/                # Test suite
└── data/
    └── stores.db         # SQLite database
```

---

## 🔑 Key Files to Understand

### 1. `src/scrapers/base.py` (CRITICAL)
**Purpose:** Abstract base class for all scrapers

**Key Features:**
- `scrape()` method (abstract - must implement)
- `validate_and_fix_coordinates()` - automatic validation
- `filter_country()` - filter by country code
- `validate_store()` - ensure required fields present

**Usage Pattern:**
```python
from .base import BaseScraper, Store

class NewChainScraper(BaseScraper):
    def __init__(self):
        super().__init__(chain_id="newchain", chain_name="New Chain")

    def scrape(self) -> List[Store]:
        # 1. Fetch data (API or scraping)
        # 2. Parse into Store objects
        # 3. Return list (validation happens automatically)
        pass
```

### 2. `scripts/update_stores.py` (CRITICAL)
**Purpose:** Main orchestrator - loads config and runs scrapers

**Key Features:**
- Reads `config/chains.json`
- Dynamically loads scrapers via `scraper_map`
- Processes chains by priority
- Generates statistics

**When to update:**
- Adding a new chain scraper
- Changing scraping logic
- Modifying chain priority

### 3. `config/chains.json` (CRITICAL)
**Purpose:** Single source of truth for all chains

**Structure:**
```json
{
  "id": "chain_id",           // Used in database and scraper
  "name": "Display Name",     // User-facing name
  "website": "https://...",   // Chain website
  "scraper_type": "all_stores", // or "product_check"
  "priority": 1,              // Lower runs first
  "active": true              // Enable/disable
}
```

### 4. `src/storage/database.py`
**Purpose:** SQLAlchemy ORM and database operations

**Key Model:** `StoreModel`
- **Composite ID:** `{chain_id}_{store_id}`
- **Upsert logic:** Updates if exists, inserts if new
- **Indexes:** Optimized for common queries

### 5. `src/geocoding/validator.py`
**Purpose:** Multi-layer coordinate validation

**Validation Steps:**
1. Null Island check (0, 0)
2. Country bounds check
3. Reverse geocoding
4. Distance calculation (max 50km)
5. Automatic fix via geocoding

---

## 💻 Coding Standards & Best Practices

### 1. Logging (NEVER use print!)
```python
import logging

logger = logging.getLogger(__name__)

# Good
logger.info("Scraping started")
logger.warning("Store missing coordinates")
logger.error("Failed to connect", exc_info=True)

# Bad
print("Scraping started")  # DON'T DO THIS!
```

### 2. Type Hints (Always!)
```python
from typing import List, Optional, Dict

# Good
def scrape_stores(chain_id: str) -> List[Store]:
    pass

def get_store(store_id: str) -> Optional[Store]:
    pass

# Bad
def scrape_stores(chain_id):  # Missing types
    pass
```

### 3. Error Handling
```python
# Good - Specific exceptions
try:
    response = requests.get(url, timeout=30)
    response.raise_for_status()
except requests.RequestException as e:
    logger.error(f"Request failed: {e}")
    return []

# Bad - Bare except
try:
    response = requests.get(url)
except:  # Too broad!
    pass
```

### 4. Configuration over Hardcoding
```python
# Good - Use config
chains = load_chains_config()
for chain in chains:
    if chain['active']:
        process_chain(chain)

# Bad - Hardcoded
process_chain('denns')
process_chain('alnatura')
```

### 5. Docstrings
```python
def validate_coordinates(lat: float, lon: float) -> Dict:
    """
    Validate coordinates using reverse geocoding.

    Args:
        lat: Latitude in decimal degrees
        lon: Longitude in decimal degrees

    Returns:
        Dictionary with validation results:
        {
            'valid': bool,
            'confidence': float,
            'issues': List[str]
        }
    """
    pass
```

---

## 🔨 Common Tasks & How to Do Them

### Task 1: Add a New Chain Scraper

**Steps:**
1. **Add to config** (`config/chains.json`):
   ```json
   {
     "id": "newchain",
     "name": "New Chain",
     "website": "https://newchain.de",
     "scraper_type": "all_stores",
     "priority": 7,
     "active": true
   }
   ```

2. **Create scraper** (`src/scrapers/newchain.py`):
   ```python
   import logging
   from typing import List
   from .base import BaseScraper, Store

   logger = logging.getLogger(__name__)

   class NewChainScraper(BaseScraper):
       def __init__(self):
           super().__init__(chain_id="newchain", chain_name="New Chain")

       def scrape(self) -> List[Store]:
           logger.info("Starting New Chain scrape...")
           stores = []

           # Implementation here

           logger.info(f"Scraped {len(stores)} stores")
           return self.filter_country(stores, 'DE')
   ```

3. **Register in orchestrator** (`scripts/update_stores.py`):
   ```python
   scraper_map = {
       'denns': 'src.scrapers.denns.DennsScraper',
       'alnatura': 'src.scrapers.alnatura.AlnaturaScraper',
       'tegut': 'src.scrapers.tegut.TegutScraper',
       'newchain': 'src.scrapers.newchain.NewChainScraper',  # Add this
   }
   ```

4. **Add assets** (`frontend/images/`):
   - `newchain-logo.svg`
   - `newchain-marker.svg`

5. **Test:**
   ```bash
   python scripts/update_stores.py
   ```

### Task 2: Modify Database Schema

**IMPORTANT:** Use Alembic if available, otherwise:

1. **Update model** (`src/storage/database.py`):
   ```python
   class StoreModel(Base):
       # Add new column
       new_field = Column(String, nullable=True)
   ```

2. **Update Store dataclass** (`src/scrapers/base.py`):
   ```python
   @dataclass
   class Store:
       # Add new field
       new_field: Optional[str] = None
   ```

3. **Handle migration:**
   - Delete `data/stores.db` (dev only!)
   - Or manually ALTER TABLE (production)

### Task 3: Fix Geocoding Issues

**Common Issues:**
1. **Rate limiting:** Increase `GEOCODING_DELAY` in `.env`
2. **Invalid coordinates:** Check validator logic in `src/geocoding/validator.py`
3. **Missing data:** Ensure scraper provides complete address

**Debug pattern:**
```python
# Add debug logging
logger.debug(f"Validating {store.name}: ({lat}, {lon})")
validation = validator.validate_coordinates(...)
logger.debug(f"Result: {validation}")
```

### Task 4: Update Dependencies

**Process:**
1. Check latest versions at https://pypi.org
2. Update `requirements.txt`
3. Test locally:
   ```bash
   pip install -r requirements.txt
   python scripts/update_stores.py
   pytest tests/
   ```
4. Commit if all tests pass

---

## 🌿 Git Workflow & Branch Strategy

### CRITICAL: Feature Branch Workflow (MANDATORY)

**⚠️ NEVER commit directly to `main` for new features!**

All new features, scrapers, and non-trivial changes MUST:
1. Be developed on a feature branch
2. Be tested thoroughly on the branch
3. Receive human approval before merging to main
4. Update all relevant documentation before merge

### Creating a Feature Branch

```bash
# For new features
git checkout -b feature/add-biocompany-scraper

# For bug fixes
git checkout -b fix/geocoding-timeout

# For refactoring
git checkout -b refactor/async-scraping

# For documentation
git checkout -b docs/update-installation-guide
```

**Branch naming convention:**
- `feature/*` - New features or scrapers
- `fix/*` - Bug fixes
- `refactor/*` - Code improvements without functionality changes
- `docs/*` - Documentation updates
- `test/*` - Adding or updating tests

### Development Workflow

1. **Create feature branch from main:**
   ```bash
   git checkout main
   git pull origin main
   git checkout -b feature/your-feature-name
   ```

2. **Develop and test on branch:**
   ```bash
   # Make changes
   # Run tests
   pytest tests/
   ruff check src/
   mypy src/
   python scripts/update_stores.py  # Integration test
   ```

3. **Commit regularly with clear messages:**
   ```bash
   git add -A
   git commit -m "Add Bio Company scraper with coordinate validation"
   git push origin feature/your-feature-name
   ```

4. **Before requesting merge - Update documentation:**
   - [ ] Update README.md if user-facing changes
   - [ ] Update QUICK_START.md if workflow changes
   - [ ] Update requirements.txt if dependencies added
   - [ ] Update ROADMAP.md (mark completed items)
   - [ ] Update AI_ASSISTANT_GUIDE.md if patterns changed

5. **Create pull request:**
   ```bash
   # Use GitHub UI or gh CLI
   gh pr create --title "Add Bio Company scraper" \
                --body "Implements scraper for Bio Company chain with full validation"
   ```

6. **Wait for human approval:**
   - Human reviewer will check code quality
   - Human reviewer will verify tests pass
   - Human reviewer will validate documentation updates
   - Human may request changes

7. **After approval - Merge to main:**
   ```bash
   # Human or AI can merge after approval
   git checkout main
   git merge feature/your-feature-name
   git push origin main
   ```

### Documentation Update Checklist (MANDATORY)

**Before every merge to `main`, check and update if needed:**

#### 1. README.md
Update if:
- [ ] New chain added (update status counts)
- [ ] New feature visible to users
- [ ] Installation steps changed
- [ ] New dependencies added
- [ ] API endpoints changed
- [ ] Configuration options added

#### 2. QUICK_START.md
Update if:
- [ ] Common commands changed
- [ ] Key principles changed
- [ ] Project structure changed
- [ ] Important files list changed

#### 3. requirements.txt
Update if:
- [ ] New Python packages added
- [ ] Package versions upgraded
- [ ] Dependencies removed

#### 4. ROADMAP.md
Update if:
- [ ] Completed a roadmap item (mark with [x])
- [ ] Discovered new technical debt
- [ ] Added new feature priorities
- [ ] Changed success metrics

#### 5. AI_ASSISTANT_GUIDE.md
Update if:
- [ ] New coding patterns established
- [ ] Architecture changed
- [ ] New common tasks added
- [ ] Important conventions changed

### Small Fixes & Documentation (Exception)

**Direct commits to `main` are ONLY allowed for:**
- Typo fixes in documentation
- README clarifications
- Comment improvements
- .gitignore updates
- Small bug fixes that don't change functionality

**Still require:**
- Clear commit message
- Quick sanity check
- No broken tests

### Pull Request Template

When creating a PR, include:

```markdown
## Summary
Brief description of changes

## Type of Change
- [ ] New feature (feature/*)
- [ ] Bug fix (fix/*)
- [ ] Refactoring (refactor/*)
- [ ] Documentation (docs/*)
- [ ] Tests (test/*)

## Changes Made
- Added Bio Company scraper
- Updated database schema
- Added 50+ new stores

## Testing Done
- [ ] Unit tests pass (`pytest tests/`)
- [ ] Integration test passes (`python scripts/update_stores.py`)
- [ ] Code quality checks pass (`ruff`, `mypy`)
- [ ] Manual testing completed

## Documentation Updated
- [ ] README.md updated
- [ ] QUICK_START.md updated (if needed)
- [ ] requirements.txt updated (if needed)
- [ ] ROADMAP.md updated (if needed)
- [ ] AI_ASSISTANT_GUIDE.md updated (if needed)

## Checklist
- [ ] Code follows project conventions
- [ ] Logging used (not print statements)
- [ ] Type hints added
- [ ] Tests added for new functionality
- [ ] No breaking changes (or documented)
```

### Important Notes

1. **Human Approval is Required** for:
   - All feature branches
   - Any changes that affect functionality
   - Database schema changes
   - Dependency updates
   - Architecture changes

2. **Never bypass review** by:
   - Committing directly to main
   - Merging without approval
   - Skipping documentation updates
   - Ignoring failed tests

3. **AI Assistants should**:
   - Always work on feature branches for new work
   - Ask for human review before merging
   - Proactively update documentation
   - Clearly communicate what needs review

4. **Merge Conflicts**:
   - If conflicts occur, rebase on main
   - Test thoroughly after resolving
   - Ask for help if unsure

---

## 🧪 Testing Standards

### Always Write Tests For:
1. New scrapers
2. Validation logic changes
3. Database operations
4. API endpoints

### Test Structure:
```python
# tests/test_newchain.py
import pytest
from src.scrapers.newchain import NewChainScraper

def test_scraper_returns_stores():
    scraper = NewChainScraper()
    stores = scraper.scrape()

    assert len(stores) > 0
    assert all(store.chain_id == 'newchain' for store in stores)

def test_stores_have_required_fields():
    scraper = NewChainScraper()
    stores = scraper.scrape()

    for store in stores:
        assert store.name
        assert store.street
        assert store.city
        assert store.postal_code
```

### Run Tests:
```bash
# All tests
pytest tests/

# With coverage
pytest --cov=src tests/

# Specific test
pytest tests/test_newchain.py -v
```

---

## 🚨 Common Pitfalls to Avoid

### 1. DON'T Bypass Validation
```python
# Bad - skips validation
store.latitude = some_coordinate
db.save_stores([store])

# Good - validation happens in scraper
class MyScraper(BaseScraper):
    def scrape(self):
        # Validation automatic via base class
        return stores
```

### 2. DON'T Use print() Statements
```python
# Bad
print("Starting scrape...")

# Good
logger.info("Starting scrape...")
```

### 3. DON'T Hardcode Chain Logic
```python
# Bad
if chain_id == 'denns':
    scraper = DennsScraper()
elif chain_id == 'alnatura':
    scraper = AlnaturaScraper()

# Good - use dynamic loading
scraper = get_scraper_for_chain(chain_id)
```

### 4. DON'T Ignore Rate Limits
```python
# Bad
for i in range(1000):
    geocode(address)  # Will get rate limited!

# Good
for i in range(1000):
    geocode(address)  # Has built-in delay
```

### 5. DON'T Mix Coordinate Formats
```python
# Always use decimal degrees
# Good: 52.520008, 13.404954
# Bad: 52°31'12.0"N, 13°24'17.8"E
```

---

## 🔍 Debugging Tips

### Enable Debug Logging
```python
# In .env
LOG_LEVEL=DEBUG

# Or temporarily in code
logging.basicConfig(level=logging.DEBUG)
```

### Check Database Contents
```bash
sqlite3 data/stores.db
> SELECT COUNT(*) FROM stores WHERE chain_id = 'tegut';
> SELECT name, city, latitude, longitude FROM stores LIMIT 5;
> .quit
```

### Test Single Chain
```python
# Modify scripts/update_stores.py temporarily
active_chains = [c for c in chains if c['id'] == 'tegut']
```

### Validate Coordinates Manually
```python
from src.geocoding.validator import CoordinateValidator

validator = CoordinateValidator()
result = validator.validate_coordinates(
    latitude=52.520008,
    longitude=13.404954,
    street="Unter den Linden 1",
    postal_code="10117",
    city="Berlin",
    country_code="DE"
)
print(result)
```

---

## 📚 Important Conventions

### Naming
- **Chain IDs:** lowercase, no spaces (e.g., `biocompany`, not `Bio Company`)
- **Store IDs:** Use original ID from source, string type
- **Classes:** PascalCase (e.g., `DennsScraper`)
- **Functions:** snake_case (e.g., `get_store_details`)
- **Files:** snake_case (e.g., `update_stores.py`)

### Coordinate Format
- **Always:** Decimal degrees (52.520008, 13.404954)
- **Never:** DMS format or other projections
- **Order:** latitude, longitude (not lon, lat!)

### Database IDs
- **Format:** `{chain_id}_{store_id}`
- **Example:** `denns_12345`, `tegut_berlin-mitte`
- **Purpose:** Globally unique across all chains

### File Organization
- **Scrapers:** One file per chain in `src/scrapers/`
- **Tests:** Mirror structure in `tests/`
- **Config:** Keep in `config/` directory
- **Data:** Never commit to git (in `.gitignore`)

---

## 🎯 When Unsure, Follow This Checklist

Before making changes:
- [ ] Am I on a feature branch (not main)?
- [ ] Does this follow the existing patterns?
- [ ] Am I using proper logging (not print)?
- [ ] Are all functions type-hinted?
- [ ] Did I update relevant config files?
- [ ] Will this break existing scrapers?
- [ ] Are coordinates in decimal degrees?
- [ ] Did I test locally?
- [ ] Should I update documentation?

After making changes:
- [ ] Run tests: `pytest tests/`
- [ ] Check linting: `ruff check src/`
- [ ] Check types: `mypy src/`
- [ ] Test scraping: `python scripts/update_stores.py`
- [ ] Check git status: `git status`
- [ ] Update README.md if user-facing changes
- [ ] Update QUICK_START.md if workflow changed
- [ ] Update requirements.txt if dependencies changed
- [ ] Update ROADMAP.md (mark completed items)
- [ ] Update AI_ASSISTANT_GUIDE.md if patterns changed

Before merging to main:
- [ ] All documentation updated (see checklist above)
- [ ] All tests passing
- [ ] Code quality checks passing
- [ ] Pull request created
- [ ] Human approval received
- [ ] No merge conflicts

---

## 📖 Additional Resources

### Key Dependencies Documentation
- **SQLAlchemy:** https://docs.sqlalchemy.org/
- **BeautifulSoup:** https://www.crummy.com/software/BeautifulSoup/
- **geopy:** https://geopy.readthedocs.io/
- **Leaflet.js:** https://leafletjs.com/

### Rate Limits to Remember
- **Nominatim:** 1 request/second (configurable in .env)
- **No API key required** for OSM Nominatim

### Coordinate Boundaries (Germany)
- **Latitude:** 47.27 to 55.06
- **Longitude:** 5.87 to 15.04

---

## 🤖 AI Assistant Self-Check

At the start of each session, ask yourself:

1. ✅ Have I read this guide completely?
2. ✅ Do I understand the BaseScraper pattern?
3. ✅ Do I know where chains are configured?
4. ✅ Will I use logging instead of print()?
5. ✅ Do I understand the validation flow?
6. ✅ Have I checked ROADMAP.md for context?
7. ✅ Do I know the feature branch workflow?
8. ✅ Will I update documentation before merging?
9. ✅ Do I know I need human approval before merging to main?

If any answer is "no", reread the relevant section above.

### Before Starting New Work:

**Question to ask the human:**
> "I'm about to work on [feature/fix/refactoring]. Should I create a feature branch, or is this small enough for direct commit to main?"

**Default answer (if unsure):** Create a feature branch.

**After completing work:**
> "I've completed [feature] on branch [branch-name]. I've updated [list of documentation files]. Ready for your review - would you like me to create a pull request?"

---

## 📝 Keeping This Guide Updated

**When to update this guide:**
- Major architectural changes
- New patterns established
- Common mistakes discovered
- Dependencies changed significantly

**How to update:**
- Keep examples current
- Remove outdated information
- Add new common tasks
- Update version numbers

---

**Document Version:** 1.0
**Last Updated:** 2025-10-21
**Project Version:** v0.3.0

---

## 💬 Quick Reference Commands

```bash
# Setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Development
python scripts/update_stores.py        # Update all chains
python api/server.py                   # Start API server
cd frontend && python -m http.server   # View map locally

# Testing
pytest tests/                          # Run all tests
pytest --cov=src tests/                # With coverage
ruff check src/                        # Lint code
mypy src/                              # Type check

# Database
sqlite3 data/stores.db                 # Open database
python api/export_geojson.py           # Generate GeoJSON

# Git
git status                             # Check changes
git add -A                             # Stage all
git commit -m "message"                # Commit
git push origin main                   # Push to GitHub
```

---

**Remember:** When in doubt, look at existing implementations (especially `denns.py` and `tegut.py`) as reference examples. They follow all best practices established in this guide.
