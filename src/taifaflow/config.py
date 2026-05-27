from pydantic import BaseModel


class Settings(BaseModel):
    app_name: str = "TaifaFlow"
    redis_url: str = "redis://localhost:6379/0"


settings = Settings()
