from typing import List

from pydantic_settings import SettingsConfigDict

from .api import ApiConfig
from .database import DataConfig
from .development import DeploymentConfig


class AppConfig(
    DataConfig,
    ApiConfig,
    DeploymentConfig
    ):

    model_config = SettingsConfigDict(
        # read from dotenv format config file
        env_file=".env",
        env_file_encoding="utf-8",
        frozen=True,
        # ignore extra attributes
        extra="ignore",
    )

    def set_root_path(self, root_path: str):
        object.__setattr__(self, 'root_path', root_path)  # 使用 object.__setattr__ 允许修改冻结属性

    # Before adding any config,
    # please consider to arrange it in the proper config group of existed or added
    # for better readability and maintainability.

    @property
    def wos_api_keys(self) -> List[str]:
        return self.WOS_API_KEY.split(',') if self.WOS_API_KEY else []
