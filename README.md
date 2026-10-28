
# Giga Mines — Multi-Format Document Ingestion & Tabularization

A Python proof of concept for ingesting documents in multiple formats, extracting structured information, and normalizing records into CSV and JSON. The pipeline includes field validation, a manual-review queue, error logging, and source traceability.

## Features

- Multi-format document ingestion
- Structured data extraction and field normalization
- Canonical field mapping using recognized aliases
- Validation of required fields and non-negative numeric quantities
- Manual-review queue for incomplete or invalid records
- Error handling so individual file failures do not stop the entire batch
- CSV and JSON output generation
- Source filename and extraction timestamp tracking
- OCR support for images and scanned PDFs when Tesseract is installed
- Automated unit tests for key parsing and validation behavior

## Supported Input Formats

| Format | Supported files |
|---|---|
| CSV | `.csv` |
| Excel | `.xlsx`, `.xlsm` |
| JSON | `.json` |
| Text | `.txt` with labelled fields such as `Material: Lithium` |
| Word | `.docx` with labelled paragraphs and simple tables |
| PDF | `.pdf` with extractable text; scanned pages can use OCR |
| Images | `.png`, `.jpg`, `.jpeg`, `.tif`, `.tiff`, `.bmp` |

## Project Structure

```text
gigamines-document-pipeline/
├── input_files/             # Sample documents and input files
├── output/                  # Generated results
├── src/
│   └── main.py              # Main ingestion and processing pipeline
├── tests/
│   └── test_pipeline.py     # Unit tests
├── .gitignore
├── ARCHITECTURE.md          # System architecture and design
├── README.md
└── requirements.txt         # Python dependencies
```

## Requirements

- Python 3.11 or newer recommended
- pip for installing Python dependencies
- Tesseract OCR for scanned-image and scanned-PDF OCR
- Windows PowerShell commands are provided below; the Python script uses standard cross-platform paths and libraries.

### Installing Tesseract OCR

OCR requires Tesseract to be installed separately.

If Tesseract is installed at:

```text
C:\Program Files\Tesseract-OCR\tesseract.exe
```

the script detects that path automatically. Otherwise, add Tesseract to your system PATH or configure `pytesseract.pytesseract.tesseract_cmd` in the source code.

## Setup — Windows PowerShell

Open a terminal in the project root directory.

### 1. Create a virtual environment

```powershell
python -m venv .venv
```

### 2. Activate the virtual environment

```powershell
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, you can run the commands below without activating the environment by using `.venv\Scripts\python.exe`.

### 3. Install dependencies

```powershell
python -m pip install -r requirements.txt
```

If Python is not recognized, install Python and ensure it is available on PATH. You can also try the Python launcher:

```powershell
py -m venv .venv
```

## Running the Pipeline

1. Place the documents you want to process in the `input_files/` directory.
2. Run the pipeline from the project root:

```powershell
python src/main.py
```

The pipeline discovers supported files, processes them independently, validates extracted records, and writes the generated results to `output/`.

## Generated Outputs

| Output file | Purpose |
|---|---|
| `output/combined_data.csv` | Normalized records from all successfully processed inputs |
| `output/combined_data.json` | The normalized records in JSON format |
| `output/review_queue.csv` | Records requiring manual review because of missing or invalid fields or extraction uncertainty |
| `output/errors.csv` | Files that failed during processing, with error details |
| `output/logs/pipeline.log` | Processing log |

Generated outputs are created when the pipeline runs. The `output/` directory is included in the repository with a placeholder file; generated results are not committed by default.

## Normalized Data Schema

The pipeline uses a common schema to demonstrate normalization across different input formats.

| Field | Description |
|---|---|
| `material` | Material, mineral, element, or commodity |
| `quantity` | Non-negative numeric quantity |
| `location` | Site, facility, or city |
| `source_file` | Original filename for traceability |
| `source_type` | Format or extraction route |
| `page` | PDF page or source row where applicable |
| `status` | `validated` or `needs_review` |
| `review_reasons` | Semicolon-separated validation or extraction flags |
| `extracted_at_utc` | UTC extraction timestamp |

The proof of concept uses a deliberately small common schema. Real deployments should define document-specific schemas and units for quantities rather than assuming that all quantities are directly comparable.

## Validation and Error Handling

The pipeline demonstrates the following reliability measures:

1. File extensions determine which parser is used.
2. Files are processed independently, so one failure does not stop the entire batch.
3. Recognized field aliases are mapped to canonical names.
4. Required fields and non-negative numeric quantities are validated.
5. Incomplete or invalid records are sent to `review_queue.csv` instead of being silently discarded.
6. Extracted records retain source filenames and UTC timestamps.
7. Processing failures are recorded in `errors.csv` and `output/logs/pipeline.log`.

OCR and heuristic extraction can produce incorrect results. Extracted information should be reviewed before it is used for important operational decisions.

## Running the Tests

Run the unit tests from the project root:

```powershell
python -m unittest discover -s tests -v
```

The tests cover field aliases, valid labelled records, invalid quantities, and missing required fields.

## Architecture

The application follows a file-ingestion and normalization workflow:

1. Discover supported input files.
2. Route each file to the appropriate parser.
3. Extract structured fields from the document.
4. Normalize recognized field names.
5. Validate the extracted records.
6. Route invalid or uncertain records for manual review.
7. Write normalized data, review records, and processing errors to the output directory.

See [ARCHITECTURE.md](ARCHITECTURE.md) for the architecture proposal, component responsibilities, reliability considerations, and potential production improvements.

## Limitations

- The demonstration schema is limited to `material`, `quantity`, and `location`.
- Complex PDF tables and arbitrary document layouts may require specialized extraction techniques.
- OCR requires a separate Tesseract installation.
- OCR and heuristic field extraction are not guaranteed to be correct.
- The current implementation is a local proof of concept, not a production queue or hosted service.

## Future Improvements

A production implementation could introduce:

- Object storage for uploaded documents
- A durable message queue and worker pool
- Retry handling with backoff and idempotency keys
- Database transactions and persistent record storage
- Document-specific schemas and extraction confidence scores
- Monitoring, access controls, and audit trails
- A human-review interface for low-confidence or high-impact fields
- Additional automated integration tests

## Assignment Context

This project was developed as the document-ingestion and tabularization proof of concept for the Giga Mines internship assignment. It demonstrates multi-format ingestion, structured extraction, validation, normalization, error handling, and an architecture for future production development.
