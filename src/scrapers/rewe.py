"""Scraper for REWE stores."""

import logging
import time
from typing import List, Optional, Dict
from .base import BaseScraper, Store

logger = logging.getLogger(__name__)

try:
    from curl_cffi import requests
except ImportError:
    logger.error("curl_cffi not installed. Run: pip install curl_cffi")
    raise


class REWEScraper(BaseScraper):
    """Scraper for REWE stores using state-based marketSearch API."""

    MARKET_SEARCH_URL = "https://www.rewe.de/stationary-market-search-frontend/api/marketSearch"
    MARKET_DETAILS_URL = "https://www.rewe.de/api/wksmarketsearch"

    # All 16 German states (Bundesländer)
    GERMAN_STATES = [
        "Baden-Württemberg",
        "Bayern",
        "Berlin",
        "Brandenburg",
        "Bremen",
        "Hamburg",
        "Hessen",
        "Mecklenburg-Vorpommern",
        "Niedersachsen",
        "Nordrhein-Westfalen",
        "Rheinland-Pfalz",
        "Saarland",
        "Sachsen",
        "Sachsen-Anhalt",
        "Schleswig-Holstein",
        "Thüringen",
    ]

    def __init__(self):
        """Initialize the REWE scraper."""
        super().__init__(chain_id="rewe", chain_name="REWE")

    def scrape(self) -> List[Store]:
        """
        Scrape all REWE stores using state-based marketSearch API.

        This method:
        1. Loops through all German states (Bundesländer)
        2. For each state, paginates through all stores
        3. Enriches store data with coordinates from wksmarketsearch API

        Returns:
            List of Store objects
        """
        logger.info(f"Scraping {self.chain_name} stores using state-based search...")

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'de-DE,de;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Content-Type': 'application/json',
        }

        stores = []
        seen_ids = set()

        # Process each state
        for state in self.GERMAN_STATES:
            logger.info(f"Processing state: {state}")
            state_stores = self._scrape_state(state, headers, seen_ids)
            stores.extend(state_stores)

            # Small delay between states to avoid rate limiting
            time.sleep(0.5)

        logger.info(f"Successfully scraped {len(stores)} unique stores from {len(self.GERMAN_STATES)} states")

        # Filter for German stores only
        return self.filter_country(stores, 'DE')

    def _scrape_state(self, state: str, headers: Dict, seen_ids: set) -> List[Store]:
        """
        Scrape all stores for a specific German state.

        Args:
            state: Name of the German state (e.g., "Bayern")
            headers: HTTP headers for requests
            seen_ids: Set of already-seen store IDs for deduplication

        Returns:
            List of Store objects for this state
        """
        stores = []
        page = 0
        page_size = 100  # Get many stores per request

        while True:
            try:
                # Request stores for this state
                payload = {
                    "searchTerm": "",
                    "page": page,
                    "pageSize": page_size,
                    "onlyPickup": False,
                    "lat": None,
                    "lon": None,
                    "city": None,
                    "state": state
                }

                response = requests.post(
                    self.MARKET_SEARCH_URL,
                    json=payload,
                    headers=headers,
                    impersonate='chrome120',
                    timeout=30
                )

                if response.status_code != 200:
                    logger.warning(f"Failed to fetch page {page} for {state}: HTTP {response.status_code}")
                    break

                data = response.json()
                markets = data.get('markets', [])
                total_hits = data.get('totalHits', 0)

                if not markets:
                    # No more stores on this page
                    break

                logger.info(f"  Page {page}: {len(markets)} stores (total: {total_hits})")

                # Process each market
                for market in markets:
                    store_id = market.get('wwIdent')

                    # Skip duplicates
                    if store_id in seen_ids:
                        continue

                    seen_ids.add(store_id)

                    # Parse market data
                    store = self._parse_market_search(market)
                    if store:
                        # Enrich with coordinates
                        store = self._enrich_with_coordinates(store, headers)
                        if self.validate_store(store):
                            stores.append(store)

                # Check if we've retrieved all stores
                if len(markets) < page_size:
                    # Last page
                    break

                page += 1

                # Small delay between pages
                time.sleep(0.2)

            except Exception as e:
                logger.error(f"Error scraping page {page} for state {state}: {e}", exc_info=True)
                break

        logger.info(f"  Found {len(stores)} unique stores in {state}")
        return stores

    def _parse_market_search(self, market: Dict) -> Optional[Store]:
        """
        Parse a market from marketSearch API response.

        Args:
            market: Market data from marketSearch API

        Returns:
            Store object (without coordinates) or None
        """
        try:
            ww_ident = market.get('wwIdent', '')
            market_name = market.get('marketName', '')
            company_name = market.get('companyName', '')
            street = market.get('street', '')
            zip_code = market.get('zipCode', '')
            city = market.get('city', '')

            # Build full store name
            if company_name and company_name != market_name:
                full_name = f"{market_name} ({company_name})"
            else:
                full_name = market_name

            store = Store(
                chain_id=self.chain_id,
                store_id=ww_ident,
                name=full_name,
                street=street,
                postal_code=zip_code,
                city=city,
                country_code='DE',  # REWE is Germany-only
                latitude=None,  # Will be enriched later
                longitude=None,
            )

            return store

        except Exception as e:
            logger.error(f"Error parsing market {market.get('wwIdent', 'unknown')}: {e}")
            return None

    def _enrich_with_coordinates(self, store: Store, headers: Dict) -> Store:
        """
        Enrich store data with coordinates using wksmarketsearch API.

        Args:
            store: Store object without coordinates
            headers: HTTP headers for requests

        Returns:
            Store object with coordinates
        """
        try:
            # Search by postal code to get detailed market info with coordinates
            response = requests.get(
                self.MARKET_DETAILS_URL,
                params={'searchTerm': store.postal_code},
                headers=headers,
                impersonate='chrome120',
                timeout=30
            )

            if response.status_code != 200:
                logger.warning(f"Failed to get coordinates for {store.name}")
                return store

            data = response.json()
            markets = data.get('markets', [])

            # Find the matching store by ID
            for market in markets:
                if market.get('wwIdent') == store.store_id:
                    # Extract coordinates
                    location = market.get('location', {})
                    latitude = location.get('latitude')
                    longitude = location.get('longitude')

                    if latitude and longitude:
                        store.latitude = latitude
                        store.longitude = longitude

                    # Also extract opening hours
                    opening_hours = self._parse_opening_hours(market.get('openingInfo', []))
                    if opening_hours:
                        store.opening_hours = opening_hours

                    break

        except Exception as e:
            logger.debug(f"Failed to enrich coordinates for {store.name}: {e}")

        return store

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
