import threading
import time
import logging
from datetime import datetime, timedelta


logger = logging.getLogger(__name__)


class DailyApiKeyManager:
    """管理多个Daily API key的使用"""
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, api_keys: list[str] = None):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, api_keys: list[str] = None, name: str = None):
        if self._initialized:
            return

        self.api_keys = api_keys
        self.name = name
        self.usage_count = {key: 0 for key in api_keys}  # 记录每个key的使用次数
        self.daily_limit = 50  # WOS API每个key每天的调用限制
        self.current_key_index = 0
        self._last_reset = datetime.now()

        # 启动自动重置线程
        self._start_auto_reset()
        self._initialized = True

    def _start_auto_reset(self):
        """启动自动重置线程"""

        def reset_checker():
            while True:
                now = datetime.now()
                # 如果已经过了一天
                if (now - self._last_reset).days >= 1:
                    self.reset_usage()
                    self._last_reset = now
                # 计算到下一个0点的秒数
                next_day = (now + timedelta(days=1)).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                sleep_seconds = (next_day - now).total_seconds()
                time.sleep(sleep_seconds)

        # 启动后台线程
        thread = threading.Thread(target=reset_checker, daemon=True)
        thread.start()

    def get_next_available_key(self) -> str:
        """获取下一个可用的API key"""
        if not self.api_keys:
            raise ValueError("No %s API keys available", self.name)

        with self._lock:
            # 检查所有key的使用情况
            start_index = self.current_key_index
            while True:
                current_key = self.api_keys[self.current_key_index]
                if self.usage_count[current_key] < self.daily_limit:
                    return current_key

                # 移动到下一个key
                self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)

                # 如果已经检查了所有的key
                if self.current_key_index == start_index:
                    raise ValueError("All %s API keys have reached daily limit", self.name)

    def increment_usage(self, api_key: str):
        """增加指定key的使用计数"""
        with self._lock:
            if api_key in self.usage_count:
                self.usage_count[api_key] += 1

    def reset_usage(self):
        """重置所有key的使用计数"""
        with self._lock:
            self.usage_count = {key: 0 for key in self.api_keys}
            logger.info(f"Reset {self.name} API keys usage count at {datetime.now()}")

    def get_usage_info(self) -> dict:
        """获取所有key的使用情况"""
        with self._lock:
            return {
                'usage_count': self.usage_count.copy(),
                'last_reset': self._last_reset,
                'next_reset': (self._last_reset + timedelta(days=1)).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
            }