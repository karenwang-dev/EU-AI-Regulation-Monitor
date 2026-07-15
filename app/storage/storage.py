import json
from pathlib import Path
from datetime import datetime


OUTPUT_DIR = Path("output")
RAW_DIR = Path("data/raw")


OUTPUT_DIR = Path("output")


def save_result(result: dict):

    today = datetime.now().strftime("%Y-%m-%d")

    folder = OUTPUT_DIR / today

    folder.mkdir(
        parents=True,
        exist_ok=True
    )

    filename = datetime.now().strftime("%H%M%S")

    file = folder / f"{filename}.json"

    with open(
        file,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            result,
            f,
            indent=4,
            ensure_ascii=False
        )

    return file

def save_markdown(source_id: str, markdown: str):

    today = datetime.now().strftime("%Y-%m-%d")

    folder = RAW_DIR / today

    folder.mkdir(
        parents=True,
        exist_ok=True
    )

    file = folder / f"{source_id}.md"

    file.write_text(
        markdown,
        encoding="utf-8"
    )

    return file