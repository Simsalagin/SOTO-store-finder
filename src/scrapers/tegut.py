"""Scraper for tegut stores."""

import requests
import re
import time
import logging
from typing import List, Optional, Dict
from bs4 import BeautifulSoup
from .base import BaseScraper, Store

logger = logging.getLogger(__name__)


class TegutScraper(BaseScraper):
    """Scraper for tegut stores."""

    SEARCH_URL = "https://www.tegut.com/maerkte/marktsuche.html"
    BASE_URL = "https://www.tegut.com"

    def __init__(self):
        """Initialize the tegut scraper."""
        super().__init__(chain_id="tegut", chain_name="tegut")
        self.headers = {'User-Agent': 'Mozilla/5.0'}

    def scrape(self) -> List[Store]:
        """
        Scrape all tegut stores from their website.

        Returns:
            List of Store objects
        """
        logger.info("Starting tegut store scraping...")

        # Get all store URLs first
        store_urls = self._get_all_store_urls()
        logger.info(f"Found {len(store_urls)} store URLs")

        # Scrape each store
        stores = []
        for i, url in enumerate(store_urls, 1):
            if i % 50 == 0:
                logger.info(f"Progress: {i}/{len(store_urls)}")

            store = self._scrape_store_page(url)
            if store and self.validate_store(store):
                # Validate and fix coordinates
                store = self.validate_and_fix_coordinates(store)
                stores.append(store)

            # Rate limiting
            time.sleep(0.3)

        logger.info(f"Successfully scraped {len(stores)} stores")
        return self.filter_country(stores, 'DE')

    def _get_all_store_urls(self) -> List[str]:
        """
        Get all store URLs from the search page using Playwright to handle pagination.

        The tegut website uses JavaScript to load stores dynamically with a "Mehr anzeigen"
        (Show more) button. We need a headless browser to handle this.

        Returns:
            List of store URLs
        """
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            logger.error("Playwright not installed. Run: pip install playwright && playwright install chromium")
            return []

        stores_by_url = {}

        try:
            with sync_playwright() as p:
                logger.info("Launching browser for pagination...")
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()

                logger.info("Loading store search page...")
                page.goto(f"{self.SEARCH_URL}?mksearch[address]=&mksearch[submit]=1")
                time.sleep(3)

                page_num = 1
                while True:
                    html = page.content()
                    soup = BeautifulSoup(html, 'html.parser')

                    store_links = soup.find_all('a', href=re.compile(r'/maerkte/markt/.*\.html'))
                    page_urls = set()
                    for link in store_links:
                        href = link.get('href')
                        if href and '/maerkte/markt/' in href:
                            full_url = f"{self.BASE_URL}{href}" if href.startswith('/') else href
                            page_urls.add(full_url)

                    new_urls = page_urls - set(stores_by_url.keys())
                    if new_urls:
                        logger.info(f"Page {page_num}: Found {len(new_urls)} new stores ({len(stores_by_url) + len(new_urls)} total)")
                        for url in new_urls:
                            stores_by_url[url] = None
                    else:
                        logger.info(f"Page {page_num}: No new stores found")

                    # Try to click "Mehr anzeigen" (Show more) button
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
                            logger.info("Reached end of pagination")
                            break
                    except:
                        logger.info("No more pagination available")
                        break

                    # Safety limit
                    if page_num > 100:
                        logger.warning("Reached page limit (100)")
                        break

                browser.close()

            logger.info(f"Found {len(stores_by_url)} unique store URLs")
            return list(stores_by_url.keys())

        except Exception as e:
            logger.error(f"Error getting store URLs with Playwright: {e}")
            return []

    def _scrape_store_page(self, url: str) -> Optional[Store]:
        """
        Scrape details from a single store page.

        Args:
            url: Store page URL

        Returns:
            Store object or None if scraping fails
        """
        try:
            response = requests.get(url, headers=self.headers, timeout=15)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            # Extract store ID from URL
            store_id = self._extract_store_id(url)

            # Extract coordinates from JSON-LD
            latitude, longitude = self._extract_coordinates(response.text)

            # Extract store name
            name = self._extract_name(soup)

            # Extract address details
            street, postal_code, city = self._extract_address(soup)

            # Extract opening hours
            opening_hours = self._extract_opening_hours(soup, url)

            # Validate required fields
            if not all([store_id, name, street, postal_code, city, latitude, longitude]):
                logger.warning(f"Missing required fields for store at {url}")
                return None

            store = Store(
                chain_id=self.chain_id,
                store_id=store_id,
                name=name,
                street=street,
                postal_code=postal_code,
                city=city,
                country_code='DE',
                latitude=latitude,
                longitude=longitude,
                website=url,
                opening_hours=opening_hours,
                has_soto_products=True,  # Tegut carries SOTO products
            )

            return store

        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            return None

    def _extract_store_id(self, url: str) -> Optional[str]:
        """Extract store ID from URL."""
        match = re.search(r'/markt/([^/]+)\.html', url)
        return match.group(1) if match else None

    def _extract_coordinates(self, html: str) -> tuple[Optional[float], Optional[float]]:
        """Extract coordinates from JSON-LD structured data."""
        match = re.search(
            r'"@type":\s*"GroceryStore".*?"geo":\s*\{[^}]*"latitude":\s*"([^"]+)"[^}]*"longitude":\s*"([^"]+)"',
            html,
            re.DOTALL
        )
        if match:
            try:
                return float(match.group(1)), float(match.group(2))
            except (ValueError, TypeError):
                pass
        return None, None

    def _extract_name(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract store name from page."""
        h1 = soup.find('h1', class_='h1')
        return h1.get_text(strip=True) if h1 else None

    def _extract_address(self, soup: BeautifulSoup) -> tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Extract address details from page.

        Returns:
            Tuple of (street, postal_code, city)
        """
        street, postal_code, city = None, None, None

        address_div = soup.find('div', class_='address')
        if address_div:
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

        return street, postal_code, city

    def _extract_opening_hours(self, soup: BeautifulSoup, url: str) -> Optional[Dict]:
        """
        Extract opening hours from page.

        Args:
            soup: BeautifulSoup object of the page
            url: Store page URL (for AJAX requests)

        Returns:
            Dictionary of opening hours or None
        """
        opening_hours = {}

        # Try to get opening hours from AJAX endpoint
        openingtimes_div = soup.find('div', class_='openingtimes')
        if openingtimes_div:
            ajax_div = openingtimes_div.find('div', class_='loadMyContentWithAjax')
            if ajax_div and ajax_div.get('data-content-url'):
                ajax_url = ajax_div['data-content-url']
                if not ajax_url.startswith('http'):
                    ajax_url = f"{self.BASE_URL}{ajax_url}"

                try:
                    response = requests.get(ajax_url, headers=self.headers, timeout=10)
                    response.raise_for_status()

                    # Check for 24/7
                    if 'Rund um die Uhr geöffnet' in response.text:
                        return self._create_24_7_hours()

                    # Parse AJAX response
                    ajax_soup = BeautifulSoup(response.text, 'html.parser')
                    opening_hours = self._parse_opening_hours_from_html(ajax_soup)

                except Exception as e:
                    logger.debug(f"AJAX request failed for {url}: {e}")

        # Fallback to static content if AJAX didn't work
        if not opening_hours:
            opening_hours = self._parse_opening_hours_from_html(soup)

        return opening_hours if opening_hours else None

    def _create_24_7_hours(self) -> Dict:
        """Create opening hours dict for 24/7 stores."""
        days = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag']
        return {
            day: {'open_from': '00:00', 'open_until': '24:00'}
            for day in days
        }

    def _parse_opening_hours_from_html(self, soup: BeautifulSoup) -> Dict:
        """
        Parse opening hours from HTML structure.

        Args:
            soup: BeautifulSoup object

        Returns:
            Dictionary of opening hours
        """
        opening_hours = {}
        day_mapping = {
            'Mo': 'Montag', 'Di': 'Dienstag', 'Mi': 'Mittwoch',
            'Do': 'Donnerstag', 'Fr': 'Freitag', 'Sa': 'Samstag', 'So': 'Sonntag'
        }
        weekdays = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So']

        rows = soup.find_all('div', class_='row')
        for row in rows:
            cols = row.find_all('div')
            if len(cols) < 2:
                continue

            day_text = cols[0].get_text(strip=True).rstrip(':')
            time_text = cols[1].get_text(strip=True)

            # Skip if this doesn't look like a day
            if not any(day in day_text for day in weekdays):
                continue

            # Handle day ranges like "Mo-Fr"
            if '-' in day_text and not any(char.isdigit() for char in day_text):
                parsed_hours = self._parse_day_range(day_text, time_text, day_mapping, weekdays)
                opening_hours.update(parsed_hours)
            else:
                # Single day
                parsed_hours = self._parse_single_day(day_text, time_text, day_mapping)
                if parsed_hours:
                    opening_hours.update(parsed_hours)

        return opening_hours

    def _parse_day_range(self, day_text: str, time_text: str,
                        day_mapping: Dict, weekdays: List[str]) -> Dict:
        """Parse a day range like 'Mo-Fr'."""
        result = {}
        day_range = day_text.split('-')

        if len(day_range) != 2:
            return result

        start_abbr = day_range[0].strip()
        end_abbr = day_range[1].strip()

        if start_abbr not in weekdays or end_abbr not in weekdays:
            return result

        start_idx = weekdays.index(start_abbr)
        end_idx = weekdays.index(end_abbr)

        # Parse time
        hours = self._parse_time_text(time_text)
        if hours:
            for i in range(start_idx, end_idx + 1):
                day_name = day_mapping[weekdays[i]]
                result[day_name] = hours

        return result

    def _parse_single_day(self, day_text: str, time_text: str, day_mapping: Dict) -> Dict:
        """Parse a single day entry."""
        result = {}

        for abbr, full_name in day_mapping.items():
            if abbr in day_text:
                hours = self._parse_time_text(time_text)
                if hours:
                    result[full_name] = hours
                break

        return result

    def _parse_time_text(self, time_text: str) -> Optional[Dict]:
        """Parse time text into structured format."""
        if 'Rund um die Uhr geöffnet' in time_text:
            return {'open_from': '00:00', 'open_until': '24:00'}

        # Clean and parse time range
        time_clean = time_text.replace('Uhr', '').strip()
        if '-' in time_clean:
            times = time_clean.split('-')
            if len(times) == 2:
                return {
                    'open_from': times[0].strip(),
                    'open_until': times[1].strip()
                }

        return None
