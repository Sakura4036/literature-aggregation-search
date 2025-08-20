import os
import time
import logging
import traceback

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService

logger = logging.getLogger(__name__)


def wait_for_download(directory: str, pre_latest_file: str, interval: float = 1,
                      timeout: float = 180, download_available_timeout: int = 5,
                      min_file_size: int = 1024) -> tuple[bool, bool, str]:
    """
    等待下载完成并返回下载文件路径

    Args:
        directory: 下载目录
        pre_latest_file: 下载前目录中最新的文件路径
        interval: 检查间隔(秒)
        timeout: 单个文件下载超时时间(秒)
        download_available_timeout: 文件是否可下载超时时间(秒)
        min_file_size: 最小有效文件大小(字节)，默认1KB

    Returns:
        tuple[bool, bool, str]: (是否成功, 是否可下载, 文件路径)
    """
    success = False
    filepath = ''
    download_available = False
    is_timeout = False
    if not directory or not os.path.exists(directory):
        logger.error(f"Invalid download directory: {directory}")
        print(f"Invalid download directory: {directory}")
        return success, download_available, filepath

    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            # 获取当前最新文件
            latest_file = get_latest_file(directory)
            print(f"wait_for_download  current latest_file: {latest_file}")

            # 检查是否有新文件
            if not latest_file or (pre_latest_file and os.path.samefile(latest_file, pre_latest_file)):
                if time.time() - start_time >= download_available_timeout:
                    download_available = False
                    break
                time.sleep(interval)
                continue

            # 检查是否为临时文件
            if latest_file.endswith(('.crdownload', '.tmp')) or latest_file.startswith(('.com.google.Chrome')):
                download_available = True
                # 等待临时文件下载完成
                temp_file = latest_file
                temp_start_time = time.time()
                while time.time() - temp_start_time < timeout:
                    if not os.path.exists(temp_file):
                        # 临时文件消失,检查是否有新文件
                        latest_file = get_latest_file(directory)
                        if latest_file and not latest_file.endswith(('.crdownload', '.tmp')):
                            # 检查文件完整性
                            if _verify_downloaded_file(latest_file, min_file_size):
                                logger.debug(f"Download file success, cost {time.time() - temp_start_time}s.")
                                print(f"Download file success, cost {time.time() - temp_start_time}s.")
                                # 文件下载完成
                                return True, True, latest_file
                            else:
                                logger.error(f"Downloaded file verification failed: {latest_file}")
                                print(f"Downloaded file verification failed: {latest_file}")
                                try:
                                    os.remove(latest_file)
                                except OSError:
                                    pass
                                finally:
                                    return success, download_available, filepath
                        else:
                            # 临时文件消失,但没有新文件
                            is_timeout = False
                            download_available = False
                            break
                    else:
                        # 等待下载完成
                        time.sleep(interval)
                if time.time() - temp_start_time >= timeout:
                    is_timeout = True
                # 临时文件下载超时,清理并继续
                if os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                    except OSError:
                        pass
                # 下载失败， 跳出循环
                break

            # 找到有效的新文件，验证文件完整性
            if latest_file != pre_latest_file:
                if _verify_downloaded_file(latest_file, min_file_size):
                    return True, True, latest_file
                else:
                    logger.error(f"Downloaded file verification failed: {latest_file}")
                    print(f"Downloaded file verification failed: {latest_file}")
                    try:
                        os.remove(latest_file)
                    except OSError:
                        pass
                    break
        except Exception as e:
            traceback.print_exc()
            logger.error(f"Error waiting for download: {e}")
            print(f"Error waiting for download: {e}")
            break
    if is_timeout:
        logger.error(f"Download timeout after {timeout}s")
        print(f"Download timeout after {timeout}s")
    return success, download_available, filepath


def _verify_downloaded_file(file_path: str, min_file_size: int = 1024) -> bool:
    """
    验证下载文件的完整性和大小

    Args:
        file_path: 文件路径
        min_file_size: 最小有效文件大小(字节)

    Returns:
        bool: 文件是否有效
    """
    try:
        if not os.path.exists(file_path):
            logger.error(f"File does not exist: {file_path}")
            return False

        # 检查文件大小
        file_size = os.path.getsize(file_path)
        if file_size < min_file_size:
            logger.error(f"File too small ({file_size} bytes): {file_path}")
            return False

        # 尝试打开文件检查是否可读
        with open(file_path, 'rb') as f:
            # 读取文件头部检查是否为有效的PDF文件
            if file_path.lower().endswith('.pdf'):
                header = f.read(5)
                if header != b'%PDF-':
                    logger.error(f"Invalid PDF file header: {file_path}")
                    return False

            # 尝试读取文件尾部确保文件完整
            f.seek(-1024, 2)  # 从文件末尾读取最后1KB
            f.read()

        return True

    except Exception as e:
        logger.error(f"Error verifying file {file_path}: {e}")
        return False


def create_driver(executable_path: str = None, download_dir: str = None, chrome_options: Options = None, timeout: int = 30):
    """
    create chrome driver
    :param executable_path: chrome driver path
    :param download_dir: download directory
    :param chrome_options: chrome options
    :param timeout: page load timeout, script timeout
    """
    if not os.path.exists(executable_path):
        raise FileNotFoundError(f"Chrome driver not found: {executable_path}")

    # 确保下载目录是绝对路径
    if not os.path.isabs(download_dir):
        download_dir = os.path.abspath(download_dir)

    logger.info(f"Creating Chrome driver with download directory: {download_dir}")

    if not os.path.exists(download_dir):
        os.makedirs(download_dir)
        logger.info(f"Created download directory: {download_dir}")

    if not chrome_options:
        chrome_options = Options()
        prefs = {
            'download.default_directory': download_dir,
            'download.prompt_for_download': False,
            'download.directory_upgrade': True,
            "plugins.always_open_pdf_externally": True,
            'safebrowsing.enabled': False,
            'safebrowsing.disable_download_protection': True,
            'profile.default_content_settings.popups': 0,
            "profile.content_settings.exceptions.automatic_downloads.*.setting": 1,
            "profile.default_content_setting_values.automatic_downloads": 1,
            "profile.managed_default_content_settings.automatic_downloads": 1,
            "download.extensions_to_open": "applications/pdf",
        }
        chrome_options.add_experimental_option('prefs', prefs)
        chrome_options.add_argument("--mute-audio")
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--incognito")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-setuid-sandbox")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-application-cache")
        chrome_options.add_argument("--disable-infobars")
        chrome_options.add_argument("--ignore-certificate-errors")
        chrome_options.add_argument("--dns-prefetch-disable")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--proxy-server='direct://'")
        chrome_options.add_argument("--proxy-bypass-list=*")

    chrome_service = ChromeService(executable_path=executable_path)
    driver = webdriver.Chrome(service=chrome_service, options=chrome_options)
    driver.set_page_load_timeout(timeout)
    driver.set_script_timeout(timeout)

    logger.info("Chrome driver created successfully")
    return driver


def validate_file_ext(file_path: str, file_ext: str) -> bool:
    """验证下载的文件是否为有效的PDF"""
    if not file_path or not os.path.exists(file_path):
        return False
    return file_path.lower().endswith(file_ext.lower())


def get_latest_file(folder: str) -> str:
    # Step 1: Get all entries in the folder
    entries = os.listdir(folder)
    entries = [os.path.join(folder, entry) for entry in entries]
    # Step 2: Filter out directories, only keep files
    files = [entry for entry in entries if os.path.isfile(entry)]

    # Step 3: Check if the folder is empty or has no files
    if not files:
        return ''

    # Step 4: Find the file with the latest modification time
    latest_file = max(files, key=lambda f: os.path.getmtime(f))

    # Step 5: Return the filepath of the latest file
    return latest_file


def clean_file(file_path: str):
    """清理指定文件"""
    try:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
    except OSError as e:
        logger.warning(f"Failed to remove file {file_path}: {e}")