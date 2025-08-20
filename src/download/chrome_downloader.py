import os
import logging
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException, WebDriverException
from .utils import wait_for_download, create_driver, validate_file_ext, clean_file, get_latest_file

logger = logging.getLogger(__name__)


class ChromeDownloader:
    def __init__(self,
                 chrome_driver_path: str,
                 chrome_download_dir: str,
                 interval: int = 1,
                 timeout: int = 30,
                 max_retries: int = 3):
        """初始化下载器

        Args:
            chrome_driver_path: ChromeDriver路径
            chrome_download_dir: PDF下载目录
            interval: 检查下载状态间隔(秒)
            timeout: 单个文件下载超时时间(秒)
            max_retries: 下载重试次数
        """
        # 参数验证
        if not chrome_driver_path:
            raise ValueError("CHROME_DRIVER is empty!")
        if not chrome_download_dir:
            raise ValueError("CHROME_DOWNLOAD_DIR is empty!")

        # 创建下载目录
        os.makedirs(chrome_download_dir, exist_ok=True)

        # 保存配置
        self.chrome_driver_path = chrome_driver_path
        self.download_dir = chrome_download_dir
        self.timeout = timeout
        self.interval = interval
        self.max_retries = max_retries
        self.chrome_driver = None
        self.current_download_dir = chrome_download_dir  # 添加当前下载目录属性

        # 记录最新下载文件
        self.last_download_file = get_latest_file(self.download_dir)

        print(f"ChromeDownloader initialized with download dir: {chrome_download_dir}")
        print(f"last_download_file: {self.last_download_file}")

    def _create_driver(self, download_dir: str = None):
        """创建并初始化Chrome驱动，支持指定下载目录"""
        if self.chrome_driver is None:
            self.chrome_driver = create_driver(self.chrome_driver_path, download_dir or self.download_dir)
        return self.chrome_driver

    def _try_get_url(self, url: str) -> str:
        """
        尝试单次访问URL

        Args:
            url: 要下载的URL

        Returns:
            str: 当前页面URL
        """
        if not url:
            print("Empty URL provided")
            return ''

        try:
            # 确保驱动已创建
            if not self.chrome_driver:
                self._create_driver()

            # 清理可能存在的临时文件
            self._clean_temp_files()

            # 访问下载URL
            print(f"访问URL: {url}")
            self.chrome_driver.get(url)

            # 等待页面加载完成
            WebDriverWait(self.chrome_driver, self.timeout).until(
                lambda driver: driver.execute_script('return document.readyState') == 'complete'
            )
            print("页面加载完成")

            # 获取当前页面URL
            current_url = self.chrome_driver.current_url
            print(f"当前页面URL: {current_url}")

            return current_url

        except TimeoutException:
            print(f"Page load timeout: {url}")
            return ''

        except WebDriverException as e:
            print(f"WebDriver error while downloading {url}: {e}")
            return ''

        except Exception as e:
            print(f"Unexpected error while downloading {url}: {e}")
            return ''

    def download(self, url: str, file_ext: str = None, sub_dir: str = None) -> str:
        """
        下载文件

        Args:
            url: 要下载的URL
            file_ext: 下载文件扩展名
            sub_dir: 子目录名称，如果指定则在download_dir下创建子目录
        """
        # 设置下载目录
        if sub_dir:
            self.current_download_dir = os.path.join(self.download_dir, sub_dir)
            os.makedirs(self.current_download_dir, exist_ok=True)
            # 如果驱动已存在，需要重新创建以更新下载路径
            if self.chrome_driver:
                self.close()
            self._create_driver(self.current_download_dir)
        else:
            self.current_download_dir = self.download_dir

        # 基础超时时间
        current_timeout = self.timeout

        for retry in range(self.max_retries):
            try:
                # 计算当前重试的timeout时间 - 线性增加
                current_timeout = self.timeout * (retry + 1)
                print(f"Download attempt {retry + 1} for URL: {url} to dir: {self.current_download_dir} with timeout {current_timeout}s")

                # 记录下载前的最新文件
                pre_download_file = get_latest_file(self.current_download_dir)

                # 使用当前timeout设置页面加载超时
                self.chrome_driver.set_page_load_timeout(current_timeout)
                self.chrome_driver.set_script_timeout(current_timeout)

                # 尝试启动下载
                current_url = self._try_get_url(url)
                if not current_url:
                    logger.warning(f"Download attempt {retry + 1} failed for {url}")
                    continue

                # 等待下载完成，使用当前timeout
                print(f"Waiting for download to complete in directory: {self.current_download_dir}")
                success, download_available, file_path = wait_for_download(
                    self.current_download_dir,
                    pre_download_file,
                    self.interval,
                    current_timeout  # 使用当前重试的timeout
                )
                if not download_available:
                    # 不可下载
                    break

                if not success:
                    # 可能可以下载，但下载失败
                    continue

                # 验证下载文件
                if file_ext:
                    print(f"Validating downloaded file: {file_path} with extension {file_ext}")
                    if not validate_file_ext(file_path, file_ext):
                        logger.warning(f"Invalid downloaded file: {file_path}")
                        clean_file(file_path)
                        continue

                # 下载成功
                print(f"Download successful: {file_path}")
                self.last_download_file = file_path
                return file_path

            except Exception as e:
                print(f"Error on download attempt {retry + 1} with timeout {current_timeout}s: {e}")

        # 所有重试都失败
        print(f"All {self.max_retries} download attempts failed for {url}")
        return ''

    def _clean_temp_files(self):
        """清理下载目录中的临时文件"""
        for filename in os.listdir(self.download_dir):
            if filename.endswith(('.crdownload', '.tmp')):
                try:
                    os.remove(os.path.join(self.download_dir, filename))
                except OSError as e:
                    logger.warning(f"Failed to remove temp file {filename}: {e}")

    def close(self):
        """关闭下载器并释放资源"""
        if self.chrome_driver:
            try:
                self.chrome_driver.quit()
            except Exception as e:
                print(f"Error closing Chrome driver: {e}")
            finally:
                self.chrome_driver = None

    def __del__(self):
        """确保资源释放"""
        self.close()

