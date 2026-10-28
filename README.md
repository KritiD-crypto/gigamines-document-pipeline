# Giga Mines — Multi-Format Document Ingestion & Tabularization

A local proof of concept for ingesting heterogeneous documents and normalizing extracted records into CSV/JSON, with validation, a manual-review queue, and error logs.

## Supported inputs

- CSV and Excel (`.csv`, `.xlsx`, `.xlsm`)
- JSON records (`.json`)
- Labelled text (`.txt`), e.g. `Material: Lithium`
- Word documents (`.docx`) with labelled paragraphs and simple tables
- Text-based PDFs (`.pdf`); scanned pages use OCR when Tesseract is available
- Images (`.png`, `.jpg`, `.jpeg`, `.tif`, `.tiff`, `.bmp`) using Tesseract OCR

## Requirements

- Python 3.11+ recommended
- Tesseract OCR installed separately for scanned-image OCR
- Windows PowerShell instructions below; the script also uses standard Python libraries cross-platform.

## Setup (Windows PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

If Python is not recognized, use the full Python launcher (`py`) or fix the Python PATH. If Tesseract is installed at `C:\Program Files\Tesseract-OCR\tesseract.exe`, the script detects that path automatically. Otherwise add Tesseract to PATH or configure `pytesseract.pytesseract.tesseract_cmd`.

## Run

Put input documents in `input_files/`, then run:

```powershell
python src/main.py
```

Generated files are written to `output/`:

- `combined_data.csv` — normalized records from all files
- `combined_data.json` — same records as JSON
- `review_queue.csv` — records with missing/invalid required fields or extraction uncertainty
- `errors.csv` — files that failed to process
- `logs/pipeline.log` — processing log

## Normalized schema

| Field | Meaning |
|---|---|
| `material` | Material / mineral / element / commodity |
| `quantity` | Non-negative numeric quantity |
| `location` | Site / facility / city |
| `source_file` | Original filename for traceability |
| `source_type` | Format or extraction route |
| `page` | PDF page or source row where applicable |
| `status` | `validated` or `needs_review` |
| `review_reasons` | Semicolon-separated validation or extraction flags |
| `extracted_at_utc` | UTC extraction timestamp |

The proof of concept uses a deliberately small common schema to demonstrate normalization. Real deployments should define schemas per document family and units for quantities rather than assuming all quantities are directly comparable.

## Design and reliability notes

1. File extension routing selects a parser; files are processed independently so one failure does not stop the batch.
2. Tabular formats use pandas/openpyxl; Word uses python-docx; PDF text extraction uses PyMuPDF; image/scanned PDF OCR uses Tesseract via pytesseract.
3. Recognized aliases are mapped to canonical field names.
4. Required fields and non-negative numeric quantity are checked. Invalid/incomplete records are not silently discarded; they go to `review_queue.csv`.
5. Each record preserves source filename and extraction timestamp.
6. Exceptions are logged to `errors.csv` and `output/logs/pipeline.log`.
7. OCR output and heuristic field extraction are not guaranteed to be correct. Production should retain confidence scores, use document-specific schemas, compare totals where applicable, and require human approval for low-confidence or high-impact fields.

## Limitations

- The demo schema is `material`, `quantity`, `location`; adapt it to the real documents.
- Text PDFs and simple labelled lines are supported; arbitrary complex PDF tables/layouts may need table extraction or document-specific parsing.
- OCR requires Tesseract to be installed separately.
- This is a local proof of concept, not a production queue/service. A production architecture can add object storage, a durable queue, worker pool, retries with backoff, idempotency keys, database transactions, monitoring, access controls, and a review UI.
