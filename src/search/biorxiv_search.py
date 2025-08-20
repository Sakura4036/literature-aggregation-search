import logging
import requests
from datetime import datetime
from typing import Optional, Tuple

from .utils import year_split

logger = logging.getLogger(__name__)


class BioRxivSearchAPI:
    """
    bioRxiv Search API工具
    API文档: https://api.biorxiv.org/
    """
    base_url: str = "https://api.biorxiv.org"

    def __init__(self):
        """初始化bioRxiv搜索API"""
        self.limit = 100  # bioRxiv API每页最大返回100条结果

    def _process_response(self, response: dict) -> list[dict]:
        """
        处理bioRxiv API的响应数据，转换为统一格式
        
        Args:
            response: bioRxiv API的原始响应数据
            
        Returns:
            list[dict]: 处理后的论文数据列表
        """
        results = []
        if not response or 'collection' not in response:
            return results

        for paper in response['collection']:
            # 处理作者信息
            authors = []
            if paper.get('authors'):
                authors = [author.strip() for author in paper['authors'].split(';')]

            # 处理日期
            try:
                published_date = datetime.strptime(paper.get('date', ''), '%Y-%m-%d').date()
                year = published_date.year
                published_date = published_date.isoformat()
            except:
                published_date = None
                year = None

            # 构建统一格式的论文数据
            format_paper = {
                'title': paper.get('title', ''),
                'abstract': paper.get('abstract', ''),
                'authors': authors,
                'doi': paper.get('doi', ''),
                'year': year,
                'published_date': published_date,
                'journal': paper.get('server', 'biorxiv'),  # 预印本服务器名称
                'types': ['Preprint'],  # bioRxiv都是预印本
                'biorxiv': paper  # 保存原始数据
            }
            results.append(format_paper)

        return results

    def _query_once(self,
                    query: str,
                    server: str = 'biorxiv',
                    cursor: int = 0,
                    interval: Optional[str] = None) -> Tuple[int, list[dict], str]:
        """
        执行一次bioRxiv API查询
        
        Args:
            query: 查询DOI
            server: 服务器类型(biorxiv或medrxiv)
            cursor: 分页起始位置
            interval: 日期范围，格式为'YYYY-MM-DD/YYYY-MM-DD'
            
        Returns:
            Tuple[int, list[dict], str]: (总结果数, 论文列表, 请求URL)
        """
        # 构建API URL
        if query.startswith('10.1101/'):  # 如果是DOI查询
            url = f"{self.base_url}/details/{server}/{query}/na/json"
        else:  # 如果是日期范围查询
            url = f"{self.base_url}/details/{server}/{interval}/{cursor}/json"

        logger.debug(f"BioRxiv API request: {url}")

        try:
            response = requests.get(url)
            if response.status_code == 200:
                data = response.json()
                with open("temp_biorxiv.json", 'w', encoding='utf-8') as wf:
                    import json
                    json.dump(data, wf, ensure_ascii=False, indent=4)
                messages = data.get('messages', [{}])[0]
                if messages.get('status') == 'error':
                    logger.error(f"BioRxiv API request error: {messages.get('message')}")
                    return 0, [], url
                total = int(messages.get('total', 0))
                if not total:
                    total = len(data.get('collection', []))
                results = self._process_response(data)
                return total, results, url
            else:
                logger.error(f"BioRxiv API request failed: {response.status_code}")
                return 0, [], url
        except Exception as e:
            logger.error(f"BioRxiv API request error: {e}")
            return 0, [], url

    def query(self,
              query: str = '',
              server: str = 'biorxiv',
              year: str = '',
              num_results: int = 50) -> Tuple[list[dict], dict]:
        """
        查询bioRxiv论文
        
        Args:
            query: 查询DOI
            server: 服务器类型(biorxiv或medrxiv)
            year: 年份范围，格式为'YYYY-' 或 '-YYYY' 或 'YYYY-YYYY'
            num_results: 需要返回的结果数量
            
        Returns:
            Tuple[list[dict], dict]: (论文列表, 元数据)
        """
        if not num_results:
            return [], {}

        # 处理年份范围
        if year:
            start, end = year_split(year)
            if start == end:
                interval = f"{year}-01-01/{year}-12-31"
            else:
                interval = f"{start}-01-01/{end}-01-01"
        else:
            interval = None

        # 执行查询
        total, results, url = self._query_once(query, server, interval=interval)

        metadata = {
            "total": total,
            "query": query,
            "url": url,
            'server': server,
        }

        if total == 0:
            return [], metadata

        # 如果需要更多结果，继续查询
        if len(results) < num_results and len(results) < total:
            cursor = self.limit
            while cursor < total and len(results) < num_results:
                _, more_results, _ = self._query_once(query, server, cursor=cursor, interval=interval)
                results.extend(more_results)
                cursor += self.limit

        # 截取所需数量的结果
        results = results[:num_results]

        return results, metadata

    def search(self, query: str = '', year: str = '', num_results: int = 50,
               server: str = 'biorxiv') -> Tuple[list[dict], dict]:
        """
        bioRxiv论文搜索的主要接口
        
        Args:
            query: 查询DOI
            year: 年份范围
            num_results: 需要返回的结果数量
            server: 服务器类型(biorxiv或medrxiv)
            
        Returns:
            Tuple[list[dict], dict]: (论文列表, 元数据)
        """
        results, metadata = self.query(
            query=query,
            year=year,
            num_results=num_results,
            server=server
        )
        logger.debug(f"biorxiv_search result num: {len(results)}")
        return results, metadata


if __name__ == "__main__":
    api = BioRxivSearchAPI()
    print(api.search('10.1101/2025.08.04.668552', num_results=1))