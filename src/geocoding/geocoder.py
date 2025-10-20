"""Geocoding functionality using OpenStreetMap Nominatim."""

import time
from typing import Optional, Tuple
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import os


class Geocoder:
    """Geocode addresses using OpenStreetMap Nominatim."""

    def __init__(self, user_agent: Optional[str] = None, delay: float = 1.0):
        """
        Initialize the geocoder.

        Args:
            user_agent: User agent for Nominatim requests
            delay: Delay between requests in seconds (Nominatim policy: max 1 req/sec)
        """
        if user_agent is None:
            user_agent = os.getenv('GEOCODING_USER_AGENT', 'SOTO-Store-Finder/1.0')

        self.geolocator = Nominatim(user_agent=user_agent)
        self.delay = delay
        self.last_request_time = 0

    def geocode_address(
        self,
        street: str,
        postal_code: str,
        city: str,
        country_code: str = 'DE'
    ) -> Optional[Tuple[float, float]]:
        """
        Geocode an address to latitude/longitude coordinates.

        Args:
            street: Street name and number
            postal_code: Postal code
            city: City name
            country_code: ISO country code (default: 'DE')

        Returns:
            Tuple of (latitude, longitude) or None if geocoding fails
        """
        # Respect rate limiting
        self._wait_if_needed()

        # Build query string
        query = f"{street}, {postal_code} {city}, {country_code}"

        try:
            location = self.geolocator.geocode(
                query,
                exactly_one=True,
                timeout=10,
                country_codes=[country_code.lower()]
            )

            if location:
                return (location.latitude, location.longitude)
            else:
                # Try without street number if full address fails
                return self._geocode_fallback(postal_code, city, country_code)

        except (GeocoderTimedOut, GeocoderServiceError) as e:
            print(f"Geocoding error for '{query}': {e}")
            return self._geocode_fallback(postal_code, city, country_code)

    def _geocode_fallback(
        self,
        postal_code: str,
        city: str,
        country_code: str
    ) -> Optional[Tuple[float, float]]:
        """
        Fallback geocoding using only postal code and city.

        Args:
            postal_code: Postal code
            city: City name
            country_code: ISO country code

        Returns:
            Tuple of (latitude, longitude) or None if geocoding fails
        """
        self._wait_if_needed()

        query = f"{postal_code} {city}, {country_code}"

        try:
            location = self.geolocator.geocode(
                query,
                exactly_one=True,
                timeout=10,
                country_codes=[country_code.lower()]
            )

            if location:
                return (location.latitude, location.longitude)
            else:
                return None

        except (GeocoderTimedOut, GeocoderServiceError) as e:
            print(f"Fallback geocoding error for '{query}': {e}")
            return None

    def _wait_if_needed(self):
        """Ensure rate limiting delay is respected."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time

        if time_since_last < self.delay:
            time.sleep(self.delay - time_since_last)

        self.last_request_time = time.time()
