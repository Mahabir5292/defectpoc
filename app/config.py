from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    aws_region: str = "ap-south-1"
    s3_bucket: str = ""
    defects_s3_key: str = ""
    incidents_s3_key: str = ""

    database_url: str = (
        "postgresql+psycopg://"
        "triage:triage@postgres:5432/triage"
    )

    qdrant_url: str = "http://qdrant:6333"
    qdrant_collection: str = "jira_defects_titan_v2_v2"

    embedding_provider: str = "bedrock"
    embedding_model_id: str = "amazon.titan-embed-text-v2:0"
    embedding_dimensions: int = 1024

    llm_provider: str = "huggingface"
    hf_model_id: str = "Qwen/Qwen2.5-1.5B-Instruct"
    hf_max_new_tokens: int = 500
    hf_temperature: float = 0.0
    hf_device: str = "cpu"
    hf_cache_dir: str = "/models/huggingface"
    hf_torch_threads: int = 4

    llm_model_id: str = ""

    top_k: int = 25
    final_k: int = 8
    min_score: float = 0.20
    max_context_chars: int = 14000

    vector_weight: float = 0.70
    lexical_weight: float = 0.30

    log_level: str = "INFO"


settings = Settings()
