#!/usr/bin/env python3
"""
REWE SOTO Bio Query Solution
Uses "SOTO Bio" query for more accurate market-specific results
"""

import json
import time
from typing import Dict, Optional
from pathlib import Path
from datetime import datetime

try:
    from curl_cffi import requests
except ImportError:
    print("❌ curl_cffi not installed. Run: pip install curl_cffi")
    exit(1)


class REWESOTOBioScraper:
    """Uses 'SOTO Bio' query for improved accuracy"""

    BASE_URL = "https://www.rewe.de"

    def __init__(self):
        self.session = None
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'de-DE,de;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': 'https://www.rewe.de/shop/',
            'Origin': 'https://www.rewe.de',
        }
        self.results = []

    def _get_session(self):
        """Get or create curl_cffi session"""
        if not self.session:
            self.session = requests.Session()
        return self.session

    def find_market_by_address(self, city: str, street: str = None, postal_code: str = None) -> Optional[Dict]:
        """Find REWE market by address"""
        print(f"\n🔍 Searching for REWE market in {city}...")

        search_term = postal_code if postal_code else city

        try:
            session = self._get_session()
            url = f"{self.BASE_URL}/api/wksmarketsearch"
            response = session.get(
                url,
                params={'searchTerm': search_term},
                headers=self.headers,
                impersonate="chrome120",
                timeout=30
            )

            if response.status_code != 200:
                return None

            data = response.json()
            if 'markets' not in data or len(data['markets']) == 0:
                return None

            if street:
                for market in data['markets']:
                    market_street = market.get('address', {}).get('street', '')
                    if street.lower() in market_street.lower():
                        print(f"   ✅ {market.get('name')} (ID: {market.get('wwIdent')})")
                        return market

            market = data['markets'][0]
            print(f"   ✅ {market.get('name')} (ID: {market.get('wwIdent')})")
            return market

        except Exception as e:
            print(f"   ❌ Error: {e}")
            return None

    def select_market(self, ww_ident: str) -> bool:
        """Select a REWE market for the session"""
        print(f"\n📍 Selecting market {ww_ident}...")

        try:
            session = self._get_session()
            url = f"{self.BASE_URL}/api/wksmarketselection/userselections"

            response = session.post(
                url,
                json={
                    'selectedService': 'STATIONARY',
                    'customerZipCode': None,
                    'wwIdent': ww_ident
                },
                headers=self.headers,
                impersonate="chrome120",
                timeout=30
            )

            if response.status_code == 201:
                print(f"   ✅ Market selected")
                return True
            return False

        except Exception as e:
            print(f"   ❌ Error: {e}")
            return False

    def check_product_count(self, query: str) -> int:
        """Get product count for specific query"""
        try:
            session = self._get_session()
            count_url = f"{self.BASE_URL}/api/stationary-product-search/products/count"
            response = session.get(
                count_url,
                params={'query': query},
                headers=self.headers,
                impersonate="chrome120",
                timeout=30
            )

            if response.status_code == 200:
                return response.json().get('totalHits', 0)
            return 0
        except:
            return 0

    def check_store_availability(
        self,
        store_name: str,
        city: str,
        street: str = None,
        postal_code: str = None
    ) -> Dict:
        """
        Check SOTO product availability using 'SOTO Bio' query

        Args:
            store_name: Store name
            city: City name
            street: Street name (optional)
            postal_code: Postal code (optional)

        Returns:
            dict: Store results with availability
        """
        print(f"\n{'='*80}")
        print(f"🏪 {store_name}")
        print(f"📍 {street}, {postal_code} {city}")
        print(f"{'='*80}")

        result = {
            'store_name': store_name,
            'city': city,
            'street': street,
            'postal_code': postal_code,
            'timestamp': datetime.now().isoformat(),
            'success': False,
            'market_id': None,
        }

        # Find and select market
        market = self.find_market_by_address(city, street, postal_code)
        if not market:
            result['error'] = "Market not found"
            return result

        result['market_id'] = market.get('wwIdent')
        result['market_name'] = market.get('name')

        if not self.select_market(result['market_id']):
            result['error'] = "Market selection failed"
            return result

        time.sleep(1)

        # Check with different queries for comparison
        print(f"\n📊 Query Comparison:")
        queries = {
            'SOTO': self.check_product_count('SOTO'),
            'SOTO Bio': self.check_product_count('SOTO Bio'),
            'soto': self.check_product_count('soto'),
        }

        for query, count in queries.items():
            print(f"   '{query}': {count} products")

        # Use 'SOTO Bio' as primary method
        soto_bio_count = queries['SOTO Bio']

        result['success'] = True
        result['available'] = soto_bio_count > 0
        result['product_count'] = soto_bio_count
        result['query_comparison'] = queries

        # Summary
        print(f"\n{'─'*80}")
        print("📋 RESULT")
        print(f"{'─'*80}")

        if result['available']:
            print(f"✅ SOTO Bio products AVAILABLE")
            print(f"   Count: {soto_bio_count} products")

            # Show which query method was used
            if queries['SOTO Bio'] != queries['SOTO']:
                diff = abs(queries['SOTO Bio'] - queries['SOTO'])
                print(f"   ℹ️  'SOTO Bio' query differs from 'SOTO' by {diff}")
        else:
            print(f"❌ No SOTO products at this location")

        self.results.append(result)
        return result

    def save_results(self, filename: str = None):
        """Save results to JSON file"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"rewe_soto_bio_{timestamp}.json"

        output_dir = Path(__file__).parent.parent / 'data'
        output_dir.mkdir(exist_ok=True)
        output_file = output_dir / filename

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)

        print(f"\n💾 Results saved to: {output_file}")
        return output_file

    def print_summary(self):
        """Print summary of all results"""
        print(f"\n{'='*80}")
        print("📊 SUMMARY - 'SOTO Bio' Query Method")
        print(f"{'='*80}\n")

        total_stores = len(self.results)
        stores_with_soto = sum(1 for r in self.results if r.get('available'))

        print(f"Stores checked: {total_stores}")
        print(f"With SOTO products: {stores_with_soto}")
        print(f"Without SOTO products: {total_stores - stores_with_soto}")

        print(f"\n{'─'*80}\n")

        for result in self.results:
            status = "✅" if result.get('available') else "❌"
            count = result.get('product_count', 0)

            print(f"{status} {result['store_name']}")
            print(f"   📍 {result.get('city')}")
            print(f"   Products: {count}")

            # Show query comparison
            if result.get('query_comparison'):
                comp = result['query_comparison']
                print(f"   Query comparison: SOTO={comp.get('SOTO', 0)}, SOTO Bio={comp.get('SOTO Bio', 0)}")

            print()


def main():
    """Main execution"""
    print(f"\n{'='*80}")
    print("🚀 REWE SOTO Bio Query Scraper")
    print("   Using 'SOTO Bio' for better accuracy")
    print(f"{'='*80}\n")

    scraper = REWESOTOBioScraper()

    # Test all 5 stores from documentation
    stores = [
        {
            'name': 'REWE Karsten Schmidt oHG',
            'street': 'Schönhauser Allee 80',
            'postal_code': '10439',
            'city': 'Berlin'
        },
        {
            'name': 'REWE Korbinian Röckenschuß oHG',
            'street': 'Sendlinger Straße 46',
            'postal_code': '80331',
            'city': 'München'
        },
        {
            'name': 'REWE Stanisic oHG',
            'street': 'Münchner Str. 32',
            'postal_code': '85354',
            'city': 'Freising'
        },
        {
            'name': 'REWE Markt GmbH',
            'street': 'Kronenstr. 7',
            'postal_code': '70173',
            'city': 'Stuttgart'
        },
        {
            'name': 'REWE Markt GmbH',
            'street': 'Schleifmühleweg 36',
            'postal_code': '72070',
            'city': 'Tübingen'
        }
    ]

    for i, store in enumerate(stores, 1):
        print(f"\n{'#'*80}")
        print(f"# Store {i}/{len(stores)}")
        print(f"{'#'*80}")

        scraper.check_store_availability(
            store_name=store['name'],
            city=store['city'],
            street=store['street'],
            postal_code=store['postal_code']
        )

        if i < len(stores):
            print(f"\n⏳ Waiting 3 seconds...")
            time.sleep(3)

    scraper.print_summary()
    scraper.save_results()

    print(f"\n{'='*80}")
    print("✅ Complete!")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
