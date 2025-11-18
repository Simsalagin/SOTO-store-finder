#!/usr/bin/env python3
"""
REWE SOTO Improved Scraper with Product Validation
Solves the false positive problem using query refinement approach
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


class REWEImprovedScraper:
    """
    Improved REWE scraper that distinguishes between:
    - SOTO outdoor products (kocher, brenner, camping gear)
    - SOTO food products (bio samosas, falafel, etc.)
    """

    BASE_URL = "https://www.rewe.de"

    # Product categories
    PRODUCT_CATEGORIES = {
        'outdoor': {
            'queries': ['SOTO kocher', 'SOTO outdoor', 'SOTO camping'],
            'description': 'SOTO Outdoor/Camping products (stoves, burners)'
        },
        'food': {
            'queries': ['SOTO bio'],
            'description': 'SOTO Food products (samosas, falafel, etc.)'
        }
    }

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
                count = response.json().get('totalHits', 0)
                return count
            return 0
        except Exception as e:
            print(f"   ❌ Error checking count for '{query}': {e}")
            return 0

    def check_availability_by_category(self, category: str = 'outdoor') -> Dict:
        """
        Check SOTO product availability for specific category

        Args:
            category: 'outdoor' or 'food'

        Returns:
            dict: Availability results with counts per query
        """
        if category not in self.PRODUCT_CATEGORIES:
            raise ValueError(f"Unknown category: {category}")

        cat_config = self.PRODUCT_CATEGORIES[category]
        queries = cat_config['queries']

        print(f"\n{'='*80}")
        print(f"🔍 Checking {category.upper()} products")
        print(f"   {cat_config['description']}")
        print(f"{'='*80}")

        query_results = {}
        total_count = 0

        for query in queries:
            print(f"\n📊 Query: '{query}'")
            count = self.check_product_count(query)
            print(f"   Count: {count}")

            query_results[query] = count
            total_count += count

        # Use maximum count as the likely true count (to avoid double-counting)
        max_count = max(query_results.values()) if query_results else 0

        # Determine availability
        available = max_count > 0

        result = {
            'category': category,
            'available': available,
            'max_count': max_count,  # Most reliable count
            'query_results': query_results,
            'description': cat_config['description']
        }

        if available:
            print(f"\n✅ {category.upper()} products available")
            print(f"   Estimated count: {max_count}")
        else:
            print(f"\n❌ No {category.upper()} products found")

        return result

    def check_store_availability(
        self,
        store_name: str,
        city: str,
        street: str = None,
        postal_code: str = None,
        categories: List[str] = ['outdoor']
    ) -> Dict:
        """
        Check SOTO product availability for specific store

        Args:
            store_name: Store name
            city: City name
            street: Street name (optional)
            postal_code: Postal code (optional)
            categories: List of categories to check ['outdoor', 'food']

        Returns:
            dict: Store results with availability per category
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
            'categories': {}
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

        # Check each category
        for category in categories:
            try:
                category_result = self.check_availability_by_category(category)
                result['categories'][category] = category_result
            except Exception as e:
                print(f"⚠️  Error checking {category}: {e}")
                result['categories'][category] = {
                    'available': False,
                    'error': str(e)
                }

        result['success'] = True

        # Summary
        print(f"\n{'─'*80}")
        print("📋 SUMMARY")
        print(f"{'─'*80}")

        for category, cat_result in result['categories'].items():
            status = "✅" if cat_result.get('available') else "❌"
            count = cat_result.get('max_count', 0)
            print(f"{status} {category.upper()}: {count} products")

        self.results.append(result)
        return result

    def save_results(self, filename: str = None):
        """Save results to JSON file"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"rewe_soto_improved_{timestamp}.json"

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

        for result in self.results:
            print(f"🏪 {result['store_name']}")
            print(f"   📍 {result.get('city')}")

            for category, cat_result in result.get('categories', {}).items():
                status = "✅" if cat_result.get('available') else "❌"
                count = cat_result.get('max_count', 0)
                print(f"   {status} {category.upper()}: {count} products")

            print()


def main():
    """Main execution - Test the improved scraper"""
    print(f"\n{'='*80}")
    print("🚀 REWE SOTO Improved Product Availability Checker")
    print("   Query Refinement Approach")
    print(f"{'='*80}\n")

    scraper = REWEImprovedScraper()

    # Test stores
    test_stores = [
        {
            'name': 'REWE München Sendlinger Tor',
            'street': 'Sendlinger Straße 46',
            'postal_code': '80331',
            'city': 'München'
        },
        {
            'name': 'REWE Freising',
            'street': 'Münchner Str. 32',
            'postal_code': '85354',
            'city': 'Freising'
        }
    ]

    # Check both outdoor and food products
    for i, store in enumerate(test_stores, 1):
        print(f"\n{'#'*80}")
        print(f"# Store {i}/{len(test_stores)}")
        print(f"{'#'*80}")

        scraper.check_store_availability(
            store_name=store['name'],
            city=store['city'],
            street=store['street'],
            postal_code=store['postal_code'],
            categories=['outdoor', 'food']  # Check both
        )

        if i < len(test_stores):
            print(f"\n⏳ Waiting 3 seconds before next store...")
            time.sleep(3)

    # Print summary and save
    scraper.print_summary()
    scraper.save_results()

    print(f"\n{'='*80}")
    print("✅ Testing complete!")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
