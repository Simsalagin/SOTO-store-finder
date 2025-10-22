# Quick Start Guide

**For AI Assistants:** Start here, then read [AI_ASSISTANT_GUIDE.md](AI_ASSISTANT_GUIDE.md) for complete details.

**For Humans:** This is your 5-minute project overview.

---

## 🚀 What This Project Does

**SOTO Store Finder** automatically finds all German supermarkets that sell SOTO products.

**How it works:**
1. **Scrapes** store data from supermarket websites
2. **Validates** coordinates using OpenStreetMap
3. **Stores** in SQLite database
4. **Shows** on interactive map at https://simsalagin.github.io/SOTO-store-finder/

**Current status:** 1,054 stores across 3 chains (denn's, Alnatura, tegut)

---

## 📁 Project Layout (30 Seconds)

```
src/scrapers/     → Get store data (one file per chain)
src/geocoding/    → Validate coordinates
src/storage/      → Save to database
scripts/          → Main update script
config/           → Chain configuration (chains.json)
frontend/         → Interactive map
api/              → REST API server
```

---

## 🔧 Common Commands

```bash
# Setup (first time)
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Update all stores
python scripts/update_stores.py

# Start API server
python api/server.py

# View map locally
cd frontend && python -m http.server 8000

# Run tests
pytest tests/

# Check code quality
ruff check src/
mypy src/
```

---

## ➕ Adding a New Chain (5 Minutes)

1. **Add to config/chains.json:**
   ```json
   {"id": "newchain", "name": "New Chain", "active": true, "priority": 7}
   ```

2. **Create src/scrapers/newchain.py:**
   ```python
   from .base import BaseScraper, Store

   class NewChainScraper(BaseScraper):
       def __init__(self):
           super().__init__(chain_id="newchain", chain_name="New Chain")

       def scrape(self):
           # Your scraping logic here
           return stores
   ```

3. **Register in scripts/update_stores.py:**
   ```python
   scraper_map = {
       'newchain': 'src.scrapers.newchain.NewChainScraper',
   }
   ```

4. **Create marker icon (frontend/images/newchain-marker.svg):**
   ```xml
   <svg width="40" height="50" xmlns="http://www.w3.org/2000/svg">
     <path d="M20 0 C8.954 0 0 8.954 0 20 C0 28 8 38 20 50 C32 38 40 28 40 20 C40 8.954 31.046 0 20 0 Z"
           fill="#YOUR_BRAND_COLOR" stroke="#DARKER_SHADE" stroke-width="2"/>
     <circle cx="20" cy="18" r="12" fill="white"/>
     <circle cx="20" cy="18" r="10" fill="#YOUR_BRAND_COLOR"/>
     <text x="20" y="23" font-family="Arial, sans-serif" font-size="14" font-weight="bold"
           fill="white" text-anchor="middle">N</text>
   </svg>
   ```
   **Color guide:** denn's=#8BC34A, Alnatura=#FF9800, tegut=#E53935, VollCorner=#00A0B0

5. **Integrate marker in frontend/index.html:**
   - Add icon definition (around line 364)
   - Update `getChainIcon()` switch case

6. **Test:**
   ```bash
   python scripts/update_stores.py
   python api/export_geojson.py
   cd frontend && python -m http.server 8000
   ```

---

## 🎯 Key Principles (Remember These!)

1. **Inherit from BaseScraper** - It handles validation automatically
2. **Use logger, not print()** - Professional logging only
3. **Type hints everywhere** - Help IDE and catch bugs
4. **Config-driven** - Don't hardcode chain logic
5. **Test before commit** - Always run pytest

---

## 📖 Important Files

| File | Purpose | When to Edit |
|------|---------|--------------|
| `config/chains.json` | Define all chains | Adding/removing chains |
| `scripts/update_stores.py` | Main orchestrator | Adding new scraper |
| `src/scrapers/base.py` | Base class | Changing validation logic |
| `src/storage/database.py` | Database schema | Schema changes |
| `AI_ASSISTANT_GUIDE.md` | Full documentation | Start of each session |
| `ROADMAP.md` | Future features | Planning next work |

---

## 🚨 Don't Do These Things

❌ Use `print()` statements (use `logger.info()` instead)
❌ Bypass coordinate validation
❌ Hardcode chain logic (use config)
❌ Commit temporary files (.csv, .html, .db)
❌ Use coordinates in DMS format (always decimal degrees)
❌ Ignore rate limits (especially OpenStreetMap)

---

## 🐛 Quick Troubleshooting

**Problem:** Geocoding timeout
**Solution:** Increase `GEOCODING_DELAY` in `.env` to 2.0

**Problem:** Import error for new scraper
**Solution:** Check scraper registered in `scraper_map`

**Problem:** Invalid coordinates
**Solution:** Validator fixes automatically, check logs

**Problem:** Tests failing
**Solution:** Run `pytest -v` to see specific failures

---

## 📚 Full Documentation

- **[AI_ASSISTANT_GUIDE.md](AI_ASSISTANT_GUIDE.md)** - Complete guide for AI assistants (READ THIS FIRST!)
- **[ROADMAP.md](ROADMAP.md)** - Future features and improvements
- **[README.md](README.md)** - User documentation and installation
- **`.claude/session-summary.md`** - Latest refactoring session notes

---

## 🤖 For AI Assistants

**On session start, always:**
1. Read [AI_ASSISTANT_GUIDE.md](AI_ASSISTANT_GUIDE.md) completely
2. Check [ROADMAP.md](ROADMAP.md) for current priorities
3. Review `.claude/session-summary.md` for recent changes
4. Follow established patterns in existing scrapers

**Before making changes:**
- ✅ Understand the BaseScraper pattern
- ✅ Know where to update config (chains.json)
- ✅ Use logging (never print)
- ✅ Add type hints
- ✅ Write/update tests

**After making changes:**
```bash
pytest tests/              # Run tests
ruff check src/            # Lint
mypy src/                  # Type check
python scripts/update_stores.py  # Integration test
```

---

## 📊 Project Status Dashboard

**Current State (2025-10-21):**
- 🟢 Chains implemented: 3 (denn's, Alnatura, tegut)
- 🟢 Total stores: 1,054
- 🟢 Architecture: Clean, modular, config-driven
- 🟢 Tests: Basic coverage (needs improvement)
- 🟢 Documentation: Excellent
- 🟢 Code quality: High (latest best practices)

**Next Priorities (from ROADMAP.md):**
1. Add Bio Company scraper
2. Improve test coverage to 80%+
3. Implement async scraping

---

## 💡 Pro Tips

1. **Look at existing code first** - `denns.py` and `tegut.py` are great examples
2. **Use logger.debug()** - Makes debugging easier later
3. **Test small** - Test individual scrapers before full run
4. **Check database** - `sqlite3 data/stores.db` to verify results
5. **Read the logs** - They tell you what went wrong

---

## 🎓 Learning Path

**New to project?** Read in this order:
1. This file (QUICK_START.md) ← You are here
2. [AI_ASSISTANT_GUIDE.md](AI_ASSISTANT_GUIDE.md) - Deep dive
3. `src/scrapers/base.py` - Understand the foundation
4. `src/scrapers/denns.py` - Simple example
5. `src/scrapers/tegut.py` - Complex example

**Ready to code?**
- Pick a task from [ROADMAP.md](ROADMAP.md)
- Follow patterns from existing code
- Test thoroughly
- Update documentation

---

## 📞 Need Help?

1. **Check logs:** `logs/store_finder.log`
2. **Debug mode:** Set `LOG_LEVEL=DEBUG` in `.env`
3. **Read documentation:** All answers in `AI_ASSISTANT_GUIDE.md`
4. **Look at examples:** Working code is the best documentation

---

**Updated:** 2025-10-21
**Version:** v0.3.0
**Status:** Production Ready ✅

---

🎯 **Remember:** When in doubt, follow existing patterns. The codebase is consistent - use it as your guide!
