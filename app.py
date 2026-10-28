"""
Molecuul-uitlegger - Streamlit-app
==================================

Start:  streamlit run app.py

Invoer: chemische naam (NL of EN), CAS-nummer of SMILES.
Uitvoer: structuur, berekende eigenschappen (RDKit), gemeten fysische eigenschappen
met bronnen (PubChem), GHS H- en P-zinnen, en optioneel AI-uitleg op niveau (Gemini).
"""

import html

import pandas as pd
import streamlit as st

from molecuul import chem, document, ghs, risico, uitleg
from molecuul.pubchem import LABEL_NAAR_GROEP, NietGevondenFout, PubChemFout, bron_prioriteit
from molecuul.rapport import MolecuulRapport, maak_rapport

st.set_page_config(page_title="Molecuul-uitlegger", page_icon="⚗️", layout="wide")
# Extra zekerheid naast toolbarMode = "minimal" in .streamlit/config.toml: geen Deploy-knop tonen.
st.markdown("<style>[data-testid='stAppDeployButton']{display:none !important}</style>", unsafe_allow_html=True)

VOORBEELDEN = {
    "Aspirine": "CC(=O)Oc1ccccc1C(=O)O",
    "Cafeïne": "cafeïne",
    "Ethanol": "ethanol",
    "Zwavelzuur": "zwavelzuur",
    "Paracetamol": "paracetamol",
}
P_GROEPEN = {
    "1": "Algemeen",
    "2": "Preventie",
    "3": "Reactie (bij een ongeval)",
    "4": "Opslag",
    "5": "Verwijdering",
}
BRON_TYPE = {
    0: "Geharmoniseerde EU-indeling (CLP bijlage VI, wettelijk bindend)",
    1: "ECHA C&L Inventory (meldingen door bedrijven in de EU)",
    2: "Overige bron",
}


# --------------------------------------------------------------------------- #
# Gegevens ophalen (gecachet: dezelfde stof wordt niet steeds opnieuw opgevraagd)
# --------------------------------------------------------------------------- #
@st.cache_data(ttl=24 * 3600, show_spinner=False)
def haal_rapport(invoer: str, modus: str, ai_vertaling: bool, sleutel: str | None, max_meetwaarden: int) -> MolecuulRapport:
    vertaler = (lambda naam: uitleg.vertaal_stofnaam(naam, sleutel=sleutel)) if ai_vertaling and sleutel else None
    return maak_rapport(invoer, modus, vertaal_naam=vertaler, max_meetwaarden=max_meetwaarden)


def bron_link(naam: str, url: str | None) -> str:
    return f"[{naam}]({url})" if url else naam


# --------------------------------------------------------------------------- #
# Zijbalk
# --------------------------------------------------------------------------- #
with st.sidebar:
    st.header("Instellingen")
    modus = st.radio(
        "Invoertype",
        ["auto", "naam", "smiles"],
        format_func={"auto": "Automatisch herkennen", "naam": "Chemische naam / CAS", "smiles": "SMILES"}.get,
    )
    niveau = st.selectbox("Niveau van de AI-uitleg", list(uitleg.NIVEAUS), index=1,
                          format_func=lambda n: uitleg.NIVEAUS[n]["label"])
    max_meetwaarden = st.slider(
        "Meetwaarden per eigenschap", 1, 10, 3,
        help="Hoeveel waarden (uit verschillende bronnen) per eigenschap worden getoond. "
             "Gecontroleerde bronnen (HSDB, ICSC) staan altijd bovenaan.",
    )

    st.divider()
    st.subheader("Gemini (AI-uitleg)")
    sleutel = uitleg.api_sleutel()
    if sleutel:
        st.success("API-sleutel gevonden in .env")
    else:
        sleutel = st.text_input(
            "Gemini API-sleutel", type="password",
            help="Niet verplicht. Zonder sleutel werkt alles behalve de AI-uitleg. "
                 "Maak een sleutel aan op https://aistudio.google.com/apikey",
        ) or None
    model = st.text_input("Model", value=uitleg.model_naam())
    ai_vertaling = st.checkbox(
        "AI mag onbekende stofnamen vertalen", value=True,
        help="Als PubChem een (Nederlandse) naam niet kent, vraagt de app Gemini om de Engelse naam. "
             "Het resultaat wordt altijd gecontroleerd in PubChem en gemeld.",
    )

    st.divider()
    st.caption(
        "Gegevens: [PubChem](https://pubchem.ncbi.nlm.nih.gov/) (NIH) · "
        "Berekeningen: [RDKit](https://www.rdkit.org/) · "
        "Uitleg: [Gemini API](https://ai.google.dev/)"
    )


# --------------------------------------------------------------------------- #
# Invoer
# --------------------------------------------------------------------------- #
st.title("⚗️ Molecuul-uitlegger")
st.write(
    "Vul een **stofnaam** (Nederlands of Engels), **CAS-nummer** of **SMILES** in. "
    "Je krijgt de structuur, fysische eigenschappen met bronnen, de H- en P-zinnen "
    "en desgewenst een uitleg op jouw niveau."
)

if "invoer" not in st.session_state:
    st.session_state.invoer = ""

kolommen = st.columns(len(VOORBEELDEN))
for kolom, (label, waarde) in zip(kolommen, VOORBEELDEN.items()):
    if kolom.button(label, use_container_width=True):
        st.session_state.invoer = waarde

with st.form("zoeken"):
    invoer = st.text_input("Stof", key="invoer", placeholder="bijv. cafeïne, 64-17-5 of CC(=O)Oc1ccccc1C(=O)O")
    gezocht = st.form_submit_button("Zoek molecuul", type="primary")

if not invoer.strip():
    st.info("Kies een voorbeeld of typ een stof om te beginnen.")
    st.stop()

try:
    with st.spinner("Gegevens ophalen bij PubChem en berekenen met RDKit..."):
        rapport = haal_rapport(invoer.strip(), modus, ai_vertaling, sleutel, max_meetwaarden)
except chem.OngeldigeSmilesFout as fout:
    st.error(f"**Ongeldige SMILES.** {fout}")
    st.stop()
except NietGevondenFout as fout:
    st.error(f"**Niet gevonden.** {fout}")
    st.stop()
except PubChemFout as fout:
    st.error(f"**PubChem-probleem.** {fout}")
    st.stop()
except ValueError as fout:
    st.error(str(fout))
    st.stop()

# --------------------------------------------------------------------------- #
# Kop + structuur
# --------------------------------------------------------------------------- #
pc = rapport.pubchem or {}
st.header(rapport.titel)
for w in rapport.waarschuwingen:
    st.warning(w)

links, rechts = st.columns([1, 1.3])
with links:
    svg = chem.teken_structuur_svg(rapport.smiles).replace("<svg ", "<svg style='width:100%;height:auto' ", 1)
    st.markdown(
        f"<div style='background:white;border-radius:8px;padding:8px;max-width:420px'>{svg}</div>",
        unsafe_allow_html=True,
    )
    st.caption("2D-structuur getekend met RDKit")
with rechts:
    rd = rapport.rdkit
    st.markdown(
        f"| | |\n|---|---|\n"
        f"| **Molecuulformule** | {rd.formule} |\n"
        f"| **Molmassa (RDKit, berekend)** | {rd.molmassa_g_per_mol} g/mol |\n"
        f"| **Molmassa (PubChem)** | {pc.get('molmassa_g_per_mol', '–')} g/mol |\n"
        f"| **IUPAC-naam** | {pc.get('iupac_naam') or '–'} |\n"
        f"| **CAS-nummer** | {pc.get('cas') or '–'} |\n"
        f"| **SMILES** | `{rd.canonieke_smiles}` |\n"
        f"| **InChIKey** | {pc.get('inchikey') or '–'} |\n"
        f"| **PubChem** | {bron_link('CID ' + str(pc['cid']), pc['url']) if pc else 'niet gevonden'} |"
    )

# GHS-bronkeuze (nodig in meerdere tabbladen)
ghs_index = 0
if rapport.ghs:
    opties = list(range(len(rapport.ghs)))
    ghs_index = st.selectbox(
        "Bron voor de GHS-indeling (H- en P-zinnen)",
        opties,
        format_func=lambda i: f"{rapport.ghs[i].bron.naam} – {rapport.ghs[i].bron.omschrijving or ''}"[:120],
        help="PubChem verzamelt indelingen van meerdere instanties. Standaard staat de wettelijk bindende "
             "EU-indeling bovenaan, daarna ECHA-meldingen van bedrijven.",
    )

tab_fys, tab_ghs, tab_risico, tab_ai, tab_rdkit, tab_bronnen = st.tabs(
    ["🌡️ Fysische eigenschappen", "⚠️ Veiligheid (H/P-zinnen)", "📋 Risk assessment", "🤖 AI-uitleg",
     "🧮 Berekend (RDKit)", "📚 Bronnen"]
)

# --------------------------------------------------------------------------- #
# Fysische eigenschappen
# --------------------------------------------------------------------------- #
with tab_fys:
    if not rapport.fysisch:
        st.info("Geen gemeten fysische eigenschappen gevonden in PubChem.")
    else:
        st.caption("Gemeten waarden zoals gerapporteerd door de oorspronkelijke bron (via PubChem). "
                   "Verschillende bronnen kunnen licht verschillende waarden geven.")
        st.caption(f"{len(rapport.fysisch)} eigenschappen gevonden. Eigenschappen zonder meetwaarde in "
                   "PubChem worden niet getoond.")
        groepen: dict[str, list[str]] = {}
        for eigenschap in rapport.fysisch:
            groepen.setdefault(LABEL_NAAR_GROEP.get(eigenschap, "Overig"), []).append(eigenschap)
        for groep, eigenschappen in groepen.items():
            with st.expander(f"**{groep}** ({len(eigenschappen)})", expanded=True):
                for eigenschap in eigenschappen:
                    st.markdown(f"**{eigenschap}**\n" + "\n".join(
                        f"- {m.waarde} — _{bron_link(m.bron.naam, m.bron.url)}_"
                        for m in rapport.fysisch[eigenschap]
                    ))

# --------------------------------------------------------------------------- #
# GHS
# --------------------------------------------------------------------------- #
with tab_ghs:
    if not rapport.ghs:
        st.warning("Geen GHS-indeling gevonden. Dat betekent **niet** dat de stof veilig is. "
                   "Raadpleeg altijd het veiligheidsinformatieblad (SDS) van de leverancier.")
    else:
        indeling = rapport.ghs[ghs_index]
        st.markdown(f"**Bron:** {bron_link(indeling.bron.naam, indeling.bron.url)}  \n"
                    f"_{BRON_TYPE[bron_prioriteit(indeling.bron)]}_")
        signaal = {"Danger": "GEVAAR", "Warning": "WAARSCHUWING"}.get(indeling.signaalwoord or "", indeling.signaalwoord)
        if signaal:
            kleur = "#c62828" if signaal == "GEVAAR" else "#ef6c00"
            st.markdown(f"<span style='background:{kleur};color:white;padding:4px 12px;border-radius:4px;"
                        f"font-weight:700'>Signaalwoord: {html.escape(signaal)}</span>", unsafe_allow_html=True)
        if indeling.pictogrammen:
            st.markdown(" ".join(
                f"<figure style='display:inline-block;text-align:center;margin:8px'>"
                f"<img src='https://pubchem.ncbi.nlm.nih.gov/images/ghs/{p}.svg' width='72' alt='{p}'>"
                f"<figcaption style='font-size:0.8em'>{p}<br>{ghs.PICTOGRAMMEN.get(p, '')}</figcaption></figure>"
                for p in indeling.pictogrammen
            ), unsafe_allow_html=True)

        st.subheader("H-zinnen (gevarenaanduidingen)")
        heeft_perc = any(h.percentage is not None for h in indeling.h_zinnen)
        st.markdown("\n".join(
            f"- **{h.code}** – {h.tekst}"
            + (f"  \n  <small>{html.escape(h.klasse)}</small>" if h.klasse else "")
            + (f" <small>· {h.percentage:g}% van de meldingen</small>" if h.percentage is not None else "")
            for h in indeling.h_zinnen
        ) or "_Geen H-zinnen in deze indeling._", unsafe_allow_html=True)
        if heeft_perc:
            st.caption("**% meldingen**: aandeel van de bedrijfsmeldingen bij ECHA dat deze H-zin gebruikt. "
                       "Een laag percentage betekent dat slechts een deel van de leveranciers de stof zo indeelt.")

        st.subheader("P-zinnen (voorzorgsmaatregelen)")
        for cijfer, groep in P_GROEPEN.items():
            zinnen = [p for p in indeling.p_zinnen if p.code[1] == cijfer]
            if zinnen:
                st.markdown(f"**{groep}**")
                st.markdown("\n".join(f"- **{p.code}** – {p.tekst}" for p in zinnen))
        st.caption(f"Teksten: officiële GHS-codelijst via [PubChem]({ghs.GHS_BRON_URL}). "
                   "Op etiketten in de EU staan de Nederlandse CLP-teksten; de codes zijn identiek.")

# --------------------------------------------------------------------------- #
# Risk assessment (Hazardous Substance Risk Assessment als Word-document)
# --------------------------------------------------------------------------- #
with tab_risico:
    st.markdown(
        "Maak een ingevulde **Hazardous Substance Risk Assessment** voor je labverslag. Alles hieronder is "
        "automatisch voorgesteld uit de PubChem-gegevens met vaste regels (geen AI). **Controleer en vul aan** "
        "voor jouw proef; het document wordt in het Engels gemaakt, zoals het sjabloon."
    )
    voorstel = risico.stel_voor(rapport, ghs_index)
    k = f"ra_{rapport.smiles}_{ghs_index}_"  # nieuwe stof of GHS-bron = nieuw voorstel
    pbm_namen = [p.item for p in voorstel.pbm]

    with st.form(k + "form"):
        st.markdown("**Proefgegevens**")
        c1, c2, c3 = st.columns([1, 2, 2])
        ref = c1.text_input("Ref.", "001", key=k + "ref")
        locatie = c2.text_input("Location/s", placeholder="bijv. Lab 2.14, zuurkast 3", key=k + "loc")
        hoeveelheid = c3.text_input("Quantity used", placeholder="bijv. 50 mL, 2 g", key=k + "hoev")
        stof = st.text_input("Substance(s) & Manufacturer/s", voorstel.stof_en_fabrikant + ", supplier: ",
                             key=k + "stof")
        taak = st.text_area("Task/s & Description", placeholder="bijv. Titratie van azijnzuur met 0,1 M NaOH",
                            key=k + "taak")
        personen = st.multiselect("Persons at Risk", risico.PERSONEN, voorstel.personen + ["Students"], key=k + "pers")

        st.markdown("**Gevaren (voorgesteld)**")
        c1, c2 = st.columns(2)
        pictos = c1.multiselect("Hazard pictograms", list(risico.PICTOGRAM_NAMEN), voorstel.pictogrammen,
                                format_func=lambda p: f"{p} – {risico.PICTOGRAM_NAMEN[p]}", key=k + "pic")
        typen = c2.multiselect("Hazard Type", risico.GEVARENTYPEN, voorstel.gevarentypen, key=k + "type")
        routes = c1.multiselect("Main Route of Exposure", risico.ROUTES, voorstel.routes, key=k + "route")
        pbm_keuze = c2.multiselect("Personal Protective Equipment", pbm_namen,
                                   [p.item for p in voorstel.pbm if p.nodig], key=k + "pbm")

        st.markdown("**Beheersmaatregelen (voorgesteld, één per regel)**")
        technisch = st.text_area("Engineering Measures", "\n".join(voorstel.technische_maatregelen), key=k + "tech")
        hygiene = st.text_area("Hygiene Measures", "\n".join(voorstel.hygiene), key=k + "hyg")

        st.markdown("**Risicobeoordeling en ondertekening**")
        c1, c2, c3, c4 = st.columns(4)
        ernst = c1.selectbox("Severity", [1, 2, 3], voorstel.ernst - 1,
                             format_func=lambda n: f"{n} – {risico.ERNST_LABEL[n]}", key=k + "ernst",
                             help="Voorstel op basis van de zwaarste H-zin.")
        kans = c2.selectbox("Likelihood", [1, 2, 3], voorstel.kans - 1,
                            format_func=lambda n: f"{n} – {risico.KANS_LABEL[n]}", key=k + "kans",
                            help="Kans op schade mét de maatregelen hierboven. Hangt af van jouw proef.")
        beoordelaar = c3.text_input("Assessed by", key=k + "door")
        datum = c4.text_input("Date", voorstel.datum, key=k + "datum")
        gemaakt = st.form_submit_button("📄 Maak risk assessment (.docx)", type="primary")

    if gemaakt:
        b = voorstel
        b.ref, b.locatie, b.hoeveelheid, b.stof_en_fabrikant, b.taak = ref, locatie, hoeveelheid, stof, taak
        b.personen, b.pictogrammen, b.gevarentypen, b.routes = personen, pictos, typen, routes
        for p in b.pbm:
            p.nodig = p.item in pbm_keuze
        b.technische_maatregelen = [r.strip() for r in technisch.splitlines() if r.strip()]
        b.hygiene = [r.strip() for r in hygiene.splitlines() if r.strip()]
        b.ernst, b.kans, b.beoordelaar, b.datum = ernst, kans, beoordelaar, datum
        st.session_state[k + "docx"] = (document.maak_docx(b), b.risicoscore, b.risiconiveau)

    if k + "docx" in st.session_state:
        inhoud, score, niveau_risico = st.session_state[k + "docx"]
        st.success(f"Risk assessment gemaakt. Risicoscore: {score} ({niveau_risico}).")
        st.download_button(
            "⬇️ Download risk assessment (.docx)", inhoud,
            file_name=f"Risk_assessment_{rapport.titel}.docx".replace(" ", "_"),
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            type="primary",
        )
        st.caption("Open het bestand in Word, selecteer alles (Ctrl+A), kopieer en plak het in je labverslag. "
                   "Controleer altijd het actuele veiligheidsinformatieblad (SDS) van de leverancier.")

# --------------------------------------------------------------------------- #
# AI-uitleg
# --------------------------------------------------------------------------- #
with tab_ai:
    st.info("De uitleg is **gegenereerd door AI** (Google Gemini) op basis van de gegevens in deze app. "
            "De AI krijgt de opdracht geen getallen te verzinnen en bronnen te noemen, maar kan fouten maken. "
            "Controleer belangrijke informatie in de tabbladen hiernaast en gebruik voor veiligheid altijd het SDS.")
    if not sleutel:
        st.warning("Vul een Gemini API-sleutel in de zijbalk in (of in .env) om AI-uitleg te genereren.")
    else:
        cache_sleutel = (rapport.smiles, niveau, ghs_index, model)
        uitlegcache = st.session_state.setdefault("uitleg", {})
        if st.button(f"Genereer uitleg ({uitleg.NIVEAUS[niveau]['label']})", type="primary"):
            try:
                with st.spinner("Gemini schrijft de uitleg..."):
                    uitlegcache[cache_sleutel] = uitleg.genereer_uitleg(
                        rapport, niveau, ghs_index, model=model, sleutel=sleutel)
            except uitleg.UitlegFout as fout:
                st.error(fout.bericht)
                if fout.technisch:
                    with st.expander("Technische details"):
                        st.code(fout.technisch)
        resultaat = uitlegcache.get(cache_sleutel)
        if resultaat:
            st.markdown(resultaat.tekst)
            st.markdown("**Bronnen**")
            st.markdown("\n".join(
                f"- **[{bid}]** {bron_link(b['naam'], b['url'])}" + (f" – {b['omschrijving']}" if b.get("omschrijving") else "")
                for bid, b in resultaat.bronnen.items()
            ))
            st.caption(f"Model: {resultaat.model} · niveau: {resultaat.niveau} · temperatuur: {uitleg.TEMPERATUUR}"
                       + (" · eerder gegenereerd (uit cache, kost geen quotum)" if resultaat.uit_cache else ""))
            with st.expander("Bekijk de prompt die naar Gemini is gestuurd (transparantie)"):
                st.markdown("**Systeeminstructie**")
                st.code(uitleg.SYSTEEM_INSTRUCTIE, language="text")
                st.markdown("**Prompt met gegevens**")
                st.code(resultaat.prompt, language="text")
            st.download_button("Download uitleg (.md)", resultaat.tekst,
                               file_name=f"uitleg_{rapport.titel}_{niveau}.md".replace(" ", "_"))

# --------------------------------------------------------------------------- #
# RDKit
# --------------------------------------------------------------------------- #
with tab_rdkit:
    st.caption("Deze waarden zijn **berekend** uit de structuur met RDKit, niet gemeten. "
               "logP (Crippen) en TPSA zijn schattingsmodellen.")
    st.dataframe(pd.DataFrame(
        [{"Eigenschap": chem.BETEKENIS.get(k, k), "Waarde": v} for k, v in rapport.rdkit.als_dict().items()
         if k != "canonieke_smiles"]
    ).astype(str), hide_index=True, use_container_width=True)

# --------------------------------------------------------------------------- #
# Bronnen
# --------------------------------------------------------------------------- #
with tab_bronnen:
    bronnen = {}
    if pc:
        bronnen[f"PubChem CID {pc['cid']}"] = pc["url"]
    for waarden in rapport.fysisch.values():
        for m in waarden:
            bronnen.setdefault(m.bron.naam, m.bron.url)
    for indeling in rapport.ghs:
        bronnen.setdefault(f"{indeling.bron.naam} (GHS)", indeling.bron.url)
    bronnen["RDKit – open-source cheminformatica"] = "https://www.rdkit.org/docs/"
    bronnen["GHS H/P-codelijst (PubChem, VN-GHS Rev. 10)"] = ghs.GHS_BRON_URL
    st.markdown("\n".join(f"- {bron_link(n, u)}" for n, u in bronnen.items()))

st.divider()
st.caption("Deze app is een leermiddel. Gebruik voor werken met chemicaliën altijd het actuele "
           "veiligheidsinformatieblad (SDS) van de leverancier en volg de instructies van je instelling.")
