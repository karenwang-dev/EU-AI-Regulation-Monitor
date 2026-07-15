from pathlib import Path
import difflib



def compare_files(
        old_file: str,
        new_file: str
):

    old_text = Path(
        old_file
    ).read_text(
        encoding="utf-8"
    )


    new_text = Path(
        new_file
    ).read_text(
        encoding="utf-8"
    )


    diff = difflib.unified_diff(

        old_text.splitlines(),

        new_text.splitlines(),

        fromfile=old_file,

        tofile=new_file

    )


    return "\n".join(diff)