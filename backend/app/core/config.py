from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    app_name: str = "SOVEREIGN AI"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    frontend_origin: str = "http://localhost:3000"
    auth_cookie_name: str = "sovereignforge_session"
    auth_session_hours: int = Field(default=24 * 7, ge=1, le=24 * 90)
    app_egress_enforced: bool = False
    egress_probe_target: str = "https://example.com"
    egress_probe_timeout_seconds: float = Field(default=3.0, ge=0.5, le=10.0)

    database_url: str = (
        "postgresql+psycopg://sovereignforge:sovereignforge_dev@localhost:5432/sovereignforge"
    )
    qdrant_url: str = "http://localhost:6333"
    ollama_base_url: str = "http://localhost:11434"
    model_keep_alive: str = "2m"
    model_context_tokens: int = Field(default=8_192, ge=2_048, le=32_768)
    model_health_ttl_seconds: int = 30
    max_concurrent_model_requests: int = Field(default=1, ge=1, le=4)
    data_root: Path = Path("data")
    max_upload_bytes: int = Field(default=20 * 1024 * 1024, ge=1024)
    max_pdf_pages: int = Field(default=100, ge=1, le=500)
    ocr_text_threshold: int = Field(default=40, ge=0)
    vision_max_pages_per_task: int = Field(default=4, ge=1, le=20)
    vision_render_dpi: int = Field(default=144, ge=72, le=216)
    max_image_pixels: int = Field(default=25_000_000, ge=1_000_000, le=100_000_000)
    qdrant_collection: str = "sovereignforge_chunks"
    chunk_size_chars: int = Field(default=2800, ge=500)
    chunk_overlap_chars: int = Field(default=400, ge=0)
    embedding_model: str = "nomic-embed-text"
    task_max_steps: int = Field(default=30, ge=3, le=40)
    task_max_retries: int = Field(default=2, ge=0, le=5)
    task_timeout_seconds: int = Field(default=180, ge=30, le=900)
    task_worker_poll_seconds: float = Field(default=1.0, ge=0.1, le=10.0)
    tool_timeout_seconds: int = Field(default=30, ge=5, le=120)
    max_tool_output_chars: int = Field(default=12_000, ge=1_000, le=50_000)
    task_direct_read_chars: int = Field(default=10_000, ge=1_000, le=50_000)
    task_ephemeral_max_chunks: int = Field(default=128, ge=8, le=512)
    task_embedding_batch_size: int = Field(default=8, ge=1, le=32)
    task_kb_hits_per_base: int = Field(default=5, ge=1, le=10)
    task_evidence_max_hits: int = Field(default=10, ge=1, le=30)
    task_evidence_max_chars: int = Field(default=24_000, ge=2_000, le=100_000)
    task_evidence_timeout_seconds: int = Field(default=120, ge=10, le=600)
    sandbox_runner_url: str = "http://sandbox-runner:8090"
    sandbox_runner_token: str = "sandbox-dev-token"
    sandbox_test_command: str = "pytest"
    sandbox_timeout_seconds: int = Field(default=45, ge=2, le=120)
    sandbox_memory_mb: int = Field(default=256, ge=64, le=512)
    sandbox_cpu_count: float = Field(default=1.0, ge=0.25, le=2)
    sandbox_pids_limit: int = Field(default=64, ge=16, le=128)
    sandbox_max_output_bytes: int = Field(default=200_000, ge=1_000, le=500_000)
    sandbox_max_repository_bytes: int = Field(default=10 * 1024 * 1024, ge=1_024)
    sandbox_max_files: int = Field(default=200, ge=1, le=1_000)
    sandbox_max_patch_chars: int = Field(default=100_000, ge=1_000, le=500_000)
    sandbox_repository_context_chars: int = Field(default=32_000, ge=2_000, le=100_000)
    sandbox_max_attempts: int = Field(default=6, ge=1, le=8)


@lru_cache
def get_settings() -> Settings:
    return Settings()
