"""Scraper for Globus stores."""

import logging
import re
from typing import List, Optional
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from bs4 import BeautifulSoup
from .base import BaseScraper, Store

logger = logging.getLogger(__name__)


class GlobusScraper(BaseScraper):
    """Scraper for Globus stores using Playwright for dynamic content."""

    STORES_URL = "https://www.globus.de/maerkte.php"

    def __init__(self):
        """Initialize the Globus scraper."""
        super().__init__(chain_id="globus", chain_name="Globus")

    def scrape(self) -> List[Store]:
        """
        Scrape all Globus stores using Playwright to load dynamic content.

        Returns:
            List of Store objects
        """
        logger.info(f"Starting Globus scrape from {self.STORES_URL}")

        try:
            with sync_playwright() as p:
                # Launch browser
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()

                # Navigate to the stores page
                logger.info("Loading Globus stores page...")
                page.goto(self.STORES_URL, wait_until='domcontentloaded')

                # Wait a bit for JavaScript to execute
                page.wait_for_timeout(3000)

                # Try to find the market-result elements
                # First check if they exist
                market_selector = '.market-result'
                try:
                    page.wait_for_selector(market_selector, timeout=10000)
                    logger.info("Market results found successfully")
                except PlaywrightTimeoutError:
                    logger.warning("Timeout waiting for .market-result, trying alternative approach")
                    # Try scrolling or triggering load
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    page.wait_for_timeout(2000)

                # Get the page content
                html_content = page.content()
                browser.close()

                # Parse with BeautifulSoup
                soup = BeautifulSoup(html_content, 'html.parser')

                # Find all store result divs
                market_results = soup.find_all('div', class_='market-result')
                logger.info(f"Found {len(market_results)} Globus stores")

                if len(market_results) == 0:
                    # Debug: print what we actually found
                    logger.warning("No market-result divs found. Checking page content...")
                    search_results = soup.find('div', class_='market-search-results')
                    if search_results:
                        logger.info("Found market-search-results div")
                    else:
                        logger.error("market-search-results div not found either")
                    return []

                # Parse all stores first (without geocoding)
                parsed_stores = []
                for idx, market_div in enumerate(market_results, start=1):
                    store = self._parse_market(market_div, idx)
                    if store and self.validate_store(store):
                        parsed_stores.append(store)
                    else:
                        logger.warning(f"Store {idx} failed validation")

                logger.info(f"Parsed {len(parsed_stores)} stores from HTML")

                # Deduplicate stores by store_id before geocoding
                unique_stores = {}
                for store in parsed_stores:
                    if store.store_id not in unique_stores:
                        unique_stores[store.store_id] = store
                    else:
                        logger.debug(f"Skipping duplicate: {store.name}")

                logger.info(f"Found {len(unique_stores)} unique stores (removed {len(parsed_stores) - len(unique_stores)} duplicates)")

                # Now geocode only unique stores
                geocoded_stores = []
                for store in unique_stores.values():
                    # Validate and fix coordinates
                    store = self.validate_and_fix_coordinates(store)
                    geocoded_stores.append(store)

                logger.info(f"Successfully scraped and geocoded {len(geocoded_stores)} Globus stores")
                # Filter for German stores only
                return self.filter_country(geocoded_stores, 'DE')

        except Exception as e:
            logger.error(f"Error scraping Globus stores: {e}", exc_info=True)
            return []

    def _parse_market(self, market_div, index: int) -> Optional[Store]:
        """
        Parse a single market div into a Store object.

        Args:
            market_div: BeautifulSoup div element containing market info
            index: Store index for ID

        Returns:
            Store object or None if parsing fails
        """
        try:
            # Extract store name
            name_elem = market_div.find('div', class_='globus-name')
            if not name_elem:
                logger.warning(f"Store {index}: No name found")
                return None
            name = name_elem.get_text(strip=True)

            # Extract address
            address_elem = market_div.find('div', class_='globus-address')
            if not address_elem:
                logger.warning(f"Store {index} ({name}): No address found")
                return None

            address_text = address_elem.get_text(strip=True)
            # Address format: "Street, Postal Code City"
            # Example: "Südring 2, 67240 Bobenheim"
            street, postal_city = self._parse_address_text(address_text)
            if not street or not postal_city:
                logger.warning(f"Store {index} ({name}): Could not parse address: {address_text}")
                return None

            postal_code, city = self._extract_postal_code_city(postal_city)
            if not postal_code or not city:
                logger.warning(f"Store {index} ({name}): Could not extract postal code and city: {postal_city}")
                return None

            # Extract opening hours
            opening_hours_text = self._extract_opening_hours(market_div)

            # Generate store ID from name
            store_id = self._generate_store_id(name, index)

            store = Store(
                chain_id=self.chain_id,
                store_id=store_id,
                name=name,
                street=street,
                postal_code=postal_code,
                city=city,
                country_code='DE',
                latitude=None,  # Will be geocoded
                longitude=None,
                opening_hours={'raw': opening_hours_text} if opening_hours_text else None,
            )

            return store

        except Exception as e:
            logger.error(f"Error parsing market {index}: {e}", exc_info=True)
            return None

    def _parse_address_text(self, address_text: str) -> tuple[Optional[str], Optional[str]]:
        """
        Parse address text into street and postal_code+city.

        Args:
            address_text: Raw address text like "Südring 2, 67240 Bobenheim"

        Returns:
            Tuple of (street, postal_city) or (None, None) if parsing fails
        """
        # Split by comma
        parts = address_text.split(',')
        if len(parts) != 2:
            return None, None

        street = parts[0].strip()
        postal_city = parts[1].strip()

        return street, postal_city

    def _extract_postal_code_city(self, postal_city: str) -> tuple[Optional[str], Optional[str]]:
        """
        Extract postal code and city from combined string.

        Args:
            postal_city: String like "67240 Bobenheim" or "99095 Erfurt"

        Returns:
            Tuple of (postal_code, city)
        """
        # Pattern: 5-digit postal code followed by city name
        match = re.match(r'^(\d{5})\s+(.+)$', postal_city)
        if match:
            return match.group(1), match.group(2)

        return None, None

    def _extract_opening_hours(self, market_div) -> Optional[str]:
        """
        Extract opening hours text from market div.

        Args:
            market_div: BeautifulSoup div element

        Returns:
            Opening hours string or None
        """
        opening_elem = market_div.find('div', class_='globus-oeffnungszeit')
        if opening_elem:
            # Find the nested text-light-grey div
            text_elem = opening_elem.find('div', class_='text-light-grey')
            if text_elem:
                return text_elem.get_text(strip=True)

        return None

    def _generate_store_id(self, name: str, index: int) -> str:
        """
        Generate a unique store ID from the store name.

        Args:
            name: Store name like "GLOBUS Bobenheim-Roxheim"
            index: Store index as fallback

        Returns:
            Store ID like "bobenheim-roxheim" or "store-1"
        """
        # Remove "GLOBUS" prefix and convert to lowercase
        store_id = name.replace('GLOBUS', '').strip().lower()

        # Replace spaces and special characters with hyphens
        store_id = re.sub(r'[^a-z0-9]+', '-', store_id)

        # Remove leading/trailing hyphens
        store_id = store_id.strip('-')

        # If empty, use index
        if not store_id:
            store_id = f"store-{index}"

        return store_id

