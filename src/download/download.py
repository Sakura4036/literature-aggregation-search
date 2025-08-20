import logging
import os
import re
import traceback
import requests
import hashlib
from core.tools.downloader.chrome_file_downloader import ChromeDownloader
from configs import app_config


class ScihubURL:
    url_templates = [
        'https://sci-hub.ru/{doi}',
        'https://sci-hub.st/{doi}',
        'https://sci-hub.se/{doi}',
        'https://sci.bban.top/pdf/{doi}.pdf',
    ]

    def get_urls(self, doi: str) -> list[str]:
        return [url.format(doi=doi) for url in self.url_templates]


class UnpaywallURL:
    url_templates = [
        'https://api.unpaywall.org/v2/{doi}?email=sdsxlwf@email.com',
    ]

    def get_urls(self, doi: str, timeout: int = 10) -> list[str]:
        """
        Get the pdf url from unpaywall api
        :param doi: the doi of the paper
        :param timeout: the timeout of the request
        """
        urls = []
        for url in self.url_templates:
            url = url.format(doi=doi)
            try:
                response = requests.get(url, allow_redirects=True, timeout=timeout)
                if response.status_code == 200:
                    response = response.json()
                    oa_locations = response.get('oa_locations')
                    if oa_locations:
                        for location in oa_locations:
                            url = location.get('url_for_pdf')
                            if url:
                                if 'pmc' in url.lower():
                                    urls.insert(0, url)
                                else:
                                    urls.append(url)
                            else:
                                url = location.get('url_for_landing_page')
                                if 'ncbi' in url and 'PMC' in url:
                                    try:
                                        headers = {
                                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                                        }
                                        response = requests.get(url, allow_redirects=True, timeout=timeout, headers=headers )
                                        if response.status_code == 200:
                                            html = response.text
                                            # 获取html中的pdf url
                                            # <meta name="citation_pdf_url" content="https://pmc.ncbi.nlm.nih.gov/articles/PMC8268301/pdf/ijms-22-07078.pdf">
                                            pdf_url = "https:" + re.findall(r'//[^\s<>"]+\.pdf', html)[0]
                                            urls.insert(0, pdf_url)
                                        else:
                                            logging.debug(f"Error while fetching pdf url in UnpaywallURL {url}, status_code: {response.json()}")
                                    except Exception as e:
                                        logging.debug(f"Error while fetching pdf url in UnpaywallURL {url}")
                                        traceback.print_exc()
                                        urls.append(url)
                                else:
                                    urls.append(url)
                                
            except Exception as e:
                logging.debug(f"Error while fetching pdf url in UnpaywallURL {url}")
                logging.error(e)
        return urls


class CrossrefURL:
    url_templates = [
        'https://api.crossref.org/works/{doi}'
    ]

    def get_urls(self, doi: str, timeout: int = 10) -> list[str]:
        urls = []
        for url in self.url_templates:
            url = url.format(doi=doi)
            try:
                response = requests.get(url, timeout=timeout)
                response.raise_for_status()
                response = response.json()
                if response['status'] != 'ok':
                    continue
                for link in response['message'].get('link', []):
                    if link['content-type'] == "application/pdf":
                        urls.append(link['URL'])
                        continue
                if 'URL' in response['message']:
                    urls.append(response['message']['URL'])
            except Exception as e:
                logging.debug(f"Error while fetching pdf url in CrossRef {url}")
                logging.error(e)
        return urls


class PaperDownloader:
    """论文下载器
    
    支持从多个来源获取和下载论文PDF。
    每个实例使用独立的Chrome下载器。
    """

    def __init__(self, download_dir: str = app_config.CHROME_DOWNLOAD_DIR):
        """
        初始化下载器
        
        Args:
            download_dir: 下载目录
        """
        self.chrome_downloader = ChromeDownloader(chrome_download_dir=download_dir)
        self.scihub_url = ScihubURL()
        self.unpaywall_url = UnpaywallURL()
        self.crossref_url = CrossrefURL()

    @staticmethod
    def _generate_download_dir(doi: str) -> str:
        # 使用MD5生成固定长度的字符串
        return hashlib.md5(doi.encode()).hexdigest()

    def download_by_doi(self, doi: str, file_ext: str = '.pdf', check_stop_func: callable = None) -> tuple[str, str]:
        """
        通过DOI下载论文
        
        Args:
            doi: 论文DOI
            file_ext: 下载文件扩展名
            check_stop_func: 检查是否停止下载的函数
            
        Returns:
            tuple[str, str]: (文件路径, 下载URL)
        """
        if not doi or not isinstance(doi, str):
            logging.error("Invalid DOI provided")
            return '', ''

        try:
            # 生成唯一的下载目录
            temp_dir = self._generate_download_dir(doi)

            # 按优先级获取下载URL
            urls = []

            # 从Unpaywall获取URL
            logging.info(f"Fetching URLs from Unpaywall for DOI: {doi}")
            unpaywall_urls = self.unpaywall_url.get_urls(doi)
            if unpaywall_urls:
                logging.info(f"Found {len(unpaywall_urls)} URLs from Unpaywall")
                urls.extend(unpaywall_urls)

            # 从Crossref获取URL
            logging.info(f"Fetching URLs from Crossref for DOI: {doi}")
            crossref_urls = self.crossref_url.get_urls(doi)
            if crossref_urls:
                logging.info(f"Found {len(crossref_urls)} URLs from Crossref")
                urls.extend(crossref_urls)

            # 从Sci-Hub获取URL
            logging.info(f"Fetching URLs from Sci-Hub for DOI: {doi}")
            scihub_urls = self.scihub_url.get_urls(doi)
            if scihub_urls:
                logging.info(f"Found {len(scihub_urls)} URLs from Sci-Hub")
                urls.extend(scihub_urls)

            if not urls:
                logging.error(f"No download URLs found for DOI: {doi}")
                return '', ''

            logging.info(f"Total {len(urls)} URLs found for DOI: {doi}")
            logging.debug(f"URLs to try: {urls}")

            # 尝试从每个URL下载
            for url in urls:
                if check_stop_func and check_stop_func():
                    logging.info("Download stopped by user")
                    return '', ''
                if not url:
                    continue
                try:
                    logging.info(f"Attempting to download from URL: {url}")
                    save_path = self.chrome_downloader.download(url, file_ext=file_ext, sub_dir=temp_dir)
                    if save_path and os.path.exists(save_path):
                        logging.info(f"Successfully downloaded paper to: {save_path}")
                        return save_path, url
                    else:
                        logging.warning(f"Download failed from URL: {url}")
                except Exception as e:
                    logging.error(f"Error downloading from {url}: {str(e)}")
                    continue

            logging.error(f"All download attempts failed for DOI: {doi}")
            return '', ''

        except Exception as e:
            logging.error(f"Error downloading {doi}: {str(e)}")
            traceback.print_exc()
            return '', ''

    def close(self):
        """关闭下载器并释放资源"""
        if hasattr(self, 'chrome_downloader') and self.chrome_downloader:
            self.chrome_downloader.close()
            self.chrome_downloader = None

    def __enter__(self):
        """支持上下文管理器"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """确保资源释放"""
        self.close()
