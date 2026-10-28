"""Gegevens ophalen uit PubChem (NCBI / National Institutes of Health).

PubChem is een openbare, gratis database die gemeten eigenschappen en
veiligheidsinformatie verzamelt uit honderden bronnen (o.a. ECHA, NIOSH,
HSDB, NITE). Elke waarde die we tonen bewaart de oorspronkelijke bron + URL.

Gebruikte API's (documentatie):
  PUG REST : https://pubchem.ncbi.nlm.nih.gov/docs/pug-rest
  PUG View : https://pubchem.ncbi.nlm.nih.gov/docs/pug-view
Gebruiksregels: max. 5 verzoeken per seconde, zie
  https://pubchem.ncbi.nlm.nih.gov/docs/programmatic-access
"""

import re
from dataclasses import dataclass, field
from urllib.parse import quote

import requests

from . import ghs

PUG_REST = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
PUG_VIEW = "https://pubchem.ncbi.nlm.nih.gov/rest/pug_view/data/compound"
TIMEOUT = 25

_sessie = requests.Session()
_sessie.headers["User-Agent"] = "Molecuul-uitlegger/1.0 (studieproject)"


class PubChemFout(RuntimeError):
    """Verbindings- of serverprobleem met PubChem."""


class NietGevondenFout(LookupError):
    """De stof staat niet in PubChem."""


@dataclass
class Bron:
    naam: str
    url: str | None = None
    omschrijving: str | None = None


@dataclass
class Meetwaarde:
    waarde: str
    bron: Bron


@dataclass
class GevarenZin:
    code: str
    tekst: str
    percentage: float | None = None  # aandeel meldingen (alleen bij ECHA-gegevens)
    klasse: str | None = None


@dataclass
class GHSClassificatie:
    bron: Bron
    signaalwoord: str | None = None
    pictogrammen: list[str] = field(default_factory=list)  # bijv. ["GHS07"]
    h_zinnen: list[GevarenZin] = field(default_factory=list)
    p_zinnen: list[GevarenZin] = field(default_factory=list)
    opmerkingen: list[str] = field(default_factory=list)


# PubChem-kopje -> (Nederlands label, groep), in de volgorde waarin we ze tonen.
# Bewust weggelaten: analytische gegevens zonder fysische betekenis voor de gebruiker
# (Kovats-retentie-index, Collision Cross Section, Caco2-permeabiliteit).
FYSISCHE_KOPPEN = {
    "Physical Description": ("Uiterlijk", "Uiterlijk"),
    "Color/Form": ("Kleur / vorm", "Uiterlijk"),
    "Odor": ("Geur", "Uiterlijk"),
    "Taste": ("Smaak", "Uiterlijk"),
    "Odor Threshold": ("Geurdrempel", "Uiterlijk"),
    "Melting Point": ("Smeltpunt", "Faseovergangen"),
    "Boiling Point": ("Kookpunt", "Faseovergangen"),
    "Heat of Vaporization": ("Verdampingswarmte", "Faseovergangen"),
    "Decomposition": ("Ontleding", "Faseovergangen"),
    "Density": ("Dichtheid", "Dichtheid en damp"),
    "Vapor Density": ("Dampdichtheid (lucht = 1)", "Dichtheid en damp"),
    "Vapor Pressure": ("Dampspanning", "Dichtheid en damp"),
    "Relative Evaporation Rate": ("Relatieve verdampingssnelheid", "Dichtheid en damp"),
    "Henry's Law Constant": ("Henry-constante", "Dichtheid en damp"),
    "Solubility": ("Oplosbaarheid", "Oplosbaarheid en zuur-base"),
    "LogP": ("logP (gemeten)", "Oplosbaarheid en zuur-base"),
    "LogS": ("logS (gemeten)", "Oplosbaarheid en zuur-base"),
    "Dissociation Constants": ("pKa", "Oplosbaarheid en zuur-base"),
    "pH": ("pH (van een oplossing)", "Oplosbaarheid en zuur-base"),
    "Flash Point": ("Vlampunt", "Brand en stabiliteit"),
    "Autoignition Temperature": ("Zelfontbrandingstemperatuur", "Brand en stabiliteit"),
    "Explosive Limits and Potential": ("Explosiegrenzen", "Brand en stabiliteit"),
    "Heat of Combustion": ("Verbrandingswarmte", "Brand en stabiliteit"),
    "Stability/Shelf Life": ("Stabiliteit / houdbaarheid", "Brand en stabiliteit"),
    "Corrosivity": ("Corrosiviteit", "Brand en stabiliteit"),
    "Viscosity": ("Viscositeit", "Overige fysische eigenschappen"),
    "Surface Tension": ("Oppervlaktespanning", "Overige fysische eigenschappen"),
    "Refractive Index": ("Brekingsindex", "Overige fysische eigenschappen"),
    "Optical Rotation": ("Optische rotatie", "Overige fysische eigenschappen"),
    "Ionization Potential": ("Ionisatiepotentiaal", "Overige fysische eigenschappen"),
}
LABEL_NAAR_GROEP = {label: groep for label, groep in FYSISCHE_KOPPEN.values()}
BESCHRIJVENDE_EIGENSCHAPPEN = {
    "Uiterlijk", "Kleur / vorm", "Geur", "Smaak", "Ontleding", "Stabiliteit / houdbaarheid", "Corrosiviteit",
}
# Secties in PubChem waar we eigenschappen uit halen (explosiegrenzen staan onder veiligheid).
EIGENSCHAP_SECTIES = ("Experimental Properties", "Explosive Limits and Potential")


def compound_url(cid: int) -> str:
    return f"https://pubchem.ncbi.nlm.nih.gov/compound/{cid}"


# --------------------------------------------------------------------------- #
# HTTP-hulpfuncties
# --------------------------------------------------------------------------- #
def _vraag(methode: str, url: str, **kwargs) -> dict:
    try:
        antwoord = _sessie.request(methode, url, timeout=TIMEOUT, **kwargs)
    except requests.Timeout as fout:
        raise PubChemFout("PubChem reageert niet op tijd. Probeer het later opnieuw.") from fout
    except requests.ConnectionError as fout:
        raise PubChemFout("Geen verbinding met PubChem. Controleer je internetverbinding.") from fout
    if antwoord.status_code == 404:
        raise NietGevondenFout("Stof niet gevonden in PubChem.")
    if antwoord.status_code in (429, 503):
        raise PubChemFout("PubChem is tijdelijk overbelast. Wacht even en probeer opnieuw.")
    if not antwoord.ok:
        raise PubChemFout(f"PubChem gaf een fout (HTTP {antwoord.status_code}).")
    try:
        return antwoord.json()
    except ValueError as fout:
        raise PubChemFout("PubChem stuurde een onleesbaar antwoord.") from fout


def _eerste_cid(data: dict) -> int:
    cids = [c for c in data.get("IdentifierList", {}).get("CID", []) if c]
    if not cids:
        raise NietGevondenFout("Stof niet gevonden in PubChem.")
    return int(cids[0])


# --------------------------------------------------------------------------- #
# Zoeken
# --------------------------------------------------------------------------- #
def cid_via_naam(naam: str) -> int:
    return _eerste_cid(_vraag("GET", f"{PUG_REST}/compound/name/{quote(naam.strip(), safe='')}/cids/JSON"))


def cid_via_smiles(smiles: str) -> int:
    # POST zodat tekens als '#', '/' en '\' in de SMILES geen URL-problemen geven.
    return _eerste_cid(_vraag("POST", f"{PUG_REST}/compound/smiles/cids/JSON", data={"smiles": smiles}))


def basisgegevens(cid: int) -> dict:
    velden = "Title,IUPACName,MolecularFormula,MolecularWeight,SMILES,InChIKey,XLogP"
    data = _vraag("GET", f"{PUG_REST}/compound/cid/{cid}/property/{velden}/JSON")
    rij = data["PropertyTable"]["Properties"][0]
    cas = _cas_nummer(cid)
    return {
        "cid": cid,
        "naam": rij.get("Title"),
        "iupac_naam": rij.get("IUPACName"),
        "formule": rij.get("MolecularFormula"),
        "molmassa_g_per_mol": float(rij["MolecularWeight"]) if rij.get("MolecularWeight") else None,
        "smiles": rij.get("SMILES"),
        "inchikey": rij.get("InChIKey"),
        "xlogp": rij.get("XLogP"),
        "cas": cas,
        "url": compound_url(cid),
    }


def _cas_nummer(cid: int) -> str | None:
    try:
        data = _vraag("GET", f"{PUG_REST}/compound/cid/{cid}/synonyms/JSON")
    except (PubChemFout, NietGevondenFout):
        return None
    synoniemen = data.get("InformationList", {}).get("Information", [{}])[0].get("Synonym", [])
    for s in synoniemen:
        if re.fullmatch(r"\d{2,7}-\d{2}-\d", s):
            return s
    return None


# --------------------------------------------------------------------------- #
# PUG View: secties met bronvermelding
# --------------------------------------------------------------------------- #
def _pug_view(cid: int, kop: str) -> dict | None:
    try:
        return _vraag("GET", f"{PUG_VIEW}/{cid}/JSON", params={"heading": kop})["Record"]
    except NietGevondenFout:
        return None  # stof heeft deze sectie niet


def _bronnen(record: dict) -> dict[int, Bron]:
    return {
        r["ReferenceNumber"]: Bron(naam=r.get("SourceName", "Onbekend"), url=r.get("URL"), omschrijving=r.get("Name"))
        for r in record.get("Reference", [])
    }


def _secties(sectie: dict):
    """Loopt recursief door alle subsecties."""
    for sub in sectie.get("Section", []):
        yield sub
        yield from _secties(sub)


def _waarde_als_tekst(waarde: dict) -> str | None:
    teksten = [m.get("String", "").strip() for m in waarde.get("StringWithMarkup", [])]
    teksten = [t for t in teksten if t]
    if teksten:
        return "; ".join(teksten)
    if "Number" in waarde:
        getallen = ", ".join(f"{n:g}" for n in waarde["Number"][:3])
        return f"{getallen} {waarde.get('Unit', '')}".strip()
    return None


# Bronnen met redactionele controle (peer review) eerst. CAMEO/NTP-gegevens gaan
# soms over oplossingen of technische kwaliteit (bijv. "spent sulfuric acid").
GECONTROLEERDE_BRONNEN = ("Hazardous Substances Data Bank", "International Chemical Safety Cards")


def _meetbron_prioriteit(bron: Bron) -> int:
    if any(naam in bron.naam for naam in GECONTROLEERDE_BRONNEN):
        return 0
    if "DrugBank" in bron.naam or "ECHA" in bron.naam or "European Chemicals" in bron.naam:
        return 1
    return 2


def fysische_eigenschappen(cid: int, max_per_eigenschap: int = 3) -> dict[str, list[Meetwaarde]]:
    """Label -> meetwaarden (beste bronnen eerst). Volgorde en groepen: zie FYSISCHE_KOPPEN."""
    resultaat: dict[str, list[Meetwaarde]] = {}
    for kop in EIGENSCHAP_SECTIES:
        record = _pug_view(cid, kop)
        if record:
            _verzamel_meetwaarden(record, max_per_eigenschap, resultaat)
    labels = [label for label, _ in FYSISCHE_KOPPEN.values()]
    return {label: resultaat[label] for label in labels if label in resultaat}


def _verzamel_meetwaarden(record: dict, max_per_eigenschap: int, resultaat: dict[str, list[Meetwaarde]]) -> None:
    bronnen = _bronnen(record)
    for sectie in _secties(record):
        label, _ = FYSISCHE_KOPPEN.get(sectie.get("TOCHeading"), (None, None))
        if not label:
            continue
        waarden: list[Meetwaarde] = []
        gezien = set()
        for info in sectie.get("Information", []):
            tekst = _waarde_als_tekst(info.get("Value", {}))
            # Verwijzingen naar tabellen ("Table: ... [Table#229]") bevatten geen waarde.
            if not tekst or tekst.lower() in gezien or len(tekst) > 300 or "[Table#" in tekst:
                continue
            gezien.add(tekst.lower())
            waarden.append(Meetwaarde(tekst, bronnen.get(info.get("ReferenceNumber"), Bron("PubChem"))))
        # Beste bron eerst; bij meetbare eigenschappen gaan waarden mét getal voor beschrijvingen
        # (bijv. "3.3-19 vol%" voor "Vapor may explode ..."). Sorteren is stabiel.
        numeriek = label not in BESCHRIJVENDE_EIGENSCHAPPEN
        waarden.sort(key=lambda m: (_meetbron_prioriteit(m.bron), numeriek and not re.search(r"\d", m.waarde)))
        if waarden:
            resultaat[label] = waarden[:max_per_eigenschap]


# Voorbeelden: "H302 (95.6%): Harmful if swallowed [Warning Acute toxicity, oral]"
#              "H225 (> 99.9%): Highly Flammable liquid and vapor [Danger Flammable liquids]"
#              "H225: Highly Flammable liquid and vapor [Danger Flammable liquids]"
_H_PATROON = re.compile(
    r"^(H\d{3}(?:\+H\d{3})*)\s*(?:\(\s*[<>]?\s*([\d.]+)\s*%\))?\s*:\s*(.*?)\s*(?:\[(.*)\])?$"
)


def _parse_h_zin(tekst: str) -> GevarenZin | None:
    m = _H_PATROON.match(tekst.strip())
    if not m:
        return None
    code, perc, omschrijving, klasse = m.groups()
    return GevarenZin(
        code=code,
        tekst=ghs.tekst_voor(code) or omschrijving,
        percentage=float(perc) if perc else None,
        klasse=klasse,
    )


def bron_prioriteit(bron: Bron) -> int:
    """Lager = betrouwbaarder voor gebruik in Nederland/de EU.

    0: geharmoniseerde EU-indeling (CLP-verordening, bijlage VI) - wettelijk bindend
    1: ECHA C&L Inventory - zelfindelingen gemeld door bedrijven in de EU
    2: overige (o.a. NITE Japan, OSHA, leveranciers)
    """
    if "1272/2008" in bron.naam:
        return 0
    if "ECHA" in bron.naam or "European Chemicals" in bron.naam:
        return 1
    return 2


def ghs_classificaties(cid: int) -> list[GHSClassificatie]:
    """Alle GHS-indelingen in PubChem, per bron, gesorteerd op bron_prioriteit."""
    record = _pug_view(cid, "GHS Classification")
    if not record:
        return []
    bronnen = _bronnen(record)
    per_bron: dict[int, GHSClassificatie] = {}
    for sectie in _secties(record):
        if sectie.get("TOCHeading") != "GHS Classification":
            continue
        for info in sectie.get("Information", []):
            ref = info.get("ReferenceNumber")
            indeling = per_bron.setdefault(ref, GHSClassificatie(bron=bronnen.get(ref, Bron("PubChem"))))
            naam = info.get("Name", "")
            waarde = info.get("Value", {})
            regels = [m.get("String", "") for m in waarde.get("StringWithMarkup", [])]
            if naam == "Pictogram(s)":
                for m in waarde.get("StringWithMarkup", []):
                    for markup in m.get("Markup", []):
                        code = re.search(r"GHS0\d", markup.get("URL", ""))
                        if code and code.group() not in indeling.pictogrammen:
                            indeling.pictogrammen.append(code.group())
            elif naam == "Signal":
                indeling.signaalwoord = regels[0].strip() if regels else None
            elif naam == "GHS Hazard Statements":
                for regel in regels:
                    zin = _parse_h_zin(regel)
                    if zin:
                        indeling.h_zinnen.append(zin)
                    elif regel.strip():
                        indeling.opmerkingen.append(regel.strip())
            elif naam == "Precautionary Statement Codes":
                for code in ghs.splits_p_codes(" ".join(regels)):
                    indeling.p_zinnen.append(GevarenZin(code=code, tekst=ghs.tekst_voor(code) or "(tekst onbekend)"))
            elif naam in ("Note", "ECHA C&L Notifications Summary"):
                indeling.opmerkingen.extend(r.strip() for r in regels if r.strip())

    indelingen = [i for i in per_bron.values() if i.h_zinnen or i.p_zinnen or i.signaalwoord]
    indelingen.sort(key=lambda i: bron_prioriteit(i.bron))  # stabiel: PubChem-volgorde blijft binnen een groep
    return indelingen
