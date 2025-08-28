#!/usr/bin/env python3
"""
UUID Migration Validation Script

This script validates that the UUID migration was successful and
all models are working correctly with UUID primary keys.
"""

import asyncio
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import (
    get_db_session, 
    create_tables, 
    Article, 
    Author, 
    DataSource,
    generate_uuid,
    validate_uuid,
    UUIDConverter
)


async def validate_uuid_functionality():
    """Validate UUID functionality without creating test data."""
    print("🔍 Validating UUID functionality...")
    
    # Test UUID utilities
    print("✅ Testing UUID utilities...")
    test_uuid = generate_uuid()
    print(f"   Generated UUID: {test_uuid}")
    
    # Test UUID validation
    valid_uuid_str = str(test_uuid)
    validated = validate_uuid(valid_uuid_str)
    assert validated == test_uuid, "UUID validation failed"
    print(f"   UUID validation: ✅")
    
    # Test UUID converter
    converter = UUIDConverter()
    converted = converter.to_uuid(valid_uuid_str)
    assert converted == test_uuid, "UUID conversion failed"
    print(f"   UUID conversion: ✅")
    
    # Test invalid UUID
    invalid_result = validate_uuid("invalid-uuid")
    assert invalid_result is None, "Invalid UUID should return None"
    print(f"   Invalid UUID handling: ✅")


async def validate_database_schema():
    """Validate database schema and UUID primary keys."""
    print("🗄️  Validating database schema...")
    
    try:
        async with get_db_session() as session:
            # Test that we can create the session
            print("   Database connection: ✅")
            
            # Check that models have UUID primary keys
            article_id_column = Article.__table__.columns['id']
            assert 'UUID' in str(article_id_column.type), "Article ID should be UUID type"
            print("   Article model UUID primary key: ✅")
            
            author_id_column = Author.__table__.columns['id']
            assert 'UUID' in str(author_id_column.type), "Author ID should be UUID type"
            print("   Author model UUID primary key: ✅")
            
            source_id_column = DataSource.__table__.columns['id']
            assert 'UUID' in str(source_id_column.type), "DataSource ID should be UUID type"
            print("   DataSource model UUID primary key: ✅")
            
    except Exception as e:
        print(f"   ❌ Database validation failed: {e}")
        return False
    
    return True


async def validate_model_creation():
    """Validate that models can be instantiated with UUID primary keys."""
    print("🏗️  Validating model instantiation...")
    
    try:
        # Test Article model
        article = Article(
            title="Test Article",
            abstract="Test abstract",
            language="eng"
        )
        print("   Article model instantiation: ✅")
        
        # Test Author model
        author = Author(
            full_name="Test Author",
            last_name="Author",
            fore_name="Test"
        )
        print("   Author model instantiation: ✅")
        
        # Test DataSource model
        source = DataSource(
            source_name="test_source",
            description="Test data source"
        )
        print("   DataSource model instantiation: ✅")
        
    except Exception as e:
        print(f"   ❌ Model instantiation failed: {e}")
        return False
    
    return True


async def main():
    """Main validation function."""
    print("🚀 Starting UUID Migration Validation")
    print("=" * 50)
    
    try:
        # Validate UUID functionality
        await validate_uuid_functionality()
        print()
        
        # Validate database schema
        schema_valid = await validate_database_schema()
        print()
        
        # Validate model creation
        models_valid = await validate_model_creation()
        print()
        
        if schema_valid and models_valid:
            print("🎉 All UUID validations passed!")
            print("✅ UUID migration implementation is working correctly")
            return True
        else:
            print("❌ Some validations failed")
            return False
            
    except Exception as e:
        print(f"❌ Validation failed with error: {e}")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)