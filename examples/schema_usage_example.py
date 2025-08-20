"""
Example usage of the literature schema classes.

This script demonstrates how to create, validate, and manipulate
literature schema objects.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models import (
    LiteratureSchema, ArticleSchema, AuthorSchema, VenueSchema,
    IdentifierType, VenueType, CategoryType
)


def create_sample_literature():
    """Create a sample literature record."""
    # Create a literature schema instance
    literature = LiteratureSchema()
    
    # Set article information
    literature.article = ArticleSchema(
        primary_doi="10.1038/nature12373",
        title="CRISPR-Cas9: A Revolutionary Gene Editing Tool",
        abstract="CRISPR-Cas9 is a revolutionary gene editing technology that allows precise modification of DNA sequences.",
        publication_year=2023,
        publication_date="2023-06-15",
        citation_count=1250,
        reference_count=45,
        is_open_access=True,
        open_access_url="https://example.com/paper.pdf"
    )
    
    # Add authors
    literature.add_author(
        "Jennifer A. Doudna",
        orcid="0000-0001-9947-4435",
        is_corresponding=True,
        affiliation="University of California, Berkeley"
    )
    literature.add_author(
        "Emmanuelle Charpentier",
        orcid="0000-0002-4343-6567",
        affiliation="Max Planck Institute for Infection Biology"
    )
    
    # Set venue information
    literature.venue = VenueSchema(
        venue_name="Nature",
        venue_type=VenueType.JOURNAL,
        iso_abbreviation="Nature",
        issn_print="0028-0836",
        issn_electronic="1476-4687",
        publisher="Nature Publishing Group"
    )
    
    # Add identifiers
    literature.add_identifier(IdentifierType.DOI, "10.1038/nature12373", is_primary=True)
    literature.add_identifier(IdentifierType.PMID, "23287718")
    
    # Add categories
    literature.add_category(
        "Gene Editing",
        CategoryType.FIELD_OF_STUDY,
        is_major_topic=True,
        confidence_score=0.95
    )
    literature.add_category(
        "CRISPR-Cas Systems",
        CategoryType.MESH_DESCRIPTOR,
        is_major_topic=True
    )
    
    # Add source-specific information
    literature.source_specific = {
        'source': 'pubmed',
        'retrieved_at': '2024-01-15T10:30:00Z',
        'raw_data': {'pmid': '23287718', 'journal_nlm_id': '0410462'}
    }
    
    return literature


def demonstrate_validation():
    """Demonstrate schema validation."""
    print("=== Schema Validation Demo ===")
    
    # Valid literature
    literature = create_sample_literature()
    is_valid, errors = literature.validate()
    print(f"Valid literature: {is_valid}")
    if errors:
        print(f"Errors: {errors}")
    
    # Invalid literature - missing title
    invalid_literature = LiteratureSchema()
    is_valid, errors = invalid_literature.validate()
    print(f"\nInvalid literature (no title): {is_valid}")
    print(f"Errors: {errors}")
    
    # Invalid DOI
    invalid_literature.article.title = "Test Article"
    invalid_literature.article.primary_doi = "invalid-doi"
    is_valid, errors = invalid_literature.validate()
    print(f"\nInvalid literature (bad DOI): {is_valid}")
    print(f"Errors: {errors}")


def demonstrate_serialization():
    """Demonstrate serialization and deserialization."""
    print("\n=== Serialization Demo ===")
    
    # Create literature
    literature = create_sample_literature()
    
    # Convert to dictionary
    data = literature.to_dict()
    print(f"Converted to dict: {len(data)} top-level keys")
    print(f"Article title: {data['article']['title']}")
    print(f"Number of authors: {len(data['authors'])}")
    
    # Convert back from dictionary
    restored_literature = LiteratureSchema.from_dict(data)
    print(f"\nRestored from dict:")
    print(f"Title: {restored_literature.article.title}")
    print(f"DOI: {restored_literature.get_doi()}")
    print(f"Authors: {[author.full_name for author in restored_literature.authors]}")


def demonstrate_identifier_methods():
    """Demonstrate identifier manipulation methods."""
    print("\n=== Identifier Methods Demo ===")
    
    literature = create_sample_literature()
    
    # Get specific identifiers
    print(f"DOI: {literature.get_doi()}")
    print(f"PMID: {literature.get_pmid()}")
    print(f"ArXiv ID: {literature.get_arxiv_id()}")  # Should be None
    
    # Add more identifiers
    literature.add_identifier(IdentifierType.ARXIV_ID, "2301.00001")
    print(f"ArXiv ID after adding: {literature.get_arxiv_id()}")
    
    # Try to add duplicate (should be ignored)
    initial_count = len(literature.identifiers)
    literature.add_identifier(IdentifierType.DOI, "10.1038/nature12373")
    final_count = len(literature.identifiers)
    print(f"Identifiers before/after duplicate: {initial_count}/{final_count}")


def demonstrate_string_representations():
    """Demonstrate string representations."""
    print("\n=== String Representations Demo ===")
    
    literature = create_sample_literature()
    
    print(f"str(): {str(literature)}")
    print(f"repr(): {repr(literature)}")


def main():
    """Main demonstration function."""
    print("Literature Schema Classes Demo")
    print("=" * 50)
    
    # Create sample literature
    literature = create_sample_literature()
    print(f"Created literature record: {literature.article.title}")
    print(f"Authors: {len(literature.authors)}")
    print(f"Identifiers: {len(literature.identifiers)}")
    print(f"Categories: {len(literature.categories)}")
    
    # Run demonstrations
    demonstrate_validation()
    demonstrate_serialization()
    demonstrate_identifier_methods()
    demonstrate_string_representations()
    
    print("\n" + "=" * 50)
    print("Demo completed successfully!")


if __name__ == "__main__":
    main()