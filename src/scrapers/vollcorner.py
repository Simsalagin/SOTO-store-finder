"""Scraper for VollCorner stores."""

import requests
from bs4 import BeautifulSoup
from typing import List, Optional
import re
import logging
from .base import BaseScraper, Store

logger = logging.getLogger(__name__)


class VollcornerScraper(BaseScraper):
    """Scraper for VollCorner stores."""

    STORE_LIST_URL = "https://www.vollcorner.de/standorte/biomaerkte/"

    def __init__(self):
        """Initialize the Vollcorner scraper."""
        super().__init__(chain_id="vollcorner", chain_name="VollCorner")

    def scrape(self) -> List[Store]:
        """
        Scrape all Vollcorner stores from their locations page.

        Returns:
            List of Store objects
        """
        logger.info("Starting Vollcorner scrape...")

        try:
            response = requests.get(self.STORE_LIST_URL, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # Extract coordinates from JavaScript
            coordinates_map = self._extract_coordinates_from_js(soup)
            logger.info(f"Found {len(coordinates_map)} stores with coordinates in JavaScript")

            # Extract stores from HTML cards
            stores = []
            store_cards = soup.find_all('div', class_='location-address')

            logger.info(f"Found {len(store_cards)} store cards")

            for card in store_cards:
                store = self._parse_store_card(card, coordinates_map)
                if store and self.validate_store(store):
                    # Validate and fix coordinates
                    store = self.validate_and_fix_coordinates(store)
                    stores.append(store)

            logger.info(f"Scraped {len(stores)} valid stores")

            # Filter for German stores only
            return self.filter_country(stores, 'DE')

        except Exception as e:
            logger.error(f"Error scraping Vollcorner: {e}", exc_info=True)
            return []

    def _extract_coordinates_from_js(self, soup: BeautifulSoup) -> dict:
        """
        Extract coordinates from JavaScript locations array.

        Returns:
            Dictionary mapping store names to (lat, lon) tuples
        """
        coordinates_map = {}

        # Find script tags containing the locations array
        scripts = soup.find_all('script')

        for script in scripts:
            if not script.string:
                continue

            # Look for the locations array pattern
            # Example: var locations = [...{lat:"48.191319",lng:"11.462819",...}...]
            if 'var locations' in script.string or 'locations =' in script.string:
                # Extract all lat/lng pairs with their titles
                # Pattern: {..."title":"Store Name"..."lat":"48.191319","lng":"11.462819"...}
                pattern = r'"title":\s*"([^"]+)"[^}]*"lat":\s*"([^"]+)"[^}]*"lng":\s*"([^"]+)"'
                matches = re.findall(pattern, script.string)

                for title, lat, lng in matches:
                    try:
                        coordinates_map[title.strip()] = (float(lat), float(lng))
                    except ValueError:
                        logger.warning(f"Invalid coordinates for {title}: {lat}, {lng}")

                logger.debug(f"Extracted {len(matches)} coordinate pairs from JavaScript")
                break

        return coordinates_map

    def _parse_store_card(self, card: BeautifulSoup, coordinates_map: dict) -> Optional[Store]:
        """
        Parse a single store card element.

        Args:
            card: BeautifulSoup element for the store card
            coordinates_map: Dictionary of store names to coordinates

        Returns:
            Store object or None if parsing fails
        """
        try:
            # Extract store name from h3 inside name-address-opening div
            name_div = card.find('div', class_='name-address-opening')
            if not name_div:
                logger.warning("Store card missing name-address-opening div")
                return None

            name_elem = name_div.find('h3')
            if not name_elem:
                logger.warning("Store card missing h3 name element")
                return None

            name = name_elem.get_text(strip=True)

            # Extract store ID from name (last part, e.g., "allach" from "VollCorner Biomarkt Allach")
            store_id = name.lower().replace('vollcorner biomarkt', '').replace('vollcorner', '').strip()
            store_id = re.sub(r'[^\w\-]', '-', store_id)  # Clean up ID

            # Extract address - look for span with class="location-address market"
            address_span = card.find('span', class_='location-address market')
            if not address_span:
                logger.warning(f"Store {name} missing address span")
                return None

            # Get the address text (before the <br> and tel link)
            address_text = address_span.get_text(strip=True).split('Tel.')[0].strip()

            # Parse address pattern: "Street, Postal City" or "Street Postal City"
            # Example: "Franz-Nißl-Str. 41, 80999 München"
            # Remove commas for easier parsing
            address_text = address_text.replace(',', ' ')

            # Match: street + number, postal code, city
            postal_city_match = re.search(r'(.+?)\s+(\d{5})\s+(.+)', address_text)
            if not postal_city_match:
                logger.warning(f"Store {name} has invalid address format: {address_text}")
                return None

            street = postal_city_match.group(1).strip()
            postal_code = postal_city_match.group(2).strip()
            city = postal_city_match.group(3).strip()

            # Extract phone
            phone = None
            phone_link = card.find('a', href=re.compile(r'tel:'))
            if phone_link:
                phone = phone_link.get_text(strip=True)

            # Extract opening hours - look for opening-times div
            opening_hours_text = None
            hours_div = card.find('div', class_='opening-times')
            if hours_div:
                # Get all text from the div (skip the icon)
                text_div = hours_div.find_all('div')[-1] if hours_div.find_all('div') else None
                if text_div:
                    opening_hours_text = text_div.get_text(separator=' ', strip=True)
                    opening_hours_text = ' '.join(opening_hours_text.split())  # Normalize whitespace

            # Get coordinates from JavaScript data
            latitude = None
            longitude = None
            if name in coordinates_map:
                latitude, longitude = coordinates_map[name]
            else:
                # Try fuzzy matching if exact match fails
                for js_name in coordinates_map.keys():
                    if store_id in js_name.lower() or js_name.lower() in name.lower():
                        latitude, longitude = coordinates_map[js_name]
                        logger.debug(f"Matched {name} to JS name {js_name}")
                        break

            if not latitude or not longitude:
                logger.warning(f"No coordinates found for {name}")

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
                phone=phone,
                website=self.STORE_LIST_URL,  # Individual store URLs not readily available
                opening_hours={'text': opening_hours_text} if opening_hours_text else None,
            )

            return store

        except Exception as e:
            logger.error(f"Error parsing store card: {e}", exc_info=True)
            return None
