# SOTO Store Finder

Ein automatisiertes System zum Scrapen, Validieren und Visualisieren von Filialstandorten für Produkte der Marke SOTO.

## 🎯 Projektziel

Entwicklung einer interaktiven Karte, die alle Filialen anzeigt, in denen SOTO-Produkte erhältlich sind. Das System scrapt automatisch Standortdaten von verschiedenen (Bio-)Supermarktketten und validiert diese mithilfe von OpenStreetMap.

## 📊 Status

**Implementierte Ketten:**
- ✅ **denn's Biomarkt** - 590 Filialen
- ✅ **Alnatura** - 150 Filialen
- ✅ **tegut** - 314 Filialen
- ✅ **VollCorner** - 21 Filialen

**Total: 1,075 validierte Filialen**

**In Entwicklung:**
- 🔄 Bio Company
- 🔄 Globus

**Features:**
- ✅ Automatische Koordinaten-Validierung
- ✅ Interaktive Karte mit Leaflet.js
- ✅ SQLite-Datenbank mit ORM
- ✅ REST API Server
- ✅ GeoJSON Export
- ✅ Konfigurationsbasiertes Chain-Management
- ✅ GitHub Pages Deployment
- ✅ **Automatische Standorterkennung** - Karte zoomt automatisch zum Nutzerstandort

## 🏗️ Projektstruktur

```
SOTO-store-finder/
├── .github/workflows/
│   └── deploy.yml          # GitHub Pages CI/CD
├── api/                     # REST API Server
│   ├── server.py           # HTTP Server für Store-Daten
│   └── export_geojson.py   # GeoJSON Export-Utility
├── config/                  # Konfigurationsdateien
│   └── chains.json         # Definition der Supermarktketten
├── data/                    # Datenbank und Cache
│   └── stores.db           # SQLite Datenbank
├── frontend/                # Web-Visualisierung
│   ├── .nojekyll           # GitHub Pages Config
│   ├── index.html          # Interaktive Karte
│   ├── stores.geojson      # GeoJSON Export
│   └── images/             # Logos und Marker-Icons
├── logs/                    # Log-Dateien
├── scripts/                 # Utility-Scripts
│   ├── update_stores.py    # Haupt-Update-Script
│   └── fix_coordinates.py  # Koordinaten-Reparatur
├── src/                     # Source Code
│   ├── scrapers/           # Scraper für verschiedene Ketten
│   │   ├── base.py         # Basis-Scraper-Klasse
│   │   ├── denns.py        # denn's Biomarkt Scraper
│   │   ├── alnatura.py     # Alnatura Scraper
│   │   └── tegut.py        # tegut Scraper
│   ├── geocoding/          # Geocoding & Validierung
│   │   ├── geocoder.py     # OpenStreetMap Geocoding
│   │   └── validator.py    # Koordinaten-Validierung
│   ├── storage/            # Datenbank-Layer
│   │   └── database.py     # SQLAlchemy ORM
│   └── export/             # Export-Funktionen
│       └── geojson.py      # GeoJSON Export
├── tests/                   # Test-Scripts
│   ├── test_denns.py       # denn's Scraper Tests
│   ├── test_alnatura.py    # Alnatura Scraper Tests
│   └── test_validation.py  # Validierungs-Tests
├── requirements.txt         # Python Dependencies
├── .env.example            # Umgebungsvariablen Template
└── README.md               # Diese Datei
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
- Lädt aktive Ketten aus `config/chains.json`
- Scrapt automatisch alle konfigurierten Ketten
- Validiert automatisch alle Koordinaten
- Speichert Daten in SQLite
- Zeigt detaillierte Statistiken

### API Server starten

```bash
python api/server.py
```

Verfügbare Endpoints:
- `http://localhost:8001/api/stores` - Alle Stores als JSON
- `http://localhost:8001/api/stores/geojson` - GeoJSON Format

### Karte anzeigen

**Lokal:**
```bash
cd frontend
python -m http.server 8000
```
Öffne: http://localhost:8000

**Live:** https://simsalagin.github.io/SOTO-store-finder/

#### 🎯 Automatische Standorterkennung

Die Karte erkennt automatisch deinen Standort und zoomt auf deine Umgebung:

1. **Browser-Geolocation (bevorzugt)**
   - Browser fragt nach Standort-Berechtigung
   - Bei Zustimmung: Präzise Standorterkennung (Zoom Stufe 12)
   - Blauer Marker zeigt "Dein Standort" an
   - Position wird 5 Minuten gecacht

2. **IP-basierte Geolocation (Fallback)**
   - Aktiviert sich automatisch bei abgelehnter Berechtigung
   - Ungefährer Standort auf Stadt-Ebene (Zoom Stufe 10)
   - Keine zusätzlichen Berechtigungen nötig
   - Verwendet ipapi.co Service

3. **Deutschland-Übersicht (Standard)**
   - Zeigt alle Filialen in Deutschland
   - Aktiviert sich wenn beide Methoden fehlschlagen
   - Zoom Stufe 6 mit allen Markern sichtbar

### GeoJSON neu generieren

```python
from src.storage.database import Database
from src.export.geojson import GeoJSONExporter

db = Database()
exporter = GeoJSONExporter(db)
exporter.export_stores(output_file='frontend/stores.geojson')
```

## 🔍 Koordinaten-Validierung

Das System validiert automatisch alle Koordinaten durch:

### 1. Null-Punkt Check
Erkennt (0,0) Koordinaten ("Null Island")

### 2. Ländergrenzen-Prüfung
Stellt sicher, dass Koordinaten in Deutschland liegen (47.27-55.06°N, 5.87-15.04°E)

### 3. Reverse Geocoding
Fragt OpenStreetMap nach der Adresse an den Koordinaten

### 4. Plausibilitätsprüfung
- Vergleicht Postleitzahl
- Vergleicht Stadt (Fuzzy-Matching)
- Berechnet Distanz (max. 50km erlaubt)

### 5. Automatische Korrektur
Bei ungültigen Koordinaten wird die Adresse neu geocoded

## 🗺️ Datenquellen

### denn's Biomarkt
- **Quelle:** JSON API
- **Typ:** Strukturierte Daten
- **Daten:** 590 Filialen
- **Infos:** Adresse, Koordinaten, Öffnungszeiten, Services

### Alnatura
- **Quelle:** Website Scraping
- **Typ:** HTML Parsing
- **Daten:** 150 Filialen

### tegut
- **Quelle:** Website Scraping mit JSON-LD
- **Typ:** HTML + Strukturierte Daten
- **Daten:** 314 Filialen
- **Infos:** Adresse, Koordinaten, Öffnungszeiten

### Geocoding/Validierung
- **Service:** OpenStreetMap Nominatim
- **Rate Limit:** 1 Request/Sekunde
- **Kostenlos:** Ja
- **User Agent:** Konfigurierbar via `.env`

## 📊 Datenbank-Schema

```sql
CREATE TABLE stores (
    id TEXT PRIMARY KEY,              -- Format: {chain_id}_{store_id}
    chain_id TEXT NOT NULL,           -- z.B. 'denns', 'alnatura', 'tegut'
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

**Indizes:**
- `idx_chain_city` - Schnelle Suche nach Kette + Stadt
- `idx_country` - Länderfilterung
- `idx_location` - Geografische Suche

## 🔄 Workflow

### Automatisches Update (empfohlen)

```bash
# Alle aktiven Ketten aktualisieren
python scripts/update_stores.py

# GeoJSON automatisch exportieren
python api/export_geojson.py

# Karte ist live auf GitHub Pages
```

### Manuelles Chain-Management

**Kette aktivieren/deaktivieren** in `config/chains.json`:
```json
{
  "id": "tegut",
  "name": "tegut",
  "active": true,  // <- auf false setzen zum Deaktivieren
  "priority": 3
}
```

### Neue Kette hinzufügen

1. **In `config/chains.json` registrieren:**
```json
{
  "id": "neue_kette",
  "name": "Neue Kette",
  "website": "https://example.com",
  "scraper_type": "all_stores",
  "priority": 7,
  "active": true
}
```

2. **Scraper implementieren in `src/scrapers/neue_kette.py`:**
```python
from .base import BaseScraper, Store

class NeueKetteScraper(BaseScraper):
    def __init__(self):
        super().__init__(chain_id="neue_kette", chain_name="Neue Kette")

    def scrape(self) -> List[Store]:
        # Implementierung hier
        pass
```

3. **In `scripts/update_stores.py` registrieren:**
```python
scraper_map = {
    'neue_kette': 'src.scrapers.neue_kette.NeueKetteScraper',
}
```

4. **Marker-Icon erstellen (`frontend/images/neue_kette-marker.svg`):**
```xml
<svg width="40" height="50" xmlns="http://www.w3.org/2000/svg">
  <!-- Marker pin shape -->
  <path d="M20 0 C8.954 0 0 8.954 0 20 C0 28 8 38 20 50 C32 38 40 28 40 20 C40 8.954 31.046 0 20 0 Z"
        fill="#MARKENFARBE" stroke="#DUNKLERER_TON" stroke-width="2"/>

  <!-- White circle background -->
  <circle cx="20" cy="18" r="12" fill="white"/>

  <!-- Colored inner circle -->
  <circle cx="20" cy="18" r="10" fill="#MARKENFARBE"/>

  <!-- Chain letter -->
  <text x="20" y="23" font-family="Arial, sans-serif" font-size="14" font-weight="bold"
        fill="white" text-anchor="middle">N</text>
</svg>
```

**Farb-Referenzen:**
- denn's: Grün `#8BC34A` / `#689F38`
- Alnatura: Orange `#FF9800` / `#F57C00`
- tegut: Rot `#E53935` / `#C62828`
- VollCorner: Türkis `#00A0B0` / `#006B75`

5. **Marker in Frontend integrieren (`frontend/index.html`):**

a. Icon-Definition hinzufügen (ca. Zeile 364):
```javascript
const neueKetteIcon = L.icon({
    iconUrl: 'images/neue_kette-marker.svg',
    iconSize: [40, 50],
    iconAnchor: [20, 50],
    popupAnchor: [0, -50]
});
```

b. In `getChainIcon()` Funktion eintragen:
```javascript
function getChainIcon(chainId) {
    switch(chainId) {
        case 'denns':
            return dennsIcon;
        case 'alnatura':
            return alnaturaIcon;
        case 'tegut':
            return tegutIcon;
        case 'vollcorner':
            return vollcornerIcon;
        case 'neue_kette':
            return neueKetteIcon;  // HINZUFÜGEN
        default:
            return dennsIcon;
    }
}
```

6. **Testen:**
```bash
python scripts/update_stores.py
python api/export_geojson.py
cd frontend && python -m http.server 8000
```

## 🛠️ Entwicklung

### Tests ausführen

```bash
# Alle Tests
pytest tests/

# Mit Coverage
pytest --cov=src tests/

# Einzelner Test
python tests/test_denns.py
```

### Code Quality

```bash
# Linting mit ruff
ruff check src/

# Type Checking mit mypy
mypy src/
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
- Kann für Tests deaktiviert werden
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
1. GeoJSON neu generieren: `python api/export_geojson.py`
2. Browser-Cache leeren
3. Console auf Fehler prüfen

### Import Error beim Update
**Problem:** Scraper nicht gefunden
**Lösung:** Prüfe, ob der Scraper in `src/scrapers/` existiert und korrekt in `update_stores.py` registriert ist

## 🚀 Deployment

### GitHub Pages (automatisch)

Push auf `main` branch löst automatisch aus:
1. GitHub Actions Workflow
2. Build & Deploy zu GitHub Pages
3. Live unter: https://simsalagin.github.io/SOTO-store-finder/

### Manuelle Aktualisierung

```bash
# 1. Stores aktualisieren
python scripts/update_stores.py

# 2. GeoJSON exportieren
python api/export_geojson.py

# 3. Committen und pushen
git add frontend/stores.geojson data/stores.db
git commit -m "Update store data"
git push origin main
```

## 📦 Dependencies

- **beautifulsoup4** 4.12.3 - HTML Parsing
- **requests** 2.32.3 - HTTP Requests
- **lxml** 5.3.0 - XML/HTML Parser
- **geopy** 2.4.1 - Geocoding
- **sqlalchemy** 2.0.36 - ORM
- **pandas** 2.2.3 - Data Processing
- **pytest** 8.3.4 - Testing
- **ruff** 0.8.4 - Linting
- **mypy** 1.13.0 - Type Checking

## 📄 Lizenz

[Lizenz hier einfügen]

## 👥 Kontakt

[Kontakt hier einfügen]

## 🗓️ Changelog

### v0.3.0 - Refactoring & Best Practices (2025-10-21)
- ♻️ Refactored tegut scraper to use BaseScraper architecture
- 🔧 Made chains.json functional - dynamic scraper loading
- 📝 Standardized logging across all modules
- 📦 Updated dependencies to latest stable versions
- 🔒 Fixed API server schema issues
- 🧹 Cleaned up temporary files and old code
- 📚 Improved .gitignore coverage
- 🚀 Enhanced README with current project state

### v0.2.0 - Multi-Chain Support (2025-10-20)
- ✅ Added Alnatura scraper (150 stores)
- ✅ Added tegut scraper (314 stores)
- ✅ Total: 1,054 stores across 3 chains
- ✅ Added GitHub Pages deployment
- ✅ Added chain-specific logos and markers

### v0.1.0 - MVP (2025-10-20)
- ✅ denn's Biomarkt Scraper
- ✅ Koordinaten-Validierung via OSM
- ✅ SQLite Datenbank
- ✅ GeoJSON Export
- ✅ Interaktive Leaflet-Karte
- ✅ 590 validierte Filialen
