"""Fix stores with missing or invalid coordinates using geocoding."""

from src.storage.database import Database
from src.geocoding.geocoder import Geocoder
from sqlalchemy.orm import Session


def fix_invalid_coordinates():
    """Find and fix stores with invalid (0.0) coordinates."""
    print("=" * 60)
    print("Fixing Invalid Coordinates")
    print("=" * 60)

    # Initialize
    db = Database()
    geocoder = Geocoder(delay=1.5)  # Be conservative with API rate

    # Get stores with invalid coordinates
    from src.storage.database import StoreModel
    session = db.Session()
    try:
        all_stores = session.query(StoreModel).filter_by(chain_id='denns').all()

        invalid_stores = [
            s for s in all_stores
            if s.latitude == 0.0 or s.longitude == 0.0 or s.latitude is None or s.longitude is None
        ]

        print(f"\nFound {len(invalid_stores)} stores with invalid coordinates\n")

        if not invalid_stores:
            print("No stores need geocoding!")
            return

        # Geocode each store
        success_count = 0
        failed = []

        for i, store in enumerate(invalid_stores, 1):
            print(f"[{i}/{len(invalid_stores)}] Geocoding: {store.name}")
            print(f"    Address: {store.street}, {store.postal_code} {store.city}")

            coords = geocoder.geocode_address(
                street=store.street,
                postal_code=store.postal_code,
                city=store.city,
                country_code=store.country_code
            )

            if coords:
                lat, lon = coords
                store.latitude = lat
                store.longitude = lon
                print(f"    ✓ Success: {lat:.6f}, {lon:.6f}")
                success_count += 1
            else:
                print(f"    ✗ Failed to geocode")
                failed.append(store.name)

            print()

        # Commit changes
        session.commit()

        print("=" * 60)
        print(f"✓ Successfully geocoded: {success_count}/{len(invalid_stores)}")
        if failed:
            print(f"\n✗ Failed to geocode {len(failed)} stores:")
            for name in failed:
                print(f"  - {name}")
        print("=" * 60)

    except Exception as e:
        session.rollback()
        print(f"Error: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    fix_invalid_coordinates()
