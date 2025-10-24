#!/bin/bash
# Quick test script for Globus integration

echo "🧪 Testing Globus Integration"
echo "=============================="
echo ""

# Activate venv
source venv/bin/activate

echo "1️⃣ Checking if Globus scraper exists..."
if [ -f "src/scrapers/globus.py" ]; then
    echo "   ✅ Globus scraper found"
else
    echo "   ❌ Globus scraper not found"
    exit 1
fi

echo ""
echo "2️⃣ Checking if Globus marker icon exists..."
if [ -f "frontend/images/globus-marker.svg" ]; then
    echo "   ✅ Globus marker icon found"
else
    echo "   ❌ Globus marker icon not found"
    exit 1
fi

echo ""
echo "3️⃣ Checking if frontend includes Globus icon..."
if grep -q "globusIcon" frontend/index.html; then
    echo "   ✅ Globus icon integrated in frontend"
else
    echo "   ❌ Globus icon not found in frontend"
    exit 1
fi

echo ""
echo "4️⃣ Checking database for Globus stores..."
count=$(sqlite3 data/stores.db "SELECT COUNT(*) FROM stores WHERE chain_id = 'globus';" 2>/dev/null || echo "0")
echo "   📊 Found $count Globus stores in database"

echo ""
echo "5️⃣ Checking GeoJSON for Globus stores..."
if [ -f "frontend/stores.geojson" ]; then
    geojson_count=$(grep -c '"chain_id": "globus"' frontend/stores.geojson 2>/dev/null || echo "0")
    echo "   📊 Found $geojson_count Globus stores in GeoJSON"

    if [ "$geojson_count" -gt "0" ]; then
        echo "   ✅ Globus stores ready for display on map!"
    else
        echo "   ⚠️  No Globus stores in GeoJSON yet - run: python api/export_geojson.py"
    fi
else
    echo "   ⚠️  GeoJSON file not found - run: python api/export_geojson.py"
fi

echo ""
echo "=============================="
echo "📝 Next steps:"
echo ""
echo "If Globus stores are not in the database yet:"
echo "  → Wait for the scraper to finish running"
echo ""
echo "If stores are in database but not in GeoJSON:"
echo "  → Run: python api/export_geojson.py"
echo ""
echo "To view the map:"
echo "  → Run: python -m http.server 8000 --directory frontend"
echo "  → Open: http://localhost:8000"
echo ""
