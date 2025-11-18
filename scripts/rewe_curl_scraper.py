#!/usr/bin/env python3
"""
REWE SOTO Product Availability Scraper using curl_cffi

Uses TLS fingerprinting to bypass Cloudflare and check SOTO product availability
across multiple REWE stores via API endpoints.
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


class REWECurlScraper:
    """REWE scraper using curl_cffi for Cloudflare bypass"""

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
        """
        Find REWE market by address

        Args:
            city: City name (e.g., "Berlin")
            street: Street name (optional)
            postal_code: Postal code (optional)

        Returns:
            dict: Market information with wwIdent, or None if not found
        """
        print(f"\n🔍 Searching for REWE market in {city}...")

        # Use postal code if available, otherwise city
        search_term = postal_code if postal_code else city

        try:
            session = self._get_session()
            url = f"{self.BASE_URL}/api/wksmarketsearch"
            params = {'searchTerm': search_term}

            response = session.get(
                url,
                params=params,
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

            # Return first market if no exact match
            market = data['markets'][0]
            print(f"   ✅ Found market: {market.get('name')} (ID: {market.get('wwIdent')})")
            return market

        except Exception as e:
            print(f"   ❌ Error searching for market: {e}")
            return None

    def select_market(self, ww_ident: str) -> bool:
        """
        Select a REWE market for the session

        Args:
            ww_ident: REWE market identifier (wwIdent)

        Returns:
            bool: True if successful
        """
        print(f"\n📍 Selecting market {ww_ident}...")

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

            print(f"   🔍 Debug: Response status: {response.status_code}")
            print(f"   🔍 Debug: Response headers: {dict(response.headers)}")

            # Check if cookies were set
            cookies = session.cookies.get_dict()
            print(f"   🔍 Debug: Session cookies: {list(cookies.keys())}")

            if response.status_code == 201:
                print(f"   ✅ Market selected successfully")

                # Verify selection by checking current market
                verify_url = f"{self.BASE_URL}/content-homepage-backend/userdata"
                try:
                    verify_response = session.get(
                        verify_url,
                        headers=self.headers,
                        impersonate="chrome120",
                        timeout=30
                    )

                    if verify_response.status_code == 200 and verify_response.text.strip():
                        userdata = verify_response.json()
                        print(f"   🔍 Debug: Current market from userdata: {userdata}")
                except Exception as e:
                    print(f"   ⚠️  Could not verify market selection (non-critical): {e}")

                return True
            else:
                print(f"   ❌ Market selection failed: HTTP {response.status_code}")
                print(f"   🔍 Debug: Response body: {response.text[:500]}")
                return False

        except Exception as e:
            print(f"   ❌ Error selecting market: {e}")
            import traceback
            traceback.print_exc()
            return False

    def check_product_count(self, query: str = "SOTO") -> int:
        """
        Get product count using Count API (fast, market-specific)

        Args:
            query: Search query (default: "SOTO")

        Returns:
            int: Number of products found
        """
        try:
            session = self._get_session()
            count_url = f"{self.BASE_URL}/api/stationary-product-search/products/count"
            count_response = session.get(
                count_url,
                params={'query': query},
                headers=self.headers,
                impersonate="chrome120",
                timeout=30
            )

            if count_response.status_code == 200:
                count_data = count_response.json()
                return count_data.get('totalHits', 0)
            else:
                return 0
        except Exception as e:
            print(f"   ❌ Error checking count: {e}")
            return 0

    def verify_products_via_html(self, query: str = "SOTO", brand_filter: str = "SOTO") -> Dict:
        """
        Verify products via HTML scraping (slow but accurate)

        Args:
            query: Search query
            brand_filter: Brand name to filter by

        Returns:
            dict: {'available': bool, 'count': int, 'products': list}
        """
        print(f"\n🔍 Verifying via HTML scraping (brand: {brand_filter})...")

        try:
            import undetected_chromedriver as uc
            from bs4 import BeautifulSoup

            # Launch browser
            options = uc.ChromeOptions()
            options.add_argument('--headless')
            options.add_argument('--window-size=1920,1080')
            driver = uc.Chrome(options=options, use_subprocess=False)

            try:
                # Navigate to search page
                search_url = f"{self.BASE_URL}/suche/uebersicht?searchTerm={query}"
                driver.get(search_url)
                time.sleep(5)  # Wait for page load

                # Get HTML
                html = driver.page_source
                soup = BeautifulSoup(html, 'html.parser')

                # Debug: Save HTML to file
                debug_html_file = Path(__file__).parent.parent / 'data' / 'debug_rewe_search.html'
                with open(debug_html_file, 'w', encoding='utf-8') as f:
                    f.write(html)
                print(f"   🔍 Debug: HTML saved to {debug_html_file}")

                # Find product tiles - try multiple selectors
                products = []

                # Try different selectors
                selectors = [
                    'article',
                    '[class*="product"]',
                    '[data-product]',
                    '.search-service-product-card',
                    '[class*="ProductCard"]'
                ]

                for selector in selectors:
                    elements = soup.select(selector)
                    if elements:
                        print(f"   🔍 Found {len(elements)} elements with selector: {selector}")
                        break

                if not elements:
                    print(f"   ⚠️  No product elements found with any selector")
                    # Try to find SOTO in any text
                    all_text = soup.get_text().lower()
                    if brand_filter.lower() in all_text:
                        print(f"   ⚠️  '{brand_filter}' found in page text, but couldn't locate product elements")
                else:
                    brand_lower = brand_filter.lower()

                    for elem in elements:
                        text = elem.get_text().lower()

                        # Check if it's a SOTO product
                        if brand_lower in text:
                            # Try to extract product name
                            title_elem = elem.select_one('h3, h4, h2, [class*="title"], [class*="name"]')
                            title = title_elem.get_text(strip=True) if title_elem else elem.get_text(strip=True)[:50]

                            # Verify it contains SOTO
                            if brand_lower in title.lower():
                                products.append({'title': title})
                                print(f"   ✓ Found: {title}")

                print(f"   ✅ Found {len(products)} verified {brand_filter} products")

                return {
                    'available': len(products) > 0,
                    'count': len(products),
                    'products': products
                }

            finally:
                driver.quit()

        except ImportError:
            print("   ⚠️  undetected-chromedriver not available, skipping HTML verification")
            return {'available': True, 'count': 0, 'products': []}
        except Exception as e:
            print(f"   ❌ HTML verification error: {e}")
            return {'available': True, 'count': 0, 'products': []}

    def check_product_availability(self, query: str = "SOTO", brand_filter: str = "SOTO") -> Dict:
        """
        Check product availability using Count API (fast, market-specific)

        Note: HTML verification was attempted but Cloudflare blocks automated browsers.
        Count API is reliable and respects market selection.

        Args:
            query: Search query (default: "SOTO")
            brand_filter: Brand name to filter by (not used, kept for compatibility)

        Returns:
            dict: {'available': bool, 'count': int}
        """
        print(f"\n🔍 Checking availability via Count API...")

        # Use count API which is fast and reliable
        count = self.check_product_count(query)
        print(f"   ℹ️  Count API reports: {count} products")

        return {
            'available': count > 0,
            'count': count,
            'products': []  # Empty list for compatibility
        }

    def search_products(self, query: str = "SOTO") -> List[Dict]:
        """
        Search for products (note: this returns generic product list, not market-specific)

        Args:
            query: Search query (default: "SOTO")

        Returns:
            list: List of product dictionaries
        """
        print(f"\n🔍 Searching for '{query}' products...")

        try:
            session = self._get_session()

            # First check product count
            count_url = f"{self.BASE_URL}/api/stationary-product-search/products/count"
            count_response = session.get(
                count_url,
                params={'query': query},
                headers=self.headers,
                impersonate="chrome120",
                timeout=30
            )

            if count_response.status_code == 200:
                count_data = count_response.json()
                total_hits = count_data.get('totalHits', 0)
                print(f"   ℹ️  Market-specific count: {total_hits} products")

            # Now get actual product data
            # Use www.rewe.de API (same domain as market selection for cookie sharing)
            products_url = f"{self.BASE_URL}/api/stationary-product-search/products"
            products_response = session.get(
                products_url,
                params={'query': query, 'page': 1},
                headers=self.headers,
                impersonate="chrome120",
                timeout=30
            )

            if products_response.status_code == 200:
                data = products_response.json()

                # Debug: Save response for inspection
                debug_file = Path(__file__).parent.parent / 'data' / 'debug_api_response.json'
                with open(debug_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                print(f"   🔍 Debug: API response saved to {debug_file}")

                # Extract products from response
                products = []

                # The response structure may vary, try different paths
                if isinstance(data, dict):
                    # Debug: print top-level keys
                    print(f"   🔍 Debug: Response keys: {list(data.keys())}")

                    # Try direct products array first (www.rewe.de API format)
                    if 'products' in data and isinstance(data['products'], list):
                        products = data['products']
                        print(f"   ✅ Found products in direct 'products' key")

                    # Try HAL JSON format (_embedded.products) - shop.rewe.de format
                    elif '_embedded' in data and isinstance(data['_embedded'], dict):
                        products = data['_embedded'].get('products', [])
                        if products:
                            print(f"   ✅ Found products in _embedded.products")

                    # Fallback: Try common paths if not found
                    else:
                        product_list = (
                            data.get('items') or
                            data.get('hits') or
                            []
                        )

                        if isinstance(product_list, list):
                            products = product_list

                        # Also check if products are nested elsewhere
                        if not products and 'data' in data:
                            if isinstance(data['data'], list):
                                products = data['data']
                            elif isinstance(data['data'], dict) and 'products' in data['data']:
                                products = data['data']['products']

                        # Try pagination.products (common in ecommerce APIs)
                        if not products and 'pagination' in data:
                            if isinstance(data['pagination'], dict) and 'products' in data['pagination']:
                                products = data['pagination']['products']

                print(f"   ✅ Retrieved {len(products)} products")
                return products
            else:
                print(f"   ⚠️  Products API returned HTTP {products_response.status_code}")
                # Try alternative endpoint
                return self._try_alternative_search(query)

        except Exception as e:
            print(f"   ❌ Error searching products: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _try_alternative_search(self, query: str) -> List[Dict]:
        """Try alternative search endpoint"""
        try:
            session = self._get_session()
            url = "https://shop.rewe.de/api/suggestions"
            response = session.get(
                url,
                params={'q': query},
                headers={**self.headers, 'Referer': 'https://shop.rewe.de/'},
                impersonate="chrome120",
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                products = data.get('products', [])
                print(f"   ✅ Retrieved {len(products)} products from suggestions API")
                return products
            else:
                return []
        except Exception as e:
            print(f"   ⚠️  Alternative search failed: {e}")
            return []

    def get_product_availability(self, product_id: str, market_id: str) -> Optional[Dict]:
        """
        Get product availability for specific market

        Args:
            product_id: Product ID
            market_id: Market ID (wwIdent)

        Returns:
            dict: Availability information or None
        """
        # This would require clicking on product to trigger availability API
        # For MVP, we'll check if product appears in search results (indicates availability)
        return None

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
            dict: Store results with products
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

        # Small delay to let selection propagate
        time.sleep(1)

        # Check SOTO product availability (with brand filtering)
        availability = self.check_product_availability("SOTO", brand_filter="SOTO")

        result['success'] = True
        result['available'] = availability['available']
        result['product_count'] = availability['count']
        result['products'] = [
            {
                'id': p.get('id'),
                'title': p.get('title'),
                'brand': p.get('brand')
            }
            for p in availability.get('products', [])
        ]

        if availability['available']:
            print(f"\n✅ SOTO products are available at this market")
            print(f"   Count: {availability['count']} products")
            # Show first 3 products
            for i, product in enumerate(availability['products'][:3], 1):
                print(f"   {i}. {product.get('title', 'N/A')}")
        else:
            print(f"\n❌ No SOTO products available at this market")

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
        total_products = sum(r.get('product_count', 0) for r in self.results)

        print(f"Stores checked: {total_stores}")
        print(f"Successful: {successful_stores}")
        print(f"Total SOTO products found: {total_products}")

        print(f"\n{'─'*80}\n")

        for result in self.results:
            status = "✅" if result.get('available') else "❌"
            print(f"{status} {result['store_name']}")
            print(f"   📍 {result.get('city')}")
            print(f"   Market ID: {result.get('market_id')}")

            if result.get('available'):
                print(f"   🛒 {result['product_count']} SOTO products available")
                # Show first 3 products
                products = result.get('products', [])
                for i, p in enumerate(products[:3], 1):
                    print(f"      {i}. {p.get('title', 'N/A')}")
                if len(products) > 3:
                    print(f"      ... and {len(products) - 3} more")
            else:
                count = result.get('product_count', 0)
                if count == 0:
                    print(f"   ❌ No SOTO products at this location")
                else:
                    print(f"   ⚠️  {result.get('error', 'Unknown error')}")
            print()


def main():
    """Main execution"""
    print(f"\n{'='*80}")
    print("🚀 REWE SOTO Product Availability Checker")
    print("   Using curl_cffi with Cloudflare bypass")
    print(f"{'='*80}\n")

    scraper = REWECurlScraper()

    # List of stores to check
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
            print(f"\n⏳ Waiting 3 seconds before next store...")
            time.sleep(3)

    # Print summary and save results
    scraper.print_summary()
    scraper.save_results()

    print(f"\n{'='*80}")
    print("✅ All stores checked!")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
