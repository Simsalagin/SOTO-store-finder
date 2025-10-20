"""Test coordinate validation with sample data."""

from src.geocoding.validator import CoordinateValidator
import logging

logging.basicConfig(level=logging.INFO)


def test_validation():
    """Test coordinate validation with various scenarios."""
    print("=" * 60)
    print("Testing Coordinate Validation")
    print("=" * 60)

    validator = CoordinateValidator()

    # Test cases
    test_cases = [
        {
            'name': 'Valid coordinates - Berlin',
            'lat': 52.587174,
            'lon': 13.389093,
            'street': 'Friedrich-Engels-Str. 92',
            'postal_code': '13156',
            'city': 'Berlin',
            'expected': 'valid'
        },
        {
            'name': 'Null Island (0, 0)',
            'lat': 0.0,
            'lon': 0.0,
            'street': 'Teststr. 1',
            'postal_code': '12345',
            'city': 'Berlin',
            'expected': 'invalid'
        },
        {
            'name': 'Coordinates outside Germany',
            'lat': 48.8566,  # Paris
            'lon': 2.3522,
            'street': 'Teststr. 1',
            'postal_code': '10115',
            'city': 'Berlin',
            'expected': 'invalid'
        },
        {
            'name': 'Valid coordinates - Munich',
            'lat': 48.1351,
            'lon': 11.5820,
            'street': 'Marienplatz 1',
            'postal_code': '80331',
            'city': 'München',
            'expected': 'valid'
        },
    ]

    print("\nRunning validation tests...\n")

    for i, test in enumerate(test_cases, 1):
        print(f"Test {i}: {test['name']}")
        print(f"  Coords: ({test['lat']}, {test['lon']})")
        print(f"  Address: {test['street']}, {test['postal_code']} {test['city']}")

        result = validator.validate_coordinates(
            latitude=test['lat'],
            longitude=test['lon'],
            street=test['street'],
            postal_code=test['postal_code'],
            city=test['city'],
            country_code='DE'
        )

        status = "✓ PASS" if (result['valid'] and test['expected'] == 'valid') or \
                             (not result['valid'] and test['expected'] == 'invalid') else "✗ FAIL"

        print(f"  Result: {'VALID' if result['valid'] else 'INVALID'} "
              f"(confidence: {result['confidence']:.2f})")
        if result['issues']:
            print(f"  Issues: {', '.join(result['issues'])}")
        if result['reverse_geocoded_address']:
            print(f"  Reverse: {result['reverse_geocoded_address'][:80]}...")
        if result['distance_km'] is not None:
            print(f"  Distance: {result['distance_km']:.2f} km")
        print(f"  {status}\n")

    print("=" * 60)
    print("Validation tests completed")
    print("=" * 60)


if __name__ == "__main__":
    test_validation()
