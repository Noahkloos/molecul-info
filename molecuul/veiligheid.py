"""Veiligheidsgegevens uit PubChem voor de risicobeoordeling (Hazardous Substance Risk Assessment).

Eén PUG View-verzoek naar de sectie "Safety and Hazards" levert o.a. blootstellingsgrenzen,
EHBO, preventie per blootstellingsroute, opslag, morsen en brandbestrijding. De kortste en
best gecontroleerde teksten komen meestal van de ILO-WHO International Chemical Safety Cards
(ICSC); die staan daarom bovenaan (zie pubchem._meetbron_prioriteit).
"""

import re

from . import pubchem
from .pubchem import Bron, Meetwaarde

# (PubChem-kopje, naam van het informatie-item of None) -> sleutel in het resultaat.
# Een item met een specifieke naam gaat voor op het kopje in het algemeen.
VELDEN = {
    # Blootstellingsgrenzen
    ("Threshold Limit Values (TLV)", None): "grens_tlv",
    ("Permissible Exposure Limit (PEL)", None): "grens_pel",
    ("Recommended Exposure Limit (REL)", None): "grens_rel",
    ("Occupational Exposure Limits (OEL)", None): "grens_oel",
    ("Immediately Dangerous to Life or Health (IDLH)", None): "grens_idlh",
    ("Lower Explosive Limit (LEL)", None): "lel",
    ("Upper Explosive Limit (UEL)", None): "uel",
    # Gezondheid en blootstelling
    ("Inhalation Risk", None): "inademingsrisico",
    ("Effects of Short Term Exposure", None): "effecten_kort",
    ("Effects of Long Term Exposure", None): "effecten_lang",
    # Preventie (ICSC)
    ("Inhalation Prevention", None): "preventie_inademing",
    ("Skin Prevention", None): "preventie_huid",
    ("Eye Prevention", None): "preventie_ogen",
    ("Ingestion Prevention", None): "preventie_inslikken",
    ("Fire Prevention", None): "preventie_brand",
    ("Exposure Prevention", None): "preventie_algemeen",
    # EHBO (ICSC gebruikt per route een eigen naam)
    ("First Aid Measures", "Inhalation First Aid"): "ehbo_inademing",
    ("First Aid Measures", "Skin First Aid"): "ehbo_huid",
    ("First Aid Measures", "Eye First Aid"): "ehbo_ogen",
    ("First Aid Measures", "Ingestion First Aid"): "ehbo_inslikken",
    # Brand, opslag, morsen, afval, reactiviteit
    ("Fire Fighting Procedures", None): "brandbestrijding",
    ("Safe Storage", None): "opslag",
    ("Storage Conditions", None): "opslag",
    ("Spillage Disposal", None): "morsen",
    ("Disposal Methods", None): "afval",
    ("Hazardous Reactivities and Incompatibilities", None): "onverenigbaar",
    ("Chemical Dangers", None): "chemische_gevaren",
}
# Grenswaarden: het naamveld (bijv. "TLV-TWA") is nodig om de waarde te begrijpen.
NAAM_TONEN = {"grens_tlv", "grens_pel", "grens_rel", "grens_oel", "grens_idlh"}
MAX_LENGTE = 450


def veiligheidsgegevens(cid: int, max_per_veld: int = 2) -> dict[str, list[Meetwaarde]]:
    record = pubchem._pug_view(cid, "Safety and Hazards")
    if not record:
        return {}
    bronnen = pubchem._bronnen(record)
    verzameld: dict[str, list[Meetwaarde]] = {}
    gezien: dict[str, set] = {}
    for sectie in pubchem._secties(record):
        kop = sectie.get("TOCHeading")
        for info in sectie.get("Information", []):
            naam = (info.get("Name") or "").strip()
            sleutel = VELDEN.get((kop, naam)) or VELDEN.get((kop, None))
            if not sleutel:
                continue
            tekst = pubchem._waarde_als_tekst(info.get("Value", {}))
            if not tekst or "[Table#" in tekst:
                continue
            if sleutel in NAAM_TONEN | {"lel", "uel"} and not re.search(r"\d", tekst):
                continue  # bijv. "none See Appendix G" of "N.D.; See: IDLH INDEX"
            # PubChem verliest soms het superscript: "380 mg/m" betekent 380 mg/m³.
            tekst = re.sub(r"mg/m(?![³3\w])", "mg/m³", tekst)
            if sleutel in NAAM_TONEN and naam and naam.lower() not in ("none", ""):
                tekst = f"{naam}: {tekst}"
            if len(tekst) > MAX_LENGTE:
                tekst = tekst[:MAX_LENGTE].rsplit(" ", 1)[0] + " …"
            if tekst.lower() in gezien.setdefault(sleutel, set()):
                continue
            gezien[sleutel].add(tekst.lower())
            verzameld.setdefault(sleutel, []).append(
                Meetwaarde(tekst, bronnen.get(info.get("ReferenceNumber"), Bron("PubChem")))
            )
    return {
        sleutel: sorted(waarden, key=lambda m: pubchem._meetbron_prioriteit(m.bron))[:max_per_veld]
        for sleutel, waarden in verzameld.items()
    }
