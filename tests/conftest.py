import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from db.db_models import Base

@pytest.fixture(scope="function")
def db_session():
    # Use SQLite in-memory for tests
    engine = create_engine("sqlite:///:memory:")
    TestingSessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    yield session
    session.close()