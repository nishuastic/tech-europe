import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Gradium AI
    gradium_api_key: str = os.getenv("GRADIUM_API_KEY", "")
    
    # Dify
    dify_api_key: str = os.getenv("DIFY_API_KEY", "")
    dify_api_url: str = os.getenv("DIFY_API_URL", "https://api.dify.ai/v1")
    
    # OpenAI (optional fallback)
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    
    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
