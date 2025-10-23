# Testing Globus Stores on the Map

## Quick Test (After Database Update Completes)

### 1. Export Stores to GeoJSON
```bash
source venv/bin/activate
python api/export_geojson.py
```

This will update `frontend/stores.geojson` with all stores including Globus.

### 2. Start Local Server
```bash
python -m http.server 8000 --directory frontend
```

### 3. Open in Browser
Open: http://localhost:8000

You should now see blue Globus markers (with "G" letter) on the map alongside the other store markers!

## What to Look For

- **Blue markers with "G"**: These are Globus stores
- **Store count**: Should show ~61 Globus stores across Germany
- **Click a marker**: Should show store details in popup (name, address, opening hours)
- **Cluster behavior**: Multiple nearby stores should cluster together

## Troubleshooting

### No Globus markers visible
1. Check browser console for errors (F12)
2. Verify stores.geojson includes Globus stores:
   ```bash
   grep -c '"chain_id": "globus"' frontend/stores.geojson
   ```
3. Check that the marker icon loaded:
   ```bash
   ls -la frontend/images/globus-marker.svg
   ```

### Database check
```bash
sqlite3 data/stores.db "SELECT COUNT(*) FROM stores WHERE chain_id = 'globus';"
```

## Re-running the Scraper

If you need to refresh Globus data:

```bash
source venv/bin/activate

# Update database
python << 'EOF'
import sys
sys.path.insert(0, '/Users/martingugel/Repos/SOTO-store-finder')

from src.scrapers.globus import GlobusScraper
from src.storage.database import Database

scraper = GlobusScraper()
db = Database()

stores = scraper.scrape()
print(f"Scraped {len(stores)} stores")

for store in stores:
    db.add_or_update_store(store)

db.commit()
print("Database updated!")
EOF

# Export to frontend
python api/export_geojson.py
```

## Map Features to Test

1. **Zoom in/out**: Markers should cluster/uncluster appropriately
2. **Click markers**: Store info should display
3. **Filter by chain** (if implemented): Should be able to show/hide Globus stores
4. **Search**: If address search is enabled, try searching for a Globus store city

## Sample Globus Store Locations

- Bobenheim-Roxheim (Rheinland-Pfalz)
- Bochum (Nordrhein-Westfalen)
- Hamburg-Lurup (Hamburg)
- Dresden (Sachsen)
- München area stores
