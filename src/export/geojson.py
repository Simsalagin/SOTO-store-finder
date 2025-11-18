"""Export store data to GeoJSON format for map visualization."""

import json
from typing import List, Dict, Optional
from ..storage.database import Database, StoreModel


class GeoJSONExporter:
    """Export store data to GeoJSON format."""

    def __init__(self, database: Database):
        """
        Initialize the GeoJSON exporter.

        Args:
            database: Database instance
        """
        self.database = database

    def export_stores(
        self,
        chain_id: Optional[str] = None,
        city: Optional[str] = None,
        output_file: Optional[str] = None
    ) -> Dict:
        """
        Export stores to GeoJSON format.

        Args:
            chain_id: Filter by chain ID
            city: Filter by city
            output_file: Optional file path to save GeoJSON

        Returns:
            GeoJSON dictionary
        """
        stores = self.database.get_stores(chain_id=chain_id, city=city)
        geojson = self._create_geojson(stores)

        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(geojson, f, ensure_ascii=False, indent=2)

        return geojson

    def _create_geojson(self, stores: List[StoreModel]) -> Dict:
        """
        Create GeoJSON FeatureCollection from stores.

        Only includes stores with SOTO products (has_soto_products=True).

        Args:
            stores: List of StoreModel objects

        Returns:
            GeoJSON FeatureCollection dictionary
        """
        features = []

        for store in stores:
            # Skip stores without coordinates
            if store.latitude is None or store.longitude is None:
                continue

            # IMPORTANT: Only include stores with SOTO products
            if store.has_soto_products is not True:
                continue

            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [store.longitude, store.latitude]
                },
                "properties": {
                    "id": store.id,
                    "chain_id": store.chain_id,
                    "store_id": store.store_id,
                    "name": store.name,
                    "street": store.street,
                    "postal_code": store.postal_code,
                    "city": store.city,
                    "country_code": store.country_code,
                    "phone": store.phone,
                    "email": store.email,
                    "website": store.website,
                    "opening_hours": store.opening_hours,
                    "services": store.services,
                    "address": f"{store.street}, {store.postal_code} {store.city}",
                }
            }

            features.append(feature)

        geojson = {
            "type": "FeatureCollection",
            "features": features
        }

        return geojson

    def get_bounds(self, chain_id: Optional[str] = None) -> Optional[Dict]:
        """
        Get bounding box for stores.

        Args:
            chain_id: Filter by chain ID

        Returns:
            Dictionary with bounds (south, west, north, east)
        """
        stores = self.database.get_stores(chain_id=chain_id)

        lats = [s.latitude for s in stores if s.latitude is not None]
        lons = [s.longitude for s in stores if s.longitude is not None]

        if not lats or not lons:
            return None

        return {
            "south": min(lats),
            "west": min(lons),
            "north": max(lats),
            "east": max(lons)
        }
