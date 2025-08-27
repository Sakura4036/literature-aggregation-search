import logging
import time

from .model import SemanticScholarPaper, SemanticResultFormatter


logger = logging.getLogger(__name__)


def semantic_batch_search(ids: list[str], fields: str = None, filtered: bool = True, max_query_size: int = 500,
                          max_retries: int = 3, retry_delay: int = 60) -> list[dict]:
    fields = SemanticScholarPaper.get_fields(fields)
    base_url = "https://api.semanticscholar.org/graph/v1/paper/batch"
    if len(ids) > max_query_size:
        raise ValueError('The number of papers should be less than 500')
    retries = 0
    while retries < max_retries:
        try:
            import requests
            response = requests.post(base_url, json={"ids": ids}, params={"fields": fields})
            response = response.json()
            if isinstance(response, dict):
                if response.get('code') == 429:
                    retries += 1
                    if retries < max_retries:
                        time.sleep(retry_delay)
                        continue
                    else:
                        return []
                return []
            break
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
        paper['id'] = pid
        result.append(paper)
    return SemanticResultFormatter().response_format(result)

def semantic_paper_search(paper_ids: dict, fields: str = None) -> dict:
    if not fields:
        fields = SemanticScholarPaper.batch_search_fields()
    if fields.lower() == 'detail':
        fields = SemanticScholarPaper.detail_fields()
    base_url = "https://api.semanticscholar.org/graph/v1/paper/{}"
    ids = []
    for paper_id in ['doi', 'arxiv', 'pmid', 'url']:
        if paper_ids.get(paper_id):
            ids.append(f"{paper_id.upper()}:{paper_ids[paper_id]}")
    for paper_id in ids:
        try:
            import requests
            response = requests.get(base_url.format(paper_id), params={"fields": fields})
            response = response.json()
            if 'error' in response:
                continue
            return SemanticResultFormatter().response_format([response])[0]
        except Exception as e:
            time.sleep(1)
            logger.warning(e)
            continue
    return {}

def semantic_title_search(title: str, fields: str = None) -> tuple[bool, list[dict]]:
    if not fields:
        fields = SemanticScholarPaper.batch_search_fields()
    if fields.lower() == 'detail':
        fields = SemanticScholarPaper.detail_fields()
    base_url = f"https://api.semanticscholar.org/graph/v1/paper/search/match?query={title}&fields={fields}"
    try:
        import requests
        response = requests.get(base_url)
        response = response.json()
        papers = SemanticResultFormatter().response_format(response.get('data', []))
        if papers:
            return True, papers
        else:
            return False, []
    except Exception as e:
        logger.error(f"Semantic title search error: {e}")
        return False, []

def semantic_title_batch_search(titles: list[str], fields: str = None) -> tuple[list[dict], int]:
    if not fields:
        fields = SemanticScholarPaper.batch_search_fields()
    if fields.lower() == 'detail':
        fields = SemanticScholarPaper.detail_fields()
    papers = []
    count = 0
    for title in titles:
        success, result = semantic_title_search(title, fields)
        if success:
            papers.extend(result)
            count += 1
    return papers, count


def semantic_recommend_search(paper_id: str, limit: int = 100, fields: str = None, pool: str = 'recent') -> list[dict]:
    if not fields:
        fields = SemanticScholarPaper.batch_search_fields()
    if not limit:
        return []
    base_url = "https://api.semanticscholar.org/recommendations/v1/papers/forpaper/{paper_id}"
    url = base_url.format(paper_id=paper_id)
    url = f"{url}?from={pool}&limit={limit}&fields={fields}"
    results = []
    try:
        import requests
        response = requests.get(url)
        response = response.json()
        results = response.get('recommendedPapers', [])
    except Exception as e:
        logger.error(f"SemanticRecommendApi error: {e}")

    return SemanticResultFormatter().response_format(results)
