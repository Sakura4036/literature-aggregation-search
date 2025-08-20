"""
Literature data models and schemas.

This module provides data models and schemas for literature information
based on the database design in docs/database_design.md.
"""

from .enums import IdentifierType, VenueType, CategoryType, PublicationTypeSource
from .schemas import (
    ArticleSchema,
    AuthorSchema,
    VenueSchema,
    PublicationSchema,
    IdentifierSchema,
    CategorySchema,
    PublicationTypeSchema,
    LiteratureSchema
)

__all__ = [
    'IdentifierType',
    'VenueType',
    'CategoryType',
    'PublicationTypeSource',
    'ArticleSchema',
    'AuthorSchema',
    'VenueSchema',
    'PublicationSchema',
    'IdentifierSchema',
    'CategorySchema',
    'PublicationTypeSchema',
    'LiteratureSchema'
]