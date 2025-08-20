import requests
import logging
import xml.etree.ElementTree as ET
import time
from datetime import datetime
from typing import Dict, List, Tuple, Any, Optional

from .base_engine import BaseSearchEngine, NetworkError, FormatError
from .utils import year_split
from ..models.schemas import LiteratureSchema, ArticleSchema, AuthorSchema, VenueSchema, PublicationSchema, IdentifierSchema
from ..models.enums import IdentifierType, VenueType

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

    def query_for_pmid_list(self, query: str, year: str = '', field: str = '', restart: int = 0, retmax: int = 20, date_type: str = 'mdat',
                            sort: str = 'relevance', retmode: str = 'json'):
        """
        执行单次PubMed搜索查询
        api doc: https://www.ncbi.nlm.nih.gov/books/NBK25499/#chapter4.ESearch

        Args:
            query: 搜索关键词
            year: 年份, 格式为YYYY-YYYY
            field: 搜索字段 ('Title', 'Abstract', 'Author', 'Journal')
            restart: 起始结果索引
            retmax: 返回结果数量, 最大值为10000
            date_type: 日期类型 ('mdat', 'pdat', 'edat'), 其中edat支持reldate=int， 和（min_date, max_date）的形式， min_date和max_date的格式支持YYYY[/MM][/DD]
            sort: 排序方式 ('relevance', 'pub_date', 'Author', 'JournalName')
            retmode: 返回格式 ('json' or 'xml')

        Returns:
            dict: 包含搜索结果的字典
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

        url = self.pubmed_search_url + '&'.join([f"{k}={v}" for k, v in params.items()])

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
                response = requests.get(url)
                if response.status_code == 429 and retry < self.max_retry:
                    logger.error(f"Too Many Requests, waiting for {self.sleep_time:.2f} seconds...")
                    time.sleep(self.sleep_time)
                    self.sleep_time *= 2
                    retry += 1
                else:
                    response.raise_for_status()
                    break
            except Exception as e:
                logger.error(f"Error in query_once: {e}")
                return result

        response = response.json()
        if esearch_result := response.get('esearchresult', {}):
            result.update(esearch_result)
        return result

    def _parse_fetch_result(self, xml_text: str) -> list[dict]:
        """解析PubMed返回的XML格式数据
        
        Args:
            xml_text: XML格式的字符串数据
            
        Returns:
            list[dict]: 解析后的文章信息列表
        """
        try:
            with open("temp.xml", 'w', encoding='utf-8') as wf:
                wf.write(xml_text)
            root = ET.fromstring(xml_text)
            results = []

            # 遍历每篇文章
            for article in root.findall('.//PubmedArticle'):
                # 获取基本信息
                pmid = article.find('.//PMID').text

                # 获取标题
                title_elem = article.find('.//ArticleTitle')
                title = title_elem.text if title_elem is not None else ''

                # 获取摘要
                abstract_elem = article.find('.//AbstractText')
                abstract = abstract_elem.text if abstract_elem is not None else ''

                # 获取作者列表
                authors = []
                author_list = article.findall('.//Author')
                for author in author_list:
                    last_name = author.find('LastName')
                    fore_name = author.find('ForeName')
                    if last_name is not None and fore_name is not None:
                        authors.append(f"{fore_name.text} {last_name.text}")

                # 获取期刊信息
                journal_elem = article.find('.//Journal/Title')
                journal = journal_elem.text if journal_elem is not None else ''
                issn = article.find('.//Journal/ISSN[@IssnType="Print"]')
                issn = issn.text if issn is not None else ''
                volume = article.find('.//Journal/JournalIssue/Volume')
                volume = volume.text if volume is not None else ''
                issue = article.find('.//Journal/JournalIssue/Issue')
                issue = issue.text if issue is not None else ''
                eissn = article.find('.//Journal/ISSN[@IssnType="Electronic"]')
                eissn = eissn.text if eissn is not None else ''

                # 获取DOI
                doi_elem = article.find(".//ArticleId[@IdType='doi']")
                doi = doi_elem.text if doi_elem is not None else ''

                # 获取发布日期 - 优先使用pubmed状态的日期，其次使用entrez状态的日期
                pub_date = article.find('.//PubMedPubDate[@PubStatus="pubmed"]')
                if pub_date is None:
                    pub_date = article.find('.//PubMedPubDate[@PubStatus="entrez"]')
                pub_datetime = None
                if pub_date is not None:
                    year = pub_date.find('Year')
                    month = pub_date.find('Month')
                    day = pub_date.find('Day')
                    if year is not None:
                        pub_date_str = year.text
                        if month is not None:
                            if month.text in ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']:
                                month = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'].index(month.text) + 1  
                                pub_date_str += f"-{month:02d}"
                            else:
                                pub_date_str += f"-{month.text}"
                            if day is not None:
                                pub_date_str += f"-{day.text}"
                                pub_datetime = datetime.strptime(pub_date_str, '%Y-%m-%d').date()
                            else:
                                pub_datetime = datetime.strptime(pub_date_str, '%Y-%m').date()
                        else:
                            pub_datetime = datetime.strptime(pub_date_str, '%Y').date()
                year = pub_datetime.year if pub_datetime else None
                pub_datetime = pub_datetime.isoformat() if pub_datetime else None
                # 构建文章信息字典
                article_info = {
                    'pmid': pmid,
                    'title': title or '',
                    'abstract': abstract or '',
                    'authors': authors or [],
                    'journal': journal or '',
                    'issn': issn or '',
                    'volume': volume or '',
                    'issue': issue or '',
                    'eissn': eissn or '',
                    'doi': doi or '',
                    'published_date': pub_datetime,
                    'year': year
                }

                results.append(article_info)

            return results

        except ET.ParseError as e:
            logger.error(f"XML解析错误: {e}")
            return []
        except Exception as e:
            logger.error(f"解析PubMed数据时发生错误: {e}")
            return []

    def fetch_info_by_pmid_list(self, pmid_list: list[str], webenv: str = '', query_key: str = '', retstart: int = 0, retmax: int = 20) -> list[dict]:
        """根据PMID列表获取文章信息
        api文档：https://www.ncbi.nlm.nih.gov/books/NBK25499/#chapter4.EFetch
        
        Args:
            pmid_list: PMID列表
            webenv: WebEnv参数，用于从Entrez History server获取结果
            query_key: Query key参数，与WebEnv配合使用
            retstart: 起始结果索引
            retmax: 返回结果数量
            
        Returns:
            list[dict]: 解析后的文章信息列表
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
        # 构建完整URL
        if pmid_list_len < 100:
            url = self.pubmed_fetch_url + '&'.join([f"{k}={v}" for k, v in params.items()])
        else:
            url = self.pubmed_fetch_url

        retry = 0
        while retry < self.max_retry:
            try:
                response = requests.get(url) if pmid_list_len < 100 else requests.post(url, data=params)
                if response.status_code == 429:
                    logger.debug(
                        f"Too Many Requests, "
                        f"waiting for {self.sleep_time:.2f} seconds..."
                    )
                    time.sleep(self.sleep_time)
                    self.sleep_time *= 2
                    retry += 1
                    continue

                response.raise_for_status()
                return self._parse_fetch_result(response.content.decode("utf-8"))

            except requests.exceptions.RequestException as e:
                logger.error(f"请求PubMed API时发生错误: {e}")
                retry += 1

        logger.error(f"在{self.max_retry}次重试后仍未成功获取数据")
        return []

    def get_pmid_by_doi(self, doi: str) -> str:
        while self._check_timeout_error():
            time.sleep(3)
        esearch_url = self.pubmed_search_url + f"db=pubmed&term={doi}[DOI]"
        try:
            esearch_response = requests.get(esearch_url, timeout=10)
            esearch_tree = ET.fromstring(esearch_response.content)
            pmid = esearch_tree.findtext('IdList/Id')
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            logger.error(f"Pubmed 请求超时或连接错误: {e}")
            self.timeout_error_flag = True
            self.last_timeout_time = time.time()
            raise TimeoutError(f"Pubmed 请求超时或连接错误 {e}")
        except Exception as e:
            logger.error(f"Error in get_pmid_by_doi for doi {doi}: {e}")
            return ""
        return pmid

    def query(self, query: str, year: str = '', field: str = '', sort: str = 'relevance', num_results: int = 20):
        """
        执行完整的PubMed搜索查询
        
        Args:
            query: 搜索关键词
            year: 年份范围 ('YYYY-' or '-YYYY' or 'YYYY-YYYY')
            field: 搜索字段
            sort: 排序方式
            num_results: 需要返回的结果数量, 最大值10000

        Returns:
            tuple: (paper字典列表, 元数据)
        """
        # 初始查询
        search_results = self.query_for_pmid_list(query, year, field=field, retmax=num_results, sort=sort)
        pmid_list = search_results.get('idlist', [])
        webenv = search_results.get('webenv', '')
        query_key = search_results.get('querykey', '')
        retstart = search_results.get('retstart', 0)
        retmax = search_results.get('retmax', num_results)

        if not pmid_list:
            return [], search_results

        # sleep for a while to avoid being blocked by PubMed
        time.sleep(1)

        # fetch paper info with pmid list
        papers = self.fetch_info_by_pmid_list(pmid_list, webenv, query_key, retstart=retstart, retmax=retmax)

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
            self.logger.error(f"Error in PubMed search: {e}")
            raise NetworkError(f"PubMed search failed: {e}") from e
    
    def _response_format(self, results: List[Dict], source: str) -> List[Dict]:
        """
        Format raw PubMed results into standardized LiteratureSchema format.
        
        Args:
            results: Raw search results from PubMed API
            source: Data source name (should be 'pubmed')
            
        Returns:
            List[Dict]: Formatted results conforming to LiteratureSchema
            
        Raises:
            FormatError: If formatting fails
        """
        try:
            formatted_results = []
            
            for item in results:
                try:
                    # Create article schema
                    article = ArticleSchema(
                        primary_doi=item.get('doi') or None,
                        title=item.get('title', ''),
                        abstract=item.get('abstract') or None,
                        publication_year=item.get('year'),
                        publication_date=item.get('published_date'),
                        is_open_access=False,  # PubMed doesn't provide this directly
                        open_access_url=None
                    )
                    
                    # Create author schemas
                    authors = []
                    for i, author_name in enumerate(item.get('authors', [])):
                        if author_name and author_name.strip():
                            authors.append(AuthorSchema(
                                full_name=author_name.strip(),
                                author_order=i + 1
                            ))
                    
                    # Create venue schema
                    venue = VenueSchema(
                        venue_name=item.get('journal', ''),
                        venue_type=VenueType.JOURNAL,
                        issn_print=item.get('issn') or None,
                        issn_electronic=item.get('eissn') or None
                    )
                    
                    # Create publication schema
                    publication = PublicationSchema(
                        volume=item.get('volume') or None,
                        issue=item.get('issue') or None
                    )
                    
                    # Create identifiers
                    identifiers = []
                    
                    # Add DOI if present
                    doi = item.get('doi')
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
                    
                    # Create complete literature schema
                    literature = LiteratureSchema(
                        article=article,
                        authors=authors,
                        venue=venue,
                        publication=publication,
                        identifiers=identifiers,
                        source_specific={
                            'source': 'pubmed',
                            'raw_data': item
                        }
                    )
                    
                    # Validate the schema
                    is_valid, errors = literature.validate()
                    if not is_valid:
                        self.logger.warning(f"Schema validation failed for item: {errors}")
                    
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
                        'categories': [],
                        'publication_types': [],
                        'source_specific': literature.source_specific
                    }
                    
                    formatted_results.append(result_dict)
                    
                except Exception as e:
                    self.logger.error(f"Error formatting individual PubMed result: {e}")
                    # Continue processing other results
                    continue
            
            return formatted_results
            
        except Exception as e:
            self.logger.error(f"Error formatting PubMed results: {e}")
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
            valid_fields = ['Title', 'Title/Abstract', 'Author', 'Journal', 'MeSH Terms', 'Date - Publication']
            if field and not any(f"[{vf}]" in field for vf in valid_fields):
                # Allow field without brackets for backward compatibility
                pass
        
        sort = kwargs.get('sort', 'relevance')
        if sort not in ['relevance', 'pub_date', 'Author', 'JournalName']:
            self.logger.error(f"Invalid sort parameter for PubMed: {sort}")
            return False
        
        return True
    
    def search_legacy(self, query: str, year: str = '', field: str = '', sort: str = 'relevance', num_results: int = 20):
        """
        Legacy search method for backward compatibility.
        
        This method maintains the original interface while using the new architecture internally.
        
        Args:
            query: Search query string
            year: Year range
            field: Search field
            sort: Sort order
            num_results: Number of results to return
            
        Returns:
            tuple: (formatted articles, metadata)
        """
        # Use the new search method
        formatted_results, metadata = self.search(
            query=query,
            year=year,
            field=field,
            sort=sort,
            num_results=num_results
        )
        
        # Convert back to legacy format if needed
        legacy_results = []
        for result in formatted_results:
            # Extract raw data from source_specific
            raw_data = result.get('source_specific', {}).get('raw_data', {})
            legacy_results.append(raw_data)
        
        return legacy_results, metadata

    def _check_timeout_error(self):
        current_time = time.time()
        if self.timeout_error_flag and current_time - self.last_timeout_time < self.timeout_interval:
            return True
        self.timeout_error_flag = False
        self.last_timeout_time = current_time
        return False

 

if __name__ == '__main__':
    api = PubmedSearchAPI()

    # 测试查询
    # params = {'db': 'pubmed', 'retmode': 'xml', 'WebEnv': 'MCID_67a6f465ea2727cf3b058df5', 'query_key': '1', 'retstart': '0', 'retmax': '5'}
    pmid_list = [
        "10580082",
        "10052956",
        "18411226",
        "8323535",
        "20632947",
        "1798702",
        "3288990",
        "16859742",
    ]
    # data = api.fetch_info_by_pmid_list(pmid_list=[], webenv=params['WebEnv'], query_key=params['query_key'], retstart=int(params['retstart']), retmax=int(params['retmax']))
    # data = api.fetch_info_by_pmid_list(pmid_list=pmid_list)

    # print(api.query_for_pmid_list('"synthetic biology"[MeSH Terms] OR Synthetic Biology[Text Word]'))
    data, metadata = api.search('"Enzymes"[Mesh] AND ncbijournals[filter]', 
                                # field="Journal Article",
                                num_results=3)
    print(data)
    print("\n\n")
    print(metadata)
