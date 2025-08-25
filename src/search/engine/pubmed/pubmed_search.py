"""
PubMed search API implementation with enhanced XML parsing.

This module provides search functionality for PubMed literature database,
using improved XML parsing based on the pubmed_xml_parser implementation.
"""

import logging
import time
import requests
import xml.etree.ElementTree as ET
from typing import Dict, List, Tuple, Optional


from src.search.engine.base_engine import BaseSearchEngine, NetworkError, FormatError
from src.search.utils import year_split
from .pubmed_xml_parser import parse_single_article
from src.models.schemas import (
    LiteratureSchema, ArticleSchema, AuthorSchema, VenueSchema,
    PublicationSchema, IdentifierSchema, CategorySchema, PublicationTypeSchema
)
from src.models.enums import IdentifierType, VenueType, CategoryType, PublicationTypeSource

logger = logging.getLogger(__name__)


class PubmedSearchAPI(BaseSearchEngine):
    """
    PubMed search API implementation.

    This class provides search functionality for PubMed literature database,
    inheriting from BaseSearchEngine to ensure consistent interface and behavior.
    """

    def __init__(self):
        """Initialize PubMed search API."""
        super().__init__()
        self.pubmed_search_url: str = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?"
        self.pubmed_fetch_url: str = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?"
        self.sleep_time: float = 1.0
        self.timeout_error_flag = False
        self.last_timeout_time = 0
        self.timeout_interval = 60

    def get_source_name(self) -> str:
        """Get the name of the data source."""
        return "pubmed"

    def query_for_pmid_list(self, query: str, year: str = '', field: str = '',
                            restart: int = 0, retmax: int = 20, date_type: str = 'mdat',
                            sort: str = 'relevance', retmode: str = 'json') -> dict:
        """
        Execute single PubMed search query.

        API doc: https://www.ncbi.nlm.nih.gov/books/NBK25499/#chapter4.ESearch

        Args:
            query: Search keywords
            year: Year range, format YYYY-YYYY
            field: Search field ('Title', 'Abstract', 'Author', 'Journal')
            restart: Starting result index
            retmax: Number of results to return, max 10000
            date_type: Date type ('mdat', 'pdat', 'edat')
            sort: Sort order ('relevance', 'pub_date', 'Author', 'JournalName')
            retmode: Return format ('json' or 'xml')

        Returns:
            dict: Dictionary containing search results
        """
        retmax = min(retmax, 10000)

        # 构建esearch请求URL
        params = {
            'db': 'pubmed',
            'term': query,
            'retstart': restart,
            'retmax': retmax,
            'sort': sort,
            'retmode': retmode,
            'datetype': date_type,
            'usehistory': 'y'
        }
        if field:
            params['field'] = field

        if year:
            start, end = year_split(year)
            params['datetype'] = 'edat'
            params['mindate'] = start
            params['maxdate'] = end

        url = self.pubmed_search_url + \
            '&'.join([f"{k}={v}" for k, v in params.items()])

        result = {
            'count': 0,
            'webenv': '',
            'querykey': '',
            'retstart': restart,
            'retmax': retmax,
            'idlist': [],
            'url': url,
            'query': query,
        }

        retry = 0
        while True:
            try:
                response = requests.get(url, timeout=30)
                if response.status_code == 429 and retry < self.max_retry:
                    self.logger.warning("Too Many Requests, waiting for %.2f seconds...",
                                        self.sleep_time)
                    time.sleep(self.sleep_time)
                    self.sleep_time *= 2
                    retry += 1
                else:
                    response.raise_for_status()
                    break
            except Exception as e:
                self.logger.error("Error in query_once: %s", e)
                return result

        response = response.json()
        if esearch_result := response.get('esearchresult', {}):
            result.update(esearch_result)
        return result

    def _parse_fetch_result(self, xml_text: str) -> List[Dict]:
        """
        Parse PubMed XML response data using enhanced parsing logic.

        Args:
            xml_text: XML format string data

        Returns:
            List[Dict]: List of parsed article information
        """
        try:
            root = ET.fromstring(xml_text)
            results = []

            # Process each article
            for article in root.findall('.//PubmedArticle'):
                article_data = parse_single_article(article)
                if article_data:
                    results.append(article_data)

            return results

        except ET.ParseError as e:
            self.logger.error("XML parsing error: %s", e)
            return []
        except Exception as e:
            self.logger.error("Error parsing PubMed data: %s", e)
            return []
    
    def fetch_info_by_pmid_list(self, pmid_list: List[str], webenv: str = '',
                                query_key: str = '', retstart: int = 0,
                                retmax: int = 20) -> List[Dict]:
        """
        Fetch article information by PMID list.

        API doc: https://www.ncbi.nlm.nih.gov/books/NBK25499/#chapter4.EFetch

        Args:
            pmid_list: List of PMIDs
            webenv: WebEnv parameter for Entrez History server
            query_key: Query key parameter used with WebEnv
            retstart: Starting result index
            retmax: Number of results to return

        Returns:
            List[Dict]: List of parsed article information
        """
        while self._check_timeout_error():
            time.sleep(3)
        pmid_list_len = len(pmid_list)
        # 构建基础URL参数
        params = {
            'db': 'pubmed',
            'retmode': 'xml'
        }

        # 根据输入参数选择使用ID列表还是WebEnv
        # if pmid_list_len >= 200 and webenv and query_key:
        if webenv and query_key:
            params.update({
                'WebEnv': webenv,
                'query_key': query_key,
                'retstart': str(retstart),
                'retmax': str(retmax)
            })
        else:
            # 将PMID列表转换为逗号分隔的字符串
            params['id'] = ','.join(str(pmid) for pmid in pmid_list)
        # Build complete URL
        if pmid_list_len < 100:
            url = self.pubmed_fetch_url + \
                '&'.join([f"{k}={v}" for k, v in params.items()])
        else:
            url = self.pubmed_fetch_url

        retry = 0
        while retry < self.max_retry:
            try:
                if pmid_list_len < 100:
                    response = requests.get(url, timeout=30)
                else:
                    response = requests.post(url, data=params, timeout=30)

                if response.status_code == 429:
                    self.logger.debug("Too Many Requests, waiting for %.2f seconds...",
                                      self.sleep_time)
                    time.sleep(self.sleep_time)
                    self.sleep_time *= 2
                    retry += 1
                    continue

                response.raise_for_status()
                return self._parse_fetch_result(response.content.decode("utf-8"))

            except requests.exceptions.RequestException as e:
                self.logger.error("Error requesting PubMed API: %s", e)
                retry += 1

        self.logger.error(
            "Failed to get data after %d retries", self.max_retry)
        return []

    def get_pmid_by_doi(self, doi: str) -> str:
        """
        Get PMID by DOI.

        Args:
            doi: DOI string

        Returns:
            str: PMID if found, empty string otherwise
        """
        while self._check_timeout_error():
            time.sleep(3)
        esearch_url = self.pubmed_search_url + f"db=pubmed&term={doi}[DOI]"
        try:
            esearch_response = requests.get(esearch_url, timeout=10)
            esearch_tree = ET.fromstring(esearch_response.content)
            pmid = esearch_tree.findtext('IdList/Id')
            return pmid or ""
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            self.logger.error(
                "PubMed request timeout or connection error: %s", e)
            self.timeout_error_flag = True
            self.last_timeout_time = time.time()
            raise TimeoutError(
                f"PubMed request timeout or connection error: {e}") from e
        except Exception as e:
            self.logger.error(
                "Error in get_pmid_by_doi for doi %s: %s", doi, e)
            return ""

    def query(self, query: str, year: str = '', field: str = '',
              sort: str = 'relevance', num_results: int = 20):
        """
        Execute complete PubMed search query.

        Args:
            query: Search keywords
            year: Year range ('YYYY-' or '-YYYY' or 'YYYY-YYYY')
            field: Search field
            sort: Sort order
            num_results: Number of results to return, max 10000

        Returns:
            tuple: (paper dictionary list, metadata)
        """
        # Initial query
        search_results = self.query_for_pmid_list(
            query, year, field=field, retmax=num_results, sort=sort
        )
        pmid_list = search_results.get('idlist', [])
        webenv = search_results.get('webenv', '')
        query_key = search_results.get('querykey', '')
        retstart = search_results.get('retstart', 0)
        retmax = search_results.get('retmax', num_results)

        if not pmid_list:
            return [], search_results

        # Sleep to avoid being blocked by PubMed
        time.sleep(1)

        # Fetch paper info with pmid list
        papers = self.fetch_info_by_pmid_list(
            pmid_list, webenv, query_key, retstart=retstart, retmax=retmax
        )

        return papers, search_results

    def _search(self, query: str, **kwargs) -> Tuple[List[Dict], Dict]:
        """
        Execute raw PubMed search.

        Args:
            query: Search query string
            **kwargs: Additional search parameters including:
                - year: Year range (e.g., '2020-2023')
                - field: Search field
                - sort: Sort order ('relevance', 'pub_date')
                - num_results: Number of results to return

        Returns:
            Tuple[List[Dict], Dict]: Raw search results and metadata

        Raises:
            NetworkError: If API requests fail
        """
        try:
            # Extract parameters with defaults
            year = kwargs.get('year', '')
            field = kwargs.get('field', '')
            sort = kwargs.get('sort', 'relevance')
            num_results = kwargs.get('num_results', self.default_results)

            # Execute query to get article list
            articles, metadata = self.query(
                query=query,
                year=year,
                field=field,
                sort=sort,
                num_results=num_results,
            )

            return articles, metadata

        except Exception as e:
            self.logger.error("Error in PubMed search: %s", e)
            raise NetworkError(f"PubMed search failed: {e}") from e

    def _response_format(self, results: List[Dict]) -> List[Dict]:
        """
        Format raw PubMed results into standardized LiteratureSchema format.

        Args:
            results: Raw search results from PubMed API

        Returns:
            List[Dict]: Formatted results conforming to LiteratureSchema

        Raises:
            FormatError: If formatting fails
        """
        try:
            formatted_results = []

            for item in results:
                try:
                    # Extract DOI from identifiers
                    identifiers_dict = item.get('identifiers', {})
                    doi = (identifiers_dict.get('doi') or
                           identifiers_dict.get('elocation_doi') or None)

                    # Create article schema
                    article = ArticleSchema(
                        primary_doi=doi,
                        title=item.get('title', ''),
                        abstract=item.get('abstract') or None,
                        language=item.get('language', 'eng'),
                        publication_year=item.get('year'),
                        publication_date=item.get('published_date'),
                        is_open_access=False,  # PubMed doesn't provide this directly
                        open_access_url=None
                    )

                    # Create author schemas
                    authors = []
                    for i, author_data in enumerate(item.get('authors', [])):
                        if isinstance(author_data, dict):
                            # Build full name
                            fore_name = author_data.get('fore_name', '')
                            last_name = author_data.get('last_name', '')
                            full_name = f"{fore_name} {last_name}".strip()

                            if full_name:
                                # Get first affiliation if available
                                affiliations = author_data.get(
                                    'affiliations', [])
                                affiliation = affiliations[0] if affiliations else None

                                authors.append(AuthorSchema(
                                    full_name=full_name,
                                    last_name=last_name or None,
                                    fore_name=fore_name or None,
                                    initials=author_data.get(
                                        'initials') or None,
                                    affiliation=affiliation,
                                    author_order=i + 1
                                ))

                    # Create venue schema
                    venue = VenueSchema(
                        venue_name=item.get('journal_title', ''),
                        venue_type=VenueType.JOURNAL,
                        iso_abbreviation=item.get(
                            'journal_iso_abbreviation') or None,
                        issn_print=item.get('issn_print') or None,
                        issn_electronic=item.get('issn_electronic') or None
                    )

                    # Create publication schema
                    publication = PublicationSchema(
                        volume=item.get('volume') or None,
                        issue=item.get('issue') or None,
                        start_page=item.get('start_page') or None,
                        end_page=item.get('end_page') or None,
                        page_range=item.get('medline_pgn') or None
                    )

                    # Create identifiers
                    identifiers = []

                    # Add DOI if present
                    if doi and doi.strip():
                        identifiers.append(IdentifierSchema(
                            identifier_type=IdentifierType.DOI,
                            identifier_value=doi.strip(),
                            is_primary=True
                        ))

                    # Add PMID if present
                    pmid = item.get('pmid')
                    if pmid and str(pmid).strip():
                        identifiers.append(IdentifierSchema(
                            identifier_type=IdentifierType.PMID,
                            identifier_value=str(pmid).strip(),
                            is_primary=not bool(doi)  # Primary if no DOI
                        ))

                    # Add PMC ID if present
                    pmc_id = identifiers_dict.get('pmc')
                    if pmc_id and pmc_id.strip():
                        identifiers.append(IdentifierSchema(
                            identifier_type=IdentifierType.PMC_ID,
                            identifier_value=pmc_id.strip(),
                            is_primary=False
                        ))

                    # Create categories from MeSH headings
                    categories = []
                    for mesh_heading in item.get('mesh_headings', []):
                        descriptor_name = mesh_heading.get(
                            'descriptor_name', '')
                        if descriptor_name:
                            is_major = mesh_heading.get(
                                'major_topic_yn', 'N') == 'Y'
                            categories.append(CategorySchema(
                                category_name=descriptor_name,
                                category_code=mesh_heading.get(
                                    'descriptor_ui'),
                                category_type=CategoryType.MESH_DESCRIPTOR,
                                is_major_topic=is_major
                            ))

                    # Create publication types
                    publication_types = []
                    for pub_type in item.get('publication_types', []):
                        type_name = pub_type.get('type', '')
                        if type_name:
                            publication_types.append(PublicationTypeSchema(
                                type_name=type_name,
                                type_code=pub_type.get('ui'),
                                source_type=PublicationTypeSource.PUBMED
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
                            'raw_data': item
                        }
                    )

                    # Validate the schema
                    is_valid, errors = literature.validate()
                    if not is_valid:
                        self.logger.warning(
                            "Schema validation failed for item: %s", errors)

                    # Convert to dict for return with proper enum handling
                    result_dict = {
                        'article': {
                            'primary_doi': article.primary_doi,
                            'title': article.title,
                            'abstract': article.abstract,
                            'language': article.language,
                            'publication_year': article.publication_year,
                            'publication_date': article.publication_date,
                            'updated_date': article.updated_date,
                            'citation_count': article.citation_count,
                            'reference_count': article.reference_count,
                            'influential_citation_count': article.influential_citation_count,
                            'is_open_access': article.is_open_access,
                            'open_access_url': article.open_access_url
                        },
                        'authors': [
                            {
                                'full_name': author.full_name,
                                'last_name': author.last_name,
                                'fore_name': author.fore_name,
                                'initials': author.initials,
                                'orcid': author.orcid,
                                'semantic_scholar_id': author.semantic_scholar_id,
                                'affiliation': author.affiliation,
                                'is_corresponding': author.is_corresponding,
                                'author_order': author.author_order
                            } for author in authors
                        ],
                        'venue': {
                            'venue_name': venue.venue_name,
                            'venue_type': venue.venue_type.value,
                            'iso_abbreviation': venue.iso_abbreviation,
                            'issn_print': venue.issn_print,
                            'issn_electronic': venue.issn_electronic,
                            'publisher': venue.publisher,
                            'country': venue.country
                        },
                        'publication': {
                            'volume': publication.volume,
                            'issue': publication.issue,
                            'start_page': publication.start_page,
                            'end_page': publication.end_page,
                            'page_range': publication.page_range,
                            'article_number': publication.article_number
                        },
                        'identifiers': [
                            {
                                'identifier_type': identifier.identifier_type.value,
                                'identifier_value': identifier.identifier_value,
                                'is_primary': identifier.is_primary
                            } for identifier in identifiers
                        ],
                        'categories': [
                            {
                                'category_name': category.category_name,
                                'category_code': category.category_code,
                                'category_type': category.category_type.value,
                                'is_major_topic': category.is_major_topic,
                                'confidence_score': category.confidence_score
                            } for category in categories
                        ],
                        'publication_types': [
                            {
                                'type_name': pub_type.type_name,
                                'type_code': pub_type.type_code,
                                'source_type': pub_type.source_type.value
                            } for pub_type in publication_types
                        ],
                        'source_specific': literature.source_specific
                    }

                    formatted_results.append(result_dict)

                except Exception as e:
                    self.logger.error(
                        "Error formatting individual PubMed result: %s", e)
                    # Continue processing other results
                    continue

            return formatted_results

        except Exception as e:
            self.logger.error("Error formatting PubMed results: %s", e)
            raise FormatError(f"Failed to format PubMed results: {e}") from e

    def validate_params(self, query: str, **kwargs) -> bool:
        """
        Validate PubMed-specific search parameters.

        Args:
            query: Search query string
            **kwargs: Additional search parameters

        Returns:
            bool: True if parameters are valid, False otherwise
        """
        # Call parent validation first
        if not super().validate_params(query, **kwargs):
            return False

        # PubMed-specific validation
        field = kwargs.get('field')
        if field is not None:
            # Validate PubMed field format (should be in brackets like [Title])
            valid_fields = ['Title', 'Title/Abstract', 'Author',
                            'Journal', 'MeSH Terms', 'Date - Publication']
            if field and not any(f"[{vf}]" in field for vf in valid_fields):
                # Allow field without brackets for backward compatibility
                pass

        sort = kwargs.get('sort', 'relevance')
        if sort not in ['relevance', 'pub_date', 'Author', 'JournalName']:
            self.logger.error("Invalid sort parameter for PubMed: %s", sort)
            return False

        return True

    def _check_timeout_error(self):
        current_time = time.time()
        if self.timeout_error_flag and current_time - self.last_timeout_time < self.timeout_interval:
            return True
        self.timeout_error_flag = False
        self.last_timeout_time = current_time
        return False


def main():
    """Main function for testing PubMed search functionality."""

    api = PubmedSearchAPI()

    # Test search
    data, metadata = api.search(
        '"Enzymes"[Mesh] AND ncbijournals[filter]',
        num_results=3
    )
    print("Search Results:")
    print(data)
    print("\n\nMetadata:")
    print(metadata)


if __name__ == '__main__':
    main()
