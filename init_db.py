"""
Database initialization script.
Runs migrations and seeds default data.
"""

import os
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.dirname(__file__))

from models import DEFAULT_ROLES, Base, Role  # noqa: E402


def get_database_url():
    return os.getenv(
        "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/app_db"
    )


def init_db():
    """Initialize database: run migrations and seed data."""
    engine = create_engine(get_database_url())

    print("Creating tables...")
    Base.metadata.create_all(engine)
    print("Tables created successfully.")

    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    try:
        existing_roles = session.query(Role).count()
        if existing_roles > 0:
            print(f"Database already has {existing_roles} roles. Skipping seed.")
            return

        print("Seeding default roles...")
        for role_name, role_data in DEFAULT_ROLES.items():
            role = Role(
                name=role_name,
                description=role_data["description"],
                permissions=role_data["permissions"],
            )
            session.add(role)

        session.commit()
        print("Default roles seeded successfully.")
        print(f"Roles created: {list(DEFAULT_ROLES.keys())}")

    except Exception as e:
        session.rollback()
        print(f"Error during initialization: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    init_db()
