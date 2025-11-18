"""Scraper for REWE stores."""

import logging
from typing import List, Optional, Dict
from .base import BaseScraper, Store

logger = logging.getLogger(__name__)

try:
    from curl_cffi import requests
except ImportError:
    logger.error("curl_cffi not installed. Run: pip install curl_cffi")
    raise


class REWEScraper(BaseScraper):
    """Scraper for REWE stores."""

    API_URL = "https://www.rewe.de/api/wksmarketsearch"

    def __init__(self):
        """Initialize the REWE scraper."""
        super().__init__(chain_id="rewe", chain_name="REWE")

    def scrape(self) -> List[Store]:
        """
        Scrape all REWE stores from their API.

        Note: REWE's API has broken pagination - it returns the same stores
        on every page. Instead, we search by postal code to collect all stores.

        Returns:
            List of Store objects
        """
        logger.info(f"Scraping {self.chain_name} stores using postal code search...")

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'de-DE,de;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
        }

        stores = []
        seen_ids = set()

        # Generate German postal codes (01001-99998)
        # We sample every 10th code to balance coverage vs speed
        # This covers ~1000 searches and should capture most stores
        postal_codes = [f"{i:05d}" for i in range(1001, 100000, 100)]

        total_codes = len(postal_codes)
        logger.info(f"Searching {total_codes} postal codes...")

        for idx, postal_code in enumerate(postal_codes, 1):
            if idx % 50 == 0:
                logger.info(f"Progress: {idx}/{total_codes} codes searched, {len(stores)} stores found")

            try:
                response = requests.get(
                    self.API_URL,
                    params={'searchTerm': postal_code},
                    headers=headers,
                    impersonate='chrome120',
                    timeout=30
                )

                if response.status_code != 200:
                    continue

                data = response.json()
                markets = data.get('markets', [])

                for market in markets:
                    # Deduplicate by store ID
                    store_id = market.get('wwIdent')
                    if store_id in seen_ids:
                        continue

                    seen_ids.add(store_id)

                    store = self._parse_market(market)
                    if store and self.validate_store(store):
                        # Skip coordinate validation for performance
                        # (REWE provides accurate coordinates)
                        stores.append(store)

            except Exception as e:
                logger.debug(f"Search failed for postal code {postal_code}: {e}")
                continue

        logger.info(f"Successfully scraped {len(stores)} unique stores from {total_codes} postal codes")

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
            # Extract basic info
            ww_ident = market.get('wwIdent', '')
            name = market.get('name', '')
            company_name = market.get('companyName', '')
            street = market.get('street', '')
            zip_code = market.get('zipCode', '')
            city = market.get('city', '')

            # Extract coordinates
            location = market.get('location', {})
            latitude = location.get('latitude')
            longitude = location.get('longitude')

            # Parse opening hours
            opening_hours = self._parse_opening_hours(market.get('openingInfo', []))

            # Build full store name (include company name if different from name)
            if company_name and company_name != name:
                full_name = f"{name} ({company_name})"
            else:
                full_name = name

            store = Store(
                chain_id=self.chain_id,
                store_id=ww_ident,
                name=full_name,
                street=street,
                postal_code=zip_code,
                city=city,
                country_code='DE',  # REWE is Germany-only
                latitude=latitude,
                longitude=longitude,
                opening_hours=opening_hours,
            )

            return store

        except Exception as e:
            logger.error(f"Error parsing market {market.get('wwIdent', 'unknown')}: {e}")
            return None

    def _parse_opening_hours(self, opening_info: List[Dict]) -> Optional[Dict]:
        """
        Parse opening hours into a structured format.

        Args:
            opening_info: List of opening hours information

        Returns:
            Dictionary with opening hours or None
        """
        if not opening_info:
            return None

        opening_hours = {}

        for entry in opening_info:
            opening_type = entry.get('openingType', '')
            days = entry.get('days', '')
            hours = entry.get('hours', '')

            # Only parse regular opening hours (skip special openings)
            if opening_type == 'REGULAR' and days and hours:
                opening_hours[days] = hours

        return opening_hours if opening_hours else None
