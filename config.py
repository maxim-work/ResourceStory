import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
EXPORT_DIR = Path("exports")
MAX_URL_LENGTH = 2048
