#!/usr/bin/env python3
"""
Export stores from SQLite database to GeoJSON format
"""

import sqlite3
import json
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'stores.db')
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), '..', 'frontend', 'stores.geojson')

def export_to_geojson():
    """Export all stores from database to GeoJSON file"""
    print("Exporting stores from database to GeoJSON...")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute('''
        SELECT * FROM stores ORDER BY chain_id, city, name
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
                'district': store['district'],
                'country_code': store['country_code'],
                'phone': store['phone'],
                'email': store['email'],
                'website': store['website'],
                'opening_hours': opening_hours,
                'services': services,
                'address': store['address']
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

if __name__ == '__main__':
    export_to_geojson()
