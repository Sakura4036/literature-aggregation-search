"""
Database module with UUID-based models and utilities.

This module provides database models, repositories, and utilities
for working with UUID primary keys.
"""

from .models import Base, Article, Author, Venue, DataSource
from .mixins import UUIDMixin, TimestampMixin
from .repositories import BaseRepository, ArticleRepository, AuthorRepository
from .uuid_utils import (
    generate_uuid, 
    validate_uuid, 
    is_valid_uuid, 
    UUIDConverter,
    create_test_uuid
)
from .connection import (
    get_db_session,
    create_tables,
    drop_tables,
    close_database,
    health_check,
    init_database,
    cleanup_database
)

__all__ = [
    # Models
    'Base',
    'Article', 
    'Author', 
    'Venue', 
    'DataSource',
    
    # Mixins
    'UUIDMixin',
    'TimestampMixin',
    
    # Repositories
    'BaseRepository',
    'ArticleRepository', 
    'AuthorRepository',
    
    # UUID utilities
    'generate_uuid',
    'validate_uuid',
    'is_valid_uuid',
    'UUIDConverter',
    'create_test_uuid',
    
    # Connection utilities
    'get_db_session',
    'create_tables',
    'drop_tables', 
    'close_database',
    'health_check',
    'init_database',
    'cleanup_database'
]