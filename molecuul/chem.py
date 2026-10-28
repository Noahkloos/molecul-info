"""RDKit-berekeningen voor de Molecuul-uitlegger.

Alle waarden in dit bestand worden lokaal *berekend* uit de structuur (SMILES).
Het zijn dus geen meetwaarden; gemeten eigenschappen komen uit PubChem (zie
pubchem.py). Functies volgens de officiële RDKit-documentatie:
https://www.rdkit.org/docs/GettingStartedInPython.html
https://www.rdkit.org/docs/source/rdkit.Chem.Descriptors.html
"""

from dataclasses import asdict, dataclass

from rdkit import Chem, RDLogger
from rdkit.Chem import Crippen, Descriptors, Draw, Lipinski, rdMolDescriptors

RDLogger.DisableLog("rdApp.*")


class OngeldigeSmilesFout(ValueError):
    """De invoer kon door RDKit niet als SMILES worden gelezen."""


@dataclass
class RDKitEigenschappen:
    canonieke_smiles: str
    formule: str
    molmassa_g_per_mol: float
    exacte_massa_da: float
    zware_atomen: int
    formele_lading: int
    ringen: int
    aromatische_ringen: int
    h_brug_donoren: int
    h_brug_acceptoren: int
    draaibare_bindingen: int
    tpsa_a2: float
    logp_crippen: float
    molrefractie_crippen: float
    fractie_sp3: float
    heteroatomen: int
    stereocentra: int
    valentie_elektronen: int
    lipinski_overtredingen: int

    def als_dict(self) -> dict:
        return asdict(self)


def is_geldige_smiles(tekst: str) -> bool:
    tekst = (tekst or "").strip()
    return bool(tekst) and " " not in tekst and Chem.MolFromSmiles(tekst) is not None


def smiles_naar_molecuul(smiles: str) -> Chem.Mol:
    smiles = (smiles or "").strip()
    if not smiles:
        raise OngeldigeSmilesFout("Er is geen SMILES-string ingevoerd.")
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise OngeldigeSmilesFout(
            f"'{smiles}' is geen geldige SMILES-string. Controleer haakjes, "
            "ringnummers en atoomsymbolen."
        )
    return mol


def bereken_eigenschappen(smiles: str) -> RDKitEigenschappen:
    mol = smiles_naar_molecuul(smiles)
    mw = Descriptors.MolWt(mol)
    logp = Crippen.MolLogP(mol)
    hbd = Lipinski.NumHDonors(mol)
    hba = Lipinski.NumHAcceptors(mol)
    # Lipinski's "rule of five": vuistregel voor orale opneembaarheid van geneesmiddelen.
    overtredingen = sum([mw > 500, logp > 5, hbd > 5, hba > 10])
    return RDKitEigenschappen(
        canonieke_smiles=Chem.MolToSmiles(mol),
        formule=rdMolDescriptors.CalcMolFormula(mol),
        molmassa_g_per_mol=round(mw, 2),
        exacte_massa_da=round(Descriptors.ExactMolWt(mol), 4),
        zware_atomen=mol.GetNumHeavyAtoms(),
        formele_lading=Chem.GetFormalCharge(mol),
        ringen=rdMolDescriptors.CalcNumRings(mol),
        aromatische_ringen=rdMolDescriptors.CalcNumAromaticRings(mol),
        h_brug_donoren=hbd,
        h_brug_acceptoren=hba,
        draaibare_bindingen=rdMolDescriptors.CalcNumRotatableBonds(mol),
        tpsa_a2=round(rdMolDescriptors.CalcTPSA(mol), 1),
        logp_crippen=round(logp, 2),
        molrefractie_crippen=round(Crippen.MolMR(mol), 2),
        fractie_sp3=round(rdMolDescriptors.CalcFractionCSP3(mol), 2),
        heteroatomen=rdMolDescriptors.CalcNumHeteroatoms(mol),
        stereocentra=len(Chem.FindMolChiralCenters(mol, includeUnassigned=True, useLegacyImplementation=False)),
        valentie_elektronen=Descriptors.NumValenceElectrons(mol),
        lipinski_overtredingen=int(overtredingen),
    )


def teken_structuur_svg(smiles: str, breedte: int = 420, hoogte: int = 320) -> str:
    """2D-structuurtekening als SVG-tekst."""
    mol = smiles_naar_molecuul(smiles)
    tekenaar = Draw.rdMolDraw2D.MolDraw2DSVG(breedte, hoogte)
    tekenaar.drawOptions().clearBackground = False
    tekenaar.DrawMolecule(mol)
    tekenaar.FinishDrawing()
    return tekenaar.GetDrawingText()


# Uitleg per eigenschap, voor de tabel in de app.
BETEKENIS = {
    "formule": "Molecuulformule (Hill-notatie)",
    "molmassa_g_per_mol": "Molmassa (g/mol)",
    "exacte_massa_da": "Monoisotopische massa (Da)",
    "zware_atomen": "Aantal zware atomen (geen H)",
    "formele_lading": "Formele lading",
    "ringen": "Aantal ringen",
    "aromatische_ringen": "Aromatische ringen",
    "h_brug_donoren": "H-brugdonoren",
    "h_brug_acceptoren": "H-brugacceptoren",
    "draaibare_bindingen": "Draaibare bindingen",
    "tpsa_a2": "Polair oppervlak TPSA (Å²)",
    "logp_crippen": "logP (berekend, Crippen)",
    "molrefractie_crippen": "Molrefractie (berekend, Crippen, m³/mol × 10⁻⁶)",
    "fractie_sp3": "Fractie sp³-koolstof",
    "heteroatomen": "Heteroatomen (niet C of H)",
    "stereocentra": "Stereocentra",
    "valentie_elektronen": "Valentie-elektronen",
    "lipinski_overtredingen": "Overtredingen Lipinski-regel van 5",
}
