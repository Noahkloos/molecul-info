"""
Markdown-documentatie omzetten naar een opgemaakt Word-document (.docx)
======================================================================

Ondersteunt wat in docs/*.md wordt gebruikt: koppen (#, ##, ###), alinea's, opsommingen
(- en 1.), tabellen, codeblokken, citaten (>), en **vet**, _cursief_, `code` en [links](url).
Elk document krijgt een titelpagina, een inhoudsopgave en paginanummers.

Gebruik (vanuit de projectmap):
    python scripts/md_naar_word.py docs/onderzoeksverslag.md docs/leeruitkomsten.md

De inhoudsopgave wordt bijgewerkt zodra je het document in Word opent
(of: rechtermuisklik op de inhoudsopgave -> Veld bijwerken).
"""

import re
import sys
from datetime import date
from pathlib import Path

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ACCENT = RGBColor(0x1F, 0x4E, 0x79)       # donkerblauw voor koppen
KOP_TABEL = "1F4E79"                       # tabelkop
ZEBRA = "EAF1F8"                           # lichte rijkleur
CODE_ACHTERGROND = "F2F2F2"
LETTERTYPE = "Calibri"

INLINE = re.compile(r"(\*\*.+?\*\*|`[^`]+`|\[[^\]]+\]\([^)]+\)|(?<![\w*])_[^_]+_(?!\w)|(?<![\w*])\*[^*]+\*(?!\w))")


# --------------------------------------------------------------------------- #
# Hulpjes voor Word-XML
# --------------------------------------------------------------------------- #
def _arcering(element, kleur: str) -> None:
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), kleur)
    element.append(shd)


def _veld(alinea, instructie: str, tekst: str = "") -> None:
    """Voegt een Word-veld in (bijv. TOC of PAGE)."""
    run = alinea.add_run()
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldChar"), "begin")
    begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = instructie
    scheiding = OxmlElement("w:fldChar")
    scheiding.set(qn("w:fldCharType"), "separate")
    run._r.extend([begin, instr, scheiding])
    alinea.add_run(tekst)
    eind = OxmlElement("w:fldChar")
    eind.set(qn("w:fldCharType"), "end")
    alinea.add_run()._r.append(eind)


def _hyperlink(alinea, tekst: str, url: str) -> None:
    deel = alinea.part
    rel_id = deel.relate_to(url, "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink",
                            is_external=True)
    link = OxmlElement("w:hyperlink")
    link.set(qn("r:id"), rel_id)
    run = OxmlElement("w:r")
    rpr = OxmlElement("w:rPr")
    kleur = OxmlElement("w:color")
    kleur.set(qn("w:val"), "0563C1")
    onderstreep = OxmlElement("w:u")
    onderstreep.set(qn("w:val"), "single")
    rpr.extend([kleur, onderstreep])
    run.append(rpr)
    t = OxmlElement("w:t")
    t.text = tekst
    t.set(qn("xml:space"), "preserve")
    run.append(t)
    link.append(run)
    alinea._p.append(link)


def _inline(alinea, tekst: str, vet: bool = False, kleur: RGBColor | None = None) -> None:
    """Zet Markdown-opmaak binnen een regel om naar Word-runs."""
    for deel in INLINE.split(tekst):
        if not deel:
            continue
        if deel.startswith("**") and deel.endswith("**"):
            _inline(alinea, deel[2:-2], vet=True, kleur=kleur)
        elif deel.startswith("`") and deel.endswith("`"):
            run = alinea.add_run(deel[1:-1])
            run.font.name = "Consolas"
            run.font.size = Pt(9)
            run.bold = vet
            run.font.color.rgb = RGBColor(0xA3, 0x15, 0x15)
        elif deel.startswith("[") and "](" in deel:
            label, url = re.match(r"\[([^\]]+)\]\(([^)]+)\)", deel).groups()
            if url.startswith("http"):
                _hyperlink(alinea, label, url)
            else:
                run = alinea.add_run(label)  # interne verwijzing: alleen de tekst
                run.bold = vet
        elif (deel[0] in "_*") and deel[-1] == deel[0] and len(deel) > 2:
            run = alinea.add_run(deel[1:-1])
            run.italic, run.bold = True, vet
            if kleur:
                run.font.color.rgb = kleur
        else:
            run = alinea.add_run(deel)
            run.bold = vet
            if kleur:
                run.font.color.rgb = kleur


# --------------------------------------------------------------------------- #
# Documentopmaak
# --------------------------------------------------------------------------- #
def _stijlen(doc) -> None:
    normaal = doc.styles["Normal"]
    normaal.font.name = LETTERTYPE
    normaal.font.size = Pt(10.5)
    normaal.paragraph_format.space_after = Pt(6)
    normaal.paragraph_format.line_spacing = 1.15
    for naam, grootte, voor in (("Heading 1", 17, 18), ("Heading 2", 13.5, 14), ("Heading 3", 11.5, 10)):
        stijl = doc.styles[naam]
        stijl.font.name = LETTERTYPE
        stijl.font.size = Pt(grootte)
        stijl.font.bold = True
        stijl.font.color.rgb = ACCENT
        stijl.paragraph_format.space_before = Pt(voor)
        stijl.paragraph_format.space_after = Pt(6)
        stijl.paragraph_format.keep_with_next = True
        # Thema-lettertype uitschakelen zodat Calibri overal geldt
        rpr = stijl.element.get_or_add_rPr()
        fonts = rpr.find(qn("w:rFonts"))
        if fonts is not None:
            for attr in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
                fonts.attrib.pop(qn(attr), None)


def _titelpagina(doc, titel: str, ondertitel: str) -> None:
    for _ in range(8):
        doc.add_paragraph()
    p = doc.add_paragraph()
    run = p.add_run(titel)
    run.font.size, run.bold = Pt(30), True
    run.font.color.rgb = ACCENT
    # lijn onder de titel
    ppr = p._p.get_or_add_pPr()
    rand = OxmlElement("w:pBdr")
    onder = OxmlElement("w:bottom")
    for k, v in (("w:val", "single"), ("w:sz", "12"), ("w:space", "6"), ("w:color", "1F4E79")):
        onder.set(qn(k), v)
    rand.append(onder)
    ppr.append(rand)
    p = doc.add_paragraph()
    run = p.add_run(ondertitel)
    run.font.size = Pt(14)
    run.font.color.rgb = RGBColor(0x59, 0x59, 0x59)
    for _ in range(14):
        doc.add_paragraph()
    p = doc.add_paragraph()
    run = p.add_run(f"Project: Molecuul-uitlegger\nDatum: {date.today():%d-%m-%Y}")
    run.font.size = Pt(11)
    run.font.color.rgb = RGBColor(0x59, 0x59, 0x59)
    p.add_run().add_break(WD_BREAK.PAGE)


def _inhoudsopgave(doc) -> None:
    p = doc.add_paragraph()
    run = p.add_run("Inhoudsopgave")
    run.font.size, run.bold = Pt(17), True
    run.font.color.rgb = ACCENT
    _veld(doc.add_paragraph(), 'TOC \\o "1-2" \\h \\z \\u',
          "Klik met de rechtermuisknop en kies 'Veld bijwerken' om de inhoudsopgave te tonen.")
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)


def _voettekst(doc, titel: str) -> None:
    for sectie in doc.sections:
        sectie.different_first_page_header_footer = True  # geen nummer op de titelpagina
        p = sectie.footer.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(f"{titel}  ·  pagina ")
        run.font.size = Pt(8.5)
        run.font.color.rgb = RGBColor(0x7F, 0x7F, 0x7F)
        _veld(p, "PAGE", "1")


def _tabel(doc, rijen: list[list[str]], breedte_cm: float) -> None:
    kop, *data = rijen
    tabel = doc.add_table(rows=len(rijen), cols=len(kop))
    tabel.style = "Table Grid"
    tabel.alignment = WD_TABLE_ALIGNMENT.CENTER
    # Kolombreedte naar verhouding van de tekstlengte (eerste kolom vaak kort)
    lengtes = [max(len(r[i]) if i < len(r) else 0 for r in rijen) for i in range(len(kop))]
    lengtes = [min(max(l, 8), 90) for l in lengtes]
    breedtes = [breedte_cm * l / sum(lengtes) for l in lengtes]
    for r, rij in enumerate(rijen):
        for c in range(len(kop)):
            cel = tabel.cell(r, c)
            cel.width = Cm(breedtes[c])
            tekst = rij[c] if c < len(rij) else ""
            p = cel.paragraphs[0]
            p.paragraph_format.space_after = Pt(2)
            p.paragraph_format.line_spacing = 1.0
            if r == 0:
                _inline(p, tekst, vet=True, kleur=RGBColor(0xFF, 0xFF, 0xFF))
                _arcering(cel._tc.get_or_add_tcPr(), KOP_TABEL)
            else:
                _inline(p, tekst)
                if r % 2 == 0:
                    _arcering(cel._tc.get_or_add_tcPr(), ZEBRA)
            for run in p.runs:
                run.font.size = Pt(9)
    # koprij herhalen op elke pagina
    trpr = tabel.rows[0]._tr.get_or_add_trPr()
    herhaal = OxmlElement("w:tblHeader")
    herhaal.set(qn("w:val"), "true")
    trpr.append(herhaal)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def _codeblok(doc, regels: list[str]) -> None:
    tabel = doc.add_table(rows=1, cols=1)
    tabel.alignment = WD_TABLE_ALIGNMENT.CENTER
    cel = tabel.cell(0, 0)
    _arcering(cel._tc.get_or_add_tcPr(), CODE_ACHTERGROND)
    for i, regel in enumerate(regels):
        p = cel.paragraphs[0] if i == 0 else cel.add_paragraph()
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.line_spacing = 1.0
        run = p.add_run(regel or " ")
        run.font.name = "Consolas"
        run.font.size = Pt(8.5)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def _citaat(doc, tekst: str) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Cm(0.5)
    ppr = p._p.get_or_add_pPr()
    rand = OxmlElement("w:pBdr")
    links = OxmlElement("w:left")
    for k, v in (("w:val", "single"), ("w:sz", "18"), ("w:space", "8"), ("w:color", "1F4E79")):
        links.set(qn(k), v)
    rand.append(links)
    ppr.append(rand)
    _arcering(ppr, ZEBRA)
    _inline(p, tekst)


# --------------------------------------------------------------------------- #
# Omzetten
# --------------------------------------------------------------------------- #
def _cellen(regel: str) -> list[str]:
    return [c.strip() for c in regel.strip().strip("|").split("|")]


def zet_om(md_pad: Path, docx_pad: Path) -> None:
    regels = md_pad.read_text(encoding="utf-8").splitlines()
    titel = next((r[2:].strip() for r in regels if r.startswith("# ")), md_pad.stem)
    ondertitel = {
        "onderzoeksverslag": "Onderzoeksverslag: chemische data en AI-uitleg combineren",
        "leeruitkomsten": "Verantwoording van stories, criteria en leeruitkomsten",
    }.get(md_pad.stem, "")

    doc = Document()
    for sectie in doc.sections:
        sectie.orientation = WD_ORIENT.PORTRAIT
        sectie.left_margin = sectie.right_margin = Cm(2.2)
        sectie.top_margin = sectie.bottom_margin = Cm(2.0)
    tekstbreedte = 21.0 - 2 * 2.2
    _stijlen(doc)
    _titelpagina(doc, titel, ondertitel)
    _inhoudsopgave(doc)

    i = 0
    titel_overgeslagen = False
    while i < len(regels):
        regel = regels[i]
        kaal = regel.strip()
        if kaal.startswith("```"):
            blok = []
            i += 1
            while i < len(regels) and not regels[i].strip().startswith("```"):
                blok.append(regels[i])
                i += 1
            _codeblok(doc, blok)
        elif kaal.startswith("|") and i + 1 < len(regels) and re.match(r"^\s*\|[\s:|-]+\|\s*$", regels[i + 1]):
            rijen = [_cellen(regel)]
            i += 2
            while i < len(regels) and regels[i].strip().startswith("|"):
                rijen.append(_cellen(regels[i]))
                i += 1
            _tabel(doc, rijen, tekstbreedte)
            continue
        elif kaal.startswith("# "):
            if titel_overgeslagen:
                doc.add_heading(kaal[2:], level=1)
            titel_overgeslagen = True  # de titel staat al op de titelpagina
        elif kaal.startswith("## "):
            doc.add_heading(kaal[3:], level=1)
        elif kaal.startswith("### "):
            doc.add_heading(kaal[4:], level=2)
        elif kaal.startswith("#### "):
            doc.add_heading(kaal[5:], level=3)
        elif kaal in ("---", "***"):
            pass
        elif kaal.startswith(">"):
            _citaat(doc, kaal.lstrip("> ").strip())
        elif re.match(r"^\s*[-*] ", regel):
            niveau = (len(regel) - len(regel.lstrip())) // 2
            p = doc.add_paragraph(style="List Bullet 2" if niveau else "List Bullet")
            p.paragraph_format.space_after = Pt(3)
            _inline(p, re.sub(r"^\s*[-*] ", "", regel))
        elif re.match(r"^\s*\d+\. ", regel):
            p = doc.add_paragraph(style="List Number")
            p.paragraph_format.space_after = Pt(3)
            _inline(p, re.sub(r"^\s*\d+\. ", "", regel))
        elif kaal:
            # Opeenvolgende tekstregels horen bij dezelfde alinea
            alinea = [kaal]
            # ...behalve een regel die met een vet label begint, zoals "**Datum:** ..."
            while i + 1 < len(regels) and regels[i + 1].strip() and not re.match(
                    r"^\s*([-*] |\d+\. |#|\||>|```|\*\*)", regels[i + 1]):
                i += 1
                alinea.append(regels[i].strip())
            _inline(doc.add_paragraph(), " ".join(alinea))
        i += 1

    _voettekst(doc, titel)
    doc.save(docx_pad)
    _werk_inhoudsopgave_bij(docx_pad)


def _werk_inhoudsopgave_bij(docx_pad: Path) -> None:
    """Laat Word (indien geïnstalleerd, Windows) de inhoudsopgave invullen. Lukt dat niet,
    dan blijft de tekst 'Veld bijwerken' staan en werkt de gebruiker hem zelf bij in Word."""
    try:
        import win32com.client
    except ImportError:
        return
    word = None
    try:
        word = win32com.client.DispatchEx("Word.Application")
        word.Visible = False
        document = word.Documents.Open(str(docx_pad.resolve()))
        for inhoud in document.TablesOfContents:
            inhoud.Update()
        document.Save()
        document.Close(False)
    except Exception as fout:  # Word niet beschikbaar of pad te lang: geen probleem
        print(f"  (inhoudsopgave niet automatisch bijgewerkt: {fout})")
    finally:
        if word is not None:
            word.Quit()


def main(paden: list[str]) -> int:
    if not paden:
        print(__doc__)
        return 1
    for pad in paden:
        bron = Path(pad)
        doel = bron.with_suffix(".docx")
        zet_om(bron, doel)
        print(f"{bron} -> {doel}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
