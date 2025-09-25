import os
from functools import lru_cache
from dotenv import load_dotenv

load_dotenv()

class Settings:
    aws_region: str = os.getenv("AWS_REGION", "us-east-1")
    s3_bucket: str = os.getenv("S3_BUCKET", "aidiscovery")
    s3_prefix: str = os.getenv(
        "S3_PREFIX",
        "c0e02a19-d4b3-42c7-909a-576b7bc0d4a1/activitytrackercontainer",
    )

    mongodb_uri: str = os.getenv("MONGODB_URI", "")
    mongodb_db: str = os.getenv("MONGODB_DB", "test")

    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-5-mini")
    vision_enabled: bool = os.getenv("VISION_ENABLED", "false").lower() == "true"

    frame_interval_sec: int = int(os.getenv("FRAME_INTERVAL_SEC", "30"))

@lru_cache()
def get_settings() -> Settings:
    return Settings()
