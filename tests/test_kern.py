"""Automatische tests (zonder internet en zonder API-sleutel).

Uitvoeren vanuit de projectmap:  python -m unittest discover tests -v
"""

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from molecuul import chem, ghs, uitleg  # noqa: E402
from molecuul.pubchem import Bron, GevarenZin, GHSClassificatie, Meetwaarde, _parse_h_zin  # noqa: E402
from molecuul.rapport import MolecuulRapport, _naam_kandidaten, bepaal_invoertype  # noqa: E402


class TestRDKit(unittest.TestCase):
    def test_molmassa_aspirine(self):
        e = chem.bereken_eigenschappen("CC(=O)Oc1ccccc1C(=O)O")
        self.assertEqual(e.formule, "C9H8O4")
        self.assertAlmostEqual(e.molmassa_g_per_mol, 180.16, places=2)

    def test_molmassa_cafeine(self):
        self.assertAlmostEqual(chem.bereken_eigenschappen("CN1C=NC2=C1C(=O)N(C(=O)N2C)C").molmassa_g_per_mol, 194.19, places=2)

    def test_ongeldige_smiles_geeft_nette_fout(self):
        for fout in ["C1CC(", "XYZ", "", "   "]:
            with self.assertRaises(chem.OngeldigeSmilesFout):
                chem.bereken_eigenschappen(fout)

    def test_structuurtekening_is_svg(self):
        self.assertIn("<svg", chem.teken_structuur_svg("CCO"))


class TestInvoer(unittest.TestCase):
    def test_invoertype(self):
        self.assertEqual(bepaal_invoertype("CCO"), "smiles")
        self.assertEqual(bepaal_invoertype("caffeine"), "naam")
        self.assertEqual(bepaal_invoertype("acetic acid"), "naam")
        self.assertEqual(bepaal_invoertype("CCO", "naam"), "naam")

    def test_nederlandse_namen(self):
        self.assertIn("caffeine", _naam_kandidaten("cafeïne"))
        self.assertIn("sulfuric acid", _naam_kandidaten("Zwavelzuur"))
        self.assertIn("hexane", _naam_kandidaten("hexaan"))


class TestGHS(unittest.TestCase):
    def test_codelijst_geladen(self):
        self.assertEqual(ghs.tekst_voor("H225"), "Highly Flammable liquid and vapor")
        self.assertTrue(ghs.tekst_voor("P305+P351+P338").startswith("IF IN EYES"))

    def test_p_codes_splitsen(self):
        tekst = "P261, P264, P264+P265, P305+P351+P338, and P501 (click each P-code to see the statement)"
        self.assertEqual(ghs.splits_p_codes(tekst), ["P261", "P264", "P264+P265", "P305+P351+P338", "P501"])

    def test_h_zin_formaten(self):
        z = _parse_h_zin("H302 (95.6%): Harmful if swallowed [Warning Acute toxicity, oral]")
        self.assertEqual((z.code, z.percentage, z.klasse), ("H302", 95.6, "Warning Acute toxicity, oral"))
        z = _parse_h_zin("H225 (> 99.9%): Highly Flammable liquid and vapor [Danger Flammable liquids]")
        self.assertEqual((z.code, z.percentage), ("H225", 99.9))
        z = _parse_h_zin("H225: Highly Flammable liquid and vapor [Danger Flammable liquids]")
        self.assertEqual((z.code, z.percentage), ("H225", None))


def nep_rapport() -> MolecuulRapport:
    bron = Bron("Hazardous Substances Data Bank (HSDB)", "https://example.org/hsdb")
    return MolecuulRapport(
        invoer="ethanol", invoertype="naam", smiles="CCO",
        rdkit=chem.bereken_eigenschappen("CCO"),
        pubchem={"cid": 702, "naam": "Ethanol", "iupac_naam": "ethanol", "cas": "64-17-5",
                 "molmassa_g_per_mol": 46.07, "url": "https://pubchem.ncbi.nlm.nih.gov/compound/702"},
        fysisch={"Kookpunt": [Meetwaarde("78.24 °C", bron)]},
        ghs=[GHSClassificatie(bron=Bron("Regulation (EC) No 1272/2008"), signaalwoord="Danger",
                              pictogrammen=["GHS02"], h_zinnen=[GevarenZin("H225", "Highly Flammable liquid and vapor")],
                              p_zinnen=[GevarenZin("P210", "Keep away from heat...")])],
    )


class TestPrompt(unittest.TestCase):
    def test_data_dynamisch_in_prompt(self):
        prompt, bronnen = uitleg.bouw_prompt(nep_rapport(), "leek")
        data = json.loads(prompt.split("<GEGEVENS>")[1].split("</GEGEVENS>")[0])
        self.assertEqual(data["berekend_door_rdkit"]["molecuulformule"], "C2H6O")
        self.assertEqual(data["berekend_door_rdkit"]["molmassa_g_per_mol"], 46.07)
        self.assertEqual(data["ghs_indeling"]["H_zinnen"][0]["code"], "H225")
        self.assertEqual(data["gemeten_eigenschappen"]["Kookpunt"][0]["bron"], "B3")
        self.assertIn("B3", bronnen)

    def test_niveau_verandert_prompt(self):
        leek, _ = uitleg.bouw_prompt(nep_rapport(), "leek")
        expert, _ = uitleg.bouw_prompt(nep_rapport(), "expert")
        self.assertIn("zonder scheikundeachtergrond", leek)
        self.assertIn("chemicus", expert)
        self.assertNotEqual(leek, expert)

    def test_onbekend_niveau(self):
        with self.assertRaises(ValueError):
            uitleg.bouw_prompt(nep_rapport(), "baby")

    def test_geen_sleutel_geeft_nette_fout(self):
        import os
        oud = {k: os.environ.pop(k, None) for k in ("GEMINI_API_KEY", "GOOGLE_API_KEY")}
        try:
            with self.assertRaises(uitleg.UitlegFout) as ctx:
                uitleg.genereer_uitleg(nep_rapport(), "leek", gebruik_cache=False)
            self.assertIn("API-sleutel", ctx.exception.bericht)
        finally:
            for k, v in oud.items():
                if v is not None:
                    os.environ[k] = v


class NepAPIFout:
    """Lijkt op google.genai.errors.APIError (alleen de velden die wij gebruiken)."""

    def __init__(self, code, message, details=None):
        self.code, self.message, self.details = code, message, details


class TestQuotumEnCache(unittest.TestCase):
    DAG = ("Quota exceeded ... description: Generate content requests per day limit exceeded on Free Tier.\n"
           "Please retry in 15h16m27.76s.")
    MINUUT = "Generate content requests per minute limit exceeded on Free Tier.\nPlease retry in 7.5s."

    def test_dagquotum_herkennen(self):
        self.assertTrue(uitleg._is_dagquotum(NepAPIFout(429, self.DAG)))
        self.assertFalse(uitleg._is_dagquotum(NepAPIFout(429, self.MINUUT)))
        self.assertEqual(uitleg._reset_tekst(NepAPIFout(429, self.DAG)), "15 uur en 16 minuten")

    def test_dagquotum_melding(self):
        fout = uitleg._vertaal_api_fout(NepAPIFout(429, self.DAG), "gemini-x")
        self.assertIn("dagquotum", fout.bericht)
        self.assertIn("15 uur", fout.bericht)

    def test_samenvatting_alle_modellen(self):
        mislukt = [
            ("model-a", uitleg.UitlegFout("Het dagquotum van 'model-a' is op ... komt weer vrij over 3 uur en 5 minuten.", "x", 429)),
            ("model-b", uitleg.UitlegFout("overbelast", "y", 503)),
        ]
        fout = uitleg._alle_modellen_mislukt(mislukt)
        self.assertIn("model-a: dagquotum op, over 3 uur en 5 minuten", fout.bericht)
        self.assertIn("model-b: overbelast bij Google (503)", fout.bericht)

    def test_cache_spaart_api_aanroep(self):
        import tempfile
        from unittest import mock
        with tempfile.TemporaryDirectory() as map_, \
                mock.patch.object(uitleg, "CACHE_MAP", Path(map_)), \
                mock.patch.object(uitleg, "_genereer", return_value=("uitlegtekst", "model-z")) as nep:
            eerste = uitleg.genereer_uitleg(nep_rapport(), "leek", sleutel="x")
            tweede = uitleg.genereer_uitleg(nep_rapport(), "leek", sleutel="x")
            self.assertEqual(nep.call_count, 1)
            self.assertFalse(eerste.uit_cache)
            self.assertTrue(tweede.uit_cache)
            self.assertEqual(tweede.tekst, "uitlegtekst")
            uitleg.genereer_uitleg(nep_rapport(), "expert", sleutel="x")  # ander niveau = nieuwe aanroep
            self.assertEqual(nep.call_count, 2)


class TestRisicobeoordeling(unittest.TestCase):
    def test_temperatuur_lezen(self):
        from molecuul.risico import temperatuur_c
        self.assertEqual(temperatuur_c("-114.14 °C"), -114.1)
        self.assertEqual(temperatuur_c("460 °F (NTP, 1992)"), 237.8)
        self.assertEqual(temperatuur_c("235-237"), 235.0)
        self.assertIsNone(temperatuur_c("decomposes"))

    def test_ethanol_vloeistof_damp_inademing(self):
        from molecuul import risico
        r = nep_rapport()
        r.fysisch["Smeltpunt"] = [Meetwaarde("-114.14 °C", Bron("HSDB"))]
        b = risico.stel_voor(r)
        self.assertEqual(risico.aggregatietoestand(r), "Liquid")
        self.assertIn("Vapour", b.gevarentypen)          # kookpunt 78 °C en H225
        self.assertIn("Inhalation", b.routes)
        self.assertEqual(b.pictogrammen, ["GHS02"])
        self.assertTrue(any("ignition" in t for t in b.technische_maatregelen))
        self.assertEqual(b.ernst, 2)                      # H225 = middel

    def test_corrosief_geeft_gelaatsscherm(self):
        from molecuul import risico
        r = nep_rapport()
        r.ghs[0].h_zinnen = [GevarenZin("H314", "Causes severe skin burns and eye damage")]
        r.ghs[0].pictogrammen = ["GHS05"]
        b = risico.stel_voor(r)
        nodig = {p.item for p in b.pbm if p.nodig}
        self.assertIn("Face shield / visor", nodig)
        self.assertIn("Chemical splash goggles", nodig)
        self.assertNotIn("Safety glasses with side shields", nodig)
        self.assertEqual(set(b.routes) >= {"Skin", "Eyes"}, True)
        self.assertEqual(b.ernst, 3)

    def test_docx_wordt_gemaakt(self):
        import io as _io
        from docx import Document
        from molecuul import document, risico
        b = risico.stel_voor(nep_rapport())
        b.locatie = "Lab 2.14"
        inhoud = document.maak_docx(b)
        tekst = "\n".join(c.text for t in Document(_io.BytesIO(inhoud)).tables for rij in t.rows for c in rij.cells)
        for verwacht in ("Hazardous Substance Risk Assessment", "Ethanol", "H225", "P210", "Lab 2.14", "☒ Liquid"):
            self.assertIn(verwacht, tekst)


if __name__ == "__main__":
    unittest.main()
