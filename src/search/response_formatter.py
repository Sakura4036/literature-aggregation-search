"""
This module provides a ResponseFormatter class to transform search results from various APIs
(PubMed, Arxiv, Semantic Scholar, WoS) into a unified format based on the database_design.md schema.
"""

class ResponseFormatter:
    """
    A class to format responses from different literature search APIs.
    """

    @staticmethod
    def format(response: dict, source: str) -> dict:
        """
        General format method that dispatches to the specific formatter.

        :param response: The raw response dictionary from a search API.
        :param source: The source of the response (e.g., 'pubmed', 'arxiv').
        :return: A formatted dictionary conforming to the database schema.
        """
        if source == 'pubmed':
            return ResponseFormatter.format_pubmed(response)
        elif source == 'arxiv':
            return ResponseFormatter.format_arxiv(response)
        elif source == 'semantic_scholar':
            return ResponseFormatter.format_semantic_scholar(response)
        elif source == 'wos':
            return ResponseFormatter.format_wos(response)
        else:
            # Return as-is if source is unknown, or raise an error
            # For now, let's return as-is to avoid breaking anything unexpectedly
            return response

    @staticmethod
    def format_pubmed(item: dict) -> dict:
        """
        Formats a single item from a PubMed search result into the unified format.
        """
        # Mapping based on database_design.md and pubmed_search.py output
        return {
            'article': {
                'primary_doi': item.get('doi'),
                'title': item.get('title'),
                'abstract': item.get('abstract'),
                'publication_year': item.get('year'),
                'publication_date': item.get('published_date'),
                'is_open_access': False,  # PubMed API doesn't provide this directly
                'open_access_url': None,
            },
            'authors': [{'full_name': author} for author in item.get('authors', [])],
            'venue': {
                'venue_name': item.get('journal'),
                'venue_type': 'journal',
                'issn_print': item.get('issn'),
                'issn_electronic': item.get('eissn'),
            },
            'publication': {
                'volume': item.get('volume'),
                'issue': item.get('issue'),
            },
            'identifiers': [
                {'identifier_type': 'doi', 'identifier_value': item.get('doi'), 'is_primary': True},
                {'identifier_type': 'pmid', 'identifier_value': item.get('pmid'), 'is_primary': False},
            ],
            'source_specific': {
                'source': 'pubmed',
                'raw': item
            }
        }

    @staticmethod
    def format_arxiv(item: dict) -> dict:
        """
        Formats a single item from an ArXiv search result into the unified format.
        """
        # Mapping based on database_design.md and arxiv_search.py output
        return {
            'article': {
                'primary_doi': item.get('doi'),
                'title': item.get('title'),
                'abstract': item.get('abstract'),
                'publication_year': item.get('year'),
                'publication_date': item.get('published_date'),
                'updated_date': item.get('updated_date'),
                'is_open_access': True,  # ArXiv is open access
                'open_access_url': item.get('pdf_url'),
            },
            'authors': [{'full_name': author} for author in item.get('authors', [])],
            'venue': {
                'venue_name': item.get('journal'),
                'venue_type': 'preprint_server',
            },
            'publication': {},
            'identifiers': [
                {'identifier_type': 'doi', 'identifier_value': item.get('doi'), 'is_primary': True},
                {'identifier_type': 'arxiv_id', 'identifier_value': item.get('arxiv_id'), 'is_primary': False},
            ],
            'source_specific': {
                'source': 'arxiv',
                'raw': item.get('arxiv', {})
            }
        }

    @staticmethod
    def format_semantic_scholar(item: dict) -> dict:
        """
        Formats a single item from a Semantic Scholar search result into the unified format.
        """
        # Mapping based on database_design.md and semantic_search.py output
        return {
            'article': {
                'primary_doi': item.get('doi'),
                'title': item.get('title'),
                'abstract': item.get('abstract'),
                'publication_year': item.get('year'),
                'publication_date': item.get('published_date'),
                'citation_count': item.get('citation_count'),
                'reference_count': item.get('references_count'),
                'is_open_access': item.get('isOpenAccess', False),
                'open_access_url': item.get('openAccessPdf'),
            },
            'authors': [{'full_name': author} for author in item.get('authors', [])],
            'venue': {
                'venue_name': item.get('journal') or item.get('venue'),
                'venue_type': 'journal' if item.get('journal') else 'other',
            },
            'publication': {
                'volume': item.get('volume'),
                'issue': item.get('issue'),
            },
            'identifiers': [
                {'identifier_type': 'doi', 'identifier_value': item.get('doi'), 'is_primary': True},
                {'identifier_type': 'pmid', 'identifier_value': item.get('pmid'), 'is_primary': False},
                {'identifier_type': 'arxiv_id', 'identifier_value': item.get('arxiv_id'), 'is_primary': False},
                {'identifier_type': 'semantic_scholar_id', 'identifier_value': item.get('paperId'), 'is_primary': False},
            ],
            'publication_types': [{'type_name': t} for t in item.get('types', [])],
            'source_specific': {
                'source': 'semantic_scholar',
                'raw': item.get('semantic_scholar', {})
            }
        }

    @staticmethod
    def format_wos(item: dict) -> dict:
        """
        Formats a single item from a Web of Science search result into the unified format.
        """
        # Mapping based on database_design.md and wos_search.py output
        return {
            'article': {
                'primary_doi': item.get('doi'),
                'title': item.get('title'),
                'abstract': item.get('abstract'),
                'publication_year': item.get('year'),
                'publication_date': item.get('published_date'),
            },
            'authors': [{'full_name': author} for author in item.get('authors', [])],
            'venue': {
                'venue_name': item.get('journal'),
                'venue_type': 'journal',
                'issn_print': item.get('issn'),
                'issn_electronic': item.get('eissn'),
            },
            'publication': {
                'volume': item.get('volume'),
                'issue': item.get('issue'),
            },
            'identifiers': [
                {'identifier_type': 'doi', 'identifier_value': item.get('doi'), 'is_primary': True},
                {'identifier_type': 'pmid', 'identifier_value': item.get('pmid'), 'is_primary': False},
                {'identifier_type': 'wos_uid', 'identifier_value': item.get('wos', {}).get('uid'), 'is_primary': False},
            ],
            'publication_types': [{'type_name': t} for t in item.get('types', [])],
            'source_specific': {
                'source': 'wos',
                'raw': item.get('wos', {})
            }
        }
