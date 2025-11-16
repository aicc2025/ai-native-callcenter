"""Application configuration."""
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class DatabaseConfig:
    host: str = os.getenv("POSTGRES_HOST", "localhost")
    port: int = int(os.getenv("POSTGRES_PORT", "5432"))
    user: str = os.getenv("POSTGRES_USER", "callcenter")
    password: str = os.getenv("POSTGRES_PASSWORD", "callcenter_dev")
    database: str = os.getenv("POSTGRES_DB", "callcenter")

    @property
    def url(self) -> str:
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"


@dataclass
class RedisConfig:
    host: str = os.getenv("REDIS_HOST", "localhost")
    port: int = int(os.getenv("REDIS_PORT", "6379"))
    password: str = os.getenv("REDIS_PASSWORD", "")


@dataclass
class MinIOConfig:
    endpoint: str = os.getenv("MINIO_ENDPOINT", "localhost:9000")
    access_key: str = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
    secret_key: str = os.getenv("MINIO_SECRET_KEY", "minioadmin")
    secure: bool = os.getenv("MINIO_SECURE", "false").lower() == "true"


@dataclass
class APIConfig:
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    deepgram_api_key: str = os.getenv("DEEPGRAM_API_KEY", "")


@dataclass
class SIPConfig:
    host: str = os.getenv("SIP_HOST", "0.0.0.0")
    port: int = int(os.getenv("SIP_PORT", "5060"))


@dataclass
class AppConfig:
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    database: DatabaseConfig = DatabaseConfig()
    redis: RedisConfig = RedisConfig()
    minio: MinIOConfig = MinIOConfig()
    api: APIConfig = APIConfig()
    sip: SIPConfig = SIPConfig()


config = AppConfig()
