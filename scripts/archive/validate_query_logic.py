#!/usr/bin/env python3
"""
Validate what "SOTO Bio" query actually finds
"""

import time
from curl_cffi import requests

session = requests.Session()
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json, text/plain, */*',
}

# Select München market
print("Setting up München market...")
session.get(
    "https://www.rewe.de/api/wksmarketsearch",
    params={'searchTerm': '80331'},
    headers=headers,
    impersonate="chrome120"
)

session.post(
    "https://www.rewe.de/api/wksmarketselection/userselections",
    json={'selectedService': 'STATIONARY', 'customerZipCode': None, 'wwIdent': '562368'},
    headers=headers,
    impersonate="chrome120"
)

time.sleep(1)

# Test queries
queries = [
    'SOTO',
    'SOTO Bio',
    'Bio',
    'Bio SOTO',
    '"SOTO"',
    '"SOTO Bio"',
    '+SOTO +Bio',
]

print("\n📊 Query Test Results:\n")
print(f"{'Query':<20} {'Count':>10}")
print("=" * 35)

for query in queries:
    response = session.get(
        "https://www.rewe.de/api/stationary-product-search/products/count",
        params={'query': query},
        headers=headers,
        impersonate="chrome120"
    )

    count = response.json().get('totalHits', 0) if response.status_code == 200 else 0
    print(f"{query:<20} {count:>10}")
    time.sleep(0.5)

print("\n🔍 Analysis:")
print("If 'SOTO Bio' ≈ 'Bio', then it's finding ALL Bio products!")
print("If 'SOTO Bio' is between 'SOTO' and 'Bio', it's using OR logic")
print("If 'SOTO Bio' < 'SOTO', it's using AND logic (correct!)")
