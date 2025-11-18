#!/usr/bin/env python3
"""
REWE SOTO Product Availability Scraper - Final Version
Uses Count API with exact search '"SOTO"' for accurate results
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


class REWESOTOScraper:
    """
    REWE SOTO scraper using Count API with exact search

    Method: Uses '"SOTO"' query (with quotes) for exact brand matching
    """

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

    def find_market_by_address(
        self,
        city: str,
        street: str = None,
        postal_code: str = None
    ) -> Optional[Dict]:
        """
        Find REWE market by address

        Args:
            city: City name
            street: Street name (optional)
            postal_code: Postal code (optional)

        Returns:
            dict: Market information or None
        """
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

            # Try to find exact match if street is provided
            if street:
                for market in data['markets']:
                    market_street = market.get('address', {}).get('street', '')
                    if street.lower() in market_street.lower():
                        return market

            # Return first market
            return data['markets'][0]

        except Exception as e:
            return None

    def select_market(self, ww_ident: str) -> bool:
        """
        Select a REWE market for the session

        Args:
            ww_ident: Market identifier

        Returns:
            bool: True if successful
        """
        try:
            session = self._get_session()
            url = f"{self.BASE_URL}/api/wksmarketselection/userselections"

            payload = {
                'selectedService': 'STATIONARY',
                'customerZipCode': None,
                'wwIdent': ww_ident
            }

            response = session.post(
                url,
                json=payload,
                headers=self.headers,
                impersonate="chrome120",
                timeout=30
            )

            return response.status_code == 201

        except Exception as e:
            return False

    def check_product_count(self, query: str = '"SOTO"') -> int:
        """
        Get product count using Count API

        Uses exact search with quotes to avoid false positives

        Args:
            query: Search query (default: '"SOTO"' with quotes)

        Returns:
            int: Number of products found
        """
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
                count_data = response.json()
                return count_data.get('totalHits', 0)

            return 0

        except Exception as e:
            return 0

    def check_store_availability(
        self,
        store_name: str,
        city: str,
        street: str = None,
        postal_code: str = None
    ) -> Dict:
        """
        Check SOTO product availability for a specific store

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

        # Find market
        print(f"\n🔍 Finding market...")
        market = self.find_market_by_address(city, street, postal_code)
        if not market:
            result['error'] = "Market not found"
            print(f"   ❌ Market not found")
            return result

        result['market_id'] = market.get('wwIdent')
        result['market_name'] = market.get('name')
        print(f"   ✅ {market.get('name')} (ID: {result['market_id']})")

        # Select market
        print(f"\n📍 Selecting market...")
        if not self.select_market(result['market_id']):
            result['error'] = "Market selection failed"
            print(f"   ❌ Selection failed")
            return result

        print(f"   ✅ Market selected")
        time.sleep(1)  # Let selection propagate

        # Check SOTO product availability with exact search
        print(f"\n📊 Checking availability...")
        print(f"   Query: '\"SOTO\"' (exact search)")

        product_count = self.check_product_count('"SOTO"')

        result['success'] = True
        result['available'] = product_count > 0
        result['product_count'] = product_count

        # Summary
        print(f"\n{'─'*80}")
        print("📋 RESULT")
        print(f"{'─'*80}")

        if result['available']:
            print(f"✅ SOTO products AVAILABLE")
            print(f"   Count: {product_count}")
        else:
            print(f"❌ No SOTO products at this location")

        self.results.append(result)
        return result

    def save_results(self, filename: str = None):
        """Save results to JSON file"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"rewe_soto_availability_{timestamp}.json"

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
        print("📊 SUMMARY")
        print(f"{'='*80}\n")

        total_stores = len(self.results)
        successful_stores = sum(1 for r in self.results if r['success'])
        stores_with_soto = sum(1 for r in self.results if r.get('available'))

        print(f"Stores checked: {total_stores}")
        print(f"Successful checks: {successful_stores}")
        print(f"With SOTO products: {stores_with_soto}")
        print(f"Without SOTO products: {successful_stores - stores_with_soto}")

        print(f"\n{'─'*80}\n")

        for result in self.results:
            if not result['success']:
                print(f"❌ {result['store_name']}")
                print(f"   📍 {result.get('city')}")
                print(f"   Error: {result.get('error', 'Unknown error')}")
            else:
                status = "✅" if result.get('available') else "❌"
                count = result.get('product_count', 0)

                print(f"{status} {result['store_name']}")
                print(f"   📍 {result.get('city')}")
                print(f"   Products: {count}")

            print()


def main():
    """Main execution"""
    print(f"\n{'='*80}")
    print("🚀 REWE SOTO Product Availability Checker")
    print("   Using exact search with Count API")
    print(f"{'='*80}\n")

    scraper = REWESOTOScraper()

    # List of stores to check (from original documentation)
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

    # Check each store
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

        # Delay between stores to avoid rate limiting
        if i < len(stores):
            print(f"\n⏳ Waiting 3 seconds...")
            time.sleep(3)

    # Print summary and save results
    scraper.print_summary()
    scraper.save_results()

    print(f"\n{'='*80}")
    print("✅ All stores checked!")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
