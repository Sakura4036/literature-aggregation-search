import requests
import logging
import copy
import json
import time
import traceback
from dataclasses import dataclass
from datetime import datetime
from .response_formatter import ResponseFormatter


logger = logging.getLogger(__name__)

"""
Semantic document type:
    Review
    JournalArticle
    CaseReport
    ClinicalTrial
    Conference
    Dataset
    Editorial
    LettersAndComments
    MetaAnalysis
    News
    Study
    Book
    BookSection
"""

normal_document_type_to_semantic = {
    'Review': 'Review',
    'Article': 'JournalArticle',
    'Book': 'Book',
}

semantic_document_type_to_normal = {v: k for k, v in normal_document_type_to_semantic.items()}


@dataclass
class Paper:
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

    # tldr: dict  # {model: model_version, text: summary}

    @staticmethod
    def batch_search_fields():
        return 'paperId,corpusId,externalIds,url,title,abstract,venue,publicationVenue,year,referenceCount,citationCount,influentialCitationCount,isOpenAccess,openAccessPdf,fieldsOfStudy,publicationTypes,publicationDate,journal,citationStyles,authors'

    @staticmethod
    def detail_fields():
        return 'paperId,corpusId,externalIds,url,title,abstract,venue,publicationVenue,year,referenceCount,citationCount,influentialCitationCount,isOpenAccess,openAccessPdf,fieldsOfStudy,publicationTypes,publicationDate,journal,citationStyles,authors,citations,references'

    @staticmethod
    def get_fields(fields):
        if not fields:
            return Paper.batch_search_fields()
        if fields.lower == 'detail':
            return Paper.detail_fields()
        return fields


def document_type_to_semantic(document_type: str):
    """
    将自定义文献类型转换为 Semantic Scholar 的文献类型
    """
    if not document_type or document_type.lower() == 'all':
        return ''
    if document_type in normal_document_type_to_semantic:
        return normal_document_type_to_semantic[document_type]
    else:
        raise ValueError(f"Invalid publication type: {document_type}")


def document_type_to_normal(document_type: str):
    """
    将 Semantic Scholar 的文献类型转换为自定义文献类型
    """
    if document_type in semantic_document_type_to_normal:
        return semantic_document_type_to_normal[document_type]
    else:
        return document_type


class SemanticBulkSearchAPI:
    """
    A tool for searching literatures on Semantic Scholar.
    """
    base_url: str = "https://api.semanticscholar.org/graph/v1/paper/search/bulk?"
    switch_grammar = {
        "AND": '+',
        "OR": '|',
        "NOT": '-',
    }

    def check_query(self, query: str):
        for key, value in self.switch_grammar.items():
            query = query.replace(key, value)
        return f"({query})"

    def query_once(self, query: str,
                   year: str = '',
                   document_type: str = '',
                   fields_of_study: str = '',
                   fields: str = '',
                   offset: int = 0,
                   limit: int = 100,
                   token: str = None,
                   filtered: bool = False) -> tuple[int, list, str, str]:
        """
        Query once for the semantic scholar bulk search.
        """
        # 构建基础 URL
        url = f"{self.base_url}query={query}"

        # 添加年份过滤
        if year:
            url += f"&year={year}"

        # 添加文档类型过滤    
        if document_type:
            url += f"&publicationTypes={document_type}"

        # 添加学科领域过滤    
        if fields_of_study:
            url += f"&fieldsOfStudy={fields_of_study}"

        # 添加返回字段限制    
        if fields:
            url += f"&fields={fields}"

        # 添加分页 token    
        if token:
            url += f"&token={token}"

        url += f"&offset={offset}&limit={limit}"

        logger.debug(f"Semantic Scholar bulk search request: {url}")

        try:
            response = requests.get(url, timeout=30)  # 添加超时限制
            if response.status_code != 200:
                logger.error(f"Semantic Scholar API request failed: {response.status_code}")
                return 0, [], url, ''

            response = response.json()
            total = response.get('total', 0)
            data = response.get('data', [])
            next_token = response.get('token')

            if filtered:
                data = [paper for paper in data if paper and
                        ('abstract' not in fields or paper.get('abstract'))]

            logger.debug(f"Semantic Scholar bulk search response: total={total}, data_length={len(data)}")
            return total, data, url, next_token

        except requests.Timeout:
            logger.error("Semantic Scholar API request timeout")
            return 0, [], url, ''
        except Exception as e:
            logger.error(f"Semantic Scholar API request error: {e}")
            traceback.print_exc()
            return 0, [], url, ''

    def query(self, query: str,
              year: str = '',
              document_type: str = '',
              fields_of_study: str = '',
              fields: str = '',
              num_results: int = 50,
              filtered: bool = False) -> tuple[list[dict], dict]:
        """
        Paper bulk search on Semantic Scholar.
        """
        query = self.check_query(query)
        document_type = document_type_to_semantic(document_type)
        fields = Paper.get_fields(fields)
        limit = min(num_results, 1000)

        # 初始查询
        total, data, url, token = self.query_once(query, year, document_type, fields_of_study, fields, filtered=filtered, limit=limit)

        logger.debug(f"Semantic Scholar bulk search: {url} success. Total: {total}")

        metadata = {
            "total": total,
            "url": url,
            "token": token,
            "query": query,
        }

        if total == 0:
            return [], metadata

        result = data
        # 如果需要更多结果且有下一页，继续获取
        max_attempts = min(num_results // 1000 + 1, 10)  # 限制最大请求次数
        attempts = 1

        while token and len(result) < num_results and attempts < max_attempts:
            time.sleep(1)  # 添加短暂延迟避免请求过快
            attempts += 1
            limit = min(num_results - len(result), 1000)

            total, data, url, token = self.query_once(
                query, year, document_type, fields_of_study, fields,
                offset=len(result), limit=limit, token=token, filtered=filtered,
            )
            if not data:
                break
            result.extend(data)
            logger.debug(f"Retrieved {len(result)} results after {attempts} attempts")

        # 截取所需数量的结果
        result = result[:num_results]
        logger.debug(f"Final results: {len(result)}")
        return result, metadata

    def search(self, query: str, year: str = '', document_type: str = '',
               fields_of_study: str = '', fields: str = '', num_results: int = 50,
               filtered: bool = False) -> tuple[list[dict], dict]:
        """
        Paper relevance search on Semantic Scholar. API documentation: https://api.semanticscholar.org/api-docs#tag/Paper-Data/operation/get_graph_paper_relevance_search

        return example:
        [
            {
                "paperId": "649def34f8be52c8b66281af98ae884c09aef38b",
                "externalIds": {
                "DOI": "10.1145/3292500.3330665",
                "ArXiv": "1905.12616",
                "PubMed": "31199361",
                },
                "title": "Construction of the Literature Graph in Semantic Scholar",
                "abstract": "We describe a deployed scalable system ...",
            }
        ]
        """
        if not num_results:
            return [], {}
        result, metadata = self.query(query, year, document_type, fields_of_study, fields, num_results, filtered)
        logger.debug(f"semantic_bulk_search result num: {len(result)}")
        result = process_papers(result)
        return result, metadata


class SemanticCitationAPI:
    """
    A tool for getting the citation of a paper on Semantic Scholar.
    """
    base_url: str = "https://api.semanticscholar.org/graph/v1/paper/{paper_id}/citations"

    def query_once(self, paper_id: str, offset: int = 0, limit: int = 100, fields: str = None):
        """
        Query once for the citation of a paper on Semantic Scholar.
        """
        url = self.base_url.format(paper_id=paper_id)
        fields = Paper.get_fields(fields)
        url = f"{url}?offset={offset}&limit={limit}&fields={fields}"
        logger.debug(f"Semantic Scholar citation search: {url}")
        try:
            response = requests.get(url, stream=False)
        except Exception as e:
            logger.error(f"Semantic Scholar citation search Error: {e}")
            traceback.print_exc()
            return offset, None, []

        if response.status_code != 200:
            return offset, None, []
        response = response.json()
        offset = response.get('offset', 0)  # Starting position of the current batch.
        next_batch = response.get('next', None)  # Starting position of the next batch. Absent if no more data exists.
        data = []

        for paper in response.get('data', []):
            if paper and 'citingPaper' in paper:
                data.append(paper.get('citingPaper'))

        return offset, next_batch, data

    def query(self, paper_id: str, limit: int = 100, fields: str = None) -> list[dict]:
        """
        Query the citation of a paper on Semantic Scholar.
        """
        fields = Paper.get_fields(fields)
        offset, next_batch, data = self.query_once(paper_id, limit=limit, fields=fields)
        total = len(data)
        if next_batch and limit > 1000:
            # if the number of results is greater than 1000, get the next page of results
            new_limit = limit - 1000
            while next_batch and total < limit:
                offset, next_batch, new_data = self.query_once(paper_id, offset=next_batch, limit=new_limit, fields=fields)
                data.extend(new_data)
                total = len(data)
                # sleep for 15 seconds to avoid rate limit
                time.sleep(15)

        logger.debug(f"Total citations: {total}")

        return data


class SemanticReferenceAPI:
    """
    A tool for getting the reference of a paper on Semantic Scholar.
    """
    base_url: str = "https://api.semanticscholar.org/graph/v1/paper/{paper_id}/references"

    def query_once(self, paper_id: str, offset: int = 0, limit: int = 100, fields: str = None):
        """
        Query once for the citation of a paper on Semantic Scholar.
        """
        url = self.base_url.format(paper_id=paper_id)
        fields = Paper.get_fields(fields)
        url = f"{url}?offset={offset}&limit={limit}&fields={fields}"
        logger.debug(f"Semantic Scholar citation search: {url}")
        try:
            response = requests.get(url, stream=False)
        except Exception as e:
            logger.error(f"Semantic Scholar citation search Error: {e}")
            traceback.print_exc()
            return offset, None, []

        if response.status_code != 200:
            return offset, None, []
        response = response.json()
        offset = response.get('offset', 0)  # Starting position of the current batch.
        next_batch = response.get('next', None)  # Starting position of the next batch. Absent if no more data exists.
        data = []

        for paper in response.get('data', []):
            if paper and 'citedPaper' in paper:
                data.append(paper.get('citedPaper'))

        return offset, next_batch, data

    def query(self, paper_id: str, limit: int = 100, fields: str = None) -> list[dict]:
        """
        Query the citation of a paper on Semantic Scholar.
        """
        fields = Paper.get_fields(fields)
        offset, next_batch, data = self.query_once(paper_id, limit=limit, fields=fields)
        total = len(data)
        if next_batch and limit > 1000:
            # if the number of results is greater than 1000, get the next page of results
            new_limit = limit - 1000
            while next_batch and total < limit:
                offset, next_batch, new_data = self.query_once(paper_id, offset=next_batch, limit=new_limit, fields=fields)
                data.extend(new_data)
                total = len(data)
                # sleep for 15 seconds to avoid rate limit
                time.sleep(15)

        logger.debug(f"Total citations: {total}")

        return data


def process_papers(paper_list: list[dict]) -> list[dict]:
    """
    Process the result from Semantic Scholar search.
    """
    format_papers = []

    for paper in paper_list:
        format_paper = copy.deepcopy(paper)
        if not paper.get('externalIds'):
            paper['externalIds'] = {}
        if 'openAccessPdf' in paper and paper['openAccessPdf']:
            format_paper['openAccessPdf'] = paper['openAccessPdf'].get('url', '')
        format_paper['title'] = paper.get('title', '')
        format_paper['abstract'] = paper.get('abstract', '')
        format_paper['doi'] = paper.get('externalIds', {}).get('DOI', '')
        format_paper['pmid'] = paper.get('externalIds', {}).get('PubMed', '')
        format_paper['arxiv_id'] = paper.get('externalIds', {}).get('ArXiv', '')
        # get paper types
        format_paper['types'] = []
        for document_type in paper.get('publicationTypes') or []:
            format_paper['types'].append(document_type_to_normal(document_type))

        format_paper['year'] = paper.get('year', '')
        publicationDate = paper.get('publicationDate', '')
        if publicationDate:
            format_paper['published_date'] = datetime.strptime(publicationDate, '%Y-%m-%d').date().isoformat()
        else:
            format_paper['published_date'] = None
        if paper.get('journal'):
            format_paper['journal'] = paper['journal'].get('name', '')
            format_paper['volume'] = paper['journal'].get('volume', '')
            format_paper['issue'] = paper['journal'].get('pages', '')
        else:
            format_paper['journal'] = ''
            format_paper['volume'] = ''
            format_paper['issue'] = ''  
        format_paper['citation_count'] = paper.get("citationCount", None)
        format_paper['references_count'] = paper.get("referencesCount", None)
        format_paper['authors'] = [author.get("name") for author in paper.get("authors") or []]
        format_paper['semantic_scholar'] = paper
        format_papers.append(format_paper)
    return format_papers


def semantic_bulk_search(query: str,
                         year: str = '',
                         document_type: str = '',
                         fields_of_study: str = '',
                         fields: str = '',
                         num_results: int = 50,
                         filtered: bool = False) -> tuple[list[dict], dict]:
    """
    Paper relevance search on Semantic Scholar. API documentation: https://api.semanticscholar.org/api-docs#tag/Paper-Data/operation/get_graph_paper_relevance_search

    return example:
    [
        {
            "paperId": "649def34f8be52c8b66281af98ae884c09aef38b",
            "externalIds": {
            "DOI": "10.1145/3292500.3330665",
            "ArXiv": "1905.12616",
            "PubMed": "31199361",
            },
            "title": "Construction of the Literature Graph in Semantic Scholar",
            "abstract": "We describe a deployed scalable system ...",
        }
    ]
    """
    if not num_results:
        return [], {}
    result, metadata = SemanticBulkSearchAPI().query(query, year, document_type, fields_of_study, fields, num_results, filtered)
    logger.debug(f"semantic_bulk_search result num: {len(result)}")
    result = process_papers(result)

    # Format the results
    formatted_results = [ResponseFormatter.format(r, 'semantic_scholar') for r in result]

    return formatted_results, metadata


def semantic_batch_search(ids: list[str], fields: str = None, filtered: bool = True, max_query_size: int = 500,
                          max_retries: int = 3, retry_delay: int = 60) -> list[dict]:
    """
    get details for multiple papers at once.

    Args:
        ids: a list of paper ids
        fields: a comma separated list of fields to return
        filtered: whether to filter out papers with missing fields
        max_query_size: the maximum number of papers to query at once
        max_retries: maximum number of retry attempts for rate limit errors
        retry_delay: delay between retries in seconds
    """
    fields = Paper.get_fields(fields)
    base_url = "https://api.semanticscholar.org/graph/v1/paper/batch"
    if len(ids) > max_query_size:
        raise ValueError('The number of papers should be less than 500')

    retries = 0
    while retries < max_retries:
        try:
            response = requests.post(base_url, json={"ids": ids}, params={"fields": fields})
            response = response.json()
            if isinstance(response, dict):
                # semantic 返回dict时表示错误，否则返回list[dict]
                if response.get('code') == 429:  # 速率限制错误
                    retries += 1
                    if retries < max_retries:
                        time.sleep(retry_delay)
                        continue
                    else:
                        return []  # 达到最大重试次数
                return []  # 其他错误直接返回空列表
            break  # 成功获取数据，跳出重试循环

        except Exception as e:
            retries += 1
            if retries < max_retries:
                time.sleep(retry_delay)
                continue
            return []

    result = []
    for pid, paper in zip(ids, response):
        if not paper:
            continue
        if filtered and 'abstract' in fields:
            if not paper.get('abstract', ''):
                continue
        # used for check
        paper['id'] = pid
        result.append(paper)

    return process_papers(result)


def semantic_paper_search(paper_ids: dict, fields: str = None) -> dict:
    """
    Get paper details by paper id, doi, arxiv, pmid or url.
    :param paper_ids: a dict of paper ids. supported ids are doi, arxiv, pmid, and url.
    :param fields: a comma separated list of fields to return.
    """
    if not fields:
        fields = Paper.batch_search_fields()
    if fields.lower() == 'detail':
        fields = Paper.detail_fields()
    base_url = "https://api.semanticscholar.org/graph/v1/paper/{}"

    ids = []
    for paper_id in ['doi', 'arxiv', 'pmid', 'url']:
        if paper_ids.get(paper_id):
            ids.append(f"{paper_id.upper()}:{paper_ids[paper_id]}")

    for paper_id in ids:
        try:
            response = requests.get(base_url.format(paper_id), params={"fields": fields})
            response = response.json()
            if 'error' in response:
                # semantic search error
                continue
            return process_papers([response])[0]
        except Exception as e:
            time.sleep(1)
            logger.warning(e)
            continue
    return {}


def semantic_title_search(title: str, fields: str = None) -> tuple[bool, list[dict]]:
    """
    Paper title search on Semantic Scholar.
    API documentation: https://api.semanticscholar.org/api-docs#tag/Paper-Data/operation/get_graph_paper_title_search
    """
    if not fields:
        fields = Paper.batch_search_fields()
    if fields.lower() == 'detail':
        fields = Paper.detail_fields()
    base_url = f"https://api.semanticscholar.org/graph/v1/paper/search/match?query={title}&fields={fields}"
    try:
        response = requests.get(base_url)
        response = response.json()
        papers = process_papers(response.get('data', []))
        if papers:
            return True, papers
        else:
            return False, []
    except Exception as e:
        logger.error(f"Semantic title search error: {e}")
        return False, []


def semantic_title_batch_search(titles: list[str], fields: str = None) -> tuple[list[dict], int]:
    """
    Batch paper title search on Semantic Scholar.
    """
    if not fields:
        fields = Paper.batch_search_fields()
    if fields.lower() == 'detail':
        fields = Paper.detail_fields()

    papers = []
    count = 0
    for title in titles:
        success, result = semantic_title_search(title, fields)
        if success:
            papers.extend(result)
            count += 1
    return papers, count


def semantic_citation_search(paper_id: str, limit: int = 100, fields: str = None) -> list[dict]:
    papers = SemanticCitationAPI().query(paper_id, limit, fields)
    return process_papers(papers)


def semantic_reference_search(paper_id: str, limit: int = 100, fields: str = None) -> list[dict]:
    papers = SemanticReferenceAPI().query(paper_id, limit, fields)
    return process_papers(papers)


def semantic_recommend_search(paper_id: str, limit: int = 100, fields: str = None, pool: str = 'recent') -> list[dict]:
    if not fields:
        fields = Paper.batch_search_fields()
    if not limit:
        return []
    base_url = "https://api.semanticscholar.org/recommendations/v1/papers/forpaper/{paper_id}"

    url = base_url.format(paper_id=paper_id)
    url = f"{url}?from={pool}&limit={limit}&fields={fields}"
    results = []
    try:
        response = requests.get(url)
        response = response.json()
        results = response.get('recommendedPapers', [])
    except Exception as e:
        logger.error(f"SemanticRecommendApi error: {e}")
    finally:
        return process_papers(results)


if __name__ == '__main__':
    ids = ['DOI:10.1590/S1415-52732009000600009',
           'DOI:10.1590/S0101-20612010000300041',
           'DOI:10.1021/jf2037714', 'DOI:10.1111/j.1439-037X.2007.00263.x',
           'DOI:10.29019/enfoque.v10n2.424', 'DOI:10.1590/S0101-20612011000200019', 'DOI:10.1590/S1516-35982008001000001',
           'DOI:10.1590/S1516-35982011000800015', 'DOI:10.1590/S1516-35982006000400016', 'DOI:10.1590/S1516-35982007000700016',
           'DOI:10.1590/S1516-35982003000700019', 'DOI:10.1590/S0103-50532009001000003', 'DOI:10.29019/enfoqueute.v9n2.300', 'DOI:10.15381/rivep.v34i1.22182',
           'DOI:10.1590/S1413-70542006000100022', 'DOI:10.19053/01211129.v28.n52.2019.9654', 'DOI:10.1590/S0101-20612010005000017',
           'DOI:10.1590/S1516-35982008001100016', 'DOI:10.1023/A:1015512607352', 'DOI:10.1590/S1516-35982010000500020', 'DOI:10.1590/S0103-90162008000200004',
           'DOI:10.1590/S1516-35982002000300003', 'DOI:10.1590/1983-40632021v5166584', 'DOI:10.1590/S1516-35982004000900022',
           'DOI:10.1590/S1516-35982008001200001', 'DOI:10.1590/S1516-35982009000600003']
    # semantic_batch_search(ids)

    result = semantic_recommend_search(
        paper_id='649def34f8be52c8b66281af98ae884c09aef38b',
        limit=10,
        fields='title,abstract,externalIds,openAccessPdf,year,publicationTypes'
    )

    print(result)
