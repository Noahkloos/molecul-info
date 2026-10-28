"""Officiële teksten van GHS H- en P-zinnen.

Bron: PubChem "GHS Classification" codelijst (data/ghscode_10.txt), gebaseerd op
de VN-GHS (Rev. 10). https://pubchem.ncbi.nlm.nih.gov/ghs/
De lijst wordt lokaal meegeleverd zodat de app ook zonder internet de teksten kent.
"""

import re
from functools import lru_cache
from pathlib import Path

GHS_BESTAND = Path(__file__).resolve().parent.parent / "data" / "ghscode_10.txt"
GHS_BRON_URL = "https://pubchem.ncbi.nlm.nih.gov/ghs/"

# Pictogramcodes -> Nederlandse betekenis (CLP-verordening, bijlage V).
PICTOGRAMMEN = {
    "GHS01": "Ontplofbaar",
    "GHS02": "Ontvlambaar",
    "GHS03": "Oxiderend",
    "GHS04": "Gassen onder druk",
    "GHS05": "Bijtend",
    "GHS06": "Giftig (acuut)",
    "GHS07": "Schadelijk / irriterend",
    "GHS08": "Ernstig gezondheidsgevaar",
    "GHS09": "Milieugevaarlijk",
}

CODE_PATROON = re.compile(r"^[HP]\d{3}(?:\+[HP]\d{3})*$")


@lru_cache(maxsize=1)
def laad_zinnen() -> dict[str, str]:
    """Leest code -> officiële Engelse tekst uit de PubChem-codelijst."""
    zinnen: dict[str, str] = {}
    if not GHS_BESTAND.exists():
        return zinnen
    for regel in GHS_BESTAND.read_text(encoding="utf-8", errors="replace").splitlines():
        delen = regel.split("\t")
        if len(delen) < 2:
            continue
        code, tekst = delen[0].strip(), delen[1].strip()
        if CODE_PATROON.match(code) and code not in zinnen:
            zinnen[code] = tekst
    return zinnen


def tekst_voor(code: str) -> str | None:
    return laad_zinnen().get(code.strip())


def splits_p_codes(tekst: str) -> list[str]:
    """'P261, P264, P264+P265, ... and P501 (click ...)' -> ['P261', 'P264', ...]"""
    return re.findall(r"P\d{3}(?:\+P\d{3})*", tekst)
