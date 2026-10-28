"""
LS - RDKit-eigenschappen doorsturen naar Gemini en uitleg op niveau genereren
=============================================================================

Testopstelling voor de leerstory: haalt een stof op (RDKit + PubChem), bouwt de
prompt waarin de data dynamisch wordt meegegeven, en vraagt Gemini om uitleg op
het gekozen niveau. Elk resultaat (prompt + antwoord) wordt opgeslagen in
docs/testresultaten/ als bewijs.

Voorbeelden (vanuit de projectmap):
    python scripts/ls_gemini_test.py                                  # aspirine, niveau scholier
    python scripts/ls_gemini_test.py --stof caffeine --niveau leek
    python scripts/ls_gemini_test.py --stof "CCO" --alle-niveaus      # vergelijk alle niveaus
    python scripts/ls_gemini_test.py --droog                          # alleen prompt tonen, geen API-call
    python scripts/ls_gemini_test.py --test-fouten                    # demonstreert de foutafhandeling

Benodigd: GEMINI_API_KEY in .env (behalve bij --droog).
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from molecuul import uitleg  # noqa: E402
from molecuul.chem import OngeldigeSmilesFout  # noqa: E402
from molecuul.pubchem import NietGevondenFout, PubChemFout  # noqa: E402
from molecuul.rapport import maak_rapport  # noqa: E402

UITVOER = PROJECT / "docs" / "testresultaten"


def bewaar(stof: str, niveau: str, prompt: str, antwoord: str, model: str) -> Path:
    UITVOER.mkdir(parents=True, exist_ok=True)
    tijd = datetime.now().strftime("%Y%m%d-%H%M%S")
    veilige_naam = "".join(c if c.isalnum() else "_" for c in stof)[:40]
    pad = UITVOER / f"{tijd}_{veilige_naam}_{niveau}.md"
    pad.write_text(
        f"# Testresultaat: {stof} - niveau {niveau}\n\n"
        f"- Datum: {datetime.now():%Y-%m-%d %H:%M}\n- Model: {model}\n- Temperatuur: {uitleg.TEMPERATUUR}\n\n"
        f"## Systeeminstructie\n\n```text\n{uitleg.SYSTEEM_INSTRUCTIE}```\n\n"
        f"## Prompt (dynamisch opgebouwd)\n\n```text\n{prompt}\n```\n\n"
        f"## Antwoord van Gemini\n\n{antwoord}\n",
        encoding="utf-8",
    )
    return pad


def test_fouten(rapport) -> None:
    """Laat zien dat API-fouten netjes worden opgevangen i.p.v. dat het script crasht."""
    gevallen = [
        ("Ongeldige API-sleutel", dict(sleutel="ONGELDIGE-SLEUTEL-123")),
        ("Niet-bestaand model", dict(model="gemini-bestaat-niet")),
    ]
    for titel, opties in gevallen:
        print(f"\n--- Test: {titel} ---")
        try:
            uitleg.genereer_uitleg(rapport, "leek", **opties)
            print("  Onverwacht: geen fout.")
        except uitleg.UitlegFout as fout:
            print(f"  Netjes opgevangen -> melding: {fout.bericht}")
            print(f"  Technisch: {fout.technisch}")
    print("\n--- Test: ongeldig niveau ---")
    try:
        uitleg.bouw_prompt(rapport, "baby")
    except ValueError as fout:
        print(f"  Netjes opgevangen -> {fout}")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--stof", default="CC(=O)Oc1ccccc1C(=O)O", help="stofnaam of SMILES (standaard: aspirine)")
    p.add_argument("--niveau", default="scholier", choices=list(uitleg.NIVEAUS))
    p.add_argument("--alle-niveaus", action="store_true", help="genereer uitleg voor elk niveau")
    p.add_argument("--droog", action="store_true", help="toon alleen de prompt, roep de API niet aan")
    p.add_argument("--test-fouten", action="store_true", help="test de foutafhandeling van de API")
    args = p.parse_args()

    try:
        rapport = maak_rapport(args.stof)
    except (OngeldigeSmilesFout, NietGevondenFout, PubChemFout, ValueError) as fout:
        print(f"FOUT bij ophalen stof: {fout}")
        return 1

    print(f"Stof: {rapport.titel}  |  {rapport.rdkit.formule}  |  {rapport.rdkit.molmassa_g_per_mol} g/mol")
    for w in rapport.waarschuwingen:
        print(f"  Let op: {w}")

    if args.test_fouten:
        test_fouten(rapport)
        return 0

    niveaus = list(uitleg.NIVEAUS) if args.alle_niveaus else [args.niveau]
    for niveau in niveaus:
        prompt, _ = uitleg.bouw_prompt(rapport, niveau)
        print(f"\n{'=' * 70}\nNIVEAU: {niveau}  ({uitleg.NIVEAUS[niveau]['label']})\n{'=' * 70}")
        if args.droog:
            print(prompt)
            continue
        try:
            resultaat = uitleg.genereer_uitleg(rapport, niveau)
        except uitleg.UitlegFout as fout:
            print(f"FOUT: {fout.bericht}")
            if fout.technisch:
                print(f"(technisch: {fout.technisch})")
            return 2
        print(resultaat.tekst)
        print(f"\n[opgeslagen: {bewaar(rapport.titel, niveau, prompt, resultaat.tekst, resultaat.model).relative_to(PROJECT)}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
