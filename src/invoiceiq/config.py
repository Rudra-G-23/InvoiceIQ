from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./invoiceiq.db"
    upload_dir: Path = Path("storage/uploads")
    demo_mode: bool = True
    max_upload_mb: int = 10
    max_pdf_pages: int = 8
    frontend_origin: str = "http://localhost:5173"
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen2.5:1.5b-instruct"
    rule_only: bool = False


settings = Settings()
