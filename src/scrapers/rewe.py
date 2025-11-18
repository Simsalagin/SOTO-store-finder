"""Scraper for REWE stores."""

import logging
import time
from typing import List, Optional, Dict
from .base import BaseScraper, Store

logger = logging.getLogger(__name__)

try:
    from curl_cffi import requests
    from curl_cffi.requests.exceptions import ConnectionError as CurlConnectionError
except ImportError:
    logger.error("curl_cffi not installed. Run: pip install curl_cffi")
    raise


class REWEScraper(BaseScraper):
    """Scraper for REWE stores using state-based marketSearch API."""

    MARKET_SEARCH_URL = "https://www.rewe.de/stationary-market-search-frontend/api/marketSearch"
    MARKET_DETAILS_URL = "https://www.rewe.de/api/wksmarketsearch"
    MARKET_SELECTION_URL = "https://www.rewe.de/api/wksmarketselection/userselections"
    PRODUCT_COUNT_URL = "https://www.rewe.de/api/stationary-product-search/products/count"

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

    def __init__(self, states: Optional[List[str]] = None, check_soto_availability: bool = False):
        """
        Initialize the REWE scraper.

        Args:
            states: Optional list of state names to scrape. If None, scrapes all states.
                   Example: ["Bayern", "Baden-Württemberg"]
            check_soto_availability: Whether to check SOTO product availability for each store.
                                    Adds significant time to scraping. Default: False.
        """
        super().__init__(chain_id="rewe", chain_name="REWE")
        self.states_to_scrape = states if states is not None else self.GERMAN_STATES
        self.check_soto_availability = check_soto_availability

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
        for state in self.states_to_scrape:
            logger.info(f"Processing state: {state}")
            state_stores = self._scrape_state(state, headers, seen_ids)
            stores.extend(state_stores)

            # Small delay between states to avoid rate limiting
            time.sleep(0.5)

        logger.info(f"Successfully scraped {len(stores)} unique stores from {len(self.states_to_scrape)} states")

        # Filter for German stores only
        return self.filter_country(stores, 'DE')

    def _scrape_state(self, state: str, headers: Dict, seen_ids: set) -> List[Store]:
        """
        Scrape all stores for a specific German state with retry logic.

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
            # Retry logic for this page
            success = False
            retry_count = 0
            max_retries = 3

            while not success and retry_count < max_retries:
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
                        retry_count += 1
                        if retry_count < max_retries:
                            wait_time = 2 ** retry_count  # Exponential backoff: 2, 4, 8 seconds
                            logger.info(f"  Retrying in {wait_time} seconds... (attempt {retry_count + 1}/{max_retries})")
                            time.sleep(wait_time)
                            continue
                        else:
                            break

                    data = response.json()
                    markets = data.get('markets', [])
                    total_hits = data.get('totalHits', 0)

                    if not markets:
                        # No more stores on this page
                        success = True
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
                            # Enrich with coordinates (with retry)
                            store = self._enrich_with_coordinates_retry(store, headers)

                            # Enrich with SOTO availability if enabled
                            if self.check_soto_availability:
                                store = self._enrich_with_soto_retry(store, headers)

                            if self.validate_store(store):
                                stores.append(store)

                    # Mark this page as successful
                    success = True

                    # Check if we've retrieved all stores (last page)
                    is_last_page = len(markets) < page_size

                    if not is_last_page:
                        # Move to next page
                        page += 1
                        # Small delay between pages
                        time.sleep(0.2)

                except CurlConnectionError as e:
                    retry_count += 1
                    if retry_count < max_retries:
                        wait_time = 2 ** retry_count  # Exponential backoff
                        logger.warning(f"  Connection error on page {page}: {e}")
                        logger.info(f"  Retrying in {wait_time} seconds... (attempt {retry_count + 1}/{max_retries})")
                        time.sleep(wait_time)
                    else:
                        logger.error(f"  Max retries reached for page {page} of {state}")
                        break

                except Exception as e:
                    logger.error(f"Error scraping page {page} for state {state}: {e}", exc_info=True)
                    retry_count += 1
                    if retry_count < max_retries:
                        wait_time = 2 ** retry_count
                        logger.info(f"  Retrying in {wait_time} seconds... (attempt {retry_count + 1}/{max_retries})")
                        time.sleep(wait_time)
                    else:
                        break

            # Check if we should stop pagination
            if not success:
                logger.warning(f"  Stopping pagination for {state} at page {page} due to errors")
                break

            # Check if this was the last page
            if 'is_last_page' in locals() and is_last_page:
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

    def _enrich_with_coordinates_retry(self, store: Store, headers: Dict, max_retries: int = 2) -> Store:
        """
        Enrich store data with coordinates using wksmarketsearch API with retry logic.

        Args:
            store: Store object without coordinates
            headers: HTTP headers for requests
            max_retries: Maximum number of retry attempts

        Returns:
            Store object with coordinates
        """
        for attempt in range(max_retries):
            try:
                return self._enrich_with_coordinates(store, headers)
            except CurlConnectionError as e:
                if attempt < max_retries - 1:
                    wait_time = 0.5 * (2 ** attempt)  # 0.5, 1 second
                    logger.debug(f"Connection error enriching {store.name}, retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    logger.debug(f"Failed to enrich coordinates for {store.name} after {max_retries} attempts")
                    return store
            except Exception as e:
                logger.debug(f"Failed to enrich coordinates for {store.name}: {e}")
                return store

        return store

    def _select_market(self, ww_ident: str, headers: Dict) -> bool:
        """
        Select a REWE market for the session.

        This is required before checking product availability.

        Args:
            ww_ident: Market identifier
            headers: HTTP headers for requests

        Returns:
            True if selection successful, False otherwise
        """
        try:
            payload = {
                'selectedService': 'STATIONARY',
                'customerZipCode': None,
                'wwIdent': ww_ident
            }

            response = requests.post(
                self.MARKET_SELECTION_URL,
                json=payload,
                headers=headers,
                impersonate='chrome120',
                timeout=30
            )

            return response.status_code == 201

        except Exception as e:
            logger.debug(f"Failed to select market {ww_ident}: {e}")
            return False

    def _check_soto_availability(self, headers: Dict) -> int:
        """
        Check SOTO product availability for the currently selected market.

        Uses exact search with quotes to avoid false positives.

        Args:
            headers: HTTP headers for requests

        Returns:
            Number of SOTO products found (0 if none)

        Raises:
            Exception: If API request fails (for retry logic)
        """
        response = requests.get(
            self.PRODUCT_COUNT_URL,
            params={'query': '"SOTO"'},  # Exact search with quotes
            headers=headers,
            impersonate='chrome120',
            timeout=30
        )

        if response.status_code == 200:
            count_data = response.json()
            return count_data.get('totalHits', 0)

        # Raise exception for non-200 responses to trigger retry
        raise Exception(f"API returned status {response.status_code}")

    def _enrich_with_soto(self, store: Store, headers: Dict) -> Store:
        """
        Enrich store with SOTO product availability information.

        Args:
            store: Store object to enrich
            headers: HTTP headers for requests

        Returns:
            Store object with has_soto_products field set

        Raises:
            Exception: If SOTO check fails (for retry logic)
        """
        # Select the market
        if not self._select_market(store.store_id, headers):
            logger.debug(f"Could not select market for {store.name}")
            store.has_soto_products = None
            return store

        # Small delay to let selection propagate
        time.sleep(0.5)

        # Check SOTO availability (may raise exception)
        product_count = self._check_soto_availability(headers)
        store.has_soto_products = product_count > 0

        logger.debug(
            f"{store.name}: {'has' if store.has_soto_products else 'no'} "
            f"SOTO products (count: {product_count})"
        )

        return store

    def _enrich_with_soto_retry(self, store: Store, headers: Dict, max_retries: int = 2) -> Store:
        """
        Enrich store with SOTO availability with retry logic.

        Args:
            store: Store object to enrich
            headers: HTTP headers for requests
            max_retries: Maximum number of retry attempts

        Returns:
            Store object with has_soto_products field set
        """
        last_exception = None

        for attempt in range(max_retries):
            try:
                return self._enrich_with_soto(store, headers)
            except (CurlConnectionError, Exception) as e:
                last_exception = e
                if attempt < max_retries - 1:
                    wait_time = 0.5 * (2 ** attempt)
                    logger.debug(f"Error checking SOTO for {store.name}, retrying in {wait_time}s... ({e})")
                    time.sleep(wait_time)
                else:
                    logger.debug(f"Failed to check SOTO for {store.name} after {max_retries} attempts: {e}")

        # All retries failed
        store.has_soto_products = None
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
