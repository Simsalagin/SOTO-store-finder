#!/usr/bin/env python3
"""
REWE SOTO Product Validator
Filters SOTO outdoor products from SOTO food products and false positives
"""

import json
from typing import Dict, List, Optional
from pathlib import Path

try:
    from curl_cffi import requests
except ImportError:
    print("❌ curl_cffi not installed. Run: pip install curl_cffi")
    exit(1)


class SOTOProductValidator:
    """Validates SOTO outdoor products vs food products and false positives"""

    # Keywords that indicate SOTO outdoor/camping products
    OUTDOOR_KEYWORDS = [
        'kocher', 'brenner', 'burner', 'stove', 'gas', 'outdoor', 'camping',
        'kartuschen', 'windscreen', 'windschutz', 'regulator', 'amicus',
        'windmaster', 'muka', 'fusion', 'titan'
    ]

    # Keywords that indicate SOTO food products (to exclude)
    FOOD_KEYWORDS = [
        'bio', 'samosa', 'falafel', 'burger', 'börek', 'edamame', 'spinat',
        'cashew', 'taler', 'bällchen', 'röllchen', 'linsen', 'süßkartoffel',
        'sterne', 'glücks', 'gute-laune', 'vegan', 'vegetarisch', 'mediterran',
        'oriental', 'black bean'
    ]

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
        self.base_url = "https://www.rewe.de"

    def is_outdoor_product(self, product: Dict) -> bool:
        """
        Determine if a product is a SOTO outdoor product (vs food product)

        Args:
            product: Product dictionary from API

        Returns:
            bool: True if outdoor product, False if food product or unclear
        """
        title = product.get('title', '').lower()

        # Check for food keywords (exclude these)
        for keyword in self.FOOD_KEYWORDS:
            if keyword in title:
                return False

        # Check for outdoor keywords (include these)
        for keyword in self.OUTDOOR_KEYWORDS:
            if keyword in title:
                return True

        # If unclear, check brand and title together
        brand = product.get('brand', '').lower()
        if brand == 'soto':
            # If it's SOTO brand but no clear category, assume food (safer)
            # Unless it has outdoor-related commodity group or explicit mention
            return False

        return False

    def get_products_with_brand_filter(
        self,
        query: str = "SOTO",
        outdoor_only: bool = True
    ) -> List[Dict]:
        """
        Get SOTO products using brand filtering from Product List API

        Args:
            query: Search query
            outdoor_only: If True, filter only outdoor products

        Returns:
            list: Filtered products
        """
        print(f"\n🔍 Fetching products with query: '{query}'...")

        try:
            url = f"{self.base_url}/api/stationary-product-search/products"
            response = self.session.get(
                url,
                params={'query': query},
                headers=self.headers,
                impersonate="chrome120",
                timeout=30
            )

            if response.status_code != 200:
                print(f"   ❌ API request failed: HTTP {response.status_code}")
                return []

            data = response.json()
            all_products = data.get('products', [])

            print(f"   ℹ️  Total products from API: {len(all_products)}")

            # Filter by brand
            brand_filtered = [
                p for p in all_products
                if p.get('brand', '').lower() == 'soto'
            ]

            print(f"   ℹ️  After brand filter: {len(brand_filtered)} products")

            if not outdoor_only:
                return brand_filtered

            # Filter outdoor products only
            outdoor_products = [
                p for p in brand_filtered
                if self.is_outdoor_product(p)
            ]

            print(f"   ✅ Outdoor products: {len(outdoor_products)}")

            # Show what was filtered out
            food_products = [
                p for p in brand_filtered
                if not self.is_outdoor_product(p)
            ]
            if food_products:
                print(f"   ℹ️  Excluded {len(food_products)} food products:")
                for p in food_products[:3]:
                    print(f"      • {p.get('title')}")
                if len(food_products) > 3:
                    print(f"      ... and {len(food_products) - 3} more")

            return outdoor_products

        except Exception as e:
            print(f"   ❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return []

    def compare_query_strategies(self) -> Dict:
        """
        Compare different query strategies to find best approach

        Returns:
            dict: Comparison results
        """
        print(f"\n{'='*80}")
        print("🧪 COMPARING QUERY STRATEGIES")
        print(f"{'='*80}\n")

        strategies = [
            {'name': 'Generic SOTO', 'query': 'SOTO', 'outdoor_only': False},
            {'name': 'SOTO with outdoor filter', 'query': 'SOTO', 'outdoor_only': True},
            {'name': 'SOTO outdoor query', 'query': 'SOTO outdoor', 'outdoor_only': False},
            {'name': 'SOTO kocher query', 'query': 'SOTO kocher', 'outdoor_only': False},
            {'name': 'SOTO camping query', 'query': 'SOTO camping', 'outdoor_only': False},
        ]

        results = {}

        for strategy in strategies:
            print(f"\n--- Strategy: {strategy['name']} ---")
            products = self.get_products_with_brand_filter(
                query=strategy['query'],
                outdoor_only=strategy['outdoor_only']
            )

            results[strategy['name']] = {
                'query': strategy['query'],
                'outdoor_only': strategy['outdoor_only'],
                'count': len(products),
                'products': [
                    {
                        'id': p.get('id'),
                        'title': p.get('title'),
                        'brand': p.get('brand'),
                        'is_outdoor': self.is_outdoor_product(p)
                    }
                    for p in products
                ]
            }

            if products:
                print(f"\n   Products found:")
                for p in products:
                    is_outdoor = "🏕️ " if self.is_outdoor_product(p) else "🍽️  "
                    print(f"   {is_outdoor} {p.get('title')}")

        return results

    def get_count_api_result(self, query: str = "SOTO") -> int:
        """Get count from Count API for comparison"""
        try:
            url = f"{self.base_url}/api/stationary-product-search/products/count"
            response = self.session.get(
                url,
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

    def validate_approach(self) -> Dict:
        """
        Validate the best approach for SOTO outdoor product detection

        Returns:
            dict: Validation results with recommended approach
        """
        print(f"\n{'='*80}")
        print("🎯 VALIDATION: Finding Best Approach for SOTO Outdoor Products")
        print(f"{'='*80}\n")

        # Compare Count API with different queries
        print("📊 Count API Results:")
        count_queries = ['SOTO', 'SOTO outdoor', 'SOTO kocher', 'SOTO camping']

        count_results = {}
        for query in count_queries:
            count = self.get_count_api_result(query)
            count_results[query] = count
            print(f"   '{query}': {count} products")

        # Compare with Product List API
        print("\n📋 Product List API Comparison:")
        strategy_results = self.compare_query_strategies()

        # Summary
        print(f"\n{'='*80}")
        print("📝 SUMMARY & RECOMMENDATION")
        print(f"{'='*80}\n")

        # Find best strategy
        outdoor_counts = {
            name: result['count']
            for name, result in strategy_results.items()
            if result['count'] > 0
        }

        if outdoor_counts:
            best_strategy = min(outdoor_counts, key=outdoor_counts.get)
            print(f"✅ RECOMMENDED APPROACH: {best_strategy}")
            print(f"   Products found: {outdoor_counts[best_strategy]}")
            print(f"   Query: '{strategy_results[best_strategy]['query']}'")
            print(f"   Outdoor filter: {strategy_results[best_strategy]['outdoor_only']}")

            best_products = strategy_results[best_strategy]['products']
            if best_products:
                print(f"\n   Products:")
                for p in best_products:
                    print(f"   • {p['title']}")

        else:
            print("⚠️  No outdoor products found with any strategy")
            print("   This may indicate:")
            print("   1. Store has no SOTO outdoor products")
            print("   2. Only SOTO food products available")
            print("   3. Need different search approach")

        # Save results
        output = {
            'timestamp': str(Path(__file__).parent),
            'count_api': count_results,
            'product_list_api': strategy_results,
            'recommendation': {
                'strategy': best_strategy if outdoor_counts else None,
                'outdoor_product_count': outdoor_counts.get(best_strategy, 0) if outdoor_counts else 0
            }
        }

        output_dir = Path(__file__).parent.parent / 'data' / 'investigation'
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / 'validation_results.json'

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        print(f"\n💾 Results saved to: {output_file}")

        return output


def main():
    """Main execution"""
    print(f"\n{'#'*80}")
    print("# SOTO Product Validator")
    print("# Goal: Distinguish SOTO outdoor products from food products")
    print(f"{'#'*80}\n")

    validator = SOTOProductValidator()

    # Note: This validator works without market selection
    # It will show all available products in the catalog
    # For market-specific results, integrate with REWECurlScraper

    validator.validate_approach()


if __name__ == "__main__":
    main()
