#!/usr/bin/env python3

import csv
import json
import re
import sys
from datetime import datetime


RE_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def normalize_date(value: str) -> str:
    s = (value or "").strip()[:10]
    if not RE_ISO_DATE.match(s):
        raise ValueError(f"Invalid date (expected YYYY-MM-DD): {value!r}")
    # Validate actual calendar date
    datetime.strptime(s, "%Y-%m-%d")
    return s


def get(row, key: str) -> str:
    return (row.get(key) or "").strip()


def to_record(row, idx: int):
    date = normalize_date(get(row, "date"))
    municipality = get(row, "municipality")
    if not municipality:
        raise ValueError("Missing municipality")
    company_name = get(row, "company_name")
    if not company_name:
        raise ValueError("Missing company_name")

    province = get(row, "province")
    enterprise_number = get(row, "enterprise_number")
    postal_code = get(row, "postal_code")
    street = get(row, "street")
    court = get(row, "court")
    source_ref = get(row, "source_ref")
    source_url = get(row, "source_url")

    rid = f"{date}-{re.sub(r'[^a-z0-9]+', '-', municipality.lower()).strip('-')}-{idx}"

    return {
        "id": rid,
        "date": date,
        "municipality": municipality,
        "province": province,
        "company_name": company_name,
        "enterprise_number": enterprise_number,
        "street": street,
        "postal_code": postal_code,
        "court": court,
        "source_ref": source_ref,
        "source_url": source_url,
    }


def main():
    if len(sys.argv) != 3:
        print(
            "Usage: import_faillissementen.py <input.csv> <output.json>\n"
            "Required columns: date, municipality, company_name\n"
            "Optional columns: enterprise_number, postal_code, street, province, court, source_ref, source_url",
            file=sys.stderr,
        )
        return 2

    input_path = sys.argv[1]
    output_path = sys.argv[2]

    rows = []
    with open(input_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise SystemExit("CSV has no header row")
        for i, row in enumerate(reader, start=1):
            # Skip completely empty lines
            if not any((v or "").strip() for v in row.values()):
                continue
            try:
                rows.append(to_record(row, i))
            except Exception as e:
                raise SystemExit(f"Row {i}: {e}")

    with open(output_path, "w", encoding="utf-8") as out:
        json.dump(rows, out, ensure_ascii=False, indent=2)
        out.write("\n")

    print(f"Wrote {len(rows)} records to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

