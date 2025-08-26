import logging
import time
import traceback
import requests
from .model import SemanticScholarPaper, SemanticResultFormatter


logger = logging.getLogger(__name__)

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
        fields = SemanticScholarPaper.get_fields(fields)
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

    def query(self, paper_id: str, limit: int = 100, fields: str = None, format:bool=True) -> list[dict]:
        """
        Query the citation of a paper on Semantic Scholar.
        """
        fields = SemanticScholarPaper.get_fields(fields)
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

        if format:
            return SemanticResultFormatter.response_format(data)

        return data
