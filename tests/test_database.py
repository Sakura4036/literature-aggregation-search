import pytest
import pytest_asyncio
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from src.database.connection import AsyncDatabaseManager
from src.database.services import LiteratureService
from src.models import schemas
from src.models.enums import IdentifierType

# Test database URL (in-memory SQLite)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest_asyncio.fixture(scope="function")
async def db_manager() -> AsyncGenerator[AsyncDatabaseManager, None]:
    """Fixture to create a new database manager for each test function."""
    manager = AsyncDatabaseManager(TEST_DATABASE_URL)
    await manager.create_tables()
    yield manager
    await manager.drop_tables()
    await manager.close()

@pytest_asyncio.fixture(scope="function")
async def db_session(db_manager: AsyncDatabaseManager) -> AsyncGenerator[AsyncSession, None]:
    """Fixture to get a database session for each test function."""
    async with db_manager.get_session() as session:
        yield session

@pytest.mark.asyncio
async def test_create_and_get_article(db_session: AsyncSession):
    """
    Test creating a new article and then retrieving it.
    """
    literature_service = LiteratureService(db_session)

    # 1. Create a literature schema object
    literature = schemas.LiteratureSchema(
        article=schemas.ArticleSchema(
            title="Test Article",
            abstract="This is a test abstract.",
            publication_year=2024,
            is_open_access=True,
        ),
        authors=[schemas.AuthorSchema(full_name="John Doe", author_order=1)],
        identifiers=[
            schemas.IdentifierSchema(
                identifier_type=IdentifierType.DOI,
                identifier_value="10.1234/test.doi"
            )
        ]
    )

    # 2. Create the article in the database
    created_article = await literature_service.create_or_update_article(literature)

    assert created_article is not None
    assert created_article.id is not None
    assert created_article.title == "Test Article"

    # 3. Retrieve the article from the database
    retrieved_article = await literature_service.get_article_by_id(created_article.id)

    assert retrieved_article is not None
    assert retrieved_article.title == "Test Article"
    assert retrieved_article.abstract == "This is a test abstract."
    assert len(retrieved_article.authors) == 1
    assert retrieved_article.authors[0].author.full_name == "John Doe"
    assert len(retrieved_article.identifiers) == 1
    assert retrieved_article.identifiers[0].identifier_value == "10.1234/test.doi"

@pytest.mark.asyncio
async def test_find_article_by_identifier(db_session: AsyncSession):
    """
    Test finding an article by its identifier.
    """
    literature_service = LiteratureService(db_session)

    # Create a test article first
    literature = schemas.LiteratureSchema(
        article=schemas.ArticleSchema(title="Another Test Article"),
        identifiers=[
            schemas.IdentifierSchema(
                identifier_type=IdentifierType.PMID,
                identifier_value="12345678"
            )
        ]
    )
    await literature_service.create_or_update_article(literature)

    # Now try to find it
    found_article = await literature_service._find_article_by_identifiers(literature.identifiers)

    assert found_article is not None
    assert found_article.title == "Another Test Article"
