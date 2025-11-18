"""Scraper for Alnatura stores."""

import requests
from bs4 import BeautifulSoup
from typing import List, Optional, Dict
import re
import time
from .base import BaseScraper, Store


class AlnaturaScraper(BaseScraper):
    """Scraper for Alnatura stores."""

    SITEMAP_URL = "https://www.alnatura.de/sitemap.xml"
    BASE_URL = "https://www.alnatura.de"

    def __init__(self):
        """Initialize the Alnatura scraper."""
        super().__init__(chain_id="alnatura", chain_name="Alnatura")

    def scrape(self) -> List[Store]:
        """
        Scrape all Alnatura stores from their sitemap and individual pages.

        Returns:
            List of Store objects
        """
        # Get all city URLs from sitemap
        city_urls = self._get_market_urls()
        print(f"Found {len(city_urls)} city pages")

        # Get all individual store URLs from city pages
        all_store_urls = []
        for i, city_url in enumerate(city_urls, 1):
            if i % 10 == 0:
                print(f"Gathering store URLs: {i}/{len(city_urls)}")

            store_urls = self._get_store_urls_from_city_page(city_url)
            all_store_urls.extend(store_urls)
            time.sleep(0.3)

        print(f"Found {len(all_store_urls)} individual stores")

        # Scrape each individual store
        stores = []
        for i, url in enumerate(all_store_urls, 1):
            if i % 20 == 0:
                print(f"Scraping stores: {i}/{len(all_store_urls)}")

            store = self._scrape_store_detail_page(url)
            if store and self.validate_store(store):
                # Validate and fix coordinates
                store = self.validate_and_fix_coordinates(store)
                stores.append(store)

            time.sleep(0.5)

        # Filter for German stores only
        return self.filter_country(stores, 'DE')

    def _get_market_urls(self) -> List[str]:
        """
        Get all market page URLs from sitemap.

        Returns:
            List of market page URLs
        """
        response = requests.get(self.SITEMAP_URL, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'xml')
        locs = soup.find_all('loc')

        # Filter for actual store pages (marktseiten/)
        # Exclude sub-pages (those with "alnatura-super-natur-markt" in URL - these are individual store pages)
        market_urls = [
            loc.text for loc in locs
            if '/maerkte/marktseiten/' in loc.text
            and loc.text != f'{self.BASE_URL}/de-de/maerkte/marktseiten/'  # Exclude index page
            and 'alnatura-super-natur-markt' not in loc.text.lower()  # Exclude sub-pages
            and 'kaffee-to-go' not in loc.text.lower()  # Exclude coffee pages
            and 'belegte-broetchen' not in loc.text.lower()  # Exclude sandwich pages
        ]

        return market_urls

    def _get_store_urls_from_city_page(self, city_url: str) -> List[str]:
        """
        Get all individual store URLs from a city page.

        Args:
            city_url: City page URL

        Returns:
            List of store detail page URLs
        """
        try:
            response = requests.get(city_url, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # Find all store links
            store_links = soup.find_all('a', class_='content-teaser-list__item')

            store_urls = []
            for link in store_links:
                href = link.get('href')
                if href and '/maerkte/marktseiten/' in href:
                    full_url = f"{self.BASE_URL}{href}" if not href.startswith('http') else href
                    store_urls.append(full_url)

            return store_urls

        except Exception as e:
            print(f"Error getting store URLs from {city_url}: {e}")
            return []

    def _scrape_store_detail_page(self, url: str) -> Optional[Store]:
        """
        Scrape a single store detail page.

        Args:
            url: Store detail page URL

        Returns:
            Store object or None if parsing fails
        """
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # Extract store ID from URL
            store_id = url.rstrip('/').split('/')[-1]

            # Try JSON-LD first (Schema.org Store data)
            import json
            json_ld = soup.find('script', type='application/ld+json')
            if json_ld:
                try:
                    data = json.loads(json_ld.string)
                    if data.get('@type') == 'Store':
                        address = data.get('address', {})

                        # Extract opening hours from page text
                        opening_hours_text = self._extract_opening_hours_text(soup)

                        return Store(
                            chain_id=self.chain_id,
                            store_id=data.get('@id', store_id),
                            name=data.get('name', f"Alnatura {store_id}"),
                            street=address.get('streetAddress', ''),
                            postal_code=address.get('postalCode', ''),
                            city=address.get('addressLocality', ''),
                            country_code='DE',
                            latitude=float(data.get('geo', {}).get('latitude')) if data.get('geo') else None,
                            longitude=float(data.get('geo', {}).get('longitude')) if data.get('geo') else None,
                            phone=None,  # Don't show phone numbers
                            website=url,
                            opening_hours={'text': opening_hours_text} if opening_hours_text else None,
                has_soto_products=True,  # Alnatura carries SOTO products
                        )
                except:
                    pass  # Fall through to alternative method

            # Alternative: Extract from page text
            h1 = soup.find('h1')
            name = h1.get_text(strip=True) if h1 else f"Alnatura {store_id}"

            # Find address text (look for postal code pattern)
            postal_pattern = r'([^|\n]+)\s*\|\s*(\d{5})\s+([^|\n]+)'
            texts_with_postal = soup.find_all(string=re.compile(r'\d{5}'))

            address_data = None
            for text in texts_with_postal:
                text_str = text.strip()
                match = re.search(postal_pattern, text_str)
                if match:
                    address_data = {
                        'street': match.group(1).strip(),
                        'postal_code': match.group(2).strip(),
                        'city': match.group(3).strip(),
                    }
                    break

            if not address_data:
                print(f"Could not extract address from {url}")
                return None

            coords = self._extract_coordinates(soup)
            opening_hours_text = self._extract_opening_hours_text(soup)

            store = Store(
                chain_id=self.chain_id,
                store_id=store_id,
                name=name,
                street=address_data['street'],
                postal_code=address_data['postal_code'],
                city=address_data['city'],
                country_code='DE',
                latitude=coords[0] if coords else None,
                longitude=coords[1] if coords else None,
                phone=None,  # Don't show phone numbers
                website=url,
                opening_hours={'text': opening_hours_text} if opening_hours_text else None,
                has_soto_products=True,  # Alnatura carries SOTO products
            )

            return store

        except Exception as e:
            print(f"Error scraping {url}: {e}")
            return None

    def _scrape_market_page(self, url: str) -> Optional[Store]:
        """
        Scrape a single market page.

        Args:
            url: Market page URL

        Returns:
            Store object or None if parsing fails
        """
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # Extract store ID from URL (last part of path)
            store_id = url.rstrip('/').split('/')[-1]

            # Extract data from page
            name = self._extract_name(soup, store_id)
            address_data = self._extract_address(soup)

            if not address_data:
                print(f"Could not extract address from {url}")
                return None

            # Try to extract coordinates from Google Maps link
            coords = self._extract_coordinates(soup)

            # Extract contact info
            phone = self._extract_phone(soup)

            # Extract opening hours
            opening_hours = self._extract_opening_hours(soup)

            store = Store(
                chain_id=self.chain_id,
                store_id=store_id,
                name=name,
                street=address_data.get('street', ''),
                postal_code=address_data.get('postal_code', ''),
                city=address_data.get('city', ''),
                country_code='DE',  # Assuming Germany
                latitude=coords[0] if coords else None,
                longitude=coords[1] if coords else None,
                phone=phone,
                website=url,
                opening_hours=opening_hours,
            )

            return store

        except Exception as e:
            print(f"Error scraping {url}: {e}")
            return None

    def _extract_name(self, soup: BeautifulSoup, store_id: str) -> str:
        """Extract store name from page."""
        # Generate simple name from store_id (city name)
        city_name = store_id.replace('-', ' ').title()
        return f"Alnatura {city_name}"

    def _extract_address(self, soup: BeautifulSoup) -> Optional[Dict[str, str]]:
        """Extract address information from page."""
        # Look for text patterns that contain address
        # German postal code pattern: 5 digits
        postal_code_pattern = r'\b\d{5}\b'

        # Find all text that might contain address
        text_elements = soup.find_all(string=re.compile(postal_code_pattern))

        for elem in text_elements:
            text = elem.strip()
            # Look for pattern: Street Number, Postal Code City
            match = re.search(r'([^,\n]+),?\s*(\d{5})\s+([^,\n]+)', text)
            if match:
                street = match.group(1).strip().rstrip('|').strip()
                postal_code = match.group(2).strip()
                city = match.group(3).strip().rstrip('|').strip()
                return {
                    'street': street,
                    'postal_code': postal_code,
                    'city': city,
                }

        return None

    def _extract_coordinates(self, soup: BeautifulSoup) -> Optional[tuple]:
        """Extract coordinates from Google Maps link or embedded map."""
        # Look for Google Maps links
        maps_links = soup.find_all('a', href=re.compile(r'maps\.google|google\.com/maps'))

        for link in maps_links:
            href = link.get('href', '')
            # Extract coordinates from URL
            # Pattern: @lat,lon or q=lat,lon
            coord_match = re.search(r'[@q=](-?\d+\.\d+),(-?\d+\.\d+)', href)
            if coord_match:
                lat = float(coord_match.group(1))
                lon = float(coord_match.group(2))
                return (lat, lon)

        return None

    def _extract_phone(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract phone number from page."""
        tel_links = soup.find_all('a', href=re.compile(r'tel:'))
        if tel_links:
            # Get first phone number
            phone = tel_links[0].get('href', '').replace('tel:', '').strip()
            return phone if phone else None

        return None

    def _extract_opening_hours(self, soup: BeautifulSoup) -> Optional[Dict]:
        """Extract opening hours from page."""
        # This is complex and varies by page structure
        # For now, return None - can be enhanced later
        return None

    def _extract_opening_hours_text(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Extract opening hours as text from page.

        Returns:
            Opening hours string like "Mo-Sa 7-21 Uhr" or None
        """
        # Pattern for opening hours: Mo-Sa 7-21 Uhr, Mo-Fr 8-20 Uhr, etc.
        pattern = re.compile(r'(Mo|Di|Mi|Do|Fr|Sa|So).*?\d+[:-]\d+.*?Uhr', re.I)

        texts = soup.find_all(string=pattern)
        if texts:
            # Get first match and clean it up
            hours_text = texts[0].strip()
            # Clean up extra whitespace
            hours_text = ' '.join(hours_text.split())
            return hours_text

        return None
