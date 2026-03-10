#!/usr/bin/env python3
"""
Parse een KBO daily wijzigingsbestand (zip met CSV) naar faillissementen JSON.

Werkwijze:
- verwacht een zip met minstens één CSV. We kiezen het eerste CSV-bestand dat kolommen bevat
  waarin een faillissementsstatus te vinden is.
- filtert records waar een statusveld de substring 'faill' bevat (case-insensitive).
- kiest als datum de kolom die lijkt op een status- of wijzigingsdatum; valt terug op vandaag.

CLI:
  python3 scripts/import_kbo_daily.py <input.zip> <output.json> [--muni data/municipalities.json]

Output JSON schema (compatibel met de webapp):
  [
    {
      "id": "<date>-<enterprise_number>",
      "date": "YYYY-MM-DD",
      "municipality": "...",
      "province": "...",        # optioneel, ingevuld als matching gemeente bekend is
      "company_name": "...",
      "enterprise_number": "...",
      "street": "...",
      "postal_code": "...",
      "court": "",
      "source_ref": "KBO daily <zipfile>",
      "source_url": ""
    },
    ...
  ]
"""

import argparse
import csv
import io
import json
import re
import sys
import zipfile
from datetime import date
from pathlib import Path


def normalize_str(s: str) -> str:
    return (s or "").strip()


def parse_date(value: str) -> str:
    s = normalize_str(value)[:10]
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return s
    if re.fullmatch(r"\d{2}/\d{2}/\d{4}", s):
        d, m, y = s.split("/")
        return f"{y}-{m}-{d}"
    return ""


def load_municipalities(path: Path):
    if not path:
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return {}
    idx = {}
    for m in data:
        idx[m.get("name", "").lower()] = m
        for alias in m.get("aliases", []) or []:
            idx[alias.lower()] = m
    return idx


def choose_csv_from_zip(zf: zipfile.ZipFile) -> zipfile.ZipInfo:
    csv_infos = [zi for zi in zf.infolist() if zi.filename.lower().endswith(".csv")]
    if not csv_infos:
        raise SystemExit("Geen CSV in zip gevonden.")
    # heuristiek: kies het bestand met 'ent' of 'enterprise' in naam, anders eerste
    for zi in csv_infos:
        name = zi.filename.lower()
        if "ent" in name or "ondernem" in name:
            return zi
    return csv_infos[0]


def sniff_dialect(sample: bytes):
    try:
        return csv.Sniffer().sniff(sample.decode("latin-1"))
    except Exception:
        return csv.excel


def pick_status_date(row, headers):
    for key in headers:
        v = row.get(key, "")
        if not v:
            continue
        lk = key.lower()
        if "dat" in lk:
            d = parse_date(v)
            if d:
                return d
    return date.today().isoformat()


def detect_bankruptcy(row):
    for k, v in row.items():
        if not v:
            continue
        if "faill" in v.lower():
            return True
    return False


def map_row(row, headers, muni_idx, source_ref):
    enterprise_number = normalize_str(
        row.get("enterprise_number")
        or row.get("ondernemingsnummer")
        or row.get("ondernemingsnr")
        or row.get("kbo nummer")
        or row.get("kbo_nummer")
        or row.get("vat")
        or row.get("btw")
    )

    name = normalize_str(
        row.get("denomination")
        or row.get("naam")
        or row.get("benaming")
        or row.get("companyname")
        or row.get("societe")
    )

    muni = normalize_str(row.get("municipality") or row.get("gemeente") or row.get("locality"))
    postal = normalize_str(row.get("postcode") or row.get("postal_code") or row.get("zip"))
    street = normalize_str(row.get("street") or row.get("straat") or row.get("address"))

    matched_muni = muni_idx.get(muni.lower()) if muni else None

    out = {
        "id": "",
        "date": pick_status_date(row, headers),
        "municipality": matched_muni["name"] if matched_muni else muni,
        "province": matched_muni.get("province") if matched_muni else "",
        "company_name": name or enterprise_number or "Onbekend",
        "enterprise_number": enterprise_number,
        "street": street,
        "postal_code": postal,
        "court": "",
        "source_ref": source_ref,
        "source_url": "",
    }
    out["id"] = f"{out['date']}-{enterprise_number or muni or name or 'entry'}"
    return out


def main():
    ap = argparse.ArgumentParser(description="Converteer KBO daily zip naar faillissementen.json")
    ap.add_argument("zipfile", type=Path, help="Pad naar KBO daily zip")
    ap.add_argument("output", type=Path, help="Output JSON")
    ap.add_argument("--muni", type=Path, default=None, help="Optioneel: municipalities.json voor mapping")
    args = ap.parse_args()

    muni_idx = load_municipalities(args.muni)

    with zipfile.ZipFile(args.zipfile, "r") as zf:
        csv_info = choose_csv_from_zip(zf)
        raw = zf.read(csv_info)
        buf = io.BytesIO(raw)
        sample = buf.read(4000)
        buf.seek(0)
        dialect = sniff_dialect(sample)
        reader = csv.DictReader(io.TextIOWrapper(buf, encoding="latin-1"), dialect=dialect)
        headers = [h or "" for h in reader.fieldnames or []]

        rows = []
        for row in reader:
            if not detect_bankruptcy(row):
                continue
            mapped = map_row(row, headers, muni_idx, f"KBO daily {args.zipfile.name}")
            rows.append(mapped)

    with args.output.open("w", encoding="utf-8") as out:
        json.dump(rows, out, ensure_ascii=False, indent=2)
        out.write("\n")

    print(f"Wrote {len(rows)} records to {args.output}")


if __name__ == "__main__":
    sys.exit(main())

