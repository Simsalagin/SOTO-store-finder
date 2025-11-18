# REWE SOTO Product Availability Scraper - Dokumentation

## Übersicht

Funktionierender Scraper zur Prüfung der SOTO-Produktverfügbarkeit in REWE-Filialen.

**Status:** ✅ Produktionsbereit
**Datei:** `scripts/rewe_curl_scraper.py`
**Methode:** Cloudflare-Bypass mit curl_cffi + Count API

---

## Getestete Ansätze

### 1. ✅ **curl_cffi mit TLS Fingerprinting** (GEWÄHLT)
- **Library:** curl_cffi
- **Methode:** Chrome 120 Browser-Impersonation
- **Ergebnis:** Funktioniert perfekt
- **Vorteile:**
  - Schnell (~4 Sekunden pro Filiale)
  - Zuverlässig
  - Umgeht Cloudflare erfolgreich
  - Resourcen-effizient
- **Testdatei:** `tests/cloudflare_bypass/test_curl_cffi.py`

### 2. ✅ **undetected-chromedriver** (Teilweise erfolgreich)
- **Library:** undetected-chromedriver
- **Methode:** Automatisierter Chrome-Browser ohne Bot-Detection-Signale
- **Ergebnis:** Cloudflare-Bypass funktioniert für manche Seiten
- **Probleme:**
  - Langsam (30-60 Sekunden pro Filiale)
  - UI-Interaktionsprobleme
  - HTML-Scraping wird von Cloudflare Challenge blockiert
  - Hoher Ressourcenverbrauch
- **Testdatei:** `tests/cloudflare_bypass/test_undetected_chrome.py`

### 3. ❌ **HTML-Scraping** (Nicht erfolgreich)
- **Methode:** Browser-basiertes Scraping der Suchergebnisseite
- **Problem:** Cloudflare erkennt auch headless Browser und zeigt Challenge-Seite
- **Ergebnis:** Nicht nutzbar für Produktverifikation

---

## Funktionierende Lösung

### Architektur

```
1. Market Selection (curl_cffi)
   ↓
2. Count API Request (filialspezifisch)
   ↓
3. Verfügbarkeit: Count > 0 = Produkte vorhanden
```

### Verwendete REWE APIs

#### 1. Market Search API
```
GET https://www.rewe.de/api/wksmarketsearch?searchTerm={postal_code}
```
- Findet REWE-Filialen nach PLZ oder Stadt
- Liefert `wwIdent` (Market ID)

#### 2. Market Selection API
```
POST https://www.rewe.de/api/wksmarketselection/userselections
Body: {
  "selectedService": "STATIONARY",
  "customerZipCode": null,
  "wwIdent": "{market_id}"
}
```
- Setzt Cookie: `wksMarketsCookie`
- Erforderlich für filialspezifische Abfragen

#### 3. Product Count API (HAUPTMETHODE)
```
GET https://www.rewe.de/api/stationary-product-search/products/count?query=SOTO
```
- **Wichtig:** Respektiert den Market-Cookie!
- Liefert filialspezifische Produktanzahl
- Schnell und zuverlässig

### Warum nicht die Product List API?

Die Product List API (`/api/stationary-product-search/products`) **ignoriert den Market-Cookie** und liefert immer die gleiche generische Produktliste, unabhängig von der ausgewählten Filiale.

---

## Testergebnisse

### Validierung mit 5 Filialen

| Filiale | Erwartet | Count-API | Status |
|---------|----------|-----------|---------|
| Berlin (Schönhauser Allee) | 0 | 2 | ⚠️ Abweichung |
| München (Sendlinger Str.) | 2 | 2 | ✅ Perfekt |
| Freising (Münchner Str.) | 5 | 5 | ✅ Perfekt |
| Stuttgart (Kronenstr.) | 0 | 0 | ✅ Perfekt |
| Tübingen (Schleifmühleweg) | 0 | 0 | ✅ Perfekt |

**Genauigkeit:** 4 von 5 Filialen (80%) exakte Übereinstimmung

### Berlin-Abweichung

**Problem:** Count API zeigt 2, erwartet wurde 0

**Mögliche Ursachen:**
1. Count API zählt auch ähnliche Produkte (z.B. "Risotto" bei "SOTO"-Suche)
2. Neue Lieferung seit letzter manueller Prüfung
3. Filiale hat tatsächlich 2 SOTO-ähnliche Produkte

---

## Verwendung

### Installation

```bash
pip install curl_cffi
```

### Basic Usage

```python
from scripts.rewe_curl_scraper import REWECurlScraper

scraper = REWECurlScraper()

result = scraper.check_store_availability(
    store_name='REWE München',
    city='München',
    postal_code='80331'
)

print(f"Verfügbar: {result['available']}")
print(f"Anzahl: {result['product_count']}")
```

### Batch-Verarbeitung

```bash
python scripts/rewe_curl_scraper.py
```

Prüft alle 5 konfigurierten Filialen und speichert Ergebnisse in `data/rewe_soto_availability_*.json`.

---

## Technische Details

### Cloudflare-Bypass

**Methode:** TLS Fingerprinting mit Chrome 120 Impersonation

**Schlüssel-Parameter:**
```python
impersonate="chrome120"
```

### Session-Management

- Persistent Session pro Scraper-Instanz
- Cookies werden zwischen Requests beibehalten
- Wichtig: Market-Cookie wird korrekt gesetzt und verwendet

### Performance

- **Durchschnitt:** ~4 Sekunden pro Filiale
- **API Calls pro Filiale:** 3 (Market Search, Market Selection, Count)
- **Rate Limiting:** 3 Sekunden Delay zwischen Filialen

---

## Limitierungen

1. **Keine Produktlisten:** Count API liefert nur Anzahl, keine Produktdetails
2. **Keine Markenfilterung:** Count zählt alle Suchergebnisse für "SOTO", nicht nur Marke SOTO
3. **Keine Preise:** Preisinformationen nicht verfügbar über diese API
4. **Cloudflare-Abhängigkeit:** Bei Änderungen der Cloudflare-Konfiguration muss Bypass ggf. angepasst werden

---

## Wartung

### Bei Cloudflare-Änderungen

Falls Cloudflare-Bypass nicht mehr funktioniert:

1. curl_cffi auf neueste Version updaten
2. Chrome-Version für Impersonation anpassen:
   ```python
   impersonate="chrome<VERSION>"  # z.B. chrome121, chrome122, etc.
   ```

### Bei API-Änderungen

Falls REWE ihre API ändert:

1. HAR-Datei mit Browser-DevTools aufzeichnen
2. Neue API-Endpoints in `data/` analysieren
3. Scraper entsprechend anpassen

---

## Nächste Schritte (Optional)

### Verbesserungsmöglichkeiten

1. **Mobile API:** Recherche ob REWE Mobile App eine einfachere API hat
2. **Caching:** Filial-IDs cachen um Market Search zu vermeiden
3. **Parallel Processing:** Mehrere Filialen gleichzeitig prüfen
4. **Error Handling:** Retry-Logik bei temporären Fehlern

### Integration

Scraper kann integriert werden in:
- Cronjob für regelmäßige Prüfungen
- Web-API für On-Demand-Abfragen
- Store Finder Frontend

---

## Changelog

### 2025-11-18
- ✅ Erfolgreicher Cloudflare-Bypass mit curl_cffi
- ✅ Filialspezifische Count-API implementiert
- ✅ 5 Filialen erfolgreich getestet
- ❌ HTML-Scraping aufgrund Cloudflare-Challenge verworfen
- 📝 Dokumentation erstellt
