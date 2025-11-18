#!/usr/bin/env python3
"""
REWE SOTO Food Products Scraper
Validates SOTO Bio food products (Edamame, Börek, Burger, etc.) vs false positives
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


class REWESOTOFoodScraper:
    """Scraper for SOTO Bio food products with brand validation"""

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
                print(f"   ❌ Market search failed: HTTP {response.status_code}")
                return None

            data = response.json()
            if 'markets' not in data or len(data['markets']) == 0:
                print(f"   ❌ No markets found for {search_term}")
                return None

            # Try to find exact match if street is provided
            if street:
                for market in data['markets']:
                    market_street = market.get('address', {}).get('street', '')
                    if street.lower() in market_street.lower():
                        print(f"   ✅ Found exact match: {market.get('name')} (ID: {market.get('wwIdent')})")
                        return market

            # Return first market
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
                print(f"   ✅ Market selected successfully")
                return True
            else:
                print(f"   ❌ Market selection failed: HTTP {response.status_code}")
                return False

        except Exception as e:
            print(f"   ❌ Error: {e}")
            return False

    def get_soto_products(self, query: str = "SOTO") -> List[Dict]:
        """
        Get SOTO Bio food products using Product List API with brand filtering

        Args:
            query: Search query (default: "SOTO")

        Returns:
            list: List of validated SOTO brand products
        """
        print(f"\n🔍 Fetching SOTO products...")

        try:
            session = self._get_session()
            url = f"{self.BASE_URL}/api/stationary-product-search/products"

            response = session.get(
                url,
                params={'query': query, 'page': 1},
                headers=self.headers,
                impersonate="chrome120",
                timeout=30
            )

            if response.status_code != 200:
                print(f"   ❌ API request failed: HTTP {response.status_code}")
                return []

            data = response.json()
            all_products = data.get('products', [])

            print(f"   ℹ️  Total search results: {len(all_products)}")

            # Filter by brand = "soto" (case-insensitive)
            soto_products = [
                p for p in all_products
                if p.get('brand', '').lower() == 'soto'
            ]

            print(f"   ✅ Validated SOTO brand products: {len(soto_products)}")

            # Show what was filtered out (false positives)
            false_positives = [
                p for p in all_products
                if p.get('brand', '').lower() != 'soto'
            ]

            if false_positives:
                print(f"   ℹ️  Filtered out {len(false_positives)} false positives:")
                for p in false_positives[:3]:
                    brand = p.get('brand', 'N/A')
                    title = p.get('title', 'N/A')
                    print(f"      • {title} (brand: {brand})")
                if len(false_positives) > 3:
                    print(f"      ... and {len(false_positives) - 3} more")

            # Show SOTO products found
            if soto_products:
                print(f"\n   📦 SOTO Bio products found:")
                for i, p in enumerate(soto_products[:5], 1):
                    print(f"      {i}. {p.get('title')}")
                if len(soto_products) > 5:
                    print(f"      ... and {len(soto_products) - 5} more")

            return soto_products

        except Exception as e:
            print(f"   ❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return []

    def check_product_count(self, query: str = "SOTO") -> int:
        """Get count from Count API for comparison"""
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
        Check SOTO Bio food product availability for a specific store

        Args:
            store_name: Store name
            city: City name
            street: Street name (optional)
            postal_code: Postal code (optional)

        Returns:
            dict: Store results with SOTO products
        """
        print(f"\n{'='*80}")
        print(f"🏪 Checking: {store_name}")
        print(f"📍 Location: {street}, {postal_code} {city}")
        print(f"{'='*80}")

        result = {
            'store_name': store_name,
            'city': city,
            'street': street,
            'postal_code': postal_code,
            'timestamp': datetime.now().isoformat(),
            'success': False,
            'market_id': None,
            'products': []
        }

        # Find market
        market = self.find_market_by_address(city, street, postal_code)
        if not market:
            result['error'] = "Market not found"
            return result

        result['market_id'] = market.get('wwIdent')
        result['market_name'] = market.get('name')
        result['market_address'] = market.get('address')

        # Select market
        if not self.select_market(result['market_id']):
            result['error'] = "Market selection failed"
            return result

        time.sleep(1)  # Let selection propagate

        # Compare Count API vs Product List API
        print(f"\n📊 API Comparison:")
        count_api_total = self.check_product_count("SOTO")
        print(f"   Count API (query='SOTO'): {count_api_total} products")

        # Get validated SOTO products
        soto_products = self.get_soto_products("SOTO")

        result['success'] = True
        result['count_api_total'] = count_api_total
        result['validated_soto_count'] = len(soto_products)
        result['available'] = len(soto_products) > 0
        result['products'] = [
            {
                'id': p.get('id'),
                'title': p.get('title'),
                'brand': p.get('brand'),
                'image': p.get('image'),
                'available_online': p.get('availableInOnlineShop', False)
            }
            for p in soto_products
        ]

        # Summary
        print(f"\n{'─'*80}")
        print("📋 SUMMARY")
        print(f"{'─'*80}")

        if result['available']:
            print(f"✅ SOTO Bio products available: {result['validated_soto_count']}")
            print(f"   Count API showed: {count_api_total} (includes false positives)")
            print(f"   False positives filtered: {count_api_total - result['validated_soto_count']}")
        else:
            print(f"❌ No SOTO Bio products available")

        self.results.append(result)
        return result

    def save_results(self, filename: str = None):
        """Save results to JSON file"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"rewe_soto_food_{timestamp}.json"

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
        print("📊 SUMMARY - ALL STORES")
        print(f"{'='*80}\n")

        total_stores = len(self.results)
        stores_with_soto = sum(1 for r in self.results if r.get('available'))
        total_products = sum(r.get('validated_soto_count', 0) for r in self.results)

        print(f"Stores checked: {total_stores}")
        print(f"Stores with SOTO products: {stores_with_soto}")
        print(f"Total SOTO products found: {total_products}")

        print(f"\n{'─'*80}\n")

        for result in self.results:
            status = "✅" if result.get('available') else "❌"
            count = result.get('validated_soto_count', 0)

            print(f"{status} {result['store_name']}")
            print(f"   📍 {result.get('city')}")

            if result.get('available'):
                print(f"   🛒 {count} SOTO products available")

                # Show top 3 products
                products = result.get('products', [])
                for i, p in enumerate(products[:3], 1):
                    print(f"      {i}. {p.get('title')}")
                if len(products) > 3:
                    print(f"      ... and {len(products) - 3} more")
            else:
                print(f"   ❌ No SOTO products")

            print()


def main():
    """Main execution - Test with sample stores"""
    print(f"\n{'='*80}")
    print("🚀 REWE SOTO Bio Food Products Checker")
    print("   Brand Validation Approach")
    print(f"{'='*80}\n")

    scraper = REWESOTOFoodScraper()

    # Test stores from documentation
    test_stores = [
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
        }
    ]

    # Check each store
    for i, store in enumerate(test_stores, 1):
        print(f"\n{'#'*80}")
        print(f"# Store {i}/{len(test_stores)}")
        print(f"{'#'*80}")

        scraper.check_store_availability(
            store_name=store['name'],
            city=store['city'],
            street=store['street'],
            postal_code=store['postal_code']
        )

        if i < len(test_stores):
            print(f"\n⏳ Waiting 3 seconds before next store...")
            time.sleep(3)

    # Print summary and save
    scraper.print_summary()
    scraper.save_results()

    print(f"\n{'='*80}")
    print("✅ All stores checked!")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
