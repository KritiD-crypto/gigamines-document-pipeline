import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import main


class PipelineTests(unittest.TestCase):
    def test_key_value_valid_record(self):
        records = main.parse_key_value_text(
            "Material: Lithium\nQuantity: 100\nLocation: Bengaluru",
            "demo.txt", "txt"
        )
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].material, "Lithium")
        self.assertEqual(records[0].quantity, 100)
        self.assertEqual(records[0].location, "Bengaluru")
        self.assertEqual(records[0].status, "validated")

    def test_aliases(self):
        record = main.record_from_mapping(
            {"Commodity": "Cobalt", "Qty": "50", "Site": "Mysuru"},
            "demo.csv", "csv"
        )
        self.assertEqual(record.material, "Cobalt")
        self.assertEqual(record.quantity, 50)
        self.assertEqual(record.location, "Mysuru")
        self.assertEqual(record.status, "validated")

    def test_invalid_quantity_needs_review(self):
        record = main.record_from_mapping(
            {"Material": "Nickel", "Quantity": "-2", "Location": "Chennai"},
            "demo.csv", "csv"
        )
        self.assertEqual(record.status, "needs_review")
        self.assertIn("missing_or_invalid_quantity", record.review_reasons)

    def test_missing_fields_needs_review(self):
        record = main.record_from_mapping(
            {"Material": "Lithium"}, "demo.csv", "csv"
        )
        self.assertEqual(record.status, "needs_review")
        self.assertIn("missing_location", record.review_reasons)


if __name__ == "__main__":
    unittest.main()
