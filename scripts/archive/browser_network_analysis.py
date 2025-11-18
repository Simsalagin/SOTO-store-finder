#!/usr/bin/env python3
"""
Browser Network Analysis for REWE SOTO Products
Uses undetected-chromedriver to capture actual API calls made by the browser
"""

import json
import time
from pathlib import Path
from datetime import datetime

try:
    import undetected_chromedriver as uc
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
except ImportError:
    print("❌ undetected-chromedriver not installed")
    print("   Run: pip install undetected-chromedriver selenium")
    exit(1)


class BrowserNetworkAnalyzer:
    """Captures network requests from actual browser to find hidden APIs"""

    def __init__(self):
        self.driver = None
        self.network_log = []

    def setup_driver(self):
        """Setup Chrome with network logging"""
        print("\n🚀 Starting Chrome with network logging...")

        options = uc.ChromeOptions()

        # Enable performance logging to capture network requests
        options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})

        # Optional: Run headless (uncomment if needed)
        # options.add_argument('--headless=new')

        options.add_argument('--window-size=1920,1080')
        options.add_argument('--disable-blink-features=AutomationControlled')

        self.driver = uc.Chrome(options=options, use_subprocess=False)
        print("✅ Chrome started")

    def capture_network_traffic(self, url: str, wait_time: int = 10):
        """
        Load a page and capture all network requests

        Args:
            url: URL to load
            wait_time: Time to wait for page to load (seconds)
        """
        print(f"\n📄 Loading: {url}")
        self.driver.get(url)

        print(f"⏳ Waiting {wait_time} seconds for page to fully load...")
        time.sleep(wait_time)

        print("📊 Capturing network traffic...")

        # Get performance logs
        logs = self.driver.get_log('performance')

        # Parse logs to extract network requests
        api_requests = []

        for entry in logs:
            try:
                log = json.loads(entry['message'])
                message = log.get('message', {})

                # Look for Network events
                if message.get('method', '').startswith('Network'):
                    params = message.get('params', {})

                    # Network.requestWillBeSent - outgoing requests
                    if message['method'] == 'Network.requestWillBeSent':
                        request = params.get('request', {})
                        request_url = request.get('url', '')

                        # Filter for API calls
                        if '/api/' in request_url or 'soto' in request_url.lower():
                            api_requests.append({
                                'type': 'request',
                                'url': request_url,
                                'method': request.get('method'),
                                'headers': request.get('headers', {}),
                                'timestamp': params.get('timestamp')
                            })

                    # Network.responseReceived - responses
                    elif message['method'] == 'Network.responseReceived':
                        response = params.get('response', {})
                        response_url = response.get('url', '')

                        if '/api/' in response_url or 'soto' in response_url.lower():
                            # Find matching request
                            matching_request = next(
                                (r for r in api_requests if r['url'] == response_url and r['type'] == 'request'),
                                None
                            )

                            if matching_request:
                                matching_request['status'] = response.get('status')
                                matching_request['statusText'] = response.get('statusText')
                                matching_request['responseHeaders'] = response.get('headers', {})

            except Exception as e:
                continue  # Skip malformed log entries

        self.network_log = api_requests
        print(f"✅ Captured {len(api_requests)} API requests")

        return api_requests

    def analyze_soto_search(self, postal_code: str = "80331"):
        """
        Analyze network traffic when searching for SOTO products

        Args:
            postal_code: Postal code for market selection
        """
        print(f"\n{'='*80}")
        print("🔍 ANALYZING SOTO SEARCH NETWORK TRAFFIC")
        print(f"{'='*80}\n")

        try:
            self.setup_driver()

            # Step 1: Go to REWE homepage
            print("\n--- Step 1: Homepage ---")
            self.driver.get("https://www.rewe.de")
            time.sleep(3)

            # Step 2: Search for SOTO
            print("\n--- Step 2: Searching for 'SOTO' ---")
            try:
                # Find search input
                search_input = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='search'], input[placeholder*='Suche']"))
                )

                search_input.clear()
                search_input.send_keys("SOTO")

                # Submit search
                from selenium.webdriver.common.keys import Keys
                search_input.send_keys(Keys.RETURN)

                time.sleep(5)  # Wait for results

                # Capture network traffic
                requests = self.capture_network_traffic(self.driver.current_url, wait_time=2)

                # Analyze captured requests
                print("\n📋 API Endpoints Found:")
                unique_urls = set()
                for req in requests:
                    url = req['url']
                    if url not in unique_urls:
                        unique_urls.add(url)
                        print(f"\n   {req['method']} {url}")
                        print(f"      Status: {req.get('status', 'pending')}")

                        # Check for interesting query parameters
                        if '?' in url:
                            query_part = url.split('?')[1]
                            print(f"      Params: {query_part}")

            except Exception as e:
                print(f"⚠️  Could not complete search: {e}")

            # Save results
            self.save_results()

        finally:
            if self.driver:
                print("\n🔒 Closing browser...")
                self.driver.quit()

    def analyze_product_detail_page(self):
        """
        Navigate to a SOTO product detail page and capture API calls
        This might reveal product availability/stock APIs
        """
        print(f"\n{'='*80}")
        print("🔍 ANALYZING PRODUCT DETAIL PAGE")
        print(f"{'='*80}\n")

        try:
            self.setup_driver()

            # Example product: SOTO Bio product (we know it exists)
            # In a real scenario, we'd use a SOTO outdoor product URL
            search_url = "https://www.rewe.de/suche/uebersicht?searchTerm=SOTO"

            print(f"📄 Loading search page...")
            self.driver.get(search_url)
            time.sleep(5)

            # Try to click on first product
            try:
                print("🖱️  Clicking on first product...")
                product_link = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='/produkte/']"))
                )

                product_url = product_link.get_attribute('href')
                print(f"   Product URL: {product_url}")

                # Navigate to product page
                self.driver.get(product_url)
                time.sleep(5)

                # Capture network traffic from product page
                requests = self.capture_network_traffic(self.driver.current_url, wait_time=3)

                # Look for availability/stock APIs
                print("\n📋 Product Detail APIs:")
                for req in requests:
                    url = req['url']
                    if any(keyword in url.lower() for keyword in ['availability', 'stock', 'product', 'detail']):
                        print(f"\n   {req['method']} {url}")
                        print(f"      Status: {req.get('status', 'pending')}")

            except Exception as e:
                print(f"⚠️  Could not access product detail: {e}")

            # Save results
            self.save_results()

        finally:
            if self.driver:
                print("\n🔒 Closing browser...")
                self.driver.quit()

    def save_results(self):
        """Save captured network traffic to file"""
        output_dir = Path(__file__).parent.parent / 'data' / 'investigation'
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = output_dir / f'network_capture_{timestamp}.json'

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'total_requests': len(self.network_log),
                'requests': self.network_log
            }, f, indent=2, ensure_ascii=False)

        print(f"\n💾 Network log saved to: {output_file}")

        # Also create a summary
        summary_file = output_dir / f'network_summary_{timestamp}.txt'
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write("REWE SOTO Network Analysis Summary\n")
            f.write("=" * 80 + "\n\n")

            f.write(f"Total API Requests: {len(self.network_log)}\n\n")

            f.write("Unique Endpoints:\n")
            f.write("-" * 80 + "\n")

            unique_urls = {}
            for req in self.network_log:
                url = req['url']
                method = req['method']
                key = f"{method} {url}"

                if key not in unique_urls:
                    unique_urls[key] = req

            for key, req in unique_urls.items():
                f.write(f"\n{key}\n")
                f.write(f"  Status: {req.get('status', 'N/A')}\n")

                # Extract base URL and params
                if '?' in req['url']:
                    base_url, params = req['url'].split('?', 1)
                    f.write(f"  Base: {base_url}\n")
                    f.write(f"  Params: {params}\n")

        print(f"💾 Summary saved to: {summary_file}")


def main():
    """Main execution"""
    print(f"\n{'#'*80}")
    print("# Browser Network Analysis for REWE SOTO Products")
    print("# Goal: Discover hidden APIs by analyzing browser network traffic")
    print(f"{'#'*80}\n")

    analyzer = BrowserNetworkAnalyzer()

    print("This tool will open Chrome and navigate to REWE website")
    print("to capture actual API calls made by the browser.")
    print("\nChoose analysis mode:")
    print("1. Analyze SOTO search")
    print("2. Analyze product detail page")
    print("3. Both")

    choice = input("\nEnter choice (1-3) [default: 1]: ").strip() or "1"

    if choice in ["1", "3"]:
        analyzer.analyze_soto_search()

    if choice in ["2", "3"]:
        # Create new instance for second analysis
        if choice == "3":
            analyzer = BrowserNetworkAnalyzer()
        analyzer.analyze_product_detail_page()

    print(f"\n{'#'*80}")
    print("# Analysis Complete")
    print(f"{'#'*80}\n")


if __name__ == "__main__":
    main()
