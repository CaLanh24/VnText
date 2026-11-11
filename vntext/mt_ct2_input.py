"""CT2 CSV input validation; performs no model loading or writes."""
from pathlib import Path
from vntext.mt_ct2_io import _load_csv
from vntext.mt_ct2_model import EmptyCsvError

def load_translation_input(csv_path):
    csv_path = Path(csv_path).resolve()
    if not csv_path.is_file():
        raise FileNotFoundError(str(csv_path))

    fields, rows = _load_csv(csv_path)
    if not fields or "key" not in fields or "translation" not in fields:
        raise EmptyCsvError("translation.csv header không hợp lệ")
    if not rows:
        raise EmptyCsvError("translation.csv không có dòng dữ liệu")

    return csv_path, fields, rows
