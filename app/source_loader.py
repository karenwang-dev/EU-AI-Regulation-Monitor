import json
from pathlib import Path


CONFIG_FILE = Path("config/sources.json")


def load_sources():

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    return data["sources"]