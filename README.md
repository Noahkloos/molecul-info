# ⚗️ Molecuul-uitlegger

Vul een **stofnaam** (Nederlands of Engels), **CAS-nummer** of **SMILES** in. De app laat dan het volgende zien:

- de **2D-structuur** en berekende eigenschappen (RDKit),
- **gemeten fysische eigenschappen** zoals smeltpunt, kookpunt, dichtheid, oplosbaarheid en pKa, elk met de **oorspronkelijke bron** (via PubChem),
- de **H- en P-zinnen**, het signaalwoord en de pictogrammen (GHS), waarbij de wettelijk bindende EU-indeling voorrang krijgt,
- een **AI-uitleg op niveau** (leek, scholier, student of expert) via de Gemini API, met bronverwijzingen,
- een ingevulde **Hazardous Substance Risk Assessment** als Word-document (.docx), die je in je labverslag kunt plakken (tabblad "📋 Risk assessment").

### Risk assessment voor je labverslag

In het tabblad **📋 Risk assessment** stelt de app het formulier voor op basis van de PubChem-gegevens:

- de pictogrammen en het signaalwoord,
- het gevarentype en de aggregatietoestand bij 20 °C,
- de H- en P-zinnen,
- de blootstellingsroutes,
- de grenswaarden (TLV, MAK, REL, PEL),
- de technische en hygiënemaatregelen,
- de PBM met EN-norm,
- EHBO, brandbestrijding, opslag, morsen en afval,
- de fysische kerngegevens,
- een risicoscore (ernst × kans).

Jij vult de proefgegevens aan (locatie, hoeveelheid, taak, leverancier, naam), controleert de voorstellen en downloadt het .docx-bestand. Daarna open je het in Word, kopieer je alles en plak je het in je verslag. Het voorstel komt uit vaste regels en niet uit AI, zodat het controleerbaar is. Controleer het altijd met het SDS van de leverancier.

## Snel starten (Windows / PowerShell)

```powershell
# 1. Virtuele omgeving maken en packages installeren
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# 2. (Optioneel, voor de AI-uitleg) API-sleutel instellen
copy .env.example .env      # en vul GEMINI_API_KEY in (gratis via https://aistudio.google.com/apikey)

# 3. App starten
.\.venv\Scripts\python.exe -m streamlit run app.py
```

> **Probleem met een te lang pad?** Krijg je de melding `DLL load failed ... The filename or extension is too long`, dan staat het project in een map met een te lang pad. Zet de projectmap of de `.venv` dan op een korter pad, bijvoorbeeld `C:\projecten\molecuul-uitlegger`.

## Scripts (user stories)

| Bestand | Story | Uitvoeren |
|---|---|---|
| `scripts/us1_smiles_naar_molmassa.py` | US: SMILES → molmassa met RDKit | `python scripts/us1_smiles_naar_molmassa.py "CC(=O)Oc1ccccc1C(=O)O"` |
| `scripts/ls_gemini_test.py` | LS: RDKit-data → Gemini, uitleg op niveau | `python scripts/ls_gemini_test.py --stof caffeine --alle-niveaus` |
| `tests/test_kern.py` | Automatische tests (offline) | `python -m unittest discover tests -v` |

Handige opties van `ls_gemini_test.py`:

- `--droog` toont alleen de prompt en roept de API niet aan,
- `--test-fouten` laat de foutafhandeling zien,
- `--niveau leek|scholier|student|expert` kiest het niveau van de uitleg.

## Architectuur

```
invoer (naam / CAS / SMILES)
        │
        ▼
 rapport.py ──► pubchem.py ──► PubChem PUG REST/View  (CID, meetwaarden + bron, GHS)
        │                       ghs.py ──► data/ghscode_10.txt (officiële H/P-teksten)
        └─────► chem.py ──────► RDKit (formule, molmassa, descriptors, structuurtekening)
        │
        ▼
 MolecuulRapport ──► app.py (Streamlit-weergave)
        │
        ├──► uitleg.py ──► Gemini API (systeeminstructie + JSON-data + niveau)
        └──► risico.py (regels) ──► document.py ──► Word (.docx) risk assessment
             veiligheid.py ──► PubChem "Safety and Hazards" (grenswaarden, EHBO, opslag, morsen)
```

**Uitgangspunt:** alle feiten komen uit RDKit en PubChem. De AI zorgt alleen voor de formulering. Zonder API-sleutel werkt alles behalve de AI-uitleg.

## Documentatie

- [docs/onderzoeksverslag.md](docs/onderzoeksverslag.md): onderzoek, promptontwerp, keuze voor Gemini, ethiek en bronnen
- [docs/leeruitkomsten.md](docs/leeruitkomsten.md): criteria per story en leeruitkomsten met bewijs
- [docs/testresultaten/](docs/testresultaten/): testuitvoer en Gemini-antwoorden

## Configuratie (`.env`)

| Variabele | Betekenis | Standaard |
|---|---|---|
| `GEMINI_API_KEY` | API-sleutel uit Google AI Studio | (geen) |
| `GEMINI_MODEL` | Gemini-model | `gemini-3.8-flash` |
| `GEMINI_FALLBACK_MODELS` | Reservemodellen bij overbelasting (503) of een vol quotum (429), gescheiden door komma's | `gemini-3.7-flash,gemini-3.6-flash,gemini-3.5-flash,gemini-3.1-flash-lite` |

## Melding "HTTP 503" of "dagquotum op"?

Dit ligt niet aan de app. De gratis Gemini-laag staat per model maar **5 verzoeken per minuut en 20 per dag** toe, en Google geeft gratis gebruikers bij drukte lagere prioriteit (HTTP 503). De app doet daarom het volgende:

- bij een fout probeert ze automatisch de reservemodellen,
- een dagquotum herkent ze, en ze laat zien wanneer het weer vrijkomt,
- een uitleg die al gemaakt is, bewaart ze in `data/uitleg_cache/`, zodat die geen nieuw verzoek kost.

Bij 503 probeer je het over een paar minuten opnieuw. Bij een dagquotum probeer je het de volgende dag opnieuw, of gebruik je een betaalde sleutel. Alle gegevens behalve de AI-uitleg blijven altijd beschikbaar.

## Disclaimer

Deze app is een leermiddel. Gebruik voor werken met chemicaliën altijd het actuele veiligheidsinformatieblad (SDS) van de leverancier.
