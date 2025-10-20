"""Database models and operations for store data."""

from sqlalchemy import create_engine, Column, String, Float, DateTime, JSON, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from typing import List, Optional
import os

Base = declarative_base()


class StoreModel(Base):
    """SQLAlchemy model for stores."""

    __tablename__ = "stores"

    # Primary identification
    id = Column(String, primary_key=True)  # Format: {chain_id}_{store_id}
    chain_id = Column(String, nullable=False, index=True)
    store_id = Column(String, nullable=False)

    # Basic information
    name = Column(String, nullable=False)
    street = Column(String, nullable=False)
    postal_code = Column(String, nullable=False)
    city = Column(String, nullable=False, index=True)
    country_code = Column(String, nullable=False, default='DE')

    # Geolocation
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)

    # Contact
    phone = Column(String, nullable=True)
    email = Column(String, nullable=True)
    website = Column(String, nullable=True)

    # Additional data (JSON)
    opening_hours = Column(JSON, nullable=True)
    services = Column(JSON, nullable=True)

    # Metadata
    scraped_at = Column(DateTime, nullable=False, default=datetime.now)
    updated_at = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)
    is_active = Column(String, nullable=False, default='true')  # 'true', 'false', 'closed'

    # Indexes for common queries
    __table_args__ = (
        Index('idx_chain_city', 'chain_id', 'city'),
        Index('idx_country', 'country_code'),
        Index('idx_location', 'latitude', 'longitude'),
    )


class Database:
    """Database connection and operations manager."""

    def __init__(self, database_path: str = None):
        """
        Initialize database connection.

        Args:
            database_path: Path to SQLite database file
        """
        if database_path is None:
            database_path = os.getenv('DATABASE_PATH', 'data/stores.db')

        # Ensure data directory exists
        os.makedirs(os.path.dirname(database_path), exist_ok=True)

        self.engine = create_engine(f'sqlite:///{database_path}')
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def save_stores(self, stores: List) -> int:
        """
        Save or update stores in the database.

        Args:
            stores: List of Store objects from scrapers

        Returns:
            Number of stores saved/updated
        """
        session = self.Session()
        count = 0

        try:
            for store in stores:
                # Create composite ID
                store_id = f"{store.chain_id}_{store.store_id}"

                # Check if store exists
                existing = session.query(StoreModel).filter_by(id=store_id).first()

                if existing:
                    # Update existing store
                    existing.name = store.name
                    existing.street = store.street
                    existing.postal_code = store.postal_code
                    existing.city = store.city
                    existing.country_code = store.country_code
                    existing.latitude = store.latitude
                    existing.longitude = store.longitude
                    existing.phone = store.phone
                    existing.email = store.email
                    existing.website = store.website
                    existing.opening_hours = store.opening_hours
                    existing.services = store.services
                    existing.updated_at = datetime.now()
                    existing.is_active = 'true'
                else:
                    # Create new store
                    store_model = StoreModel(
                        id=store_id,
                        chain_id=store.chain_id,
                        store_id=store.store_id,
                        name=store.name,
                        street=store.street,
                        postal_code=store.postal_code,
                        city=store.city,
                        country_code=store.country_code,
                        latitude=store.latitude,
                        longitude=store.longitude,
                        phone=store.phone,
                        email=store.email,
                        website=store.website,
                        opening_hours=store.opening_hours,
                        services=store.services,
                        scraped_at=store.scraped_at,
                    )
                    session.add(store_model)

                count += 1

            session.commit()
            return count

        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def get_stores(self, chain_id: Optional[str] = None, city: Optional[str] = None) -> List[StoreModel]:
        """
        Retrieve stores from database.

        Args:
            chain_id: Filter by chain ID
            city: Filter by city

        Returns:
            List of StoreModel objects
        """
        session = self.Session()
        try:
            query = session.query(StoreModel).filter_by(is_active='true')

            if chain_id:
                query = query.filter_by(chain_id=chain_id)
            if city:
                query = query.filter_by(city=city)

            return query.all()
        finally:
            session.close()

    def get_statistics(self) -> dict:
        """
        Get database statistics.

        Returns:
            Dictionary with statistics
        """
        session = self.Session()
        try:
            total = session.query(StoreModel).count()
            active = session.query(StoreModel).filter_by(is_active='true').count()

            chains = session.query(StoreModel.chain_id).distinct().all()
            chain_counts = {}
            for (chain_id,) in chains:
                count = session.query(StoreModel).filter_by(chain_id=chain_id, is_active='true').count()
                chain_counts[chain_id] = count

            return {
                'total_stores': total,
                'active_stores': active,
                'chains': chain_counts,
            }
        finally:
            session.close()
