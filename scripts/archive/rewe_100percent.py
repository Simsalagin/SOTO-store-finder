#!/usr/bin/env python3
"""
REWE 100% Accuracy Investigation
Testing creative approaches for market-specific SOTO product validation
"""

import json
import time
from pathlib import Path
from datetime import datetime

try:
    from curl_cffi import requests
except ImportError:
    print("❌ curl_cffi not installed. Run: pip install curl_cffi")
    exit(1)


class REWE100PercentInvestigator:
    """Investigates methods to achieve 100% market-specific accuracy"""

    BASE_URL = "https://www.rewe.de"

    def __init__(self):
        self.session = requests.Session()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'de-DE,de;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': 'https://www.rewe.de/shop/',
            'Origin': 'https://www.rewe.de',
        }
        self.test_results = {}

    def setup_market(self, postal_code: str):
        """Setup test market"""
        print(f"\n🔧 Setting up market: {postal_code}")

        # Find market
        response = self.session.get(
            f"{self.BASE_URL}/api/wksmarketsearch",
            params={'searchTerm': postal_code},
            headers=self.headers,
            impersonate="chrome120",
            timeout=30
        )

        if response.status_code != 200:
            return None

        data = response.json()
        market = data['markets'][0]
        market_id = market.get('wwIdent')

        print(f"   ✅ Market: {market.get('name')} (ID: {market_id})")

        # Select market
        self.session.post(
            f"{self.BASE_URL}/api/wksmarketselection/userselections",
            json={
                'selectedService': 'STATIONARY',
                'customerZipCode': None,
                'wwIdent': market_id
            },
            headers=self.headers,
            impersonate="chrome120",
            timeout=30
        )

        time.sleep(1)
        return market

    def count_api(self, query: str) -> int:
        """Get count from Count API"""
        try:
            response = self.session.get(
                f"{self.BASE_URL}/api/stationary-product-search/products/count",
                params={'query': query},
                headers=self.headers,
                impersonate="chrome120",
                timeout=30
            )
            if response.status_code == 200:
                return response.json().get('totalHits', 0)
        except:
            pass
        return 0

    # ========================================================================
    # APPROACH 1: Query Difference Analysis
    # ========================================================================

    def approach_1_query_difference(self):
        """
        Use mathematical difference between queries to isolate SOTO products
        """
        print(f"\n{'='*80}")
        print("🧪 APPROACH 1: Query Difference Analysis")
        print(f"{'='*80}\n")

        print("Strategy: Use query combinations to mathematically isolate SOTO Bio products")

        queries = {
            'SOTO': self.count_api('SOTO'),
            'SOTO Bio': self.count_api('SOTO Bio'),
            'Bio': self.count_api('Bio'),
            'Risotto': self.count_api('Risotto'),
            'Soto': self.count_api('Soto'),  # lowercase
            'soto': self.count_api('soto'),  # all lowercase
        }

        print("\n📊 Query Results:")
        for query, count in queries.items():
            print(f"   '{query}': {count}")

        # Analysis
        print("\n🔍 Analysis:")

        # If SOTO Bio is close to SOTO, then most are Bio products
        if queries['SOTO Bio'] > 0:
            ratio = queries['SOTO Bio'] / max(queries['SOTO'], 1)
            print(f"   'SOTO Bio' / 'SOTO' ratio: {ratio:.2%}")

            if ratio > 0.8:
                print(f"   ✅ High confidence: Most SOTO results are Bio products")
                print(f"   Recommended count: {queries['SOTO Bio']}")
                return {
                    'success': True,
                    'method': 'soto_bio_query',
                    'count': queries['SOTO Bio'],
                    'confidence': 'high'
                }

        # Check if lowercase matters
        if queries['SOTO'] != queries['soto']:
            print(f"   ⚠️  Case sensitivity matters!")

        # Check for false positives
        risotto_in_soto = queries['Risotto'] > 0 and queries['SOTO'] > queries['SOTO Bio']
        if risotto_in_soto:
            print(f"   ⚠️  Possible 'Risotto' false positives detected")
            estimated = queries['SOTO'] - queries['Risotto']
            print(f"   Estimated SOTO products: {estimated}")

        return {
            'success': queries['SOTO Bio'] > 0,
            'method': 'query_difference',
            'queries': queries,
            'recommended_query': 'SOTO Bio'
        }

    # ========================================================================
    # APPROACH 2: Facet/Filter API Discovery
    # ========================================================================

    def approach_2_facet_discovery(self):
        """
        Try to discover facet/filter APIs that might be market-specific
        """
        print(f"\n{'='*80}")
        print("🧪 APPROACH 2: Facet/Filter API Discovery")
        print(f"{'='*80}\n")

        print("Testing: Various facet endpoints")

        # Test different facet endpoints
        facet_endpoints = [
            '/api/stationary-product-search/facets',
            '/api/stationary-product-search/filters',
            '/api/stationary-product-search/brands',
            '/api/stationary-product-search/categories',
            '/api/search/facets',
            '/api/facets',
        ]

        for endpoint in facet_endpoints:
            print(f"\n   Testing: {endpoint}")
            try:
                response = self.session.get(
                    f"{self.BASE_URL}{endpoint}",
                    params={'query': 'SOTO'},
                    headers=self.headers,
                    impersonate="chrome120",
                    timeout=30
                )

                if response.status_code == 200:
                    data = response.json()
                    print(f"   ✅ SUCCESS! Status: {response.status_code}")
                    print(f"   Keys: {list(data.keys())}")

                    # Save for analysis
                    output_dir = Path(__file__).parent.parent / 'data' / 'investigation'
                    output_dir.mkdir(parents=True, exist_ok=True)
                    with open(output_dir / f'facet_{endpoint.replace("/", "_")}.json', 'w') as f:
                        json.dump(data, f, indent=2)

                    return {'success': True, 'endpoint': endpoint, 'data': data}
                else:
                    print(f"   ❌ Status: {response.status_code}")

            except Exception as e:
                print(f"   ❌ Error: {e}")

            time.sleep(0.5)

        return {'success': False}

    # ========================================================================
    # APPROACH 3: Alternative Product Endpoints
    # ========================================================================

    def approach_3_alternative_endpoints(self):
        """
        Try alternative product listing endpoints that might be market-specific
        """
        print(f"\n{'='*80}")
        print("🧪 APPROACH 3: Alternative Product Endpoints")
        print(f"{'='*80}\n")

        print("Testing: Alternative product listing endpoints")

        endpoints = [
            # Different paths
            ('/api/products/search', {'q': 'SOTO'}),
            ('/api/search', {'query': 'SOTO'}),
            ('/api/stationary/search', {'query': 'SOTO'}),

            # With market parameter
            ('/api/stationary-product-search/products', {'query': 'SOTO', 'marketId': 'auto'}),

            # Pagination variants
            ('/api/stationary-product-search/products', {'query': 'SOTO', 'pageSize': 50}),

            # JSON endpoints
            ('/api/stationary-product-search/products.json', {'query': 'SOTO'}),
        ]

        for endpoint, params in endpoints:
            print(f"\n   Testing: {endpoint}")
            print(f"   Params: {params}")

            try:
                response = self.session.get(
                    f"{self.BASE_URL}{endpoint}",
                    params=params,
                    headers=self.headers,
                    impersonate="chrome120",
                    timeout=30
                )

                print(f"   Status: {response.status_code}")

                if response.status_code == 200:
                    try:
                        data = response.json()

                        # Check if response is different from standard
                        products_key = 'products' if 'products' in data else 'items'
                        if products_key in data:
                            count = len(data[products_key])
                            print(f"   ✅ Found {count} products")

                            # Check if any have availability info
                            if data[products_key]:
                                first = data[products_key][0]
                                if 'availability' in first or 'stock' in first:
                                    print(f"   🎯 HAS AVAILABILITY DATA!")
                                    return {
                                        'success': True,
                                        'endpoint': endpoint,
                                        'params': params,
                                        'count': count
                                    }

                    except:
                        pass

            except Exception as e:
                print(f"   ❌ Error: {e}")

            time.sleep(0.5)

        return {'success': False}

    # ========================================================================
    # APPROACH 4: Search with Page Parameter Manipulation
    # ========================================================================

    def approach_4_page_manipulation(self):
        """
        Test if different page sizes or parameters reveal market-specific data
        """
        print(f"\n{'='*80}")
        print("🧪 APPROACH 4: Page Parameter Manipulation")
        print(f"{'='*80}\n")

        print("Testing: Different page sizes and parameters")

        # Try to get ALL results with high page size
        page_sizes = [10, 20, 50, 100, 500]

        for size in page_sizes:
            print(f"\n   PageSize: {size}")

            try:
                response = self.session.get(
                    f"{self.BASE_URL}/api/stationary-product-search/products",
                    params={'query': 'SOTO', 'pageSize': size, 'page': 1},
                    headers=self.headers,
                    impersonate="chrome120",
                    timeout=30
                )

                if response.status_code == 200:
                    data = response.json()
                    products = data.get('products', [])
                    total_hits = data.get('totalHits', 0)

                    print(f"   Products returned: {len(products)}")
                    print(f"   Total hits: {total_hits}")

                    # Check if we got more products
                    if len(products) != 12:  # Different from standard
                        print(f"   🎯 DIFFERENT RESULT!")
                        return {
                            'success': True,
                            'method': 'page_size',
                            'page_size': size,
                            'count': len(products)
                        }

            except Exception as e:
                print(f"   ❌ Error: {e}")

            time.sleep(0.5)

        return {'success': False}

    # ========================================================================
    # APPROACH 5: POST vs GET methods
    # ========================================================================

    def approach_5_post_search(self):
        """
        Try POST requests instead of GET - might have different parameters
        """
        print(f"\n{'='*80}")
        print("🧪 APPROACH 5: POST Search Endpoints")
        print(f"{'='*80}\n")

        print("Testing: POST instead of GET for search")

        post_bodies = [
            {'query': 'SOTO', 'marketSpecific': True},
            {'query': 'SOTO', 'includeAvailability': True},
            {'searchTerm': 'SOTO', 'market': 'current'},
            {'q': 'SOTO', 'filters': {'brand': 'SOTO'}},
        ]

        endpoints = [
            '/api/stationary-product-search/products',
            '/api/search/products',
            '/api/products/search',
        ]

        for endpoint in endpoints:
            for body in post_bodies:
                print(f"\n   POST {endpoint}")
                print(f"   Body: {body}")

                try:
                    response = self.session.post(
                        f"{self.BASE_URL}{endpoint}",
                        json=body,
                        headers={**self.headers, 'Content-Type': 'application/json'},
                        impersonate="chrome120",
                        timeout=30
                    )

                    print(f"   Status: {response.status_code}")

                    if response.status_code == 200:
                        data = response.json()
                        print(f"   ✅ SUCCESS!")
                        print(f"   Keys: {list(data.keys())}")
                        return {'success': True, 'endpoint': endpoint, 'body': body}

                except Exception as e:
                    print(f"   ❌ Error: {e}")

                time.sleep(0.5)

        return {'success': False}

    # ========================================================================
    # APPROACH 6: Headers Manipulation
    # ========================================================================

    def approach_6_headers_manipulation(self):
        """
        Try different headers that might trigger market-specific responses
        """
        print(f"\n{'='*80}")
        print("🧪 APPROACH 6: Headers Manipulation")
        print(f"{'='*80}\n")

        print("Testing: Different header combinations")

        header_variants = [
            {'X-Market-Specific': 'true'},
            {'X-Include-Availability': 'true'},
            {'X-Filter-By-Market': 'true'},
            {'Accept': 'application/json;market-specific=true'},
        ]

        for variant in header_variants:
            print(f"\n   Testing headers: {variant}")

            try:
                response = self.session.get(
                    f"{self.BASE_URL}/api/stationary-product-search/products",
                    params={'query': 'SOTO'},
                    headers={**self.headers, **variant},
                    impersonate="chrome120",
                    timeout=30
                )

                if response.status_code == 200:
                    data = response.json()
                    products = data.get('products', [])

                    if len(products) != 12:
                        print(f"   🎯 DIFFERENT RESULT! Count: {len(products)}")
                        return {'success': True, 'headers': variant}

            except Exception as e:
                print(f"   ❌ Error: {e}")

            time.sleep(0.5)

        return {'success': False}

    # ========================================================================
    # Main Test Runner
    # ========================================================================

    def run_all_tests(self, postal_code="80331"):
        """Run all approaches"""
        print(f"\n{'#'*80}")
        print("# REWE 100% Accuracy Investigation")
        print("# Goal: Find market-specific product validation method")
        print(f"{'#'*80}\n")

        # Setup market
        market = self.setup_market(postal_code)
        if not market:
            print("❌ Failed to setup market")
            return

        # Run all approaches
        approaches = [
            ("Query Difference Analysis", self.approach_1_query_difference),
            ("Facet/Filter API Discovery", self.approach_2_facet_discovery),
            ("Alternative Product Endpoints", self.approach_3_alternative_endpoints),
            ("Page Parameter Manipulation", self.approach_4_page_manipulation),
            ("POST Search Endpoints", self.approach_5_post_search),
            ("Headers Manipulation", self.approach_6_headers_manipulation),
        ]

        results = {}

        for name, func in approaches:
            try:
                result = func()
                results[name] = result

                if result.get('success'):
                    print(f"\n✅ {name}: SUCCESS!")
                else:
                    print(f"\n❌ {name}: No solution found")

                time.sleep(2)

            except Exception as e:
                print(f"\n❌ {name}: Error - {e}")
                results[name] = {'success': False, 'error': str(e)}

        # Summary
        print(f"\n{'#'*80}")
        print("# SUMMARY")
        print(f"{'#'*80}\n")

        successful = [name for name, result in results.items() if result.get('success')]

        if successful:
            print(f"✅ Successful approaches ({len(successful)}):")
            for name in successful:
                print(f"\n   • {name}")
                result = results[name]
                for key, value in result.items():
                    if key != 'success' and key != 'data':
                        print(f"     {key}: {value}")
        else:
            print("❌ No successful approaches found")
            print("\n💡 Recommendation:")
            print("   1. Use 'SOTO Bio' query with Count API (best available)")
            print("   2. Manual browser network analysis needed")
            print("   3. Consider browser automation with Playwright")

        # Save results
        output_dir = Path(__file__).parent.parent / 'data' / 'investigation'
        output_dir.mkdir(parents=True, exist_ok=True)

        with open(output_dir / '100percent_investigation.json', 'w') as f:
            # Remove large data objects
            clean_results = {}
            for name, result in results.items():
                clean_results[name] = {k: v for k, v in result.items() if k != 'data'}

            json.dump({
                'timestamp': datetime.now().isoformat(),
                'market': postal_code,
                'results': clean_results,
                'successful': successful
            }, f, indent=2)

        print(f"\n💾 Results saved to investigation/100percent_investigation.json")


def main():
    investigator = REWE100PercentInvestigator()
    investigator.run_all_tests("80331")  # München


if __name__ == "__main__":
    main()
