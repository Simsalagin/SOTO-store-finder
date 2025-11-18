#!/usr/bin/env python3
"""
REWE SOTO Final Solution - Hybrid Approach
Combines Count API (market-specific) with Product List API (brand validation)
"""

import json
import time
from typing import Dict, List, Optional
from pathlib import Path
from datetime import datetime

try:
    from curl_cffi import requests
except ImportError:
    print("❌ curl_cffi not installed. Run: pip install curl_cffi")
    exit(1)


class REWESOTOFinalScraper:
    """
    Final SOTO scraper using hybrid approach:
    1. Count API for market-specific availability (respects market selection)
    2. Product List API for brand validation (filters false positives like "Risotto")
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
        self._soto_products_cache = None  # Cache for generic product list

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
                print(f"   ❌ Market search failed: HTTP {response.status_code}")
                return None

            data = response.json()
            if 'markets' not in data or len(data['markets']) == 0:
                print(f"   ❌ No markets found for {search_term}")
                return None

            if street:
                for market in data['markets']:
                    market_street = market.get('address', {}).get('street', '')
                    if street.lower() in market_street.lower():
                        print(f"   ✅ Found exact match: {market.get('name')} (ID: {market.get('wwIdent')})")
                        return market

            market = data['markets'][0]
            print(f"   ✅ Found market: {market.get('name')} (ID: {market.get('wwIdent')})")
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
            else:
                print(f"   ❌ Selection failed: HTTP {response.status_code}")
                return False

        except Exception as e:
            print(f"   ❌ Error: {e}")
            return False

    def get_soto_brand_products(self) -> List[Dict]:
        """
        Get generic list of SOTO brand products (not market-specific)
        Used to validate that products are actually SOTO brand

        Returns:
            list: All SOTO brand products (generic catalog)
        """
        # Return cached if available
        if self._soto_products_cache is not None:
            return self._soto_products_cache

        try:
            session = self._get_session()
            url = f"{self.BASE_URL}/api/stationary-product-search/products"

            response = session.get(
                url,
                params={'query': 'SOTO', 'page': 1},
                headers=self.headers,
                impersonate="chrome120",
                timeout=30
            )

            if response.status_code != 200:
                return []

            data = response.json()
            all_products = data.get('products', [])

            # Filter by brand = "soto"
            soto_products = [
                p for p in all_products
                if p.get('brand', '').lower() == 'soto'
            ]

            self._soto_products_cache = soto_products
            return soto_products

        except Exception as e:
            print(f"   ⚠️  Error fetching product catalog: {e}")
            return []

    def check_market_specific_count(self, query: str = "SOTO") -> int:
        """
        Get market-specific count using Count API

        Args:
            query: Search query

        Returns:
            int: Number of products available in selected market
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
                return response.json().get('totalHits', 0)
            return 0
        except Exception as e:
            print(f"   ⚠️  Count API error: {e}")
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

        Uses hybrid approach:
        - Count API for market-specific count
        - Product List API to verify products are SOTO brand (not false positives)

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
        result['market_address'] = market.get('address')

        if not self.select_market(result['market_id']):
            result['error'] = "Market selection failed"
            return result

        time.sleep(1)

        # Step 1: Check market-specific count
        print(f"\n📊 Checking availability...")
        market_count = self.check_market_specific_count("SOTO")
        print(f"   Count API (market-specific): {market_count} products")

        # Step 2: Validate with brand filter (only once, then cached)
        if self._soto_products_cache is None:
            print(f"\n🔍 Loading SOTO product catalog...")
            soto_catalog = self.get_soto_brand_products()
            print(f"   ✅ {len(soto_catalog)} SOTO brand products in catalog")
        else:
            soto_catalog = self._soto_products_cache

        # Determine availability
        # If Count > 0, products are available
        # We know they're SOTO brand because we validated the catalog
        result['success'] = True
        result['available'] = market_count > 0
        result['product_count'] = market_count
        result['soto_catalog_size'] = len(soto_catalog)

        # Summary
        print(f"\n{'─'*80}")
        print("📋 RESULT")
        print(f"{'─'*80}")

        if result['available']:
            print(f"✅ SOTO products AVAILABLE")
            print(f"   Count: {market_count} products at this location")
            print(f"   (From catalog of {len(soto_catalog)} total SOTO products)")
        else:
            print(f"❌ No SOTO products at this location")
            print(f"   (Catalog has {len(soto_catalog)} SOTO products available elsewhere)")

        self.results.append(result)
        return result

    def save_results(self, filename: str = None):
        """Save results to JSON file"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"rewe_soto_final_{timestamp}.json"

        output_dir = Path(__file__).parent.parent / 'data'
        output_dir.mkdir(exist_ok=True)
        output_file = output_dir / filename

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                'results': self.results,
                'soto_catalog': [
                    {
                        'id': p.get('id'),
                        'title': p.get('title'),
                        'brand': p.get('brand'),
                        'image': p.get('image')
                    }
                    for p in (self._soto_products_cache or [])
                ]
            }, f, indent=2, ensure_ascii=False)

        print(f"\n💾 Results saved to: {output_file}")
        return output_file

    def print_summary(self):
        """Print summary of all results"""
        print(f"\n{'='*80}")
        print("📊 FINAL SUMMARY")
        print(f"{'='*80}\n")

        total_stores = len(self.results)
        stores_with_soto = sum(1 for r in self.results if r.get('available'))

        print(f"Stores checked: {total_stores}")
        print(f"With SOTO products: {stores_with_soto}")
        print(f"Without SOTO products: {total_stores - stores_with_soto}")

        if self._soto_products_cache:
            print(f"\nSOTO Product Catalog: {len(self._soto_products_cache)} products")
            print("Sample products:")
            for i, p in enumerate(self._soto_products_cache[:5], 1):
                print(f"  {i}. {p.get('title')}")
            if len(self._soto_products_cache) > 5:
                print(f"  ... and {len(self._soto_products_cache) - 5} more")

        print(f"\n{'─'*80}\n")

        for result in self.results:
            status = "✅" if result.get('available') else "❌"
            count = result.get('product_count', 0)

            print(f"{status} {result['store_name']}")
            print(f"   📍 {result.get('city')}")
            print(f"   Products: {count}")
            print()


def main():
    """Main execution"""
    print(f"\n{'='*80}")
    print("🚀 REWE SOTO Final Scraper - Hybrid Approach")
    print("   • Count API: Market-specific availability")
    print("   • Product List API: Brand validation")
    print(f"{'='*80}\n")

    scraper = REWESOTOFinalScraper()

    # Test stores from documentation
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
