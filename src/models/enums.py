"""
Enumeration types for literature data models.

This module defines the enumeration types used in the literature schema classes,
based on the database design in docs/database_design.md.
"""

from enum import Enum


class IdentifierType(Enum):
    """Enumeration for different types of article identifiers."""
    DOI = "doi"
    PMID = "pmid"
    ARXIV_ID = "arxiv_id"
    SEMANTIC_SCHOLAR_ID = "semantic_scholar_id"
    WOS_UID = "wos_uid"
    PII = "pii"
    PMC_ID = "pmc_id"
    CORPUS_ID = "corpus_id"


class VenueType(Enum):
    """Enumeration for different types of publication venues."""
    JOURNAL = "journal"
    CONFERENCE = "conference"
    PREPRINT_SERVER = "preprint_server"
    BOOK = "book"
    OTHER = "other"


class CategoryType(Enum):
    """Enumeration for different types of subject categories."""
    MESH_DESCRIPTOR = "mesh_descriptor"
    ARXIV_CATEGORY = "arxiv_category"
    FIELD_OF_STUDY = "field_of_study"
    WOS_CATEGORY = "wos_category"
    OTHER = "other"


class PublicationTypeSource(Enum):
    """Enumeration for publication type sources."""
    PUBMED = "pubmed"
    SEMANTIC_SCHOLAR = "semantic_scholar"
    WOS = "wos"
    GENERAL = "general"