#!/usr/bin/env python3
"""
Simple API server to serve stores from SQLite database
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import sqlite3
import json
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'stores.db')

class StoreAPIHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/api/stores':
            self.serve_stores()
        elif self.path == '/api/stores/geojson':
            self.serve_stores_geojson()
        else:
            self.send_error(404)

    def serve_stores(self):
        """Serve stores as JSON array"""
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
                SELECT * FROM stores ORDER BY chain_id, city, name
            ''')

            stores = []
            for row in cursor.fetchall():
                store = dict(row)

                # Parse JSON fields
                if store['opening_hours']:
                    store['opening_hours'] = json.loads(store['opening_hours'])
                if store['services']:
                    store['services'] = json.loads(store['services'])

                stores.append(store)

            conn.close()

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(stores, ensure_ascii=False).encode('utf-8'))

        except Exception as e:
            self.send_error(500, str(e))

    def serve_stores_geojson(self):
        """Serve stores as GeoJSON (compatible with existing frontend)"""
        try:
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
                        'country_code': store['country_code'],
                        'phone': store['phone'],
                        'email': store['email'],
                        'website': store['website'],
                        'opening_hours': opening_hours,
                        'services': services
                    }
                }
                features.append(feature)

            conn.close()

            geojson = {
                'type': 'FeatureCollection',
                'features': features
            }

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(geojson, ensure_ascii=False, indent=2).encode('utf-8'))

        except Exception as e:
            self.send_error(500, str(e))

    def log_message(self, format, *args):
        """Custom logging"""
        print(f"[{self.log_date_time_string()}] {format % args}")

def main():
    port = 8001
    server = HTTPServer(('localhost', port), StoreAPIHandler)
    print(f"✓ API Server running on http://localhost:{port}")
    print(f"  - Stores API: http://localhost:{port}/api/stores")
    print(f"  - GeoJSON API: http://localhost:{port}/api/stores/geojson")
    print("\nPress Ctrl+C to stop\n")
    server.serve_forever()

if __name__ == '__main__':
    main()
