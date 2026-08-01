from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings): #centralized application settings loaded from environment variables and .env files
    model_config = SettingsConfigDict(
        env_file=".env", #load local development settings from a .env file when present
        env_file_encoding="utf-8", #read the env file with a predictable encoding
        extra="ignore", #ignore any environment variables we do not explicitly model yet
    )

    DATABASE_URL: str = "postgresql+psycopg://postgres:password@localhost:5432/mydb" #database connection string used by SQLAlchemy
    REDIS_URL: str | None = None #placeholder for future cache / queue integration
    JWT_SECRET_KEY: str | None = None #placeholder for future token signing
    LLM_API_KEY: str | None = None #placeholder for future LLM provider access


settings = Settings() #single shared settings instance used across the backend
DATABASE_URL = settings.DATABASE_URL #export the resolved database URL for modules that only need the connection string