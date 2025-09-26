import os
from functools import lru_cache
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


def _as_bool(val: Optional[str], default: bool = False) -> bool:
    if val is None:
        return default
    return str(val).strip().lower() in {"1", "true", "yes", "y", "on"}


class Settings:
    aws_region: str = os.getenv("AWS_REGION", "us-east-1")
    s3_bucket: str = os.getenv("S3_BUCKET", "aidiscovery")
    s3_prefix: str = os.getenv(
        "S3_PREFIX",
        "c0e02a19-d4b3-42c7-909a-576b7bc0d4a1/activitytrackercontainer",
    )
    s3_connect_timeout: int = int(os.getenv("S3_CONNECT_TIMEOUT", "5"))
    s3_read_timeout: int = int(os.getenv("S3_READ_TIMEOUT", "60"))

    mongodb_uri: str = os.getenv("MONGODB_URI", "")
    mongodb_db: str = os.getenv("MONGODB_DB", "video-summarizer")
    mongo_server_selection_timeout_ms: int = int(os.getenv("MONGO_SERVER_SELECTION_TIMEOUT_MS", "5000"))
    mongo_connect_timeout_ms: int = int(os.getenv("MONGO_CONNECT_TIMEOUT_MS", "5000"))
    mongo_socket_timeout_ms: int = int(os.getenv("MONGO_SOCKET_TIMEOUT_MS", "60000"))

    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-5-mini")
    vision_enabled: bool = _as_bool(os.getenv("VISION_ENABLED", "true"), True)

    frame_interval_sec: int = int(os.getenv("FRAME_INTERVAL_SEC", "30"))

    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    uvicorn_log_level: str = os.getenv("UVICORN_LOG_LEVEL", "info")


@lru_cache()
def get_settings() -> Settings:
    return Settings()
