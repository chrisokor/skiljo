import os

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
API_KEY: str | None = os.environ.get("API_KEY")
DEFAULT_MODEL = "claude-sonnet-4-6"
