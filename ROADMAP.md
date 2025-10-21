# SOTO Store Finder - Roadmap & Next Steps

This document tracks potential improvements, features, and refactoring opportunities for the SOTO Store Finder project.

## 🎯 Current Status (as of 2025-10-21)

- **Implemented Chains:** 3 (denn's, Alnatura, tegut)
- **Total Stores:** 1,054 validated locations
- **Architecture:** Clean, modular, config-driven
- **Deployment:** Automated via GitHub Pages

---

## 🚀 High Priority

### 1. Add Remaining Chains
**Effort:** Medium | **Impact:** High

Implement scrapers for the remaining chains defined in `config/chains.json`:

- [ ] **Bio Company** (biocompany.de)
  - Estimated stores: ~50-70
  - Website structure needs analysis
  - Create `src/scrapers/biocompany.py`

- [ ] **Vollcorner** (vollcorner.de)
  - Estimated stores: ~30-40
  - Create `src/scrapers/vollcorner.py`

- [ ] **Globus** (globus.de)
  - Large chain, ~50+ stores
  - May have structured data API
  - Create `src/scrapers/globus.py`

**Steps:**
1. Analyze website structure for each chain
2. Identify data source (API vs scraping)
3. Implement scraper following BaseScraper pattern
4. Add to scraper_map in `scripts/update_stores.py`
5. Test with `validate_coordinates=True`
6. Update README with new chain counts

### 2. Improve Test Coverage
**Effort:** Medium | **Impact:** Medium

Current test coverage is incomplete. Add comprehensive tests:

- [ ] **Integration Tests**
  - Full scrape → validate → save → export pipeline
  - Test file: `tests/test_integration.py`
  - Mock external API calls

- [ ] **API Tests**
  - Test both `/api/stores` and `/api/stores/geojson` endpoints
  - Test file: `tests/test_api.py`
  - Verify JSON structure and field presence

- [ ] **Chain Config Tests**
  - Test `load_chains_config()` function
  - Test `get_scraper_for_chain()` dynamic loading
  - Test file: `tests/test_config.py`

- [ ] **Increase Coverage to 80%+**
  ```bash
  pytest --cov=src --cov-report=html tests/
  ```

### 3. Add Async Scraping
**Effort:** High | **Impact:** High

Current scraping is sequential. For 1,000+ stores, this is slow.

- [ ] **Refactor to AsyncIO**
  - Convert BaseScraper to use `async def scrape()`
  - Use `aiohttp` instead of `requests`
  - Batch geocoding requests
  - Expected speedup: 5-10x

- [ ] **Rate Limiting**
  - Implement `asyncio.Semaphore` for Nominatim (1 req/sec)
  - Add configurable concurrency limits
  - Update `.env.example` with `MAX_CONCURRENT_REQUESTS`

**Technical approach:**
```python
import asyncio
import aiohttp

class BaseScraper(ABC):
    @abstractmethod
    async def scrape(self) -> List[Store]:
        pass
```

---

## 💡 Medium Priority

### 4. Add Database Migrations
**Effort:** Medium | **Impact:** Medium

Currently using SQLAlchemy without Alembic migrations.

- [ ] **Setup Alembic**
  ```bash
  pip install alembic
  alembic init alembic
  ```

- [ ] **Create Initial Migration**
  - Capture current schema
  - Version control database changes

- [ ] **Add to README**
  - Document migration workflow
  - Add to deployment process

### 5. Implement Pydantic for Validation
**Effort:** Medium | **Impact:** Medium

Replace dataclasses with Pydantic models for runtime validation.

- [ ] **Convert Store Dataclass**
  ```python
  from pydantic import BaseModel, validator

  class Store(BaseModel):
      chain_id: str
      latitude: float
      longitude: float

      @validator('latitude')
      def validate_lat(cls, v):
          if not -90 <= v <= 90:
              raise ValueError('Invalid latitude')
          return v
  ```

- [ ] **Add API Request/Response Models**
- [ ] **Update requirements.txt**: `pydantic>=2.0.0`

### 6. Enhanced Error Handling
**Effort:** Low | **Impact:** Medium

Improve error handling and recovery.

- [ ] **Retry Logic for Scrapers**
  - Use `tenacity` library
  - Exponential backoff for network errors
  - Max 3 retries per store

- [ ] **Circuit Breaker Pattern**
  - Stop scraping if too many failures
  - Alert/log when circuit opens

- [ ] **Graceful Degradation**
  - Continue with other chains if one fails
  - Save partial results

### 7. Store Change Detection
**Effort:** Medium | **Impact:** Low

Track which stores are new, updated, or closed.

- [ ] **Add Change Tracking**
  - Detect new stores (not in DB)
  - Detect closed stores (in DB but not scraped)
  - Detect coordinate/address changes

- [ ] **Generate Change Report**
  - Summary email/log after each update
  - "3 new stores, 1 closed, 5 updated"

- [ ] **Store History Table**
  - Track historical changes
  - `store_history` table with timestamps

---

## 🔧 Low Priority / Nice to Have

### 8. Frontend Improvements
**Effort:** Medium | **Impact:** Low

- [ ] **Filter by Chain**
  - Toggle visibility of each chain
  - Update map dynamically

- [ ] **Search Functionality**
  - Search by city, postal code, or store name
  - Auto-zoom to results

- [ ] **Store Details Panel**
  - Click marker → show full info
  - Opening hours, services, phone

- [ ] **Mobile Optimization**
  - Responsive design improvements
  - Touch-friendly controls

### 9. Scheduled Updates
**Effort:** Low | **Impact:** Low

- [ ] **GitHub Actions Scheduled Run**
  - Weekly cron job
  - Run `scripts/update_stores.py`
  - Auto-commit and push changes

- [ ] **Monitoring & Alerts**
  - Email on scraping failures
  - Slack webhook integration

### 10. Performance Optimization
**Effort:** Medium | **Impact:** Low

- [ ] **Database Indexing Review**
  - Analyze query patterns
  - Add composite indexes if needed

- [ ] **GeoJSON Caching**
  - Cache generated GeoJSON
  - Only regenerate on data changes

- [ ] **API Optimization**
  - Add ETag support
  - Implement response compression

### 11. Advanced Geocoding
**Effort:** High | **Impact:** Low

- [ ] **Multiple Geocoding Services**
  - Fallback to Google/Mapbox if OSM fails
  - Configurable provider priority

- [ ] **Geocoding Cache**
  - Cache address → coordinates mapping
  - Reduce API calls for unchanged stores

### 12. Analytics & Insights
**Effort:** Medium | **Impact:** Low

- [ ] **Store Distribution Analysis**
  - Heat map of store density
  - Charts by region/city

- [ ] **Coverage Metrics**
  - How many cities have SOTO products?
  - Gap analysis for underserved areas

---

## 🏗️ Technical Debt

### Items to Monitor/Refactor Later

1. **Type Hints Completeness**
   - Some functions still missing full type annotations
   - Goal: 100% mypy compliance

2. **Error Messages**
   - Standardize error message format
   - Add error codes for easier debugging

3. **Configuration Management**
   - Consider moving from `.env` to `config.yaml`
   - More structured configuration

4. **Documentation**
   - Add docstring examples for all public methods
   - Generate API docs with Sphinx

---

## 📊 Success Metrics

Track these metrics as the project grows:

- **Code Coverage:** Target 80%+
- **Scraping Success Rate:** Target 95%+
- **Geocoding Accuracy:** Target 98%+
- **Total Stores:** Goal 2,000+
- **Update Frequency:** Weekly minimum
- **Response Time:** API < 500ms

---

## 🤝 Contributing Guidelines

When implementing items from this roadmap:

1. **Create feature branch**
   ```bash
   git checkout -b feature/add-biocompany-scraper
   ```

2. **Follow existing patterns**
   - Use BaseScraper for new chains
   - Add proper logging (not print statements)
   - Include type hints
   - Write tests

3. **Update documentation**
   - Update README.md if adding features
   - Update this ROADMAP.md (mark completed items)
   - Add docstrings to new code

4. **Test thoroughly**
   ```bash
   pytest tests/
   ruff check src/
   mypy src/
   ```

5. **Update config**
   - Add new chains to `config/chains.json`
   - Update `.env.example` for new settings

6. **Create descriptive commits**
   - Follow conventional commit format
   - Reference issue numbers if applicable

---

## 📝 Notes

- Items marked with [ ] are not yet started
- Items marked with [x] are completed
- Effort: Low (< 1 day), Medium (1-3 days), High (> 3 days)
- Impact: High (critical features), Medium (nice to have), Low (polish)

---

**Last Updated:** 2025-10-21
**Next Review:** When starting new major feature
