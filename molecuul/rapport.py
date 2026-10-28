"""Combineert RDKit-berekeningen en PubChem-gegevens tot één molecuulrapport.

Volgorde:
  1. Bepaal of de invoer een SMILES of een naam is.
  2. Naam -> PubChem zoekt de stof en levert de SMILES.
     SMILES -> RDKit controleert de SMILES, PubChem zoekt de bijbehorende stof.
  3. RDKit berekent structuureigenschappen; PubChem levert meetwaarden en GHS.
  4. Kruiscontrole: de molmassa van RDKit en PubChem moeten overeenkomen.
"""

import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass, field

from . import chem, pubchem, veiligheid
from .pubchem import GHSClassificatie, Meetwaarde

# PubChem kent vooral Engelse namen. Veelgebruikte Nederlandse namen vertalen we
# hier vast (deterministisch, geen AI nodig).
NEDERLANDSE_NAMEN = {
    "aceton": "acetone", "ammoniak": "ammonia", "ascorbinezuur": "ascorbic acid",
    "aspirine": "aspirin", "azijnzuur": "acetic acid", "benzeen": "benzene",
    "benzoezuur": "benzoic acid", "broom": "bromine", "butaan": "butane",
    "cafeine": "caffeine", "calciumcarbonaat": "calcium carbonate", "chloor": "chlorine",
    "citroenzuur": "citric acid", "dichloormethaan": "dichloromethane",
    "ethaan": "ethane", "ether": "diethyl ether", "ethyleenglycol": "ethylene glycol",
    "fenol": "phenol", "fosforzuur": "phosphoric acid", "jodium": "iodine",
    "kaliumhydroxide": "potassium hydroxide", "kaliumpermanganaat": "potassium permanganate",
    "keukenzout": "sodium chloride", "koolstofdioxide": "carbon dioxide",
    "koolstofmonoxide": "carbon monoxide", "kopersulfaat": "copper(II) sulfate",
    "melkzuur": "lactic acid", "methaan": "methane", "mierenzuur": "formic acid",
    "natriumbicarbonaat": "sodium bicarbonate", "natriumchloride": "sodium chloride",
    "natriumhydroxide": "sodium hydroxide", "natronloog": "sodium hydroxide",
    "oxaalzuur": "oxalic acid", "ozon": "ozone", "propaan": "propane",
    "sacharose": "sucrose", "salicylzuur": "salicylic acid", "salpeterzuur": "nitric acid",
    "stikstof": "nitrogen", "styreen": "styrene", "tolueen": "toluene", "ureum": "urea",
    "vitamine c": "ascorbic acid", "waterstof": "hydrogen",
    "waterstofperoxide": "hydrogen peroxide", "zilvernitraat": "silver nitrate",
    "zoutzuur": "hydrochloric acid", "zuiveringszout": "sodium bicarbonate",
    "zuurstof": "oxygen", "zwaveldioxide": "sulfur dioxide", "zwavelwaterstof": "hydrogen sulfide",
    "zwavelzuur": "sulfuric acid",
}


def _zonder_accenten(tekst: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", tekst) if not unicodedata.combining(c))


def _naam_kandidaten(naam: str) -> list[str]:
    """Probeert: originele naam, zonder accenten, vaste vertaling, -aan/-een -> -ane/-ene."""
    basis = _zonder_accenten(naam.strip()).lower()
    kandidaten = [naam.strip(), basis, NEDERLANDSE_NAMEN.get(basis, "")]
    kandidaten.append(re.sub(r"aan$", "ane", re.sub(r"een$", "ene", basis)))
    uniek: list[str] = []
    for k in kandidaten:
        if k and k not in uniek:
            uniek.append(k)
    return uniek


def _lijkt_op_smiles(tekst: str) -> bool:
    return " " not in tekst and bool(re.search(r"[()\[\]=#@/\\]|\d", tekst))


@dataclass
class MolecuulRapport:
    invoer: str
    invoertype: str  # "naam" of "smiles"
    smiles: str
    rdkit: chem.RDKitEigenschappen
    pubchem: dict | None = None
    fysisch: dict[str, list[Meetwaarde]] = field(default_factory=dict)
    ghs: list[GHSClassificatie] = field(default_factory=list)
    veiligheid: dict[str, list[Meetwaarde]] = field(default_factory=dict)  # zie veiligheid.VELDEN
    waarschuwingen: list[str] = field(default_factory=list)

    @property
    def titel(self) -> str:
        if self.pubchem and self.pubchem.get("naam"):
            return self.pubchem["naam"]
        return self.rdkit.formule


def bepaal_invoertype(invoer: str, modus: str = "auto") -> str:
    if modus in ("naam", "smiles"):
        return modus
    return "smiles" if chem.is_geldige_smiles(invoer) else "naam"


def zoek_cid_via_naam(
    naam: str, vertaal_naam: Callable[[str], str | None] | None = None
) -> tuple[int, str | None]:
    """Geeft (cid, ai_vertaling). ai_vertaling is alleen gevuld als de AI-vertaler nodig was."""
    for kandidaat in _naam_kandidaten(naam):
        try:
            return pubchem.cid_via_naam(kandidaat), None
        except pubchem.NietGevondenFout:
            continue
    if vertaal_naam:
        vertaling = vertaal_naam(naam)
        if vertaling:
            try:
                return pubchem.cid_via_naam(vertaling), vertaling
            except pubchem.NietGevondenFout:
                pass
    if _lijkt_op_smiles(naam):
        chem.smiles_naar_molecuul(naam)  # geeft de nette SMILES-foutmelding
    raise pubchem.NietGevondenFout(
        f"'{naam}' is niet gevonden in PubChem. Probeer de Engelse naam, "
        "een CAS-nummer (bijv. 50-78-2) of een SMILES-string."
    )


def maak_rapport(
    invoer: str,
    modus: str = "auto",
    vertaal_naam: Callable[[str], str | None] | None = None,
    max_meetwaarden: int = 3,
) -> MolecuulRapport:
    """Bouwt het rapport. Gooit chem.OngeldigeSmilesFout of pubchem.NietGevondenFout
    als de stof helemaal niet te vinden is; kleinere problemen worden waarschuwingen.

    vertaal_naam: optionele (AI-)functie die een onbekende naam naar het Engels vertaalt.
    Het resultaat wordt altijd in PubChem gecontroleerd en als waarschuwing getoond."""
    invoer = (invoer or "").strip()
    if not invoer:
        raise ValueError("Vul een stofnaam of SMILES-string in.")
    invoertype = bepaal_invoertype(invoer, modus)
    waarschuwingen: list[str] = []
    cid = None

    if invoertype == "naam":
        cid, ai_vertaling = zoek_cid_via_naam(invoer, vertaal_naam)
        basis = pubchem.basisgegevens(cid)
        if ai_vertaling:
            waarschuwingen.append(
                f"'{invoer}' stond niet in PubChem en is door AI vertaald naar '{ai_vertaling}'. "
                f"Gevonden: {basis['naam']} (CAS {basis['cas'] or 'onbekend'}). Controleer of dit de bedoelde stof is."
            )
        smiles = basis["smiles"]
    else:
        smiles = invoer
        chem.smiles_naar_molecuul(smiles)  # valideert; gooit OngeldigeSmilesFout
        basis = None
        try:
            cid = pubchem.cid_via_smiles(smiles)
            basis = pubchem.basisgegevens(cid)
        except pubchem.NietGevondenFout:
            waarschuwingen.append(
                "Deze structuur staat niet in PubChem. Alleen de berekende RDKit-waarden "
                "zijn beschikbaar; er zijn geen meetwaarden of H/P-zinnen gevonden."
            )
        except pubchem.PubChemFout as fout:
            waarschuwingen.append(f"PubChem niet bereikbaar: {fout} Alleen RDKit-waarden worden getoond.")

    rdkit = chem.bereken_eigenschappen(smiles)
    rapport = MolecuulRapport(invoer, invoertype, smiles, rdkit, basis, waarschuwingen=waarschuwingen)

    if cid:
        try:
            rapport.fysisch = pubchem.fysische_eigenschappen(cid, max_meetwaarden)
        except pubchem.PubChemFout as fout:
            waarschuwingen.append(f"Fysische eigenschappen konden niet worden opgehaald: {fout}")
        try:
            rapport.ghs = pubchem.ghs_classificaties(cid)
        except pubchem.PubChemFout as fout:
            waarschuwingen.append(f"GHS-gegevens konden niet worden opgehaald: {fout}")
        try:
            rapport.veiligheid = veiligheid.veiligheidsgegevens(cid)
        except pubchem.PubChemFout as fout:
            waarschuwingen.append(f"Veiligheidsgegevens (EHBO, grenswaarden) konden niet worden opgehaald: {fout}")
        if not rapport.ghs:
            waarschuwingen.append(
                "PubChem bevat geen GHS-indeling voor deze stof. Dat betekent NIET automatisch "
                "dat de stof veilig is; raadpleeg het veiligheidsinformatieblad (SDS) van de leverancier."
            )

    # Kruiscontrole RDKit <-> PubChem
    if basis and basis.get("molmassa_g_per_mol"):
        verschil = abs(basis["molmassa_g_per_mol"] - rdkit.molmassa_g_per_mol)
        if verschil > 0.1:
            waarschuwingen.append(
                f"Molmassa RDKit ({rdkit.molmassa_g_per_mol}) wijkt {verschil:.2f} g/mol af van "
                f"PubChem ({basis['molmassa_g_per_mol']}). Controleer of de juiste stof is gevonden."
            )
    return rapport
