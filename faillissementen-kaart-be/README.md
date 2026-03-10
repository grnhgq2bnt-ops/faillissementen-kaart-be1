# Faillissementen per gemeente (BE) – Kaarttool (MVP)

Statische webapp (PWA) die faillissementen per Belgische gemeente op een kaart visualiseert, bedoeld als signaaltool voor vastgoedkantoren.

## Runnen (lokaal)

Service workers werken enkel via `http://` of `https://` (niet via `file://`).

```bash
cd faillissementen-kaart-be
python3 -m http.server 5173
```

Open daarna `http://localhost:5173`.

## Data

De app probeert eerst echte data te laden, en valt anders terug op sample data:

- `data/municipalities.json` (fallback: `data/municipalities.sample.json`)
- `data/faillissementen.json` (fallback: `data/faillissementen.sample.json`)

### CSV importeren naar JSON

Zet een CSV om naar `data/faillissementen.json`:

```bash
python3 scripts/import_faillissementen.py data/raw/faillissementen.csv data/faillissementen.json
```

Verplichte CSV kolommen:

- `date` (YYYY-MM-DD)
- `municipality` (gemeentenaam, bv. `Antwerpen`)
- `company_name`

Optionele kolommen:

- `enterprise_number`
- `postal_code`
- `street`
- `province`
- `court`
- `source_ref`
- `source_url`

### Handmatig uploaden in de webapp

Gebruik de knop “Upload CSV/JSON” bovenaan in de app:

- CSV: header met minstens `date`, `municipality`, `company_name` (optioneel: `province`, `enterprise_number`, `street`, `postal_code`, `court`, `source_ref`, `source_url`). Zowel `;` als `,` delimiters werken.
- JSON: array van objecten in hetzelfde schema als hierboven.

### Gemeentenlijst (optioneel, maar aanbevolen)

Voor volledige dekking zet je best een volledige gemeentenlijst met coordinaten klaar als `data/municipalities.json`.

CSV naar JSON:

```bash
python3 scripts/import_municipalities.py data/raw/gemeenten.csv data/municipalities.json
```

Verplichte CSV kolommen:

- `name`
- `lat`
- `lng`

Optionele kolommen:

- `id`
- `province`
- `region`
- `aliases` (bv. `Bruxelles|Brussels`)

## Volgende stap (echte dekking)

Voor “alle faillissementen in België per gemeente” heb je een consistente bron nodig (bv. Belgisch Staatsblad en/of KBO/BCE-extract) én een mapping naar gemeenten (bij voorkeur NIS-code of gemeentenaam + postcode). Deze MVP is zo opgezet dat je enkel `data/*.json` hoeft te vervangen.

## Automatisch bijwerken (GitHub Actions)

Deze repo bevat een workflow `.github/workflows/update-faillissementen.yml` die elke nacht (02:00 UTC) faillissementen ophaalt via Staatsbladmonitor en `data/faillissementen.json` bijwerkt.

In te stellen secrets (GitHub repo → Settings → Secrets → Actions):
- `SBM_APIKEY`: je Staatsbladmonitor API key.

Andere inputs:
- VAT-lijst: `data/raw/vats.txt` (één ondernemingsnummer per regel). Pas dit bestand aan naar je eigen lijst.
- Account id staat als env in de workflow (`SBM_ACCOUNTID`, nu 5113819).

Netlify: configureer de site zodat deploys automatisch gebeuren bij wijzigingen op `main` (build command leeg, publish directory `faillissementen-kaart-be`). Zodra de workflow pusht, triggert Netlify een nieuwe deploy en de app toont de nieuwste data.
