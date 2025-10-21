#!/usr/bin/env python3
"""
Automated tegut store scraper
Syncs database with tegut.com website
"""

import sqlite3
import requests
import re
import json
import time
from datetime import datetime

DB_PATH = '../data/stores.db'
CHAIN_ID = 'tegut'

def get_store_details_from_url(url):
    """Extract full store details from tegut store page"""
    try:
        from bs4 import BeautifulSoup
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        # Extract coordinates from JSON-LD
        lat, lon = None, None
        match = re.search(
            r'"@type":\s*"GroceryStore".*?"geo":\s*\{[^}]*"latitude":\s*"([^"]+)"[^}]*"longitude":\s*"([^"]+)"',
            response.text,
            re.DOTALL
        )
        if match:
            lat = float(match.group(1))
            lon = float(match.group(2))

        # Extract store name from h1
        name = None
        h1 = soup.find('h1', class_='h1')
        if h1:
            name = h1.get_text(strip=True)

        # Extract address details
        street, postal_code, city = None, None, None
        address_div = soup.find('div', class_='address')
        if address_div:
            # Find street
            rows = address_div.find_all('div', class_='row')
            for row in rows:
                cols = row.find_all('div')
                if len(cols) >= 2:
                    label = cols[0].get_text(strip=True)
                    value = cols[1].get_text(strip=True)

                    if 'Straße' in label or 'Strasse' in label:
                        street = value
                    elif 'PLZ Ort' in label:
                        # Format: "61137 Schöneck"
                        parts = value.split(maxsplit=1)
                        if len(parts) == 2:
                            postal_code = parts[0]
                            city = parts[1]

        # Extract opening hours (loaded via AJAX)
        opening_hours = {}
        openingtimes_div = soup.find('div', class_='openingtimes')
        if openingtimes_div:
            # Find AJAX URL for loading opening hours
            ajax_div = openingtimes_div.find('div', class_='loadMyContentWithAjax')
            if ajax_div and ajax_div.get('data-content-url'):
                ajax_url = ajax_div['data-content-url']
                if not ajax_url.startswith('http'):
                    ajax_url = f"https://www.tegut.com{ajax_url}"

                try:
                    ajax_response = requests.get(ajax_url, headers=headers, timeout=10)
                    ajax_response.raise_for_status()
                    ajax_soup = BeautifulSoup(ajax_response.text, 'html.parser')

                    # Check for 24/7
                    if 'Rund um die Uhr geöffnet' in ajax_response.text:
                        opening_hours = {
                            'Montag': {'open_from': '00:00', 'open_until': '24:00'},
                            'Dienstag': {'open_from': '00:00', 'open_until': '24:00'},
                            'Mittwoch': {'open_from': '00:00', 'open_until': '24:00'},
                            'Donnerstag': {'open_from': '00:00', 'open_until': '24:00'},
                            'Freitag': {'open_from': '00:00', 'open_until': '24:00'},
                            'Samstag': {'open_from': '00:00', 'open_until': '24:00'},
                            'Sonntag': {'open_from': '00:00', 'open_until': '24:00'}
                        }
                except:
                    pass  # Continue if AJAX fails

            # Also check static content (fallback or additional detail section)
            if not opening_hours:
                # Look for static opening hours in the page
                rows = soup.find_all('div', class_='row')
                day_mapping = {
                    'Mo': 'Montag', 'Di': 'Dienstag', 'Mi': 'Mittwoch',
                    'Do': 'Donnerstag', 'Fr': 'Freitag', 'Sa': 'Samstag', 'So': 'Sonntag'
                }

                for row in rows:
                    cols = row.find_all('div')
                    if len(cols) >= 2:
                        day_text = cols[0].get_text(strip=True).rstrip(':')
                        time_text = cols[1].get_text(strip=True)

                        # Skip if this doesn't look like a day
                        if not any(day in day_text for day in day_mapping.keys()):
                            continue

                        # Handle day ranges like "Mo-Fr" or "Mo-So"
                        if '-' in day_text and not any(char.isdigit() for char in day_text):
                            day_range = day_text.split('-')
                            if len(day_range) == 2:
                                start_abbr = day_range[0].strip()
                                end_abbr = day_range[1].strip()
                                weekdays = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So']

                                if start_abbr in weekdays and end_abbr in weekdays:
                                    start_idx = weekdays.index(start_abbr)
                                    end_idx = weekdays.index(end_abbr)

                                    # Parse time
                                    if '-' in time_text or 'Uhr' in time_text:
                                        # Handle various time formats
                                        time_clean = time_text.replace('Uhr', '').strip()
                                        if '-' in time_clean:
                                            times = time_clean.split('-')
                                            if len(times) == 2:
                                                open_from = times[0].strip()
                                                open_until = times[1].strip()

                                                for i in range(start_idx, end_idx + 1):
                                                    day_name = day_mapping[weekdays[i]]
                                                    opening_hours[day_name] = {
                                                        'open_from': open_from,
                                                        'open_until': open_until
                                                    }
                                        elif 'Rund um die Uhr geöffnet' in time_text:
                                            for i in range(start_idx, end_idx + 1):
                                                day_name = day_mapping[weekdays[i]]
                                                opening_hours[day_name] = {
                                                    'open_from': '00:00',
                                                    'open_until': '24:00'
                                                }
                        else:
                            # Single day
                            for abbr, full_name in day_mapping.items():
                                if abbr in day_text:
                                    if '-' in time_text or 'Uhr' in time_text:
                                        time_clean = time_text.replace('Uhr', '').strip()
                                        if '-' in time_clean:
                                            times = time_clean.split('-')
                                            if len(times) == 2:
                                                opening_hours[full_name] = {
                                                    'open_from': times[0].strip(),
                                                    'open_until': times[1].strip()
                                                }
                                    break

        return {
            'url': url,
            'name': name,
            'street': street,
            'postal_code': postal_code,
            'city': city,
            'latitude': lat,
            'longitude': lon,
            'opening_hours': opening_hours if opening_hours else None
        }

    except Exception as e:
        print(f"  Error scraping {url}: {e}")
        return None

def parse_opening_hours_text(text):
    """Parse opening hours text into structured format"""
    if not text:
        return None

    result = {}
    parts = text.replace('|', ',').split(',')

    for part in parts:
        part = part.strip()
        if ':' not in part:
            continue

        day_part, time_part = part.split(':', 1)
        day_part = day_part.strip()
        time_part = time_part.strip()

        if '-' in time_part:
            times = time_part.split('-')
            if len(times) == 2:
                open_from = times[0].strip()
                open_until = times[1].strip()

                day_mapping = {
                    'Mo': 'Montag', 'Di': 'Dienstag', 'Mi': 'Mittwoch',
                    'Do': 'Donnerstag', 'Fr': 'Freitag', 'Sa': 'Samstag', 'So': 'Sonntag'
                }

                if '-' in day_part:
                    day_range = day_part.split('-')
                    if len(day_range) == 2:
                        start_abbr = day_range[0].strip()
                        end_abbr = day_range[1].strip()
                        weekdays = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So']

                        if start_abbr in weekdays and end_abbr in weekdays:
                            start_idx = weekdays.index(start_abbr)
                            end_idx = weekdays.index(end_abbr)

                            for i in range(start_idx, end_idx + 1):
                                day_name = day_mapping[weekdays[i]]
                                result[day_name] = {
                                    'open_from': open_from,
                                    'open_until': open_until
                                }

    return result if result else None

def scrape_website_stores():
    """Scrape all stores from tegut website"""
    print("Scraping tegut.com for current stores...")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Error: Playwright not installed. Run: pip install playwright && playwright install chromium")
        return []

    stores_by_url = {}

    with sync_playwright() as p:
        print("  Launching browser...")
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print("  Loading store search page...")
        page.goto('https://www.tegut.com/maerkte/marktsuche.html?mksearch%5Baddress%5D=&mksearch%5Bsubmit%5D=1')
        time.sleep(3)

        page_num = 1
        while True:
            html = page.content()
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')

            store_links = soup.find_all('a', href=re.compile(r'/maerkte/markt/.*\.html'))
            page_urls = set()
            for link in store_links:
                href = link.get('href')
                if href and '/maerkte/markt/' in href:
                    full_url = f"https://www.tegut.com{href}" if href.startswith('/') else href
                    page_urls.add(full_url)

            new_urls = page_urls - set(stores_by_url.keys())
            if new_urls:
                print(f"  Page {page_num}: Found {len(new_urls)} new stores ({len(stores_by_url) + len(new_urls)} total)")
                for url in new_urls:
                    stores_by_url[url] = None
            else:
                print(f"  Page {page_num}: No new stores found")

            # Try to click "Mehr anzeigen"
            try:
                more_button = None
                for text in ['Mehr anzeigen', 'Mehr laden']:
                    try:
                        more_button = page.get_by_text(text, exact=False).first
                        if more_button.is_visible():
                            break
                    except:
                        continue

                if more_button and more_button.is_visible():
                    more_button.click()
                    time.sleep(2)
                    page_num += 1
                else:
                    print(f"  Reached end of pagination")
                    break
            except:
                break

            if page_num > 100:
                break

        browser.close()

    print(f"\n✓ Found {len(stores_by_url)} unique store URLs")

    # Now scrape each store
    print(f"\nScraping individual store pages...")
    stores = []
    for i, url in enumerate(stores_by_url.keys(), 1):
        if i % 50 == 0:
            print(f"  Progress: {i}/{len(stores_by_url)}")

        store_details = get_store_details_from_url(url)
        if store_details and store_details['latitude'] and store_details['longitude']:
            stores.append(store_details)
        time.sleep(0.3)

    print(f"✓ Successfully scraped {len(stores)} stores with full details\n")
    return stores

def sync_database(scraped_stores):
    """Sync database with scraped stores"""
    print("Syncing database...")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get current stores from database
    cursor.execute('SELECT id, website, latitude, longitude FROM stores WHERE chain_id = ?', (CHAIN_ID,))
    db_stores = {row[1]: {'id': row[0], 'lat': row[2], 'lon': row[3]} for row in cursor.fetchall() if row[1]}

    scraped_urls = {s['url'] for s in scraped_stores}
    db_urls = set(db_stores.keys())

    # Find new, removed, and updated stores
    new_urls = scraped_urls - db_urls
    removed_urls = db_urls - scraped_urls
    existing_urls = scraped_urls & db_urls

    print(f"  New stores: {len(new_urls)}")
    print(f"  Removed stores: {len(removed_urls)}")
    print(f"  Existing stores: {len(existing_urls)}")

    # Remove deleted stores
    if removed_urls:
        print(f"\nRemoving {len(removed_urls)} deleted stores...")
        for url in removed_urls:
            store_id = db_stores[url]['id']
            cursor.execute('DELETE FROM stores WHERE id = ?', (store_id,))
            print(f"  - Removed: {url}")

    # Add new stores with full details
    added_count = 0
    if new_urls:
        print(f"\nAdding {len(new_urls)} new stores to database...")
        for store in scraped_stores:
            if store['url'] in new_urls:
                # Convert opening hours to JSON
                opening_hours_json = json.dumps(store['opening_hours']) if store['opening_hours'] else None

                cursor.execute('''
                    INSERT INTO stores (
                        chain_id, name, street, postal_code, city,
                        latitude, longitude, website, opening_hours,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ''', (
                    CHAIN_ID,
                    store['name'],
                    store['street'],
                    store['postal_code'],
                    store['city'],
                    store['latitude'],
                    store['longitude'],
                    store['url'],
                    opening_hours_json
                ))
                added_count += 1
                print(f"  + Added: {store['name']} ({store['city']})")

        print(f"✓ Successfully added {added_count} new stores")

    # Update coordinates if changed
    updated_count = 0
    for store in scraped_stores:
        if store['url'] in db_urls:
            db_store = db_stores[store['url']]
            if abs(db_store['lat'] - store['latitude']) > 0.0001 or abs(db_store['lon'] - store['longitude']) > 0.0001:
                cursor.execute('''
                    UPDATE stores SET latitude = ?, longitude = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (store['latitude'], store['longitude'], db_store['id']))
                updated_count += 1

    if updated_count > 0:
        print(f"\nUpdated coordinates for {updated_count} stores")

    conn.commit()
    conn.close()

    print(f"\n✓ Database sync complete!")
    return {
        'new': added_count,
        'removed': len(removed_urls),
        'updated': updated_count
    }

def main():
    print("=== TEGUT STORE SCRAPER ===")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Scrape website
    scraped_stores = scrape_website_stores()

    if not scraped_stores:
        print("No stores scraped. Exiting.")
        return

    # Sync with database
    results = sync_database(scraped_stores)

    print(f"\n=== SUMMARY ===")
    print(f"Total scraped: {len(scraped_stores)}")
    print(f"New stores: {results['new']}")
    print(f"Removed stores: {results['removed']}")
    print(f"Updated stores: {results['updated']}")
    print(f"\nCompleted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == '__main__':
    main()
