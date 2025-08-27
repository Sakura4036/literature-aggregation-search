import logging
from dataclasses import dataclass
from typing import Dict, List
from src.models.enums import IdentifierType, VenueType, CategoryType, PublicationTypeSource
from src.models.schemas import LiteratureSchema, ArticleSchema, AuthorSchema, VenueSchema, PublicationSchema, IdentifierSchema, CategorySchema, PublicationTypeSchema

logger = logging.getLogger(__name__)


@dataclass
class SemanticScholarPaper:
    """ Semantic Scholar Paper"""
    paperId: str
    corpusId: int
    externalIds: dict
    url: str
    title: str
    abstract: str
    venue: str
    publicationVenue: dict
    year: int
    referenceCount: int
    citationCount: int
    influentialCitationCount: int
    isOpenAccess: bool
    openAccessPdf: dict
    fieldsOfStudy: list[str]
    publicationTypes: list[str]
    publicationDate: str  # YYYY-MM-DD
    journal: dict
    citationStyles: dict  # BibTex
    authors: list[dict]
    citations: list[dict]  # list of Paper
    references: list[dict]  # list of Paper

    @staticmethod
    def batch_search_fields():
        return 'paperId,corpusId,externalIds,url,title,abstract,venue,publicationVenue,year,referenceCount,citationCount,influentialCitationCount,isOpenAccess,openAccessPdf,fieldsOfStudy,publicationTypes,publicationDate,journal,citationStyles,authors'

    @staticmethod
    def detail_fields():
        return 'paperId,corpusId,externalIds,url,title,abstract,venue,publicationVenue,year,referenceCount,citationCount,influentialCitationCount,isOpenAccess,openAccessPdf,fieldsOfStudy,publicationTypes,publicationDate,journal,citationStyles,authors,citations,references'

    @staticmethod
    def get_fields(fields):
        if not fields:
            return SemanticScholarPaper.batch_search_fields()
        if fields.lower == 'detail':
            return SemanticScholarPaper.detail_fields()
        return fields
    

class SemanticResultFormatter:
    """ 
    A utility class to format Semantic Scholar API results into LiteratureSchema format.
    """

    def response_format(self, results: List[Dict]) -> List[Dict]:
        """
        Format raw Semantic Scholar results into LiteratureSchema format.
        
        Args:
            results: Raw search results from Semantic Scholar API
            
        Returns:
            List[Dict]: Formatted results conforming to LiteratureSchema
        """
        formatted_results = []
        
        for item in results:
            try:
                # Create LiteratureSchema instance
                literature = self._format_single_result(item)
                formatted_results.append(literature.to_dict())
            except Exception as e:
                logger.warning(f"Error formatting result: {e}, skipping item")
                continue
        
        return formatted_results
    
    def _format_single_result(self, item: Dict) -> LiteratureSchema:
        """
        Format a single Semantic Scholar result into LiteratureSchema.
        
        Args:
            item: Single raw result from Semantic Scholar
            
        Returns:
            LiteratureSchema: Formatted literature record
        """
        # Extract DOI from externalIds or direct field
        doi = item.get('doi') or item.get('externalIds', {}).get('DOI')
        
        # Create article information
        article = ArticleSchema(
            primary_doi=doi,
            title=item.get('title', ''),
            abstract=item.get('abstract'),
            publication_year=item.get('year'),
            publication_date=item.get('published_date'),
            citation_count=item.get('citation_count', item.get('citationCount', 0)),
            reference_count=item.get('references_count', item.get('referenceCount', 0)),
            influential_citation_count=item.get('influentialCitationCount', 0),
            is_open_access=item.get('isOpenAccess', False),
            open_access_url=self._extract_open_access_url(item)
        )
        
        # Create authors
        authors = []
        for i, author_name in enumerate(item.get('authors', [])):
            if isinstance(author_name, str):
                authors.append(AuthorSchema(
                    full_name=author_name,
                    author_order=i + 1
                ))
            elif isinstance(author_name, dict):
                # Handle detailed author information from raw Semantic Scholar data
                authors.append(AuthorSchema(
                    full_name=author_name.get('name', ''),
                    semantic_scholar_id=author_name.get('authorId'),
                    affiliation=', '.join(author_name.get('affiliations', [])) if author_name.get('affiliations') else None,
                    author_order=i + 1
                ))
        
        # Create venue information
        venue_name = item.get('venue', '')
        if not venue_name and item.get('journal'):
            if isinstance(item['journal'], dict):
                venue_name = item['journal'].get('name', '')
            else:
                venue_name = str(item['journal'])
        
        venue_type = self._determine_venue_type(item)
        
        venue = VenueSchema(
            venue_name=venue_name,
            venue_type=venue_type
        )
        
        # Create publication information
        volume = item.get('volume')
        issue = item.get('issue')
        
        # Extract from journal object if available
        if item.get('journal') and isinstance(item['journal'], dict):
            volume = volume or item['journal'].get('volume')
            issue = issue or item['journal'].get('pages')  # Semantic Scholar uses 'pages' for issue info
        
        publication = PublicationSchema(
            volume=volume,
            issue=issue
        )
        
        # Create identifiers
        identifiers = []
        # Add DOI from externalIds or direct field
        if doi:
            identifiers.append(IdentifierSchema(
                identifier_type=IdentifierType.DOI,
                identifier_value=doi,
                is_primary=True
            ))
        
        # Add other identifiers from externalIds
        external_ids = item.get('externalIds', {})
        if external_ids.get('PubMed'):
            identifiers.append(IdentifierSchema(
                identifier_type=IdentifierType.PMID,
                identifier_value=external_ids['PubMed'],
                is_primary=False
            ))
        
        if external_ids.get('ArXiv'):
            identifiers.append(IdentifierSchema(
                identifier_type=IdentifierType.ARXIV_ID,
                identifier_value=external_ids['ArXiv'],
                is_primary=False
            ))
        
        # Also check for direct fields (for backward compatibility)
        self._add_identifier_if_exists(identifiers, item, 'pmid', IdentifierType.PMID)
        self._add_identifier_if_exists(identifiers, item, 'arxiv_id', IdentifierType.ARXIV_ID)
        
        # Add Semantic Scholar specific identifiers
        if item.get('paperId'):
            identifiers.append(IdentifierSchema(
                identifier_type=IdentifierType.SEMANTIC_SCHOLAR_ID,
                identifier_value=item['paperId'],
                is_primary=False
            ))
        
        if item.get('corpusId'):
            identifiers.append(IdentifierSchema(
                identifier_type=IdentifierType.CORPUS_ID,
                identifier_value=str(item['corpusId']),
                is_primary=False
            ))
        
        # Create categories from fields of study
        categories = []
        for field in item.get('fieldsOfStudy', []):
            if isinstance(field, str):
                categories.append(CategorySchema(
                    category_name=field,
                    category_type=CategoryType.FIELD_OF_STUDY
                ))
        
        # Handle s2FieldsOfStudy if available
        for field in item.get('s2FieldsOfStudy', []):
            if isinstance(field, dict) and field.get('category'):
                categories.append(CategorySchema(
                    category_name=field['category'],
                    category_type=CategoryType.FIELD_OF_STUDY,
                    confidence_score=field.get('score')
                ))
        
        # Create publication types
        publication_types = []
        for pub_type in item.get('types', []):
            publication_types.append(PublicationTypeSchema(
                type_name=pub_type,
                source_type=PublicationTypeSource.SEMANTIC_SCHOLAR
            ))
        
        # Create complete literature schema
        literature = LiteratureSchema(
            article=article,
            authors=authors,
            venue=venue,
            publication=publication,
            identifiers=identifiers,
            categories=categories,
            publication_types=publication_types,
            source_specific={
                'source': self.get_source_name(),
                'raw_data': item.get('semantic_scholar', item)
            }
        )
        
        return literature
    
    def _extract_open_access_url(self, item: Dict) -> Optional[str]:
        """Extract open access URL from Semantic Scholar data."""
        # Check for openAccessPdf URL
        if item.get('openAccessPdf'):
            if isinstance(item['openAccessPdf'], dict):
                return item['openAccessPdf'].get('url')
            elif isinstance(item['openAccessPdf'], str):
                return item['openAccessPdf']
        return None
    
    def _determine_venue_type(self, item: Dict) -> VenueType:
        """Determine venue type from Semantic Scholar data."""
        # Check publicationVenue type if available
        if item.get('publicationVenue', {}).get('type') == 'conference':
            return VenueType.CONFERENCE
        elif item.get('journal'):
            return VenueType.JOURNAL
        else:
            return VenueType.OTHER
    
    def _add_identifier_if_exists(self, identifiers: List[IdentifierSchema], item: Dict, 
                                 key: str, identifier_type: IdentifierType, is_primary: bool = False):
        """Add identifier if it exists in the item."""
        value = item.get(key)
        if value and str(value).strip():
            identifiers.append(IdentifierSchema(
                identifier_type=identifier_type,
                identifier_value=str(value).strip(),
                is_primary=is_primary
            ))