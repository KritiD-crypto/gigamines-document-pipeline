from __future__ import annotations

import csv
import json
import logging
import re
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
INPUT_DIR = BASE_DIR / "input_files"
OUTPUT_DIR = BASE_DIR / "output"
LOG_DIR = OUTPUT_DIR / "logs"

SUPPORTED_EXTENSIONS = {
    ".csv", ".xlsx", ".xlsm", ".json", ".txt", ".docx", ".pdf",
    ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"
}
REQUIRED_FIELDS = ("material", "quantity", "location")
FIELD_ALIASES = {
    "material": "material", "element": "material", "commodity": "material",
    "product": "material", "mineral": "material",
    "quantity": "quantity", "qty": "quantity", "amount": "quantity",
    "weight": "quantity", "volume": "quantity",
    "location": "location", "site": "location", "city": "location",
    "facility": "location", "origin": "location",
}
TEXT_FIELD_PATTERN = re.compile(
    r"^\s*([A-Za-z][A-Za-z _/-]{0,40})\s*:\s*(.*?)\s*$"
)


@dataclass
class ExtractionRecord:
    material: str = ""
    quantity: float | None = None
    location: str = ""
    source_file: str = ""
    source_type: str = ""
    page: int | None = None
    status: str = "needs_review"
    review_reasons: str = ""
    extracted_at_utc: str = ""


def configure_logging() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=LOG_DIR / "pipeline.log",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        encoding="utf-8",
    )


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def normalize_key(key: Any) -> str:
    key_text = clean_text(key).lower().replace("-", " ").replace("_", " ")
    key_text = re.sub(r"\s+", " ", key_text)
    return FIELD_ALIASES.get(key_text, key_text.replace(" ", "_"))


def parse_quantity(value: Any) -> float | None:
    text = clean_text(value)
    if not text:
        return None
    # Accept simple numeric values, optionally with thousands separators.
    text = text.replace(",", "")
    match = re.fullmatch(r"[-+]?\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        number = float(text)
        if number < 0:
            return None
        return int(number) if number.is_integer() else number
    except ValueError:
        return None


def validate_record(record: ExtractionRecord) -> ExtractionRecord:
    reasons: list[str] = []
    record.material = clean_text(record.material)
    record.location = clean_text(record.location)

    if not record.material:
        reasons.append("missing_material")
    if record.quantity is None:
        reasons.append("missing_or_invalid_quantity")
    if not record.location:
        reasons.append("missing_location")

    record.status = "needs_review" if reasons else "validated"
    record.review_reasons = ";".join(reasons)
    record.extracted_at_utc = datetime.now(timezone.utc).isoformat()
    return record


def parse_key_value_text(text: str, source_file: str, source_type: str,
                         page: int | None = None) -> list[ExtractionRecord]:
    """Parse labelled lines such as Material: Lithium into a normalized record."""
    fields: dict[str, str] = {}
    for line in text.splitlines():
        match = TEXT_FIELD_PATTERN.match(line)
        if not match:
            continue
        key = normalize_key(match.group(1))
        value = clean_text(match.group(2))
        if key in REQUIRED_FIELDS and value:
            fields[key] = value

    # If there are no recognized labels, retain the text for manual review.
    if not fields:
        return [validate_record(ExtractionRecord(
            source_file=source_file,
            source_type=source_type,
            page=page,
            review_reasons="no_recognized_fields",
        ))]

    record = ExtractionRecord(
        material=fields.get("material", ""),
        quantity=parse_quantity(fields.get("quantity")),
        location=fields.get("location", ""),
        source_file=source_file,
        source_type=source_type,
        page=page,
    )
    return [validate_record(record)]


def record_from_mapping(mapping: dict[str, Any], source_file: str,
                        source_type: str, row_number: int | None = None) -> ExtractionRecord:
    normalized: dict[str, Any] = {}
    for key, value in mapping.items():
        normalized[normalize_key(key)] = value

    material = clean_text(normalized.get("material", ""))
    location = clean_text(normalized.get("location", ""))
    quantity = parse_quantity(normalized.get("quantity"))
    record = ExtractionRecord(
        material=material,
        quantity=quantity,
        location=location,
        source_file=source_file,
        source_type=source_type,
        page=row_number,
    )
    return validate_record(record)


def records_from_dataframe(df: pd.DataFrame, source_file: str,
                           source_type: str) -> list[ExtractionRecord]:
    if df.empty:
        raise ValueError("File contains no data rows")
    df = df.dropna(how="all")
    records: list[ExtractionRecord] = []
    for index, row in df.iterrows():
        record = record_from_mapping(
            row.to_dict(), source_file, source_type, row_number=int(index) + 2
        )
        records.append(record)
    return records


def extract_docx(path: Path) -> list[ExtractionRecord]:
    from docx import Document

    doc = Document(path)
    results: list[ExtractionRecord] = []
    paragraph_text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    if paragraph_text.strip():
        results.extend(parse_key_value_text(paragraph_text, path.name, "docx"))

    # Treat the first row of each Word table as headers.
    for table_index, table in enumerate(doc.tables, start=1):
        rows = [[clean_text(cell.text) for cell in row.cells] for row in table.rows]
        if len(rows) >= 2:
            headers = [normalize_key(h) for h in rows[0]]
            df = pd.DataFrame(rows[1:], columns=headers)
            results.extend(records_from_dataframe(df, path.name, "docx_table"))
        elif rows:
            results.append(validate_record(ExtractionRecord(
                source_file=path.name,
                source_type="docx_table",
                review_reasons=f"table_{table_index}_has_no_header",
            )))
    if not results:
        raise ValueError("No text or tables found in Word document")
    return results


def extract_pdf(path: Path) -> list[ExtractionRecord]:
    import pymupdf

    results: list[ExtractionRecord] = []
    with pymupdf.open(path) as pdf:
        if len(pdf) == 0:
            raise ValueError("PDF has no pages")
        for page_index, page in enumerate(pdf, start=1):
            text = page.get_text("text").strip()
            if not text:
                # OCR is only needed for pages without extractable text.
                try:
                    import pytesseract
                    from PIL import Image
                    from io import BytesIO

                    possible_exe = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
                    if possible_exe.exists():
                        pytesseract.pytesseract.tesseract_cmd = str(possible_exe)
                    pix = page.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False)
                    image = Image.open(BytesIO(pix.tobytes("png")))
                    text = pytesseract.image_to_string(image)
                except Exception as exc:
                    logging.warning("OCR failed for %s page %s: %s", path.name, page_index, exc)
                    results.append(validate_record(ExtractionRecord(
                        source_file=path.name,
                        source_type="pdf",
                        page=page_index,
                        review_reasons="ocr_failed_or_unavailable",
                    )))
                    continue
            if text.strip():
                results.extend(parse_key_value_text(text, path.name, "pdf", page_index))
            else:
                results.append(validate_record(ExtractionRecord(
                    source_file=path.name,
                    source_type="pdf",
                    page=page_index,
                    review_reasons="no_text_extracted",
                )))
    return results


def extract_image(path: Path) -> list[ExtractionRecord]:
    import pytesseract
    from PIL import Image

    possible_exe = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
    if possible_exe.exists():
        pytesseract.pytesseract.tesseract_cmd = str(possible_exe)
    text = pytesseract.image_to_string(Image.open(path))
    return parse_key_value_text(text, path.name, "image")


def process_file(path: Path) -> list[ExtractionRecord]:
    suffix = path.suffix.lower()
    logging.info("Starting file: %s", path.name)

    if suffix == ".csv":
        df = pd.read_csv(path)
        records = records_from_dataframe(df, path.name, "csv")
    elif suffix in {".xlsx", ".xlsm"}:
        df = pd.read_excel(path)
        records = records_from_dataframe(df, path.name, "excel")
    elif suffix == ".json":
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict):
            data = data.get("records", data.get("data", [data]))
        if not isinstance(data, list):
            raise ValueError("JSON must contain an object or list of records")
        df = pd.json_normalize(data)
        records = records_from_dataframe(df, path.name, "json")
    elif suffix == ".txt":
        text = path.read_text(encoding="utf-8-sig")
        records = parse_key_value_text(text, path.name, "txt")
    elif suffix == ".docx":
        records = extract_docx(path)
    elif suffix == ".pdf":
        records = extract_pdf(path)
    elif suffix in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}:
        records = extract_image(path)
    else:
        raise ValueError(f"Unsupported file extension: {suffix}")

    # Keep one normalized record per input row/page/text record.
    logging.info("Finished file: %s (%s records)", path.name, len(records))
    return records



def write_csv(
    path: Path,
    records: list[dict[str, Any]],
    columns: list[str] | None = None,
) -> None:
    if columns is None:
        columns = (
            list(records[0].keys())
            if records
            else list(asdict(ExtractionRecord()).keys())
        )

    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(records)



def main() -> int:
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    configure_logging()

    files = sorted(
        p for p in INPUT_DIR.iterdir()
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
    )
    if not files:
        print(f"No supported files found in: {INPUT_DIR}")
        print("Supported: CSV, XLSX, JSON, TXT, DOCX, PDF, PNG, JPG, TIFF, BMP")
        return 0

    all_records: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    for path in files:
        try:
            records = process_file(path)
            all_records.extend(asdict(record) for record in records)
            print(f"Processed: {path.name} ({len(records)} record(s))")
        except Exception as exc:
            logging.exception("Failed to process %s", path.name)
            errors.append({
                "source_file": path.name,
                "error_type": type(exc).__name__,
                "error_message": str(exc),
                "occurred_at_utc": datetime.now(timezone.utc).isoformat(),
            })
            print(f"Failed: {path.name} — {type(exc).__name__}: {exc}")

    validated = [r for r in all_records if r["status"] == "validated"]
    review = [r for r in all_records if r["status"] != "validated"]

    write_csv(OUTPUT_DIR / "combined_data.csv", all_records)
    (OUTPUT_DIR / "combined_data.json").write_text(
        json.dumps(all_records, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    write_csv(OUTPUT_DIR / "review_queue.csv", review)
    write_csv(
    OUTPUT_DIR / "errors.csv",
    errors,
    columns=["source_file", "error_type", "error_message", "occurred_at_utc"],
    )

    print("\nPipeline finished.")
    print(f"Files discovered: {len(files)}")
    print(f"Records extracted: {len(all_records)}")
    print(f"Validated records: {len(validated)}")
    print(f"Records needing review: {len(review)}")
    print(f"Files with errors: {len(errors)}")
    print(f"Outputs: {OUTPUT_DIR}")
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
