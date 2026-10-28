"""Regels om een Hazardous Substance Risk Assessment voor te vullen.

Alles wordt afgeleid uit de gegevens van RDKit en PubChem met vaste, controleerbare regels
(geen AI): aggregatietoestand uit smelt-/kookpunt, blootstellingsroutes en PBM uit de H-zinnen,
maatregelen uit de H/P-zinnen en de ICSC-preventieteksten. De gebruiker controleert en past aan
in de app voordat het document wordt gemaakt. Het document is in het Engels, net als het sjabloon.
"""

import re
from dataclasses import dataclass, field
from datetime import date, timedelta

from .rapport import MolecuulRapport

# Volgorde en Engelse namen zoals in het sjabloon.
PICTOGRAM_NAMEN = {
    "GHS08": "Serious Harm to Health",
    "GHS06": "Toxic",
    "GHS05": "Corrosive",
    "GHS07": "Irritant",
    "GHS02": "Flammable",
    "GHS03": "Oxidiser",
    "GHS01": "Explosive",
    "GHS04": "Gas Under Pressure",
    "GHS09": "Risk to Environment",
}
GEVARENTYPEN = ["Gas", "Vapour", "Mist", "Fume", "Dust", "Liquid", "Solid"]
ROUTES = ["Inhalation", "Skin", "Eyes", "Ingestion"]
PERSONEN = ["Employees", "Students", "Contractors", "Public"]

# H-codes per blootstellingsroute (GHS: acute toxiciteit, corrosie/irritatie, sensibilisatie, STOT).
ROUTE_H = {
    "Inhalation": {"H330", "H331", "H332", "H333", "H334", "H335", "H336"},
    "Skin": {"H310", "H311", "H312", "H313", "H314", "H315", "H317"},
    "Eyes": {"H314", "H318", "H319", "H320"},
    "Ingestion": {"H300", "H301", "H302", "H303", "H304", "H305"},
}
# Ernst (1-3) op basis van de zwaarste H-zin.
ERNST_HOOG = {"H300", "H310", "H330", "H314", "H318", "H340", "H350", "H360", "H370", "H372", "H224"}
ERNST_MIDDEL = {
    "H301", "H311", "H331", "H334", "H317", "H341", "H351", "H361", "H362", "H371", "H373",
    "H220", "H225", "H228", "H240", "H241", "H250", "H260", "H270", "H271", "H272", "H290", "H304",
}
ERNST_LABEL = {1: "Low", 2: "Medium", 3: "High"}
KANS_LABEL = {1: "Unlikely", 2: "Possible", 3: "Likely"}


@dataclass
class PBM:
    item: str
    standaard: str
    toelichting: str
    nodig: bool


@dataclass
class Risicobeoordeling:
    # Door de gebruiker in te vullen (met voorstel)
    ref: str = "001"
    chemische_naam: str = ""
    stof_en_fabrikant: str = ""
    locatie: str = ""
    personen: list[str] = field(default_factory=lambda: ["Employees"])
    taak: str = ""
    hoeveelheid: str = ""
    beoordelaar: str = ""
    datum: str = field(default_factory=lambda: date.today().strftime("%d-%m-%Y"))
    herzieningsdatum: str = field(default_factory=lambda: (date.today() + timedelta(days=365)).strftime("%d-%m-%Y"))
    kans: int = 1  # met de maatregelen hieronder is blootstelling meestal "unlikely"; gebruiker past aan
    # Automatisch voorgesteld, aanpasbaar
    signaalwoord: str = ""
    pictogrammen: list[str] = field(default_factory=list)
    gevarentypen: list[str] = field(default_factory=list)
    h_zinnen: list[tuple[str, str]] = field(default_factory=list)
    p_zinnen: list[tuple[str, str]] = field(default_factory=list)
    routes: list[str] = field(default_factory=list)
    grenswaarden: list[str] = field(default_factory=list)
    monitoring: str = ""
    technische_maatregelen: list[str] = field(default_factory=list)
    hygiene: list[str] = field(default_factory=list)
    pbm: list[PBM] = field(default_factory=list)
    ehbo: dict[str, str] = field(default_factory=dict)
    brand: str = ""
    opslag: str = ""
    morsen: str = ""
    afval: str = ""
    fysisch: list[tuple[str, str]] = field(default_factory=list)
    ernst: int = 1
    ghs_bron: str = ""
    bronnen: list[tuple[str, str | None]] = field(default_factory=list)

    @property
    def risicoscore(self) -> int:
        return self.ernst * self.kans

    @property
    def risiconiveau(self) -> str:
        score = self.risicoscore
        return "Low" if score <= 2 else "Medium" if score <= 4 else "High"


# --------------------------------------------------------------------------- #
# Hulpfuncties
# --------------------------------------------------------------------------- #
def losse_codes(codes: list[str]) -> set[str]:
    """['H302+H312', 'H319'] -> {'H302', 'H312', 'H319'}"""
    return {deel for code in codes for deel in code.split("+")}


_TEMPERATUUR = re.compile(r"(-?\d+(?:\.\d+)?)(?:\s*-\s*-?\d+(?:\.\d+)?)?\s*(°\s*[CF]|deg\s*[CF])?", re.I)


def temperatuur_c(tekst: str) -> float | None:
    """'460 °F (NTP, 1992)' -> 237.8; '235-237' -> 235.0; '-114.14 °C' -> -114.14"""
    m = _TEMPERATUUR.search(tekst or "")
    if not m:
        return None
    waarde = float(m.group(1))
    if m.group(2) and m.group(2).strip()[-1].upper() == "F":
        waarde = (waarde - 32) * 5 / 9
    return round(waarde, 1)


def _eerste_temperatuur(rapport: MolecuulRapport, label: str) -> float | None:
    for meting in rapport.fysisch.get(label, []):
        t = temperatuur_c(meting.waarde)
        if t is not None:
            return t
    return None


def aggregatietoestand(rapport: MolecuulRapport) -> str | None:
    """Gas, Liquid of Solid bij 20 °C (uit smelt-/kookpunt, anders uit de beschrijving)."""
    smelt = _eerste_temperatuur(rapport, "Smeltpunt")
    kook = _eerste_temperatuur(rapport, "Kookpunt")
    if smelt is not None and smelt > 20:
        return "Solid"
    if kook is not None and kook < 20:
        return "Gas"
    if smelt is not None or kook is not None:
        return "Liquid"
    beschrijving = " ".join(m.waarde for m in rapport.fysisch.get("Uiterlijk", [])).lower()
    for woord, toestand in (("gas", "Gas"), ("liquid", "Liquid"), ("powder", "Solid"),
                            ("crystal", "Solid"), ("solid", "Solid")):
        if woord in beschrijving:
            return toestand
    return None


def _tekst(rapport: MolecuulRapport, sleutel: str, aantal: int = 1) -> str:
    return " ".join(m.waarde for m in rapport.veiligheid.get(sleutel, [])[:aantal])


# --------------------------------------------------------------------------- #
# Voorstel opbouwen
# --------------------------------------------------------------------------- #
def stel_voor(rapport: MolecuulRapport, ghs_index: int = 0) -> Risicobeoordeling:
    pc = rapport.pubchem or {}
    indeling = rapport.ghs[min(ghs_index, len(rapport.ghs) - 1)] if rapport.ghs else None
    h_codes = losse_codes([h.code for h in indeling.h_zinnen]) if indeling else set()
    p_codes = losse_codes([p.code for p in indeling.p_zinnen]) if indeling else set()
    pictos = set(indeling.pictogrammen) if indeling else set()

    b = Risicobeoordeling()
    b.chemische_naam = rapport.titel
    b.stof_en_fabrikant = f"{rapport.titel} ({rapport.rdkit.formule}" + (f", CAS {pc['cas']}" if pc.get("cas") else "") + ")"
    if indeling:
        b.signaalwoord = indeling.signaalwoord or ""
        b.pictogrammen = [p for p in PICTOGRAM_NAMEN if p in pictos]
        b.h_zinnen = [(h.code, h.tekst) for h in indeling.h_zinnen]
        b.p_zinnen = [(p.code, p.tekst) for p in indeling.p_zinnen]
        b.ghs_bron = indeling.bron.naam

    # Gevarentype (vorm waarin de stof vrijkomt)
    toestand = aggregatietoestand(rapport)
    preventie = (_tekst(rapport, "preventie_algemeen") + " " + _tekst(rapport, "morsen")).upper()
    beschrijving = " ".join(m.waarde for m in rapport.fysisch.get("Uiterlijk", [])).lower()
    kookpunt = _eerste_temperatuur(rapport, "Kookpunt")
    typen = []
    if toestand == "Gas":
        typen.append("Gas")
    if toestand == "Liquid":
        typen.append("Liquid")
        if (kookpunt is not None and kookpunt < 150) or h_codes & {"H224", "H225", "H226"}:
            typen.append("Vapour")
        if "MIST" in preventie:
            typen.append("Mist")
    if toestand == "Solid":
        typen.append("Solid")
        if "DUST" in preventie or "powder" in beschrijving:
            typen.append("Dust")
    b.gevarentypen = [t for t in GEVARENTYPEN if t in typen]

    # Blootstellingsroutes
    routes = {route for route, codes in ROUTE_H.items() if h_codes & codes}
    if {"Gas", "Vapour", "Dust", "Mist"} & set(typen) and h_codes:
        routes.add("Inhalation")
    b.routes = [r for r in ROUTES if r in routes]

    # Grenswaarden en monitoring
    for sleutel, label in (("grens_tlv", "ACGIH TLV"), ("grens_oel", "OEL"), ("grens_rel", "NIOSH REL"),
                           ("grens_pel", "OSHA PEL"), ("grens_idlh", "IDLH")):
        for m in rapport.veiligheid.get(sleutel, [])[:1]:
            b.grenswaarden.append(f"{label}: {m.waarde} ({m.bron.naam})")
    for sleutel, label in (("lel", "Lower explosive limit"), ("uel", "Upper explosive limit")):
        for m in rapport.veiligheid.get(sleutel, [])[:1]:
            b.grenswaarden.append(f"{label}: {m.waarde}")
    b.monitoring = (
        "Work in a fume cupboard keeps exposure well below the limits above; no personal air monitoring "
        "is required for small-scale laboratory use. Check the fume cupboard airflow indicator before use."
        if b.grenswaarden else
        "No occupational exposure limit found in PubChem. Keep exposure as low as reasonably practicable."
    )

    # Technische maatregelen
    tm = []
    if "Inhalation" in routes or {"Gas", "Vapour", "Mist", "Dust"} & set(typen):
        tm.append("Handle in a fume cupboard (local exhaust ventilation, EN 14175); keep the sash as low as possible.")
    else:
        tm.append("Good general laboratory ventilation.")
    if "GHS02" in pictos or h_codes & {"H220", "H221", "H222", "H223", "H224", "H225", "H226", "H228"}:
        tm.append("Keep away from heat, sparks and open flames; no ignition sources (e.g. Bunsen burners) nearby; "
                  "keep container closed when not in use.")
    if "GHS05" in pictos:
        tm.append("Use a spill tray (secondary containment) and work with the smallest practical quantity.")
    if "GHS03" in pictos:
        tm.append("Keep away from combustible and reducing materials.")
    if "Dust" in typen:
        tm.append("Avoid dust formation; weigh in a ventilated balance enclosure or fume cupboard.")
    for sleutel in ("preventie_inademing", "preventie_brand"):
        if rapport.veiligheid.get(sleutel):
            tm.append(f"ICSC advice: {_tekst(rapport, sleutel)}")
    b.technische_maatregelen = tm

    # Hygiënemaatregelen
    hy = ["Wash hands thoroughly after handling (P264).",
          "Do not eat, drink or smoke in the laboratory (P270)."]
    if "P362+P364" in {p for p, _ in b.p_zinnen} or "H315" in h_codes:
        hy.append("Remove contaminated clothing and wash it before reuse (P362+P364).")
    if "H317" in h_codes:
        hy.append("Contaminated work clothing must not be allowed out of the workplace (P272).")
    hy.append("Clean the work area and equipment after use; clean up spills immediately.")
    b.hygiene = hy

    # Persoonlijke beschermingsmiddelen
    corrosief = bool(h_codes & {"H314", "H318"})
    ruimzichtbril = corrosief or bool(h_codes & ROUTE_H["Eyes"]) or (toestand == "Liquid" and bool(h_codes))
    huid = "Skin" in routes or bool(h_codes)
    inhalatie_stof = "Dust" in typen and bool(h_codes & ROUTE_H["Inhalation"])
    zeer_giftig_inademen = bool(h_codes & {"H330", "H331", "H334"})
    b.pbm = [
        PBM("Laboratory coat", "EN ISO 13688 (EN 13034 Type 6 for liquid chemicals)",
            "Fully buttoned, long sleeves.", True),
        PBM("Safety glasses with side shields", "EN 166", "Minimum eye protection in the laboratory.",
            not ruimzichtbril),
        PBM("Chemical splash goggles", "EN 166 (marking 3)", "Required when there is a splash risk to the eyes.",
            ruimzichtbril),
        PBM("Face shield / visor", "EN 166", "Wear over goggles when handling corrosive liquids.", corrosief),
        PBM("Chemical-resistant gloves", "EN ISO 374-1",
            "Nitrile is a common choice; check breakthrough time and material in the supplier SDS.", huid),
        PBM("Dust mask (FFP2)", "EN 149", "Only if dust cannot be controlled with extraction.", inhalatie_stof),
        PBM("Respirator with gas/vapour filter", "EN 14387",
            "Only if work outside a fume cupboard is unavoidable (e.g. spill clean-up).", zeer_giftig_inademen),
        PBM("Closed footwear", "-", "Standard laboratory requirement.", True),
    ]

    # EHBO, brand, opslag, morsen, afval
    for sleutel, route in (("ehbo_inademing", "Inhalation"), ("ehbo_huid", "Skin"),
                           ("ehbo_ogen", "Eyes"), ("ehbo_inslikken", "Ingestion")):
        if rapport.veiligheid.get(sleutel):
            b.ehbo[route] = _tekst(rapport, sleutel)
    b.brand = _tekst(rapport, "brandbestrijding")
    b.opslag = _tekst(rapport, "opslag")
    if rapport.veiligheid.get("onverenigbaar"):
        b.opslag = (b.opslag + " " + _tekst(rapport, "onverenigbaar")).strip()
    b.morsen = _tekst(rapport, "morsen")
    p501 = next((t for c, t in b.p_zinnen if c == "P501"), None)
    b.afval = ("Dispose of as chemical waste according to local regulations and the laboratory waste procedure "
               "(P501). Do not pour down the drain unless permitted.") if p501 or h_codes else \
              "Dispose of according to the laboratory waste procedure."

    # Fysische kerngegevens (handig in een labverslag)
    rd = rapport.rdkit
    b.fysisch = [("Molecular formula", rd.formule), ("Molar mass", f"{rd.molmassa_g_per_mol} g/mol")]
    if toestand:
        b.fysisch.append(("State at 20 °C", toestand.lower()))
    for label, engels in (("Smeltpunt", "Melting point"), ("Kookpunt", "Boiling point"), ("Dichtheid", "Density"),
                          ("Vlampunt", "Flash point"), ("Oplosbaarheid", "Solubility in water"),
                          ("Dampspanning", "Vapour pressure")):
        if rapport.fysisch.get(label):
            m = rapport.fysisch[label][0]
            b.fysisch.append((engels, f"{m.waarde} ({m.bron.naam})"))

    # Ernst en bronnen
    b.ernst = 3 if h_codes & ERNST_HOOG else 2 if h_codes & ERNST_MIDDEL else 1
    bronnen: dict[str, str | None] = {}
    if pc:
        bronnen[f"PubChem CID {pc['cid']}"] = pc.get("url")
    if indeling:
        bronnen[f"GHS classification: {indeling.bron.naam}"] = indeling.bron.url
    for waarden in list(rapport.veiligheid.values()) + list(rapport.fysisch.values()):
        for m in waarden[:1]:
            bronnen.setdefault(m.bron.naam, m.bron.url)
    bronnen["GHS hazard and precautionary statement texts (UN GHS Rev. 10, via PubChem)"] = \
        "https://pubchem.ncbi.nlm.nih.gov/ghs/"
    b.bronnen = list(bronnen.items())
    return b
