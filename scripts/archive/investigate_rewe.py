#!/usr/bin/env python3
"""
Investigation script to find methods to validate SOTO products vs false positives
Testing multiple creative approaches to filter brand-specific products
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


class REWEInvestigator:
    """Investigates REWE APIs to find SOTO product validation methods"""

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
        self.test_market_id = None  # Will be set by setup

    def setup_test_market(self, postal_code="80331"):
        """Setup a test market for investigation"""
        print(f"\n{'='*80}")
        print("🔧 SETUP: Selecting test market")
        print(f"{'='*80}\n")

        # Find market
        print(f"🔍 Finding market in {postal_code}...")
        url = f"{self.BASE_URL}/api/wksmarketsearch"
        response = self.session.get(
            url,
            params={'searchTerm': postal_code},
            headers=self.headers,
            impersonate="chrome120",
            timeout=30
        )

        if response.status_code != 200:
            print(f"❌ Failed to find market: HTTP {response.status_code}")
            return False

        data = response.json()
        if not data.get('markets'):
            print("❌ No markets found")
            return False

        market = data['markets'][0]
        self.test_market_id = market.get('wwIdent')
        print(f"✅ Found: {market.get('name')} (ID: {self.test_market_id})")

        # Select market
        print(f"\n📍 Selecting market {self.test_market_id}...")
        select_url = f"{self.BASE_URL}/api/wksmarketselection/userselections"
        select_response = self.session.post(
            select_url,
            json={
                'selectedService': 'STATIONARY',
                'customerZipCode': None,
                'wwIdent': self.test_market_id
            },
            headers=self.headers,
            impersonate="chrome120",
            timeout=30
        )

        if select_response.status_code == 201:
            print("✅ Market selected successfully")
            time.sleep(1)  # Let selection propagate
            return True
        else:
            print(f"❌ Market selection failed: HTTP {select_response.status_code}")
            return False

    def save_response(self, name, data):
        """Save response data for analysis"""
        output_dir = Path(__file__).parent.parent / 'data' / 'investigation'
        output_dir.mkdir(parents=True, exist_ok=True)

        output_file = output_dir / f"{name}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"   💾 Saved to: {output_file}")
        return output_file

    # ============================================================================
    # APPROACH 1: Product List API with detailed analysis
    # ============================================================================

    def approach_1_product_list_api(self):
        """
        APPROACH 1: Analyze Product List API response structure
        Goal: Check if API returns brand/manufacturer info we can filter by
        """
        print(f"\n{'='*80}")
        print("🧪 APPROACH 1: Product List API with Brand Filtering")
        print(f"{'='*80}\n")

        print("Testing: /api/stationary-product-search/products")
        print("Hypothesis: API returns brand/manufacturer field we can filter")

        try:
            # Try different query parameters
            test_params = [
                {'query': 'SOTO'},
                {'query': 'SOTO', 'page': 1, 'pageSize': 50},
                {'query': 'SOTO', 'filters': 'brand:SOTO'},
                {'query': 'SOTO', 'brand': 'SOTO'},
                {'query': 'SOTO', 'facets': 'true'},
            ]

            for i, params in enumerate(test_params, 1):
                print(f"\n--- Test {i}: {params} ---")

                url = f"{self.BASE_URL}/api/stationary-product-search/products"
                response = self.session.get(
                    url,
                    params=params,
                    headers=self.headers,
                    impersonate="chrome120",
                    timeout=30
                )

                print(f"Status: {response.status_code}")

                if response.status_code == 200:
                    data = response.json()

                    # Save first response for detailed analysis
                    if i == 1:
                        self.save_response("approach_1_product_list", data)

                    # Analyze structure
                    print(f"Response keys: {list(data.keys())}")

                    # Try to extract products
                    products = self._extract_products(data)
                    print(f"Products found: {len(products)}")

                    if products:
                        # Analyze first product structure
                        first_product = products[0]
                        print(f"First product keys: {list(first_product.keys())}")

                        # Check for brand information
                        brand_fields = ['brand', 'manufacturer', 'brandName', 'producer', 'supplier']
                        found_brands = {field: first_product.get(field) for field in brand_fields if field in first_product}

                        if found_brands:
                            print(f"✅ Brand fields found: {found_brands}")

                            # Check all products for SOTO brand
                            soto_products = []
                            for product in products:
                                for field, value in found_brands.keys():
                                    if product.get(field) and 'SOTO' in str(product.get(field)).upper():
                                        soto_products.append(product)
                                        break

                            print(f"✅ SOTO products after brand filter: {len(soto_products)}")
                            return {'success': True, 'method': 'brand_filter', 'count': len(soto_products)}
                        else:
                            print("⚠️  No brand fields found in product structure")
                            # Show sample product for analysis
                            print(f"Sample product: {json.dumps(first_product, indent=2, ensure_ascii=False)[:500]}")
                else:
                    print(f"❌ Request failed: {response.status_code}")

                time.sleep(1)  # Rate limiting

            return {'success': False, 'reason': 'No brand information in API'}

        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'error': str(e)}

    # ============================================================================
    # APPROACH 2: Suggestions API
    # ============================================================================

    def approach_2_suggestions_api(self):
        """
        APPROACH 2: Test Suggestions/Autocomplete API
        Goal: Autocomplete APIs often return more structured data with brands
        """
        print(f"\n{'='*80}")
        print("🧪 APPROACH 2: Suggestions/Autocomplete API")
        print(f"{'='*80}\n")

        print("Testing: Autocomplete/Suggestions endpoints")
        print("Hypothesis: Autocomplete returns brand-filtered results")

        endpoints = [
            "/api/suggestions",
            "/api/autocomplete",
            "/api/search/suggest",
            "/api/typeahead",
        ]

        for endpoint in endpoints:
            print(f"\n--- Testing: {endpoint} ---")

            try:
                url = f"{self.BASE_URL}{endpoint}"
                response = self.session.get(
                    url,
                    params={'q': 'SOTO', 'query': 'SOTO', 'term': 'SOTO'},
                    headers=self.headers,
                    impersonate="chrome120",
                    timeout=30
                )

                print(f"Status: {response.status_code}")

                if response.status_code == 200:
                    data = response.json()
                    self.save_response(f"approach_2_suggestions_{endpoint.replace('/', '_')}", data)
                    print(f"✅ Response received: {list(data.keys())}")
                    return {'success': True, 'endpoint': endpoint, 'data': data}
                else:
                    print(f"❌ Not found or failed")

            except Exception as e:
                print(f"⚠️  Error: {e}")

            time.sleep(0.5)

        return {'success': False}

    # ============================================================================
    # APPROACH 3: Search with Facets/Filters
    # ============================================================================

    def approach_3_faceted_search(self):
        """
        APPROACH 3: Use faceted search parameters
        Goal: E-commerce APIs often support facets for filtering
        """
        print(f"\n{'='*80}")
        print("🧪 APPROACH 3: Faceted Search with Filters")
        print(f"{'='*80}\n")

        print("Testing: Search API with filter parameters")
        print("Hypothesis: API supports facet/filter query parameters")

        # Common e-commerce filter patterns
        filter_patterns = [
            {'query': 'SOTO', 'facet': 'brand'},
            {'query': 'SOTO', 'filter': 'brand=SOTO'},
            {'query': 'SOTO', 'fq': 'brand:SOTO'},  # Solr style
            {'query': 'SOTO', 'refinement': 'brand|SOTO'},
            {'query': 'SOTO', 'brand': 'SOTO'},
            {'query': 'SOTO', 'manufacturer': 'SOTO'},
            {'q': 'SOTO', 'filters': json.dumps({'brand': ['SOTO']})},
        ]

        for i, params in enumerate(filter_patterns, 1):
            print(f"\n--- Test {i}: {params} ---")

            try:
                url = f"{self.BASE_URL}/api/stationary-product-search/products"
                response = self.session.get(
                    url,
                    params=params,
                    headers=self.headers,
                    impersonate="chrome120",
                    timeout=30
                )

                print(f"Status: {response.status_code}")

                if response.status_code == 200:
                    data = response.json()
                    products = self._extract_products(data)
                    count = data.get('totalHits') or len(products)

                    print(f"Products returned: {count}")

                    # Check if count is lower (indicating filtering worked)
                    if count > 0 and count < 10:  # Likely filtered
                        print(f"✅ Possible filtering detected! Count: {count}")
                        self.save_response(f"approach_3_faceted_{i}", data)
                        return {'success': True, 'params': params, 'count': count}

            except Exception as e:
                print(f"⚠️  Error: {e}")

            time.sleep(0.5)

        return {'success': False}

    # ============================================================================
    # APPROACH 4: Alternative Search Queries
    # ============================================================================

    def approach_4_query_refinement(self):
        """
        APPROACH 4: Test different query strings to reduce false positives
        Goal: Find query that returns only SOTO brand products
        """
        print(f"\n{'='*80}")
        print("🧪 APPROACH 4: Query Refinement to Reduce False Positives")
        print(f"{'='*80}\n")

        print("Testing: Different search queries")
        print("Hypothesis: More specific queries reduce false positives")

        queries = [
            'SOTO',
            'SOTO outdoor',
            'SOTO camping',
            'SOTO kocher',
            'SOTO gas',
            'SOTO brenner',
            '"SOTO"',  # Exact match
            'brand:SOTO',
            '+SOTO +outdoor',
        ]

        results = {}

        for query in queries:
            print(f"\n--- Query: '{query}' ---")

            try:
                # Count API
                count_url = f"{self.BASE_URL}/api/stationary-product-search/products/count"
                response = self.session.get(
                    count_url,
                    params={'query': query},
                    headers=self.headers,
                    impersonate="chrome120",
                    timeout=30
                )

                if response.status_code == 200:
                    count = response.json().get('totalHits', 0)
                    print(f"Count: {count}")
                    results[query] = count

                    # Lower count might mean less false positives
                    if 0 < count < 5:
                        print(f"✅ Good candidate! Low count suggests specificity")

            except Exception as e:
                print(f"⚠️  Error: {e}")

            time.sleep(0.5)

        # Find best query (lowest non-zero count)
        if results:
            self.save_response("approach_4_query_refinement", results)
            non_zero = {k: v for k, v in results.items() if v > 0}
            if non_zero:
                best_query = min(non_zero, key=non_zero.get)
                print(f"\n✅ Best query: '{best_query}' with count {non_zero[best_query]}")
                return {'success': True, 'best_query': best_query, 'count': non_zero[best_query]}

        return {'success': False}

    # ============================================================================
    # APPROACH 5: Product Detail API Analysis
    # ============================================================================

    def approach_5_product_details(self):
        """
        APPROACH 5: Get product list and fetch individual product details
        Goal: Product detail endpoints might have brand info even if list doesn't
        """
        print(f"\n{'='*80}")
        print("🧪 APPROACH 5: Product Detail API for Brand Verification")
        print(f"{'='*80}\n")

        print("Testing: Individual product detail endpoints")
        print("Hypothesis: Product detail API contains brand/manufacturer info")

        try:
            # First get product list
            print("\n📋 Step 1: Get product list...")
            list_url = f"{self.BASE_URL}/api/stationary-product-search/products"
            response = self.session.get(
                list_url,
                params={'query': 'SOTO', 'page': 1, 'pageSize': 5},
                headers=self.headers,
                impersonate="chrome120",
                timeout=30
            )

            if response.status_code != 200:
                print(f"❌ Product list failed: {response.status_code}")
                return {'success': False}

            data = response.json()
            products = self._extract_products(data)

            if not products:
                print("❌ No products found")
                return {'success': False}

            print(f"✅ Found {len(products)} products")

            # Extract product IDs and try to fetch details
            print("\n📋 Step 2: Fetch individual product details...")

            for i, product in enumerate(products[:3], 1):  # Test first 3
                product_id = product.get('id') or product.get('productId') or product.get('nan')

                if not product_id:
                    print(f"⚠️  Product {i}: No ID found")
                    continue

                print(f"\n--- Product {i}: ID={product_id} ---")

                # Try different detail endpoint patterns
                detail_endpoints = [
                    f"/api/stationary-product-search/products/{product_id}",
                    f"/api/products/{product_id}",
                    f"/api/product-detail/{product_id}",
                    f"/api/stationary/products/{product_id}",
                ]

                for endpoint in detail_endpoints:
                    try:
                        detail_url = f"{self.BASE_URL}{endpoint}"
                        detail_response = self.session.get(
                            detail_url,
                            headers=self.headers,
                            impersonate="chrome120",
                            timeout=30
                        )

                        if detail_response.status_code == 200:
                            detail_data = detail_response.json()
                            print(f"✅ {endpoint}: SUCCESS")
                            self.save_response(f"approach_5_product_detail_{i}", detail_data)

                            # Check for brand info
                            brand_info = self._extract_brand_info(detail_data)
                            if brand_info:
                                print(f"   Brand info: {brand_info}")
                                if 'SOTO' in str(brand_info).upper():
                                    print(f"   ✅ Confirmed SOTO product!")
                                    return {'success': True, 'method': 'product_detail', 'endpoint': endpoint}

                            break  # Found working endpoint

                    except Exception as e:
                        pass  # Try next endpoint

                time.sleep(1)

        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()

        return {'success': False}

    # ============================================================================
    # APPROACH 6: GraphQL API Detection
    # ============================================================================

    def approach_6_graphql(self):
        """
        APPROACH 6: Check for GraphQL endpoint
        Goal: GraphQL APIs often provide more flexible queries
        """
        print(f"\n{'='*80}")
        print("🧪 APPROACH 6: GraphQL API Detection")
        print(f"{'='*80}\n")

        print("Testing: GraphQL endpoints")
        print("Hypothesis: REWE might use GraphQL for product data")

        graphql_endpoints = [
            "/graphql",
            "/api/graphql",
            "/gql",
        ]

        query = """
        query SearchProducts($query: String!) {
            products(query: $query) {
                id
                name
                brand
                manufacturer
            }
        }
        """

        for endpoint in graphql_endpoints:
            print(f"\n--- Testing: {endpoint} ---")

            try:
                url = f"{self.BASE_URL}{endpoint}"
                response = self.session.post(
                    url,
                    json={
                        'query': query,
                        'variables': {'query': 'SOTO'}
                    },
                    headers={**self.headers, 'Content-Type': 'application/json'},
                    impersonate="chrome120",
                    timeout=30
                )

                print(f"Status: {response.status_code}")

                if response.status_code == 200:
                    data = response.json()
                    self.save_response(f"approach_6_graphql_{endpoint.replace('/', '_')}", data)
                    print(f"✅ GraphQL endpoint found!")
                    return {'success': True, 'endpoint': endpoint}

            except Exception as e:
                print(f"⚠️  Error: {e}")

            time.sleep(0.5)

        return {'success': False}

    # ============================================================================
    # Helper Methods
    # ============================================================================

    def _extract_products(self, data):
        """Extract products array from various API response formats"""
        if isinstance(data, list):
            return data

        if not isinstance(data, dict):
            return []

        # Try common product array locations
        paths = [
            ['products'],
            ['_embedded', 'products'],
            ['data', 'products'],
            ['items'],
            ['results'],
            ['hits'],
        ]

        for path in paths:
            current = data
            for key in path:
                current = current.get(key)
                if current is None:
                    break

            if isinstance(current, list):
                return current

        return []

    def _extract_brand_info(self, data):
        """Extract brand information from product data"""
        if not isinstance(data, dict):
            return None

        brand_fields = ['brand', 'brandName', 'manufacturer', 'producer', 'supplier', 'vendor']

        for field in brand_fields:
            if field in data:
                return {field: data[field]}

        # Check nested in attributes/properties
        for nested_key in ['attributes', 'properties', 'details', 'metadata']:
            if nested_key in data and isinstance(data[nested_key], dict):
                for field in brand_fields:
                    if field in data[nested_key]:
                        return {field: data[nested_key][field]}

        return None


def main():
    """Run all investigation approaches"""
    print(f"\n{'#'*80}")
    print("# REWE SOTO Product Validation Investigation")
    print("# Goal: Find methods to filter SOTO brand products from false positives")
    print(f"{'#'*80}\n")

    investigator = REWEInvestigator()

    # Setup test market
    if not investigator.setup_test_market("80331"):  # München
        print("\n❌ Failed to setup test market. Aborting.")
        return

    # Run all approaches
    approaches = [
        ("Product List API with Brand Filtering", investigator.approach_1_product_list_api),
        ("Suggestions/Autocomplete API", investigator.approach_2_suggestions_api),
        ("Faceted Search with Filters", investigator.approach_3_faceted_search),
        ("Query Refinement", investigator.approach_4_query_refinement),
        ("Product Detail API", investigator.approach_5_product_details),
        ("GraphQL API", investigator.approach_6_graphql),
    ]

    results = {}

    for name, approach_func in approaches:
        print(f"\n{'='*80}")
        print(f"🚀 Running: {name}")
        print(f"{'='*80}")

        result = approach_func()
        results[name] = result

        if result.get('success'):
            print(f"\n✅ SUCCESS! This approach works!")
        else:
            print(f"\n❌ This approach didn't work")

        time.sleep(2)  # Rate limiting between approaches

    # Summary
    print(f"\n{'#'*80}")
    print("# INVESTIGATION SUMMARY")
    print(f"{'#'*80}\n")

    successful = [name for name, result in results.items() if result.get('success')]

    if successful:
        print(f"✅ Successful approaches ({len(successful)}):")
        for name in successful:
            print(f"   • {name}")
            result_details = results[name]
            for key, value in result_details.items():
                if key != 'success' and key != 'data':
                    print(f"     - {key}: {value}")
    else:
        print("❌ No successful approaches found")
        print("\nRecommendation: Manual browser inspection needed to find additional APIs")

    # Save summary
    output_dir = Path(__file__).parent.parent / 'data' / 'investigation'
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_file = output_dir / "investigation_summary.json"

    with open(summary_file, 'w', encoding='utf-8') as f:
        # Remove large data objects before saving
        clean_results = {}
        for name, result in results.items():
            clean_results[name] = {k: v for k, v in result.items() if k != 'data'}

        json.dump({
            'timestamp': datetime.now().isoformat(),
            'results': clean_results,
            'successful_approaches': successful
        }, f, indent=2, ensure_ascii=False)

    print(f"\n💾 Summary saved to: {summary_file}")


if __name__ == "__main__":
    main()
