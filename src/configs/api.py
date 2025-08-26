from pydantic import Field
from pydantic_settings import BaseSettings


class ChromeConfig(BaseSettings):
    """
    Configuration settings for selenium and chrome
    """
    CHROME_DRIVER: str = Field(
        description="Chrome driver file path",
        default=""
    )
    CHROME_DOWNLOAD_DIR: str = Field(
        description="dir for saving Chrome download files",
        default="download"
    )
    CHROME_INTERVAL: int = Field(
        description="Interval for checking download status",
        default=1
    )
    CHROME_TIMEOUT: int = Field(
        description="Timeout for checking download status",
        default=180
    )
    CHROME_MAX_RETRIES: int = Field(
        description="Max retries for checking download status",
        default=3
    )
    CHROME_DOWNLOAD_MAX_WORKERS: int = Field(
        description="Max workers for downloading files",
        default=5
    )


class MarkerConfig(BaseSettings):
    """
    Marker, a tool for convert pdf to markdown
    """
    MARKER_API_URL: str = Field(
        description="",
        default=""
    )
    MARKER_WORKERS: int = Field(
        description="Number of workers to use for parallel processing",
        default=10
    )
    MARKER_OUTPUT_FOLDER: str = Field(
        description="Output folder for markdown files in the API server",
        default="output"
    )


class WOSConfig(BaseSettings):
    """
    Web of Science, a tool for search paper
    API documentation: https://api.clarivate.com/swagger-ui/?apikey=none&url=https%3A%2F%2Fdeveloper.clarivate.com%2Fapis%2Fwos-starter%2Fswagger
    """
    WOS_API_KEY: str = Field(
        description="API key for Web of Science, split by comma if multiple keys",
        default="",
    )
    WOS_BASE_URL: str = Field(
        description="Web of Science starter api url",
        default="https://api.clarivate.com/apis/wos-starter/v1/documents"
    )


class ApiConfig(
    ChromeConfig,
    MarkerConfig,
    WOSConfig
):
    pass