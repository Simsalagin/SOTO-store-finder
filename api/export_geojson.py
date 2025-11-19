#!/usr/bin/env python3
"""
Export stores from SQLite database to GeoJSON format
"""

import sqlite3
import json
import os
from typing import List, Optional
from pathlib import Path

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'stores.db')
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), '..', 'frontend', 'stores.geojson')

def export_to_geojson():
    """Export all stores from database to GeoJSON file"""
    print("Exporting stores from database to GeoJSON...")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute('''
        SELECT * FROM stores
        WHERE has_soto_products = 1
        ORDER BY chain_id, city, name
    ''')

    features = []
    for row in cursor.fetchall():
        store = dict(row)

        # Parse JSON fields
        opening_hours = json.loads(store['opening_hours']) if store['opening_hours'] else None
        services = json.loads(store['services']) if store['services'] else []

        feature = {
            'type': 'Feature',
            'geometry': {
                'type': 'Point',
                'coordinates': [store['longitude'], store['latitude']]
            },
            'properties': {
                'id': store['id'],
                'chain_id': store['chain_id'],
                'store_id': store['store_id'],
                'name': store['name'],
                'street': store['street'],
                'postal_code': store['postal_code'],
                'city': store['city'],
                'country_code': store['country_code'],
                'phone': store['phone'],
                'email': store['email'],
                'website': store['website'],
                'opening_hours': opening_hours,
                'services': services,
                'has_soto_products': store['has_soto_products'],
                'address': f"{store['street']}, {store['postal_code']} {store['city']}"
            }
        }
        features.append(feature)

    conn.close()

    geojson = {
        'type': 'FeatureCollection',
        'features': features
    }

    # Write to file
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(geojson, f, ensure_ascii=False, indent=2)

    print(f"✓ Exported {len(features)} stores to {OUTPUT_PATH}")

    # Count by chain
    chain_counts = {}
    for feature in features:
        chain = feature['properties']['chain_id']
        chain_counts[chain] = chain_counts.get(chain, 0) + 1

    print("\nStores by chain:")
    for chain, count in sorted(chain_counts.items()):
        print(f"  - {chain}: {count}")


def store_to_geojson_feature(store) -> dict:
    """
    Convert a Store object to a GeoJSON feature.

    Args:
        store: Store object from src.scrapers.base

    Returns:
        GeoJSON feature dict
    """
    # Handle opening_hours and services
    opening_hours = store.opening_hours if store.opening_hours else None
    services = store.services if store.services else []

    feature = {
        'type': 'Feature',
        'geometry': {
            'type': 'Point',
            'coordinates': [store.longitude, store.latitude]  # [lon, lat] per GeoJSON spec
        },
        'properties': {
            'id': f"{store.chain_id}_{store.store_id}",
            'chain_id': store.chain_id,
            'store_id': store.store_id,
            'name': store.name,
            'street': store.street,
            'postal_code': store.postal_code,
            'city': store.city,
            'country_code': store.country_code,
            'phone': store.phone,
            'email': store.email,
            'website': store.website,
            'opening_hours': opening_hours,
            'services': services,
            'address': f"{store.street}, {store.postal_code} {store.city}"
        }
    }

    # Add has_soto_products if it's set
    if store.has_soto_products is not None:
        feature['properties']['has_soto_products'] = store.has_soto_products

    return feature


def update_geojson_incremental(
    new_stores: List,
    output_path: str = OUTPUT_PATH
) -> None:
    """
    Update GeoJSON file incrementally with new/updated stores.

    This function:
    1. Loads existing GeoJSON (if exists)
    2. Creates lookup dict by unique store key (chain_id + store_id)
    3. Upserts new stores (adds new, updates existing)
    4. Writes back to file

    Args:
        new_stores: List of Store objects to add/update
        output_path: Path to GeoJSON output file (default: frontend/stores.geojson)
    """
    # Ensure output directory exists
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    # Load existing GeoJSON or create new
    if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
        try:
            with open(output_path, 'r', encoding='utf-8') as f:
                geojson = json.load(f)
        except json.JSONDecodeError:
            # File exists but has invalid JSON, start fresh
            geojson = {
                'type': 'FeatureCollection',
                'features': []
            }
    else:
        geojson = {
            'type': 'FeatureCollection',
            'features': []
        }

    # Create lookup by unique store key (chain_id + store_id)
    existing_features = {
        f['properties']['id']: f  # id is "chain_id_store_id"
        for f in geojson['features']
    }

    # Upsert new stores
    for store in new_stores:
        feature = store_to_geojson_feature(store)
        # Use composite key (chain_id + store_id) for uniqueness
        unique_key = f"{store.chain_id}_{store.store_id}"
        existing_features[unique_key] = feature

    # Update features list (maintain all stores)
    geojson['features'] = list(existing_features.values())

    # Write back to file with proper formatting
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(geojson, f, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    export_to_geojson()
