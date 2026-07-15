import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")

MODEL_NAME = "gpt-5"

OUTPUT_DIR = "output"
RAW_DATA_DIR = "data/raw"

MAX_CONTENT_LENGTH = 30000