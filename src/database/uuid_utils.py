"""
UUID utilities for database operations.

This module provides utilities for working with UUID primary keys
and validating UUID-based database operations.
"""

import uuid
from typing import Union, Optional
from uuid import UUID


def generate_uuid() -> UUID:
    """Generate a new UUID4."""
    return uuid.uuid4()


def validate_uuid(uuid_string: Union[str, UUID]) -> Optional[UUID]:
    """Validate and convert UUID string to UUID object."""
    if isinstance(uuid_string, UUID):
        return uuid_string
    
    if isinstance(uuid_string, str):
        try:
            return UUID(uuid_string)
        except ValueError:
            return None
    
    return None


def is_valid_uuid(uuid_string: Union[str, UUID]) -> bool:
    """Check if a string or UUID object is a valid UUID."""
    return validate_uuid(uuid_string) is not None


def uuid_to_string(uuid_obj: UUID) -> str:
    """Convert UUID object to string representation."""
    return str(uuid_obj)


def create_uuid_from_string(uuid_string: str) -> UUID:
    """Create UUID from string, raise ValueError if invalid."""
    try:
        return UUID(uuid_string)
    except ValueError as e:
        raise ValueError(f"Invalid UUID string: {uuid_string}") from e


class UUIDConverter:
    """Utility class for UUID conversions and validations."""
    
    @staticmethod
    def to_uuid(value: Union[str, UUID, None]) -> Optional[UUID]:
        """Convert various types to UUID, return None if invalid."""
        if value is None:
            return None
        return validate_uuid(value)
    
    @staticmethod
    def to_string(value: Union[str, UUID, None]) -> Optional[str]:
        """Convert UUID to string, return None if invalid."""
        if value is None:
            return None
        
        if isinstance(value, str):
            # Validate it's a proper UUID string
            uuid_obj = validate_uuid(value)
            return str(uuid_obj) if uuid_obj else None
        
        if isinstance(value, UUID):
            return str(value)
        
        return None
    
    @staticmethod
    def ensure_uuid(value: Union[str, UUID]) -> UUID:
        """Ensure value is UUID, raise exception if not."""
        if isinstance(value, UUID):
            return value
        
        if isinstance(value, str):
            return create_uuid_from_string(value)
        
        raise TypeError(f"Expected UUID or string, got {type(value)}")


def create_test_uuid() -> UUID:
    """Create a deterministic UUID for testing purposes."""
    return UUID('12345678-1234-5678-1234-567812345678')


def is_nil_uuid(uuid_obj: UUID) -> bool:
    """Check if UUID is the nil UUID (all zeros)."""
    return uuid_obj == UUID('00000000-0000-0000-0000-000000000000')