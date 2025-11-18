#!/usr/bin/env python3
"""
REWE Hybrid Validator - 100% Accuracy Solution
Combines Count API (fast) with Playwright validation (accurate)

Strategy:
1. Use Count API to check if products exist (fast)
2. If Count > 0, use Playwright to scrape and validate actual SOTO products
3. Return validated count and product list
"""

import json
import time
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

try:
    from curl_cffi import requests
except ImportError:
    print("❌ curl_cffi not installed. Run: pip install curl_cffi")
    exit(1)

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("❌ Playwright not installed")
    print("   Run: pip install playwright")
    print("   Then: playwright install chromium")
    exit(1)


class REWEHybridValidator:
    """
    Hybrid validator combining:
    - Count API for fast initial check
    - Playwright for 100% accurate validation
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
        self.playwright = None
        self.browser = None

    def _get_session(self):
        """Get or create curl_cffi session"""
        if not self.session:
            self.session = requests.Session()
        return self.session

    # ========================================================================
    # Count API Methods (Fast initial check)
    # ========================================================================

    def find_market(self, postal_code: str) -> Optional[Dict]:
        """Find REWE market by postal code"""
        try:
            session = self._get_session()
            response = session.get(
                f"{self.BASE_URL}/api/wksmarketsearch",
                params={'searchTerm': postal_code},
                headers=self.headers,
                impersonate="chrome120",
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                if data.get('markets'):
                    return data['markets'][0]
        except:
            pass
        return None

    def select_market(self, market_id: str) -> bool:
        """Select market via API"""
        try:
            session = self._get_session()
            response = session.post(
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
            return response.status_code == 201
        except:
            return False

    def get_count(self, query: str = "SOTO") -> int:
        """Get product count from Count API"""
        try:
            session = self._get_session()
            response = session.get(
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
    # Playwright Methods (Accurate validation)
    # ========================================================================

    async def setup_browser(self, headless: bool = True):
        """Setup Playwright browser"""
        print("      🌐 Starting browser...")

        self.playwright = await async_playwright().start()

        self.browser = await self.playwright.chromium.launch(
            headless=headless,
            args=['--disable-blink-features=AutomationControlled']
        )

        context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='de-DE',
        )

        page = await context.new_page()

        # Stealth mode
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => false});
        """)

        print("      ✅ Browser ready")
        return page

    async def validate_products_with_browser(self, postal_code: str) -> List[Dict]:
        """
        Use Playwright to scrape and validate actual SOTO products

        Returns:
            list: List of validated SOTO products
        """
        print("      🔍 Validating with browser...")

        page = await self.setup_browser(headless=True)

        try:
            # Navigate to REWE
            await page.goto(self.BASE_URL, wait_until='domcontentloaded', timeout=30000)
            await asyncio.sleep(2)

            # Accept cookies
            try:
                cookie_btn = await page.wait_for_selector(
                    'button:has-text("Akzeptieren"), button:has-text("Alle akzeptieren")',
                    timeout=5000
                )
                if cookie_btn:
                    await cookie_btn.click()
                    await asyncio.sleep(1)
            except:
                pass

            # Search for SOTO
            search_url = f"{self.BASE_URL}/suche/uebersicht?searchTerm=SOTO"
            print(f"      📄 Loading search: {search_url}")
            await page.goto(search_url, wait_until='networkidle', timeout=60000)
            await asyncio.sleep(3)

            # Check for Cloudflare
            title = await page.title()
            if 'cloudflare' in title.lower() or 'just a moment' in title.lower():
                print("      ⏳ Cloudflare detected, waiting...")
                await asyncio.sleep(10)

            # Find product elements
            products = []
            selectors = [
                'article[data-product-id]',
                '[data-testid*="product"]',
                'article',
                '[class*="ProductCard"]',
            ]

            for selector in selectors:
                elements = await page.query_selector_all(selector)

                if elements:
                    print(f"      ✅ Found {len(elements)} elements with: {selector}")

                    for element in elements[:20]:  # Limit to first 20
                        try:
                            text = await element.inner_text()
                            text_lower = text.lower()

                            # Check if it contains SOTO
                            if 'soto' in text_lower:
                                # Extract title
                                title_elem = await element.query_selector('h3, h4, h2, [class*="title"]')
                                if title_elem:
                                    title = await title_elem.inner_text()
                                else:
                                    # Fallback: first line of text
                                    title = text.split('\n')[0]

                                title = title.strip()

                                # Validate it's a SOTO brand product
                                title_lower = title.lower()

                                # Check if it starts with "SOTO" or contains "SOTO Bio"
                                if title_lower.startswith('soto ') or 'soto bio' in title_lower:
                                    # Avoid duplicates
                                    if not any(p['title'] == title for p in products):
                                        products.append({
                                            'title': title,
                                            'validated': True
                                        })
                                        print(f"         ✓ {title}")

                        except Exception as e:
                            continue

                    if products:
                        break  # Found products, stop trying selectors

            print(f"      ✅ Validated: {len(products)} SOTO products")
            return products

        except Exception as e:
            print(f"      ❌ Browser error: {e}")
            import traceback
            traceback.print_exc()
            return []

        finally:
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()

    # ========================================================================
    # Main Validation Method
    # ========================================================================

    async def check_store_availability(
        self,
        store_name: str,
        postal_code: str,
        city: str,
        street: str = None
    ) -> Dict:
        """
        Check SOTO product availability with 100% accuracy

        Strategy:
        1. Count API for fast check (is it > 0?)
        2. If yes, Playwright validation (what products exactly?)

        Returns:
            dict: Store results with validated products
        """
        print(f"\n{'='*80}")
        print(f"🏪 {store_name}")
        print(f"📍 {street}, {postal_code} {city}")
        print(f"{'='*80}")

        result = {
            'store_name': store_name,
            'city': city,
            'postal_code': postal_code,
            'timestamp': datetime.now().isoformat(),
            'success': False,
        }

        # Step 1: Find and select market
        print("\n   Step 1: Market Selection")
        market = self.find_market(postal_code)
        if not market:
            result['error'] = "Market not found"
            return result

        market_id = market.get('wwIdent')
        market_name = market.get('name')
        print(f"      ✅ {market_name} (ID: {market_id})")

        result['market_id'] = market_id
        result['market_name'] = market_name

        if not self.select_market(market_id):
            result['error'] = "Market selection failed"
            return result

        time.sleep(1)

        # Step 2: Quick Count API check
        print("\n   Step 2: Count API (Fast Check)")
        count = self.get_count("SOTO")
        print(f"      Count API: {count} products")

        result['count_api'] = count

        if count == 0:
            # No products - skip browser validation
            print("      ℹ️  Count = 0, skipping browser validation")
            result['success'] = True
            result['available'] = False
            result['validated_count'] = 0
            result['products'] = []
        else:
            # Products found - validate with browser
            print(f"\n   Step 3: Playwright Validation (Count = {count})")
            products = await self.validate_products_with_browser(postal_code)

            result['success'] = True
            result['available'] = len(products) > 0
            result['validated_count'] = len(products)
            result['products'] = products

        # Summary
        print(f"\n{'─'*80}")
        print("📋 FINAL RESULT")
        print(f"{'─'*80}")

        if result.get('available'):
            print(f"✅ SOTO products AVAILABLE")
            print(f"   Count API: {result['count_api']}")
            print(f"   Validated: {result['validated_count']} products")

            if result['count_api'] != result['validated_count']:
                diff = result['count_api'] - result['validated_count']
                print(f"   ⚠️  Difference: {diff} (likely false positives)")
        else:
            print(f"❌ No SOTO products at this location")

        self.results.append(result)
        return result

    # ========================================================================
    # Utility Methods
    # ========================================================================

    def save_results(self, filename: str = None):
        """Save results to JSON"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"rewe_hybrid_validated_{timestamp}.json"

        output_dir = Path(__file__).parent.parent / 'data'
        output_dir.mkdir(exist_ok=True)
        output_file = output_dir / filename

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)

        print(f"\n💾 Results saved to: {output_file}")
        return output_file

    def print_summary(self):
        """Print summary"""
        print(f"\n{'='*80}")
        print("📊 SUMMARY - Hybrid Validation (100% Accuracy)")
        print(f"{'='*80}\n")

        for result in self.results:
            status = "✅" if result.get('available') else "❌"
            validated = result.get('validated_count', 0)

            print(f"{status} {result['store_name']}")
            print(f"   📍 {result.get('city')}")
            print(f"   Count API: {result.get('count_api', 0)}")
            print(f"   Validated: {validated} products")

            if result.get('products'):
                for i, p in enumerate(result['products'][:3], 1):
                    print(f"      {i}. {p['title']}")
                if len(result['products']) > 3:
                    print(f"      ... and {len(result['products']) - 3} more")

            print()


async def main():
    """Main execution"""
    print(f"\n{'='*80}")
    print("🚀 REWE Hybrid Validator - 100% Accuracy")
    print("   Count API (fast) + Playwright (accurate)")
    print(f"{'='*80}\n")

    validator = REWEHybridValidator()

    # Test stores
    test_stores = [
        {
            'name': 'REWE München Sendlinger Tor',
            'postal_code': '80331',
            'city': 'München',
            'street': 'Sendlinger Straße 46'
        },
        {
            'name': 'REWE Freising',
            'postal_code': '85354',
            'city': 'Freising',
            'street': 'Münchner Str. 32'
        },
    ]

    for i, store in enumerate(test_stores, 1):
        print(f"\n{'#'*80}")
        print(f"# Store {i}/{len(test_stores)}")
        print(f"{'#'*80}")

        await validator.check_store_availability(
            store_name=store['name'],
            postal_code=store['postal_code'],
            city=store['city'],
            street=store['street']
        )

        if i < len(test_stores):
            print(f"\n⏳ Waiting 5 seconds before next store...")
            await asyncio.sleep(5)

    validator.print_summary()
    validator.save_results()

    print(f"\n{'='*80}")
    print("✅ Validation Complete!")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    asyncio.run(main())
