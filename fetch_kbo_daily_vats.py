#!/usr/bin/env python3
"""
Download de KBO daily open-data zip (probeert laatste 3 dagen) en extraheer
ondernemingsnummers waar een veld 'faill' bevat. Schrijft unieke VAT's naar
data/raw/vats.txt (overschrijft).
"""

import csv
import datetime as dt
import io
import os
import sys
import urllib.request
import zipfile

BASE_URL = "https://kbopub.economie.fgov.be/kbo-open-data/daily/KBO_PUBLIC_DAILY_{date}.zip"
OUT_PATH = os.path.join("data", "raw", "vats.txt")


def fetch_zip(date_str: str) -> bytes:
    url = BASE_URL.format(date=date_str)
    with urllib.request.urlopen(url, timeout=30) as resp:
        if resp.status != 200:
            raise RuntimeError(f"HTTP {resp.status}")
        return resp.read()


def find_csv(raw: bytes) -> io.TextIOBase:
    zf = zipfile.ZipFile(io.BytesIO(raw))
    for name in zf.namelist():
        if name.lower().endswith(".csv"):
            return io.TextIOWrapper(zf.open(name), encoding="utf-8", newline="")
    raise RuntimeError("Geen CSV in zip")


def extract_vats(fh: io.TextIOBase) -> set[str]:
    reader = csv.DictReader(fh, delimiter=";")
    vats = set()
    for row in reader:
        values = " ".join((v or "") for v in row.values()).lower()
        if "faill" not in values:
            continue
        vat = (
            row.get("ondernemingsnummer")
            or row.get("enterprise_number")
            or row.get("ondernemingsnr")
            or row.get("kbo_nr")
            or ""
        ).replace(" ", "")
        if vat:
            vats.add(vat)
    return vats


def try_dates(days: int = 3) -> set[str]:
    today = dt.date.today()
    errors = []
    for delta in range(days):
        date_str = (today - dt.timedelta(days=delta)).strftime("%Y%m%d")
        try:
            raw = fetch_zip(date_str)
            csvfh = find_csv(raw)
            vats = extract_vats(csvfh)
            if vats:
                return vats
        except Exception as exc:  # noqa: BLE001
            errors.append((date_str, str(exc)))
    raise RuntimeError(f"Geen KBO daily zip verwerkt: {errors}")


def main() -> int:
    try:
        vats = try_dates()
    except Exception as exc:  # noqa: BLE001
        print(f"[warn] kon KBO daily niet verwerken: {exc}", file=sys.stderr)
        return 0

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        for vat in sorted(vats):
            f.write(vat + "\n")
    print(f"[info] geschreven {len(vats)} VATs naar {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

