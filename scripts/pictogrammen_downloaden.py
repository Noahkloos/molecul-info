"""
Eenmalig hulpscript: GHS-pictogrammen (SVG) van PubChem downloaden en omzetten naar PNG.

Word (python-docx) kan geen SVG invoegen, dus de risicobeoordeling gebruikt PNG's.
De PNG's staan al in data/ghs_pictogrammen/; dit script is alleen nodig om ze opnieuw te maken.
De GHS-pictogrammen zijn vastgesteld door de VN (GHS) en vrij te gebruiken.

Gebruik:  python scripts/pictogrammen_downloaden.py     (vereist: pip install resvg-py)
"""

import sys
from pathlib import Path

import requests
import resvg_py

DOEL = Path(__file__).resolve().parent.parent / "data" / "ghs_pictogrammen"
URL = "https://pubchem.ncbi.nlm.nih.gov/images/ghs/{code}.svg"
PIXELS = 240


def main() -> int:
    DOEL.mkdir(parents=True, exist_ok=True)
    for nummer in range(1, 10):
        code = f"GHS0{nummer}"
        antwoord = requests.get(URL.format(code=code), timeout=30)
        antwoord.raise_for_status()
        (DOEL / f"{code}.svg").write_bytes(antwoord.content)
        png = resvg_py.svg_to_bytes(svg_string=antwoord.text, width=PIXELS, height=PIXELS)
        (DOEL / f"{code}.png").write_bytes(bytes(png))
        print(f"{code}: opgeslagen")
    return 0


if __name__ == "__main__":
    sys.exit(main())
