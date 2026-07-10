from pathlib import Path
from datetime import datetime


RAW_DIR = Path("data/raw")


def save_raw_content(
        source_id: str,
        markdown: str
):

    today = datetime.now().strftime(
        "%Y-%m-%d"
    )

    folder = RAW_DIR / today

    folder.mkdir(
        parents=True,
        exist_ok=True
    )


    file = folder / f"{source_id}.md"


    with open(
        file,
        "w",
        encoding="utf-8"
    ) as f:

        f.write(markdown)


    return file