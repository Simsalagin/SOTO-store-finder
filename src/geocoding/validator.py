"""Coordinate validation using reverse geocoding and distance checks."""

import time
import logging
from typing import Optional, Tuple, Dict
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import os

logger = logging.getLogger(__name__)


class CoordinateValidator:
    """Validate coordinates using reverse geocoding and plausibility checks."""

    def __init__(self, user_agent: Optional[str] = None, delay: float = 1.0):
        """
        Initialize the validator.

        Args:
            user_agent: User agent for Nominatim requests
            delay: Delay between requests in seconds
        """
        if user_agent is None:
            user_agent = os.getenv('GEOCODING_USER_AGENT', 'SOTO-Store-Finder/1.0')

        self.geolocator = Nominatim(user_agent=user_agent)
        self.delay = delay
        self.last_request_time = 0

        # Country bounding boxes for basic validation (Germany)
        self.country_bounds = {
            'DE': {
                'lat_min': 47.27,
                'lat_max': 55.06,
                'lon_min': 5.87,
                'lon_max': 15.04
            }
        }

    def validate_coordinates(
        self,
        latitude: float,
        longitude: float,
        street: str,
        postal_code: str,
        city: str,
        country_code: str = 'DE',
        max_distance_km: float = 50.0
    ) -> Dict:
        """
        Validate coordinates by reverse geocoding and distance check.

        Args:
            latitude: Latitude to validate
            longitude: Longitude to validate
            street: Expected street
            postal_code: Expected postal code
            city: Expected city
            country_code: Expected country code
            max_distance_km: Maximum acceptable distance from reverse geocoded location

        Returns:
            Dictionary with validation results:
            {
                'valid': bool,
                'confidence': float (0-1),
                'issues': List[str],
                'reverse_geocoded_address': Optional[str],
                'distance_km': Optional[float],
                'suggested_coords': Optional[Tuple[float, float]]
            }
        """
        result = {
            'valid': True,
            'confidence': 1.0,
            'issues': [],
            'reverse_geocoded_address': None,
            'distance_km': None,
            'suggested_coords': None
        }

        # Check 1: Not (0, 0) or null island vicinity
        if self._is_null_island(latitude, longitude):
            result['valid'] = False
            result['confidence'] = 0.0
            result['issues'].append('Coordinates are at or near (0, 0) - "Null Island"')
            return result

        # Check 2: Country bounding box
        if not self._is_in_country_bounds(latitude, longitude, country_code):
            result['valid'] = False
            result['confidence'] = 0.0
            result['issues'].append(f'Coordinates outside {country_code} boundaries')

        # Check 3: Reverse geocode and compare
        reverse_result = self._reverse_geocode(latitude, longitude, country_code)

        if reverse_result:
            result['reverse_geocoded_address'] = reverse_result['address']

            # Compare postal codes
            if reverse_result.get('postal_code'):
                if reverse_result['postal_code'] != postal_code:
                    result['confidence'] *= 0.5
                    result['issues'].append(
                        f"Postal code mismatch: expected {postal_code}, "
                        f"got {reverse_result['postal_code']}"
                    )

            # Compare cities (fuzzy match)
            if reverse_result.get('city'):
                if not self._cities_match(reverse_result['city'], city):
                    result['confidence'] *= 0.7
                    result['issues'].append(
                        f"City mismatch: expected {city}, "
                        f"got {reverse_result['city']}"
                    )

            # Calculate distance between original and reverse geocoded coords
            if reverse_result.get('coords'):
                distance = geodesic(
                    (latitude, longitude),
                    reverse_result['coords']
                ).kilometers
                result['distance_km'] = distance

                if distance > max_distance_km:
                    result['valid'] = False
                    result['confidence'] *= 0.3
                    result['issues'].append(
                        f"Distance {distance:.1f}km exceeds maximum {max_distance_km}km"
                    )
        else:
            result['confidence'] *= 0.5
            result['issues'].append('Reverse geocoding failed - unable to verify location')

        # Final validation decision
        if result['confidence'] < 0.5:
            result['valid'] = False

        return result

    def validate_and_fix(
        self,
        latitude: float,
        longitude: float,
        street: str,
        postal_code: str,
        city: str,
        country_code: str = 'DE'
    ) -> Tuple[float, float, bool]:
        """
        Validate coordinates and attempt to fix if invalid.

        Args:
            latitude: Original latitude
            longitude: Original longitude
            street: Street address
            postal_code: Postal code
            city: City name
            country_code: Country code

        Returns:
            Tuple of (validated_lat, validated_lon, was_fixed)
        """
        # First validate existing coordinates
        validation = self.validate_coordinates(
            latitude, longitude, street, postal_code, city, country_code
        )

        # If valid and high confidence, return original
        if validation['valid'] and validation['confidence'] > 0.7:
            return (latitude, longitude, False)

        # If invalid or low confidence, geocode the address
        from .geocoder import Geocoder
        geocoder = Geocoder(delay=self.delay)

        new_coords = geocoder.geocode_address(street, postal_code, city, country_code)

        if new_coords:
            # Validate the new coordinates
            new_validation = self.validate_coordinates(
                new_coords[0], new_coords[1],
                street, postal_code, city, country_code
            )

            if new_validation['valid'] and new_validation['confidence'] > validation['confidence']:
                return (new_coords[0], new_coords[1], True)

        # If nothing better found, return original
        return (latitude, longitude, False)

    def _is_null_island(self, latitude: float, longitude: float, threshold: float = 1.0) -> bool:
        """Check if coordinates are at or very near (0, 0)."""
        return abs(latitude) < threshold and abs(longitude) < threshold

    def _is_in_country_bounds(self, latitude: float, longitude: float, country_code: str) -> bool:
        """Check if coordinates are within country bounding box."""
        bounds = self.country_bounds.get(country_code)
        if not bounds:
            return True  # Unknown country, can't validate

        return (
            bounds['lat_min'] <= latitude <= bounds['lat_max'] and
            bounds['lon_min'] <= longitude <= bounds['lon_max']
        )

    def _reverse_geocode(
        self,
        latitude: float,
        longitude: float,
        country_code: str
    ) -> Optional[Dict]:
        """
        Reverse geocode coordinates to get address.

        Returns:
            Dictionary with address components or None
        """
        self._wait_if_needed()

        try:
            location = self.geolocator.reverse(
                (latitude, longitude),
                exactly_one=True,
                timeout=10,
                language='de'
            )

            if location and location.raw:
                address = location.raw.get('address', {})

                return {
                    'address': location.address,
                    'postal_code': address.get('postcode'),
                    'city': address.get('city') or address.get('town') or address.get('village'),
                    'country_code': address.get('country_code', '').upper(),
                    'coords': (location.latitude, location.longitude)
                }

            return None

        except (GeocoderTimedOut, GeocoderServiceError) as e:
            logger.warning(f"Reverse geocoding error for ({latitude}, {longitude}): {e}")
            return None

    def _cities_match(self, city1: str, city2: str) -> bool:
        """Fuzzy match city names."""
        c1 = city1.lower().strip()
        c2 = city2.lower().strip()

        # Exact match
        if c1 == c2:
            return True

        # One contains the other
        if c1 in c2 or c2 in c1:
            return True

        return False

    def _wait_if_needed(self):
        """Ensure rate limiting delay is respected."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time

        if time_since_last < self.delay:
            time.sleep(self.delay - time_since_last)

        self.last_request_time = time.time()
