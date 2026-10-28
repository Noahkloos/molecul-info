"""
US1 - SMILES inlezen en molmassa berekenen met RDKit
====================================================

Onderzoeksscript voor de Molecuul-uitlegger. Het script laat zien hoe je met
RDKit een SMILES-string omzet naar een molecuulobject (de "structuur") en daar
de molecuulformule en molmassa uit berekent.

De gebruikte functies komen uit de officiële RDKit-documentatie:
  - "Getting Started with the RDKit in Python", sectie "Reading and Writing Molecules"
    https://www.rdkit.org/docs/GettingStartedInPython.html#reading-and-writing-molecules
    -> Chem.MolFromSmiles() geeft None terug bij een ongeldige SMILES.
  - rdkit.Chem.Descriptors.MolWt / ExactMolWt
    https://www.rdkit.org/docs/source/rdkit.Chem.Descriptors.html
  - rdkit.Chem.rdMolDescriptors.CalcMolFormula
    https://www.rdkit.org/docs/source/rdkit.Chem.rdMolDescriptors.html

Gebruik (vanuit de projectmap):
    python scripts/us1_smiles_naar_molmassa.py                  # standaard teststoffen
    python scripts/us1_smiles_naar_molmassa.py "CC(=O)Oc1ccccc1C(=O)O"
    python scripts/us1_smiles_naar_molmassa.py "dit-is-geen-smiles"   # nette foutmelding

Exitcode: 0 als alle SMILES geldig waren, 1 als er minstens één ongeldig was.
"""

import sys

from rdkit import Chem, RDLogger
from rdkit.Chem import Descriptors, rdMolDescriptors

# RDKit schrijft parse-fouten standaard zelf naar stderr. Die zetten we uit,
# zodat we zelf één nette Nederlandse foutmelding kunnen tonen.
RDLogger.DisableLog("rdApp.*")

# Teststoffen met hun bekende (gemiddelde) molmassa ter controle.
# Referentiewaarden: PubChem (aspirine CID 2244, cafeïne CID 2519, ethanol CID 702).
TESTSTOFFEN = {
    "aspirine": ("CC(=O)Oc1ccccc1C(=O)O", 180.16),
    "cafeïne": ("CN1C=NC2=C1C(=O)N(C(=O)N2C)C", 194.19),
    "ethanol": ("CCO", 46.07),
}


class OngeldigeSmilesFout(ValueError):
    """Wordt opgegooid als RDKit de SMILES-string niet kan interpreteren."""


def smiles_naar_molecuul(smiles: str) -> Chem.Mol:
    """Zet een SMILES-string om naar een RDKit-molecuul.

    Chem.MolFromSmiles crasht niet bij foute invoer maar geeft None terug;
    dat vertalen we naar een duidelijke foutmelding.
    """
    smiles = (smiles or "").strip()
    if not smiles:
        raise OngeldigeSmilesFout("Er is geen SMILES-string ingevoerd.")
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise OngeldigeSmilesFout(
            f"'{smiles}' is geen geldige SMILES-string. Controleer haakjes, "
            "ringnummers en atoomsymbolen (bijv. 'Cl' in plaats van 'CL')."
        )
    return mol


def bereken_basisgegevens(smiles: str) -> dict:
    """Berekent formule, molmassa en exacte massa voor een SMILES-string."""
    mol = smiles_naar_molecuul(smiles)
    return {
        "invoer": smiles,
        "canonieke_smiles": Chem.MolToSmiles(mol),
        "formule": rdMolDescriptors.CalcMolFormula(mol),
        "molmassa": Descriptors.MolWt(mol),          # g/mol, gemiddelde isotopenmassa
        "exacte_massa": Descriptors.ExactMolWt(mol),  # monoisotopische massa (Da)
        "aantal_atomen": mol.GetNumAtoms(),           # zware atomen (zonder H)
    }


def print_resultaat(naam: str, gegevens: dict, referentie: float | None = None) -> None:
    print(f"\n=== {naam} ===")
    print(f"  Invoer (SMILES)    : {gegevens['invoer']}")
    print(f"  Canonieke SMILES   : {gegevens['canonieke_smiles']}")
    print(f"  Molecuulformule    : {gegevens['formule']}")
    print(f"  Molmassa           : {gegevens['molmassa']:.2f} g/mol")
    print(f"  Exacte massa       : {gegevens['exacte_massa']:.4f} Da")
    print(f"  Zware atomen       : {gegevens['aantal_atomen']}")
    if referentie is not None:
        verschil = abs(gegevens["molmassa"] - referentie)
        status = "OK" if verschil < 0.05 else "AFWIJKING"
        print(f"  Controle (PubChem) : {referentie:.2f} g/mol -> {status} (verschil {verschil:.3f})")


def main(argv: list[str]) -> int:
    if argv:
        invoer = [(f"Invoer {i + 1}", s, None) for i, s in enumerate(argv)]
    else:
        invoer = [(naam, s, ref) for naam, (s, ref) in TESTSTOFFEN.items()]

    fouten = 0
    for naam, smiles, referentie in invoer:
        try:
            print_resultaat(naam, bereken_basisgegevens(smiles), referentie)
        except OngeldigeSmilesFout as fout:
            fouten += 1
            print(f"\n=== {naam} ===\n  FOUT: {fout}")
    return 1 if fouten else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
