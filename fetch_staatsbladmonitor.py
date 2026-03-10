#!/usr/bin/env python3

"""
Fetch faillissementsdata via Staatsbladmonitor API voor een lijst ondernemingsnummers (VAT).

Gebruik:
  python3 scripts/fetch_staatsbladmonitor.py \
    --vat-file data/raw/vat_list.txt \
    --apikey YOUR_API_KEY \
    --accountid YOUR_ACCOUNT_ID \
    --output data/faillissementen.json

Notes:
- De API werkt per ondernemingsnummer; deze tool loopt een lijst af.
- Rate-limit: staatsbladmonitor gratis tier is 100 calls/dag. Houd je lijst kort of verhoog de slaap.
- Geen extra dependencies; gebruikt alleen standaardbibliotheek.
"""

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple


def read_vats(vat_file: Path, vat_inline: List[str]) -> List[str]:
    vats: List[str] = []
    if vat_file:
        text = vat_file.read_text(encoding="utf-8")
        for token in text.replace(",", "\n").replace(";", "\n").split():
            vats.append(token.strip())
    for v in vat_inline:
        vats.append(v.strip())
    # Basic normalization: strip spaces
    out = []
    for v in vats:
        if not v:
            continue
        out.append(v.replace(" ", ""))
    # preserve order, drop dups
    seen: Set[str] = set()
    uniq: List[str] = []
    for v in out:
        if v in seen:
            continue
        seen.add(v)
        uniq.append(v)
    return uniq


def fetch_vat(vat: str, apikey: str, accountid: str, lang: str, est: str, fin: str, timeout: float = 10.0) -> Dict:
    params = {
        "vat": vat,
        "lang": lang,
        "est": est,
        "fin": fin,
        "apikey": apikey,
        "accountid": accountid,
    }
    url = "https://www.staatsbladmonitor.be/sbmapi.json?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read()
        return json.loads(data.decode("utf-8"))


def iter_strings(obj: Any) -> Iterable[str]:
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from iter_strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from iter_strings(v)


def find_first(obj: Any, keys: Tuple[str, ...]) -> Optional[Any]:
    if isinstance(obj, dict):
        for k in keys:
            if k in obj:
                return obj[k]
        for v in obj.values():
            found = find_first(v, keys)
            if found is not None:
                return found
    if isinstance(obj, list):
        for v in obj:
            found = find_first(v, keys)
            if found is not None:
                return found
    return None


def extract_address(obj: Any) -> Tuple[str, str]:
    muni = find_first(obj, ("municipality", "gemeente", "locality", "city"))
    postal = find_first(obj, ("postal_code", "postcode", "zip", "postalcode"))
    return (str(muni) if muni else "", str(postal) if postal else "")


def extract_date(obj: Any) -> str:
    cand = find_first(
        obj,
        (
            "publicationDate",
            "decisionDate",
            "date",
            "openingDate",
            "datum",
        ),
    )
    if cand:
        s = str(cand)[:10]
        # Normalize dd/mm/yyyy → yyyy-mm-dd
        if len(s) == 10 and s[2] == "/" and s[5] == "/":
            dd, mm, yyyy = s.split("/")
            return f"{yyyy}-{mm}-{dd}"
        return s
    return ""


def is_bankruptcy(obj: Any) -> bool:
    for s in iter_strings(obj):
        sl = s.lower()
        if "faill" in sl or "bankrupt" in sl or "faillite" in sl:
            return True
    return False


def normalize_record(payload: Dict, vat: str, source_ref: str) -> Optional[Dict]:
    if not is_bankruptcy(payload):
        return None

    name = find_first(payload, ("denomination", "name", "naam", "benaming", "companyname"))
    date = extract_date(payload)
    muni, postal = extract_address(payload)

    rec = {
        "id": f"{date or 'unknown'}-{vat}",
        "date": date,
        "municipality": muni,
        "province": "",
        "company_name": name or vat,
        "enterprise_number": vat,
        "street": "",
        "postal_code": postal,
        "court": "",
        "source_ref": source_ref,
        "source_url": "",
    }
    return rec


def main() -> int:
    ap = argparse.ArgumentParser(description="Fetch faillissementen via Staatsbladmonitor API per VAT.")
    ap.add_argument("--vat-file", type=Path, help="Bestand met VAT-nummers (1 per regel, of gescheiden door , ; spaties)")
    ap.add_argument("--vat", action="append", default=[], help="Extra VAT-nummers (meerdere --vat toegestaan)")
    ap.add_argument("--apikey", required=True, help="Staatsbladmonitor API key")
    ap.add_argument("--accountid", required=True, help="Staatsbladmonitor account id")
    ap.add_argument("--lang", default="nl", help="Taalparam (nl/fr/en)")
    ap.add_argument("--est", default="0", help="est parameter (0/1)")
    ap.add_argument("--fin", default="1", help="fin parameter (0/1)")
    ap.add_argument("--sleep", type=float, default=0.6, help="Slaap tussen calls (s) om rate-limit te sparen")
    ap.add_argument("--output", type=Path, required=True, help="Doel JSON bestand voor de webapp")
    args = ap.parse_args()

    vats = read_vats(args.vat_file, args.vat)
    if not vats:
        print("Geen VAT-nummers opgegeven (--vat-file of --vat).", file=sys.stderr)
        return 1

    out: List[Dict] = []
    seen_ids: Set[str] = set()
    for i, vat in enumerate(vats, start=1):
        try:
            payload = fetch_vat(vat, args.apikey, args.accountid, args.lang, args.est, args.fin)
            rec = normalize_record(payload, vat, f"Staatsbladmonitor {vat}")
            if rec and rec["id"] not in seen_ids:
                seen_ids.add(rec["id"])
                out.append(rec)
        except Exception as e:
            print(f"[{i}/{len(vats)}] {vat}: fout {e}", file=sys.stderr)
        time.sleep(args.sleep)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"Geschreven: {len(out)} records → {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

