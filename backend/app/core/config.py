from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings): #centralized application settings loaded from environment variables and .env files
    model_config = SettingsConfigDict(
        env_file=".env", #load local development settings from a .env file when present
        env_file_encoding="utf-8", #read the env file with a predictable encoding
        extra="ignore", #ignore any environment variables we do not explicitly model yet
    )

    DATABASE_URL: str = "postgresql+psycopg://postgres@localhost:5432/mydb" #database connection string used by SQLAlchemy
    REDIS_URL: str | None = None #placeholder for future cache / queue integration
    JWT_SECRET_KEY: str | None = None #placeholder for future token signing
    LLM_API_KEY: str | None = None #placeholder for future LLM provider access
    EMBEDDING_PROVIDER: str = "local" #use "openai" to call the configured external embedding provider
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSIONS: int = 384
    HF_TOKEN: str | None = None
    HUGGINGFACE_PROVIDER: str = "hf-inference"
    HUGGINGFACE_EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    HUGGINGFACE_CHAT_PROVIDER: str = "auto"
    HUGGINGFACE_QUESTION_MODEL: str = "meta-llama/Llama-3.1-8B-Instruct"
    QUESTION_MAX_TOKENS: int = 180
    QUESTION_TEMPERATURE: float = 0.2
    MAX_QUESTION_GENERATIONS_PER_DAY: int = 20
    MAX_UPLOAD_BYTES: int = 1_000_000


settings = Settings() #single shared settings instance used across the backend
DATABASE_URL = settings.DATABASE_URL #export the resolved database URL for modules that only need the connection string
