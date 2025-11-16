"""Scraper for Bio Company stores."""

import logging
from typing import List, Optional, Dict
import requests
from .base import BaseScraper, Store

logger = logging.getLogger(__name__)


class BioCompanyScraper(BaseScraper):
    """Scraper for Bio Company stores using Uberall API."""

    API_KEY = "4w3OLJTTT66unD30WlbJhuit7Hd45w"
    # Note: radius parameter required to fetch all stores across regions (Berlin, Brandenburg, Sachsen)
    # Without radius, API defaults to ~30km from Berlin center (only returns 41 stores instead of 59)
    API_URL = f"https://locator.uberall.com/api/storefinders/{API_KEY}/locations?radius=10000000&max=200"

    # Day of week mapping for opening hours
    DAY_NAMES = {
        1: "Mo",
        2: "Di",
        3: "Mi",
        4: "Do",
        5: "Fr",
        6: "Sa",
        7: "So"
    }

    def __init__(self):
        """Initialize the Bio Company scraper."""
        super().__init__(chain_id="biocompany", chain_name="Bio Company")

    def scrape(self) -> List[Store]:
        """
        Scrape all Bio Company stores using Uberall API.

        Returns:
            List of Store objects
        """
        logger.info(f"Starting Bio Company scrape from Uberall API")

        try:
            # Fetch locations from API
            logger.info(f"Fetching data from {self.API_URL}")
            response = requests.get(self.API_URL, timeout=30)
            response.raise_for_status()

            data = response.json()

            if data.get('status') != 'SUCCESS':
                logger.error(f"API returned non-success status: {data.get('status')}")
                return []

            locations_data = data.get('response', {}).get('locations', [])
            logger.info(f"Found {len(locations_data)} Bio Company stores from API")

            if not locations_data:
                logger.warning("No locations returned from API")
                return []

            # Parse all stores
            stores = []
            for idx, location in enumerate(locations_data, start=1):
                store = self._parse_location(location, idx)
                if store and self.validate_store(store):
                    stores.append(store)
                else:
                    logger.warning(f"Store {idx} failed validation")

            logger.info(f"Parsed {len(stores)} valid stores from API")

            # Validate and fix coordinates (though API provides them)
            geocoded_stores = []
            for store in stores:
                store = self.validate_and_fix_coordinates(store)
                geocoded_stores.append(store)

            logger.info(f"Successfully scraped {len(geocoded_stores)} Bio Company stores")
            # Filter for German stores only
            return self.filter_country(geocoded_stores, 'DE')

        except requests.RequestException as e:
            logger.error(f"Error fetching data from Uberall API: {e}", exc_info=True)
            return []
        except Exception as e:
            logger.error(f"Error scraping Bio Company stores: {e}", exc_info=True)
            return []

    def _parse_location(self, location: dict, index: int) -> Optional[Store]:
        """
        Parse a single location from API into a Store object.

        Args:
            location: Location dictionary from Uberall API
            index: Store index for logging

        Returns:
            Store object or None if parsing fails
        """
        try:
            # Extract required fields
            store_id = str(location.get('id', ''))
            identifier = location.get('identifier', store_id)
            name = location.get('name', '')
            street = location.get('streetAndNumber', '')
            postal_code = location.get('zip', '')
            city = location.get('city', '')
            country_code = location.get('country', 'DE')

            # Extract optional fields
            latitude = location.get('lat')
            longitude = location.get('lng')
            phone = location.get('phone')

            # Parse opening hours
            opening_hours = self._parse_opening_hours(location.get('openingHours', []))

            # Basic validation
            if not all([store_id, name, street, postal_code, city]):
                logger.warning(f"Store {index}: Missing required fields")
                return None

            store = Store(
                chain_id=self.chain_id,
                store_id=identifier,  # Use identifier as it's more stable
                name=name,
                street=street,
                postal_code=postal_code,
                city=city,
                country_code=country_code,
                latitude=latitude,
                longitude=longitude,
                phone=phone,
                opening_hours=opening_hours,
                website=f"https://www.biocompany.de/bio-company-markt-finden/l/{city.lower()}/{street.lower().replace(' ', '-')}/{store_id}" if store_id else None
            )

            return store

        except Exception as e:
            logger.error(f"Error parsing location {index}: {e}", exc_info=True)
            return None

    def _parse_opening_hours(self, hours_data: List[dict]) -> Optional[Dict]:
        """
        Parse opening hours from API format to our format.

        Args:
            hours_data: List of opening hours dictionaries from API

        Returns:
            Dictionary with day names as keys and hours as values
        """
        if not hours_data:
            return None

        hours_dict = {}

        for day_info in hours_data:
            day_of_week = day_info.get('dayOfWeek')
            if not day_of_week or day_of_week not in self.DAY_NAMES:
                continue

            day_name = self.DAY_NAMES[day_of_week]

            # Check if closed
            if day_info.get('closed', False):
                hours_dict[day_name] = "closed"
                continue

            # Get opening hours
            from1 = day_info.get('from1', '')
            to1 = day_info.get('to1', '')

            if from1 and to1:
                hours_dict[day_name] = f"{from1}-{to1}"

                # Check for second time period
                from2 = day_info.get('from2')
                to2 = day_info.get('to2')
                if from2 and to2:
                    hours_dict[day_name] += f", {from2}-{to2}"

        return hours_dict if hours_dict else None
