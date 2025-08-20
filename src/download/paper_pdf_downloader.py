import argparse
import os
import pandas as pd
import logging
from typing import Optional, List, Dict
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from .utils import wait_for_download, get_latest_file
import concurrent.futures
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
from .chrome_downloader import ChromeDownloader

logger = logging.getLogger(__name__)


@dataclass
class DownloadTask:
    """下载任务数据类"""
    index: int  # DataFrame中的行索引
    doi: str  # DOI
    pmid: str  # PMID
    url: str  # URL


PAPER_WEB_SITE_TO_PDF_URL_XPATH = {
    'arxiv.org': "//a[contains(@class, 'abs-button') and contains(@href, '/pdf')]",
    'ieeexplore.ieee.org': "//a[contains(@class, 'pdf')]",
    'worldscientific.com': "//a[contains(@href, 'pdf') and contains(text(), 'PDF')]",
    'biorxiv.org': "//a[contains(@href, 'pdf') and contains(text(), 'DownloadPDF')]",
    'sciencedirect.com': "//a[contains(@href, '.pdf') and contains(@aria-label, 'PDF')]",
}


class PaperPDFDownloader(ChromeDownloader):
    """论文PDF下载器
    支持通过DOI、PMID和URL三种方式下载论文。
    支持多线程并行下载。
    """

    def __init__(self,
                 chrome_driver_path: str,
                 chrome_download_dir: str,
                 interval: int = 1,
                 timeout: int = 30,
                 max_retries: int = 3,
                 max_workers: int = 3):
        """初始化下载器
        
        Args:
            chrome_driver_path: ChromeDriver路径
            chrome_download_dir: PDF下载目录
            interval: 检查下载状态间隔(秒)
            timeout: 单个文件下载超时时间(秒) 
            max_retries: 下载重试次数
            max_workers: 最大并行下载线程数
        """
        super().__init__(chrome_driver_path, chrome_download_dir, interval, timeout, max_retries)

        self.max_workers = max_workers
        self.download_results: Dict[int, str] = {}  # 存储下载结果

        # PDF下载按钮和链接的常见XPath模式
        self.pdf_patterns = {
            # 直接PDF链接模式 - 优先级最高
            'direct_pdf_links': [
                "//a[contains(@href, '.pdf') and ]",
                "//a[contains(@href, '/pdf/')]",
                "//a[contains(@href, 'download') and contains(@href, '.pdf')]"
            ],
            # PDF按钮文本模式
            'pdf_text_buttons': [
                "//a[contains(text(), 'PDF')]",
                "//a[contains(text(), 'View PDF')]",
                "//a[contains(text(), 'Download PDF')]",
                "//button[contains(text(), 'PDF')]",
                "//button[contains(text(), 'Download PDF')]"
            ],
            # 通用下载按钮模式 - 优先级最低
            'download_buttons': [
                "//a[contains(text(), 'Download')]",
                "//button[contains(text(), 'Download')]",
                "//a[contains(@class, 'pdf')]",
                "//button[contains(@class, 'pdf')]",
                "//a[contains(@class, 'download')]",
                "//button[contains(@class, 'download')]"
            ]
        }

    def _try_click_pdf_button(self) -> bool:
        """尝试查找并点击PDF下载按钮或链接"""
        try:
            # 按优先级遍历不同类型的模式
            for pattern_type in ['direct_pdf_links', 'pdf_text_buttons']:
                patterns = self.pdf_patterns[pattern_type]

                # 遍历当前类型的所有XPath模式
                for pattern in patterns:
                    try:
                        # 查找所有匹配的元素
                        elements = self.chrome_driver.find_elements(By.XPATH, pattern)

                        # 遍历找到的元素
                        for element in elements:
                            try:
                                print(element.accessible_name, element.text, element.get_attribute('href'))
                                # 检查元素是否可见和可点击
                                if element.is_displayed() and element.is_enabled():
                                    # 等待元素可点击
                                    WebDriverWait(self.chrome_driver, 10).until(
                                        EC.element_to_be_clickable((By.XPATH, pattern))
                                    )
                                    # 点击元素
                                    element.click()
                                    return True
                            except Exception as e:
                                logger.error(f"Error clicking element: {e}")
                                continue
                    except:
                        continue

            logger.error("No clickable PDF download button or link found")
            return False

        except Exception as e:
            logger.error(f"Error finding and clicking PDF button: {e}")
            return False

    def _find_pdf_link(self, url: str) -> Optional[str]:
        """查找页面中的PDF下载链接
        
        Args:
            url: 页面URL
            
        Returns:
            Optional[str]: PDF文件路径,下载失败返回None
        """
        try:
            # 访问页面
            url = self._try_get_url(url)
            if not url:
                return None

            flag = False
            is_web_site = False
            for web_site, xpath in PAPER_WEB_SITE_TO_PDF_URL_XPATH.items():
                if web_site in url:
                    is_web_site = True
                    print(f"url: {url}, site: {web_site}")
                    elements = self.chrome_driver.find_elements(By.XPATH, xpath)
                    if not elements:
                        print(f"{url} not found pdf link")
                    for element in elements:
                        print(f"name:{element.accessible_name}, text:{element.text}, href:{element.get_attribute('href')}")
                        if element.is_displayed() and element.is_enabled():
                            # self.chrome_driver.execute_script("arguments[0].click();", element)  # 触发机器人验证
                            element.click()
                            flag = True
                            break

            if not is_web_site:
                # 尝试点击PDF下载按钮
                if self._try_click_pdf_button():
                    flag = True

            if not flag:
                return None

            # 等待下载完成
            pre_download_file = get_latest_file(self.current_download_dir)
            success, download_available, file_path = wait_for_download(
                self.current_download_dir,
                pre_download_file,
                self.interval,
                self.timeout
            )
            if success and download_available:
                return file_path
            return None
        except Exception as e:
            logger.error(f"Error finding PDF link: {e}")
            return None

    def _download_by_doi(self, doi: str) -> Optional[str]:
        """通过DOI下载论文"""
        if not doi:
            return None

        # 构建DOI URL
        url = f"https://doi.org/{doi}"
        return self._find_pdf_link(url)

    def _download_by_pmid(self, pmid: str) -> Optional[str]:
        """通过PMID下载论文"""
        if not pmid:
            return None

        # 构建PubMed URL
        url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}"
        return self._find_pdf_link(url)

    def _download_by_url(self, url: str) -> Optional[str]:
        """通过URL直接下载论文"""
        if not url:
            return None

        return self._find_pdf_link(url)

    def _download_single_paper(self, task: DownloadTask) -> tuple[int, str]:
        """下载单篇论文
        
        Args:
            task: 下载任务
            
        Returns:
            tuple[int, str]: (任务索引, PDF文件路径)
        """
        pdf_path = None

        try:
            # 创建线程专用的Chrome实例
            self._create_driver()
            if task.doi:
                pdf_path = self._download_by_doi(task.doi)
                if pdf_path:
                    logger.info(f"Successfully downloaded paper at index {task.index}")
                    return task.index, pdf_path
                else:
                    logger.warning(f"Failed to download paper at index {task.index}")
        except Exception as e:
            logger.error(f"Error downloading paper at index {task.index}: {e}")
        finally:
            # 确保关闭Chrome实例
            self.close()

        return task.index, pdf_path if pdf_path else ''

    def _create_download_tasks(self, df: pd.DataFrame) -> List[DownloadTask]:
        """创建下载任务列表"""
        tasks = []
        for index, row in df.iterrows():
            # 跳过已下载的论文
            if pd.notna(row['pdf_file']) and os.path.exists(row['pdf_file']):
                logger.info(f"Paper already downloaded: {row['pdf_file']}")
                self.download_results[index] = row['pdf_file']
                continue

            task = DownloadTask(
                index=index,
                doi=str(row['doi']) if pd.notna(row['doi']) else '',
                pmid=str(row['pmid']) if pd.notna(row['pmid']) else '',
                url=str(row['url']) if pd.notna(row['url']) else ''
            )
            tasks.append(task)
        return tasks

    def download_papers(self, input_file: str, output_file: str = None):
        """批量下载论文PDF
        
        Args:
            input_file: 输入的CSV/Excel文件路径
            output_file: 输出的CSV文件路径，默认在输入文件同目录下添加_with_pdf后缀
        """
        # 读取输入文件
        try:
            if input_file.endswith('.csv'):
                df = pd.read_csv(input_file)
            else:
                df = pd.read_excel(input_file)
        except Exception as e:
            logger.error(f"Error reading input file: {e}")
            return

        print("下载论文PDF数量：", len(df))
        # 设置输出文件路径
        if not output_file:
            base, ext = os.path.splitext(input_file)
            output_file = f"{base}_with_pdf.csv"

        # 确保必要的列存在
        required_cols = ['doi', 'pmid', 'url']
        for col in required_cols:
            if col not in df.columns:
                df[col] = ''

        # 添加pdf_file列
        if 'pdf_file' not in df.columns:
            df['pdf_file'] = ''

        # 创建下载任务
        tasks = self._create_download_tasks(df)
        total_tasks = len(tasks)

        if total_tasks == 0:
            logger.info("No papers to download")
            return

        logger.info(f"Starting download of {total_tasks} papers with {self.max_workers} workers")

        # 使用线程池执行下载任务
        completed_tasks = 0
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_task = {
                executor.submit(self._download_single_paper, task): task
                for task in tasks
            }

            # 处理完成的任务
            for future in concurrent.futures.as_completed(future_to_task):
                try:
                    index, pdf_path = future.result()
                    self.download_results[index] = pdf_path

                    # 更新DataFrame
                    df.at[index, 'pdf_file'] = pdf_path

                    # 定期保存进度
                    completed_tasks += 1
                    if completed_tasks % self.max_workers == 0:
                        df.to_csv(output_file, index=False)
                        logger.info(f"Progress: {completed_tasks}/{total_tasks} papers processed")

                except Exception as e:
                    logger.error(f"Task failed: {e}")

        # 最终保存结果
        df.to_csv(output_file, index=False)
        logger.info(f"Download completed. Results saved to {output_file}")


if __name__ == '__main__':
    # 参数读取
    parser = argparse.ArgumentParser(description='Paper PDF Downloader')
    parser.add_argument('-i', '--input_file', type=str, required=True, help='Input CSV/Excel file path')
    parser.add_argument('-o', '--output_file', type=str, required=False, help='Output CSV file path')
    parser.add_argument('-driver', '--chrome_driver_path', type=str, required=True, help='ChromeDriver path')
    parser.add_argument('-dir', '--chrome_download_dir', type=str, required=True, help='Chrome download directory')
    parser.add_argument('--interval', type=int, default=1, help='Check download status interval (seconds)')
    parser.add_argument('--timeout', type=int, default=60, help='Download timeout (seconds)')
    parser.add_argument('--max_retries', type=int, default=1, help='Max download retries')
    parser.add_argument('-worker', '--max_workers', type=int, default=3, help='Max concurrent download workers')
    args = parser.parse_args()

    # 初始化下载器
    downloader = PaperPDFDownloader(
        chrome_driver_path=args.chrome_driver_path,
        chrome_download_dir=args.chrome_download_dir,
        interval=args.interval,
        timeout=args.timeout,
        max_retries=args.max_retries,
        max_workers=args.max_workers
    )

    # 下载论文
    downloader.download_papers(args.input_file, args.output_file)

    # 释放资源
    del downloader
