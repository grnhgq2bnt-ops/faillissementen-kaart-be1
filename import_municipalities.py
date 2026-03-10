#!/usr/bin/env python3

import csv
import json
import re
import sys


def slugify(value: str) -> str:
    s = (value or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "unknown"


def get(row, key: str) -> str:
    return (row.get(key) or "").strip()


def to_float(value: str, field: str) -> float:
    s = (value or "").strip().replace(",", ".")
    try:
        return float(s)
    except Exception:
        raise ValueError(f"Invalid {field}: {value!r}")


def parse_aliases(value: str):
    s = (value or "").strip()
    if not s:
        return []
    # Allow pipe or comma separated aliases
    parts = [p.strip() for p in re.split(r"[|,]", s) if p.strip()]
    return parts


def to_record(row):
    name = get(row, "name")
    if not name:
        raise ValueError("Missing name")
    mid = get(row, "id") or slugify(name)
    province = get(row, "province")
    region = get(row, "region")
    lat = to_float(get(row, "lat"), "lat")
    lng = to_float(get(row, "lng"), "lng")
    aliases = parse_aliases(get(row, "aliases"))

    rec = {
        "id": mid,
        "name": name,
        "province": province,
        "region": region,
        "lat": lat,
        "lng": lng,
    }
    if aliases:
        rec["aliases"] = aliases
    return rec


def main():
    if len(sys.argv) != 3:
        print(
            "Usage: import_municipalities.py <input.csv> <output.json>\n"
            "Required columns: name, lat, lng\n"
            "Optional columns: id, province, region, aliases (pipe or comma separated)",
            file=sys.stderr,
        )
        return 2

    input_path = sys.argv[1]
    output_path = sys.argv[2]

    out = []
    with open(input_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise SystemExit("CSV has no header row")
        for i, row in enumerate(reader, start=1):
            if not any((v or "").strip() for v in row.values()):
                continue
            try:
                out.append(to_record(row))
            except Exception as e:
                raise SystemExit(f"Row {i}: {e}")

    with open(output_path, "w", encoding="utf-8") as out_f:
        json.dump(out, out_f, ensure_ascii=False, indent=2)
        out_f.write("\n")

    print(f"Wrote {len(out)} municipalities to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

