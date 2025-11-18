# REWE SOTO Scraper

## Quick Start

```bash
# Install dependencies
pip install curl_cffi

# Run scraper for all configured stores
python scripts/rewe_curl_scraper.py

# Results saved to: data/rewe_soto_availability_latest.json
```

## Features

- ✅ Cloudflare-Bypass mit curl_cffi
- ✅ Filialspezifische Verfügbarkeitsprüfung
- ✅ Automatische Market-Selektion via PLZ
- ✅ JSON-Export der Ergebnisse

## Tested Stores (November 2025)

| Store | City | Available |
|-------|------|-----------|
| REWE Karsten Schmidt oHG | Berlin | ✅ 2 products |
| REWE Korbinian Röckenschuß oHG | München | ✅ 2 products |
| REWE Stanisic oHG | Freising | ✅ 5 products |
| REWE Markt GmbH | Stuttgart | ❌ No products |
| REWE Markt GmbH | Tübingen | ❌ No products |

## Documentation

See: [docs/REWE_SCRAPER_DOCUMENTATION.md](../docs/REWE_SCRAPER_DOCUMENTATION.md)

## Architecture

```
Count API (filialspezifisch)
  ↑
Market Selection API
  ↑
Market Search API (PLZ → Market ID)
```

## Performance

- **~4 seconds per store**
- **80% accuracy** (4/5 stores exact match)
- **3 API calls per store**

## Limitations

- Count API only (no product details)
- No brand filtering (counts all "SOTO" search results)
- No prices available
