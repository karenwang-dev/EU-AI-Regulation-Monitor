import json
from pathlib import Path
from datetime import datetime


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