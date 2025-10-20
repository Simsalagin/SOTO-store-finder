# SOTO Store Finder

Ein automatisiertes System zum Scrapen, Validieren und Visualisieren von Filialstandorten für Produkte der Marke SOTO.

## 🎯 Projektziel

Entwicklung einer interaktiven Karte, die alle Filialen anzeigt, in denen SOTO-Produkte erhältlich sind. Das System scrapt automatisch Standortdaten von verschiedenen (Bio-)Supermarktketten und validiert diese mithilfe von OpenStreetMap.

## 📊 Status

**MVP abgeschlossen** - denn's Biomarkt Integration
- ✅ 590 denn's Biomarkt Filialen in Deutschland
- ✅ Automatische Koordinaten-Validierung
- ✅ Interaktive Karte mit Leaflet.js
- ✅ SQLite-Datenbank

**In Planung:**
- Alnatura
- tegut
- Bio Company
- Vollcorner
- Globus
- REWE (mit Produktverfügbarkeits-Check)

## 🏗️ Projektstruktur

```
SOTO-store-finder/
├── config/                 # Konfigurationsdateien
│   └── chains.json        # Definition der Supermarktketten
├── data/                   # Datenbank und Cache
│   └── stores.db          # SQLite Datenbank
├── frontend/               # Web-Visualisierung
│   ├── index.html         # Interaktive Karte
│   └── stores.geojson     # GeoJSON Export
├── logs/                   # Log-Dateien
├── scripts/                # Utility-Scripts
│   ├── update_stores.py   # Haupt-Update-Script
│   └── fix_coordinates.py # Koordinaten-Reparatur
├── src/                    # Source Code
│   ├── scrapers/          # Scraper für verschiedene Ketten
│   │   ├── base.py        # Basis-Scraper-Klasse
│   │   └── denns.py       # denn's Biomarkt Scraper
│   ├── geocoding/         # Geocoding & Validierung
│   │   ├── geocoder.py    # OpenStreetMap Geocoding
│   │   └── validator.py   # Koordinaten-Validierung
│   ├── storage/           # Datenbank-Layer
│   │   └── database.py    # SQLite ORM
│   └── export/            # Export-Funktionen
│       └── geojson.py     # GeoJSON Export
├── tests/                  # Test-Scripts
│   ├── test_denns.py      # denn's Scraper Tests
│   └── test_validation.py # Validierungs-Tests
├── requirements.txt        # Python Dependencies
├── .env.example           # Umgebungsvariablen Template
└── README.md              # Diese Datei
```

## 🚀 Installation

### Voraussetzungen
- Python 3.11+
- Git

### Setup

1. **Repository klonen**
```bash
git clone <repository-url>
cd SOTO-store-finder
```

2. **Virtual Environment erstellen**
```bash
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# oder
venv\Scripts\activate     # Windows
```

3. **Dependencies installieren**
```bash
pip install -r requirements.txt
```

4. **Umgebungsvariablen konfigurieren**
```bash
cp .env.example .env
# .env bei Bedarf anpassen
```

## 📖 Verwendung

### Stores aktualisieren

```bash
source venv/bin/activate
python scripts/update_stores.py
```

Dieser Befehl:
- Scrapt alle konfigurierten Ketten
- Validiert automatisch alle Koordinaten
- Speichert Daten in SQLite
- Loggt alle Aktivitäten

### Karte anzeigen

```bash
cd frontend
python -m http.server 8000
```

Öffne im Browser: http://localhost:8000

### GeoJSON neu generieren

```python
from src.storage.database import Database
from src.export.geojson import GeoJSONExporter

db = Database()
exporter = GeoJSONExporter(db)
exporter.export_stores(chain_id='denns', output_file='frontend/stores.geojson')
```

## 🔍 Koordinaten-Validierung

Das System validiert automatisch alle Koordinaten durch:

### 1. Null-Punkt Check
Erkennt (0,0) Koordinaten ("Null Island")

### 2. Ländergrenzen-Prüfung
Stellt sicher, dass Koordinaten in Deutschland liegen

### 3. Reverse Geocoding
Fragt OpenStreetMap nach der Adresse an den Koordinaten

### 4. Plausibilitätsprüfung
- Vergleicht Postleitzahl
- Vergleicht Stadt
- Berechnet Distanz (max. 50km erlaubt)

### 5. Automatische Korrektur
Bei ungültigen Koordinaten wird die Adresse neu geocoded

### Beispiel

```python
from src.geocoding.validator import CoordinateValidator

validator = CoordinateValidator()
result = validator.validate_coordinates(
    latitude=52.587174,
    longitude=13.389093,
    street='Friedrich-Engels-Str. 92',
    postal_code='13156',
    city='Berlin',
    country_code='DE'
)

print(f"Valid: {result['valid']}")
print(f"Confidence: {result['confidence']}")
print(f"Issues: {result['issues']}")
```

## 🗺️ Datenquellen

### denn's Biomarkt
- **Quelle:** https://www.biomarkt.de/page-data/marktindex/page-data.json
- **Typ:** JSON API
- **Daten:** 590 Filialen in Deutschland
- **Verfügbare Infos:** Adresse, Koordinaten, Öffnungszeiten, Services, Telefon

### Geocoding/Validierung
- **Service:** OpenStreetMap Nominatim
- **Rate Limit:** 1 Request/Sekunde
- **Kostenlos:** Ja
- **User Agent:** Konfigurierbar via .env

## 📊 Datenbank-Schema

```sql
CREATE TABLE stores (
    id TEXT PRIMARY KEY,              -- Format: {chain_id}_{store_id}
    chain_id TEXT NOT NULL,           -- z.B. 'denns'
    store_id TEXT NOT NULL,           -- Original-ID der Kette
    name TEXT NOT NULL,
    street TEXT NOT NULL,
    postal_code TEXT NOT NULL,
    city TEXT NOT NULL,
    country_code TEXT NOT NULL,
    latitude REAL,
    longitude REAL,
    phone TEXT,
    email TEXT,
    website TEXT,
    opening_hours JSON,               -- Öffnungszeiten als JSON
    services JSON,                    -- Services als JSON Array
    scraped_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    is_active TEXT DEFAULT 'true'     -- 'true', 'false', 'closed'
);
```

## 🔄 Workflow

### Manuelles Update

```bash
# 1. Stores scrapen und validieren
python scripts/update_stores.py

# 2. GeoJSON exportieren
python -c "
from src.storage.database import Database
from src.export.geojson import GeoJSONExporter
db = Database()
exporter = GeoJSONExporter(db)
exporter.export_stores(output_file='frontend/stores.geojson')
"

# 3. Karte im Browser öffnen
cd frontend && python -m http.server 8000
```

### Automatisiertes Update (geplant)

Zukünftig via Cron/Scheduler:
- Wöchentlich: Alle Stores aktualisieren
- Change Detection: Neue/geschlossene Filialen erkennen
- Export: Automatischer GeoJSON-Export

## 🛠️ Entwicklung

### Neue Kette hinzufügen

1. **Konfiguration in `config/chains.json`**
```json
{
  "id": "neue_kette",
  "name": "Neue Kette",
  "website": "https://example.com",
  "scraper_type": "all_stores",
  "active": true
}
```

2. **Scraper implementieren in `src/scrapers/neue_kette.py`**
```python
from .base import BaseScraper, Store

class NeueKetteScraper(BaseScraper):
    def __init__(self):
        super().__init__(chain_id="neue_kette", chain_name="Neue Kette")

    def scrape(self) -> List[Store]:
        # Implementierung
        pass
```

3. **In `scripts/update_stores.py` registrieren**

### Tests ausführen

```bash
# Alle Tests
pytest tests/

# Einzelner Test
python tests/test_denns.py

# Validierung testen
python tests/test_validation.py
```

### Logging

Logs werden in `logs/store_finder.log` gespeichert.

Level anpassen in `.env`:
```
LOG_LEVEL=DEBUG
```

## 📝 Best Practices

### Geocoding Rate Limits
- OpenStreetMap Nominatim: Max. 1 Request/Sekunde
- Delay ist konfigurierbar (siehe `.env`)
- Bei großen Updates: Geduld haben!

### Koordinaten-Validierung
- Immer aktiviert beim Scraping
- Kann für Tests deaktiviert werden: `validate_coordinates=False`
- Logs zeigen alle Korrekturen

### Datenbank-Updates
- Stores werden per ID aktualisiert (upsert)
- `updated_at` wird automatisch gesetzt
- Alte Stores bleiben erhalten (für Change Detection)

## 🐛 Troubleshooting

### Geocoding schlägt fehl
```
Error: GeocoderTimedOut
```
**Lösung:** Erhöhe `GEOCODING_DELAY` in `.env` auf 2.0

### Koordinaten sind (0, 0)
**Automatisch gelöst:** Validator erkennt und korrigiert dies

### Karte zeigt keine Marker
1. GeoJSON neu generieren
2. Browser-Cache leeren
3. Console auf Fehler prüfen

## 📄 Lizenz

[Lizenz hier einfügen]

## 👥 Kontakt

[Kontakt hier einfügen]

## 🗓️ Changelog

### v0.1.0 - MVP (2025-10-20)
- ✅ denn's Biomarkt Scraper
- ✅ Koordinaten-Validierung via OSM
- ✅ SQLite Datenbank
- ✅ GeoJSON Export
- ✅ Interaktive Leaflet-Karte
- ✅ 590 validierte Filialen
