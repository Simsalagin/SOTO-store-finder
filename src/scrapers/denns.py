"""Scraper for denn's Biomarkt stores."""

import logging
import requests
from typing import List, Optional, Dict
from .base import BaseScraper, Store

logger = logging.getLogger(__name__)


class DennsScraper(BaseScraper):
    """Scraper for denn's Biomarkt stores."""

    API_URL = "https://www.biomarkt.de/page-data/marktindex/page-data.json"

    def __init__(self):
        """Initialize the denn's scraper."""
        super().__init__(chain_id="denns", chain_name="denn's Biomarkt")

    def scrape(self) -> List[Store]:
        """
        Scrape all denn's Biomarkt stores from their API.

        Returns:
            List of Store objects
        """
        response = requests.get(self.API_URL, timeout=30)
        response.raise_for_status()

        data = response.json()
        markets = data.get('result', {}).get('data', {}).get('markets', {}).get('nodes', [])

        stores = []
        for market in markets:
            store = self._parse_market(market)
            if store and self.validate_store(store):
                # Validate and fix coordinates
                store = self.validate_and_fix_coordinates(store)
                stores.append(store)

        # Filter for German stores only
        return self.filter_country(stores, 'DE')

    def _parse_market(self, market: Dict) -> Optional[Store]:
        """
        Parse a single market data entry into a Store object.

        Args:
            market: Raw market data from API

        Returns:
            Store object or None if parsing fails
        """
        try:
            address = market.get('address', {})
            contact = market.get('contact', {})

            # Parse coordinates
            lat = self._parse_coordinate(address.get('lat'))
            lon = self._parse_coordinate(address.get('lon'))

            # Parse opening hours
            opening_hours = self._parse_opening_hours(market.get('openingHoursMarket', []))

            # Parse services
            services = self._parse_services(market.get('services', {}))

            store = Store(
                chain_id=self.chain_id,
                store_id=market.get('marketId', ''),
                name=market.get('name', ''),
                street=address.get('street', ''),
                postal_code=address.get('zip', ''),
                city=address.get('city', ''),
                country_code=market.get('countryCode', ''),
                latitude=lat,
                longitude=lon,
                phone=contact.get('phone'),
                email=contact.get('email'),
                website=address.get('googleProfileLink'),
                opening_hours=opening_hours,
                services=services,
                has_soto_products=True,  # denn's carries SOTO products
            )

            return store

        except Exception as e:
            logger.error(f"Error parsing market {market.get('marketId', 'unknown')}: {e}")
            return None

    def _parse_coordinate(self, value: Optional[str]) -> Optional[float]:
        """Parse coordinate string to float."""
        if not value:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    def _parse_opening_hours(self, hours_data: List[Dict]) -> Optional[Dict]:
        """
        Parse opening hours into a structured format.

        Args:
            hours_data: List of opening hours per weekday

        Returns:
            Dictionary with weekday as key and hours as value
        """
        if not hours_data:
            return None

        opening_hours = {}
        for entry in hours_data:
            weekday = entry.get('weekday', '')
            open_from = entry.get('open_from', '')
            open_until = entry.get('open_until', '')

            if weekday and open_from and open_until:
                opening_hours[weekday] = {
                    'open_from': open_from,
                    'open_until': open_until
                }

                # Handle split opening hours (e.g., lunch break)
                if entry.get('open_from_second') and entry.get('open_until_second'):
                    opening_hours[weekday]['open_from_second'] = entry['open_from_second']
                    opening_hours[weekday]['open_until_second'] = entry['open_until_second']

        return opening_hours if opening_hours else None

    def _parse_services(self, services_data: Dict) -> Optional[List[str]]:
        """
        Parse services and equipment information.

        Args:
            services_data: Services data from API

        Returns:
            List of service names
        """
        services = []

        # Add general info
        general_info = services_data.get('generalInfo', [])
        if general_info:
            services.extend(general_info)

        # Add equipment
        equipment = services_data.get('equipment', [])
        if equipment:
            services.extend(equipment)

        # Add assortment
        assortment = services_data.get('assortment', [])
        if assortment:
            services.extend(assortment)

        return services if services else None
