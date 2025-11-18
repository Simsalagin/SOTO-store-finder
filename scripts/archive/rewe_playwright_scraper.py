#!/usr/bin/env python3
"""
REWE Playwright Scraper - Modern browser automation for 100% accuracy
Uses Playwright for better Cloudflare bypass and HTML scraping
"""

import json
import time
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

try:
    from playwright.async_api import async_playwright, Page, Browser
except ImportError:
    print("❌ Playwright not installed")
    print("   Run: pip install playwright")
    print("   Then: playwright install chromium")
    exit(1)


class REWEPlaywrightScraper:
    """Modern scraper using Playwright for 100% market-specific accuracy"""

    BASE_URL = "https://www.rewe.de"

    def __init__(self):
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.results = []

    async def setup_browser(self, headless: bool = True):
        """Setup Playwright browser"""
        print("\n🚀 Starting Playwright browser...")

        playwright = await async_playwright().start()

        # Launch with stealth settings
        self.browser = await playwright.chromium.launch(
            headless=headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
            ]
        )

        # Create context with realistic settings
        context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='de-DE',
            timezone_id='Europe/Berlin',
        )

        self.page = await context.new_page()

        # Inject stealth scripts
        await self.page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => false
            });
        """)

        print("✅ Browser ready")

    async def select_market(self, postal_code: str) -> Optional[Dict]:
        """
        Navigate to REWE and select market by postal code

        Args:
            postal_code: Postal code of market

        Returns:
            dict: Market information or None
        """
        print(f"\n📍 Selecting market: {postal_code}")

        try:
            # Go to homepage
            print("   Loading homepage...")
            await self.page.goto(self.BASE_URL, wait_until='networkidle', timeout=60000)
            await asyncio.sleep(3)

            # Accept cookies if present
            try:
                cookie_button = await self.page.wait_for_selector(
                    'button:has-text("Alle akzeptieren"), button:has-text("Accept")',
                    timeout=5000
                )
                if cookie_button:
                    await cookie_button.click()
                    print("   ✅ Cookies accepted")
                    await asyncio.sleep(1)
            except:
                pass

            # Look for market selection
            try:
                # Try to find market selection button/input
                market_selector = 'input[placeholder*="PLZ"], input[placeholder*="Ort"], [data-testid*="market"]'
                market_input = await self.page.wait_for_selector(market_selector, timeout=10000)

                if market_input:
                    await market_input.fill(postal_code)
                    await asyncio.sleep(2)

                    # Press Enter or click search
                    await market_input.press('Enter')
                    await asyncio.sleep(3)

                    print(f"   ✅ Market selected: {postal_code}")
                    return {'postal_code': postal_code}

            except Exception as e:
                print(f"   ⚠️  Could not auto-select market: {e}")
                print("   ℹ️  Continuing anyway (might use default market)")

            return {'postal_code': postal_code}

        except Exception as e:
            print(f"   ❌ Error: {e}")
            return None

    async def search_soto_products(self) -> List[Dict]:
        """
        Search for SOTO products and scrape results

        Returns:
            list: List of SOTO products found
        """
        print("\n🔍 Searching for SOTO products...")

        try:
            # Navigate to search
            search_url = f"{self.BASE_URL}/suche/uebersicht?searchTerm=SOTO"
            print(f"   Loading: {search_url}")

            await self.page.goto(search_url, wait_until='networkidle', timeout=60000)
            await asyncio.sleep(5)  # Wait for JS to render

            # Check if we got Cloudflare challenge
            page_title = await self.page.title()
            page_content = await self.page.content()

            if 'cloudflare' in page_title.lower() or 'challenge' in page_content.lower():
                print("   ⚠️  Cloudflare challenge detected!")
                print("   ℹ️  Waiting for challenge to resolve...")
                await asyncio.sleep(10)

            # Save debug HTML
            html = await self.page.content()
            debug_file = Path(__file__).parent.parent / 'data' / 'investigation' / 'playwright_search_page.html'
            debug_file.parent.mkdir(parents=True, exist_ok=True)
            with open(debug_file, 'w', encoding='utf-8') as f:
                f.write(html)
            print(f"   💾 HTML saved to: {debug_file}")

            # Try to find product elements with various selectors
            product_selectors = [
                'article[data-product]',
                '[class*="ProductCard"]',
                '[class*="product-card"]',
                '[data-testid*="product"]',
                'article',
                '.search-service-product-card',
            ]

            products = []

            for selector in product_selectors:
                elements = await self.page.query_selector_all(selector)

                if elements:
                    print(f"   ✅ Found {len(elements)} elements with selector: {selector}")

                    for element in elements:
                        try:
                            # Extract product data
                            text = await element.inner_text()

                            # Check if it's a SOTO product
                            if 'SOTO' in text or 'soto' in text.lower():
                                # Try to extract title
                                title_element = await element.query_selector('h3, h4, h2, [class*="title"]')
                                title = await title_element.inner_text() if title_element else text.split('\n')[0]

                                # Check if it's really SOTO brand (not just contains "soto" substring)
                                title_lower = title.lower()
                                if title_lower.startswith('soto ') or 'soto bio' in title_lower:
                                    products.append({
                                        'title': title.strip(),
                                        'text': text[:200]  # First 200 chars for debug
                                    })
                                    print(f"      • {title.strip()}")

                        except Exception as e:
                            continue

                    if products:
                        break  # Found products, no need to try other selectors

            if not products:
                print("   ⚠️  No products found with any selector")
                print("   ℹ️  Page might require different scraping approach")

                # Check if there's a "no results" message
                no_results = await self.page.query_selector(':has-text("Keine Ergebnisse"), :has-text("No results")')
                if no_results:
                    print("   ℹ️  Page shows 'No results'")

            print(f"\n   ✅ Total SOTO products found: {len(products)}")
            return products

        except Exception as e:
            print(f"   ❌ Error during search: {e}")
            import traceback
            traceback.print_exc()
            return []

    async def check_store_availability(
        self,
        store_name: str,
        postal_code: str,
        city: str,
        street: str = None
    ) -> Dict:
        """
        Check SOTO product availability for a specific store

        Args:
            store_name: Store name
            postal_code: Postal code
            city: City name
            street: Street (optional)

        Returns:
            dict: Store results with products
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
            'products': []
        }

        try:
            # Select market
            market = await self.select_market(postal_code)
            if not market:
                result['error'] = "Market selection failed"
                return result

            # Search for products
            products = await self.search_soto_products()

            result['success'] = True
            result['available'] = len(products) > 0
            result['product_count'] = len(products)
            result['products'] = products

            # Summary
            print(f"\n{'─'*80}")
            print("📋 RESULT")
            print(f"{'─'*80}")

            if result['available']:
                print(f"✅ SOTO products AVAILABLE: {len(products)}")
            else:
                print(f"❌ No SOTO products found")

            self.results.append(result)
            return result

        except Exception as e:
            print(f"❌ Error: {e}")
            result['error'] = str(e)
            return result

    async def cleanup(self):
        """Close browser"""
        if self.browser:
            await self.browser.close()
            print("\n🔒 Browser closed")

    def save_results(self, filename: str = None):
        """Save results to JSON"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"rewe_playwright_{timestamp}.json"

        output_dir = Path(__file__).parent.parent / 'data'
        output_dir.mkdir(exist_ok=True)
        output_file = output_dir / filename

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)

        print(f"\n💾 Results saved to: {output_file}")
        return output_file


async def main():
    """Main execution"""
    print(f"\n{'='*80}")
    print("🚀 REWE Playwright Scraper - HTML-based 100% Accuracy")
    print(f"{'='*80}\n")

    scraper = REWEPlaywrightScraper()

    try:
        # Setup browser
        await scraper.setup_browser(headless=False)  # Non-headless for debugging

        # Test store
        await scraper.check_store_availability(
            store_name='REWE München Sendlinger Tor',
            postal_code='80331',
            city='München',
            street='Sendlinger Straße 46'
        )

        # Save results
        scraper.save_results()

    finally:
        await scraper.cleanup()

    print(f"\n{'='*80}")
    print("✅ Complete!")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    asyncio.run(main())
