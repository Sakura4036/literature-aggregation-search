"""
Unit tests for enumeration types in literature data models.
"""

import pytest
from src.models.enums import IdentifierType, VenueType, CategoryType, PublicationTypeSource


class TestIdentifierType:
    """Test cases for IdentifierType enum."""
    
    def test_identifier_type_values(self):
        """Test that all identifier types have correct values."""
        assert IdentifierType.DOI.value == "doi"
        assert IdentifierType.PMID.value == "pmid"
        assert IdentifierType.ARXIV_ID.value == "arxiv_id"
        assert IdentifierType.SEMANTIC_SCHOLAR_ID.value == "semantic_scholar_id"
        assert IdentifierType.WOS_UID.value == "wos_uid"
        assert IdentifierType.PII.value == "pii"
        assert IdentifierType.PMC_ID.value == "pmc_id"
        assert IdentifierType.CORPUS_ID.value == "corpus_id"
    
    def test_identifier_type_from_string(self):
        """Test creating IdentifierType from string values."""
        assert IdentifierType("doi") == IdentifierType.DOI
        assert IdentifierType("pmid") == IdentifierType.PMID
        assert IdentifierType("arxiv_id") == IdentifierType.ARXIV_ID
    
    def test_identifier_type_invalid_value(self):
        """Test that invalid values raise ValueError."""
        with pytest.raises(ValueError):
            IdentifierType("invalid_type")


class TestVenueType:
    """Test cases for VenueType enum."""
    
    def test_venue_type_values(self):
        """Test that all venue types have correct values."""
        assert VenueType.JOURNAL.value == "journal"
        assert VenueType.CONFERENCE.value == "conference"
        assert VenueType.PREPRINT_SERVER.value == "preprint_server"
        assert VenueType.BOOK.value == "book"
        assert VenueType.OTHER.value == "other"
    
    def test_venue_type_from_string(self):
        """Test creating VenueType from string values."""
        assert VenueType("journal") == VenueType.JOURNAL
        assert VenueType("conference") == VenueType.CONFERENCE
        assert VenueType("preprint_server") == VenueType.PREPRINT_SERVER
    
    def test_venue_type_invalid_value(self):
        """Test that invalid values raise ValueError."""
        with pytest.raises(ValueError):
            VenueType("invalid_venue")


class TestCategoryType:
    """Test cases for CategoryType enum."""
    
    def test_category_type_values(self):
        """Test that all category types have correct values."""
        assert CategoryType.MESH_DESCRIPTOR.value == "mesh_descriptor"
        assert CategoryType.ARXIV_CATEGORY.value == "arxiv_category"
        assert CategoryType.FIELD_OF_STUDY.value == "field_of_study"
        assert CategoryType.WOS_CATEGORY.value == "wos_category"
        assert CategoryType.OTHER.value == "other"
    
    def test_category_type_from_string(self):
        """Test creating CategoryType from string values."""
        assert CategoryType("mesh_descriptor") == CategoryType.MESH_DESCRIPTOR
        assert CategoryType("arxiv_category") == CategoryType.ARXIV_CATEGORY
        assert CategoryType("field_of_study") == CategoryType.FIELD_OF_STUDY


class TestPublicationTypeSource:
    """Test cases for PublicationTypeSource enum."""
    
    def test_publication_type_source_values(self):
        """Test that all publication type sources have correct values."""
        assert PublicationTypeSource.PUBMED.value == "pubmed"
        assert PublicationTypeSource.SEMANTIC_SCHOLAR.value == "semantic_scholar"
        assert PublicationTypeSource.WOS.value == "wos"
        assert PublicationTypeSource.GENERAL.value == "general"
    
    def test_publication_type_source_from_string(self):
        """Test creating PublicationTypeSource from string values."""
        assert PublicationTypeSource("pubmed") == PublicationTypeSource.PUBMED
        assert PublicationTypeSource("semantic_scholar") == PublicationTypeSource.SEMANTIC_SCHOLAR
        assert PublicationTypeSource("wos") == PublicationTypeSource.WOS
        assert PublicationTypeSource("general") == PublicationTypeSource.GENERAL