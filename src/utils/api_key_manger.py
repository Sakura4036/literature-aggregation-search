import threading
import time
import logging
from datetime import datetime, timedelta


logger = logging.getLogger(__name__)


class ApiKeyManager:
    """
    管理多个API key的使用，支持多种重置周期（daily, monthly, days）
    """
    _lock = threading.Lock()

    def __init__(
        self,
        name: str = None,
        api_keys: list[str] = None,
        limit: int = 50,
        reset_period: str = "daily",  # 支持 "daily", "monthly", "days"
        period_days: int = None       # 当reset_period为"days"时指定周期天数
    ):
        self.api_keys = api_keys
        self.name = name
        self.limit = limit
        self.reset_period = reset_period
        self.period_days = period_days
        self.usage_count = {key: 0 for key in api_keys}
        self.current_key_index = 0
        self._last_reset = datetime.now()

        # 启动自动重置线程
        self._start_auto_reset()
        self._initialized = True

    def _get_next_reset_time(self, now: datetime):
        if self.reset_period == "daily":
            next_reset = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        elif self.reset_period == "monthly":
            year = now.year + (now.month // 12)
            month = (now.month % 12) + 1
            next_reset = now.replace(year=year, month=month, day=1, hour=0, minute=0, second=0, microsecond=0)
        elif self.reset_period == "days" and self.period_days:
            next_reset = self._last_reset + timedelta(days=self.period_days)
        else:
            next_reset = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        return next_reset

    def _start_auto_reset(self):
        """启动自动重置线程"""
        def reset_checker():
            while True:
                now = datetime.now()
                next_reset = self._get_next_reset_time(now)
                if now >= next_reset:
                    self.reset_usage()
                    self._last_reset = now
                    next_reset = self._get_next_reset_time(now)
                sleep_seconds = (next_reset - now).total_seconds()
                time.sleep(max(sleep_seconds, 1))

        thread = threading.Thread(target=reset_checker, daemon=True)
        thread.start()

    def get_next_available_key(self) -> str:
        """获取下一个可用的API key"""
        if not self.api_keys:
            raise ValueError(f"No {self.name} API keys available")

        with self._lock:
            start_index = self.current_key_index
            while True:
                current_key = self.api_keys[self.current_key_index]
                if self.usage_count[current_key] < self.limit:
                    return current_key
                self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
                if self.current_key_index == start_index:
                    raise ValueError(f"All {self.name} API keys have reached limit")

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
            next_reset = self._get_next_reset_time(datetime.now())
            return {
                'usage_count': self.usage_count.copy(),
                'last_reset': self._last_reset,
                'next_reset': next_reset
            }