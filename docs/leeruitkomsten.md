# Verantwoording: stories, criteria en leeruitkomsten

Dit document koppelt elke eis uit de backlog aan concreet bewijs in het project.
Stukken tussen **[ ]** vul je zelf in. Het gaat om jouw eigen keuzes en reflectie, en die kan alleen jij beschrijven.

---

## Deel A: User stories en criteria

### US: SMILES inlezen met RDKit

| Criterium | Status | Bewijs |
|---|---|---|
| AC1: werkend script, via Claude Code, dat RDKit importeert | ✅ | `scripts/us1_smiles_naar_molmassa.py` |
| AC2: leest minimaal één teststof in (aspirine `CC(=O)Oc1ccccc1C(=O)O`) | ✅ | Aspirine, cafeïne en ethanol staan standaard in het script |
| AC3: berekent de molmassa en print die netjes in de terminal | ✅ | `docs/testresultaten/us1_en_unittests_output.txt` (180,16 g/mol, gecontroleerd tegen PubChem) |
| KC1: voorbeelden uit de officiële RDKit-documentatie | ✅ | De docstring van het script verwijst naar *Getting Started* en de API-documentatie van `Descriptors` en `rdMolDescriptors` |
| KC2: geen crash bij een ongeldige SMILES, maar een nette foutmelding | ✅ | `C1CC(` en `XYZ` in de testuitvoer, plus de unittest `test_ongeldige_smiles_geeft_nette_fout` |
| KC3: helder gedocumenteerd en makkelijk opnieuw uit te voeren | ✅ | Docstring met gebruiksvoorbeelden, README hoofdstuk "Snel starten" |

### LS: RDKit-data naar Gemini, uitleg op niveau

| Criterium | Status | Bewijs |
|---|---|---|
| AC1: getest met een prompt waarin de RDKit-data dynamisch wordt meegegeven | ✅ | `molecuul/uitleg.py` → `bouw_prompt()`; elke prompt staat volledig in `docs/testresultaten/*.md`; unittest `test_data_dynamisch_in_prompt` |
| AC2: een variabele voor het niveau (leek/expert) | ✅ | Parameter `niveau` met vier opties (`leek`, `scholier`, `student`, `expert`), `--niveau` / `--alle-niveaus`, keuzemenu in de app |
| AC3: een werkend testantwoord waarin Gemini de data correct vertaalt | ✅ | 5 testantwoorden in `docs/testresultaten/`: ethanol op alle 4 de niveaus, cafeïne op leekniveau. Beoordeling in onderzoeksverslag §7.1: geen verzonnen getallen, alle H-zinnen genoemd |
| KC1: instructies en context logisch opgebouwd | ✅ | Onderzoeksverslag §5.1–5.2: systeeminstructie en data gescheiden, JSON met eenheden, berekend en gemeten apart |
| KC2: bewust nagedacht over het meesturen van parameters | ✅ | Onderzoeksverslag §5.2: niveau als apart blok, temperatuur 0,2, model via `GEMINI_MODEL` |
| KC3: API-fouten netjes opgevangen | ✅ | `UitlegFout`, reservemodellen en wachten volgens Google (onderzoeksverslag §6). Getest met de echte API: ongeldige sleutel (400), onbekend model (404), overbelasting (503) en quotum (429) gaven allemaal een nette melding |

### Onderzoeksstory: chemische data en AI-uitleg combineren

| Criterium | Status | Bewijs |
|---|---|---|
| AC1: kort onderzoeksverslag met bevindingen | ✅ | `docs/onderzoeksverslag.md` |
| AC2: werkend voorbeeld van stof → RDKit → Gemini → tekst | ✅ | `app.py` (tabblad AI-uitleg), `scripts/ls_gemini_test.py` en de testantwoorden in `docs/testresultaten/` |
| AC3: de gebruikte aanpak is beschreven | ✅ | Onderzoeksverslag §2: deskresearch, prototypen, prompts testen, unittests |
| KC1: promptopbouw en optimalisatie gedocumenteerd | ✅ | Onderzoeksverslag §5 |
| KC2: betrouwbare bronnen gebruikt | ✅ | Onderzoeksverslag §12: RDKit- en PubChem-documentatie, Google AI-documentatie, CLP, GHS, vakliteratuur |
| KC3: onderbouwd waarom Gemini past | ✅ | Onderzoeksverslag §8: vergelijking met de OpenAI-API en lokale modellen |

---

## Deel B: Leeruitkomsten

| LU | Leeruitkomst | Niveau | Argumentatie en bewijs |
|---|---|---|---|
| **LU 1** | AI-impact op de beroepspraktijk analyseren en evalueren | [zelf invullen] | In het onderzoeksverslag (§10) analyseer ik wat een tool als deze betekent voor laboranten, docenten en studenten: tijdwinst en uitleg op niveau, tegenover het risico dat AI-tekst blind wordt vertrouwd en data van oplossingen voor zuivere stof wordt aangezien. Dat laatste risico heb ik concreet aangetoond bij zwavelzuur (§4.2). **Bewijs:** onderzoeksverslag §4.2 en §10. **[Eigen aanvulling: bijvoorbeeld een kort gesprek met een docent of laborant over hoe zij nu H/P-zinnen opzoeken.]** |
| **LU 2** | Praktijkgerichte AI-oplossing ontwerpen, realiseren en presenteren | [zelf invullen] | Ik heb een werkende app ontworpen en gebouwd die drie bronnen combineert: RDKit voor berekeningen, PubChem voor meetwaarden en GHS, en Gemini voor de uitleg. De architectuur volgt het principe "data uit bronnen, AI alleen voor formulering". De app werkt ook zonder AI. De oplossing is direct bruikbaar in de praktijk: ze maakt een ingevulde *Hazardous Substance Risk Assessment* (.docx) in het format van het schoolsjabloon, klaar om in een labverslag te plakken. **Bewijs:** `app.py`, de map `molecuul/` (o.a. `risico.py` en `document.py`), README (architectuur), onderzoeksverslag §8b, unittests. **[Presentatie: link naar je slides of demo-opname toevoegen.]** |
| **LU 3** | Ethiek en verantwoord AI-gebruik beoordelen | [zelf invullen] | Ik heb de AI-uitvoer kritisch beoordeeld: 5 antwoorden regel voor regel vergeleken met de data. Daarbij vond ik een fout die uit de prompt kwam (berekend versus gemeten) en die heb ik opgelost (onderzoeksverslag §7.1 en §5.3). Voor de risicobeoordeling heb ik bewust gekozen voor controleerbare regels in plaats van AI, omdat het een veiligheidsdocument is (onderzoeksverslag §8b). Daarnaast heb ik concrete maatregelen genomen tegen hallucinatie en misleiding: de AI mag geen getallen verzinnen, er staan bron-ID's bij elke uitspraak, berekend en gemeten worden apart benoemd, de AI-tekst is gelabeld, de prompt is in te zien, "geen GHS-data" wordt niet als "veilig" gepresenteerd, AI-vertalingen van namen worden gecontroleerd, en ik heb nagedacht over de privacy van de gratis Gemini-laag. **Bewijs:** onderzoeksverslag §9, `SYSTEEM_INSTRUCTIE` in `molecuul/uitleg.py`, de disclaimer in de app. |
| **LU 4** | AI-tools en technieken gebruiken | [zelf invullen] | Ik heb meerdere AI-tools en -technieken gebruikt: **Claude Code** als programmeerassistent (bijvoorbeeld voor het genereren van het RDKit-script, zoals AC1 van de US vraagt), de **Gemini API** met systeeminstructies, gestructureerde context (JSON), temperatuur, retry/backoff en een niveau-parameter, en **prompt engineering** met grounding, bronverwijzingen en scheiding tussen data en instructie. **Bewijs:** `molecuul/uitleg.py`, `scripts/ls_gemini_test.py`, `docs/testresultaten/`, onderzoeksverslag §5. **[Eigen aanvulling: welke prompts gaf jij aan Claude Code en wat stuurde je bij?]** |
| **LU 5** | Zelfstandig en zelfsturend werken | [zelf invullen] | Ik heb het project zelf gestuurd: vooraf een backlog met stories, acceptatie- en kwaliteitscriteria opgesteld, tussentijds getest en bijgestuurd (meer fysische eigenschappen, een risk assessment voor labverslagen), zelf keuzes gemaakt over scope en techniek, en problemen opgelost tot en met de online publicatie. Zie de toelichting hieronder. **Bewijs:** de backlog, de versiegeschiedenis op GitHub (`Noahkloos/molecul-info`), onderzoeksverslag §4.4 en §6. |

## Toelichting LU 5: zelfstandig en zelfsturend werken

### Hoe ik het project heb aangepakt

Ik ben begonnen met een backlog: een user story, een leerstory en een onderzoeksstory, elk met acceptatie- en kwaliteitscriteria, plus de vijf leeruitkomsten die ik moest aantonen. Met die backlog als opdracht heb ik Claude Code de eerste versie laten bouwen. Zo had ik vanaf het begin een duidelijk eindbeeld waarmee ik het resultaat kon controleren, en hoefde ik niet alleen te vertrouwen op wat de AI opleverde.

Daarna heb ik in korte rondes gewerkt: de app gebruiken, kijken wat ontbrak of niet klopte, en gericht bijsturen. Op die manier heb ik de volgende stappen zelf bepaald:

- **Meer fysische eigenschappen.** De eerste versie toonde 12 eigenschappen. Voor een chemicus is dat te weinig, dus ik heb gevraagd om uitbreiding. Nu zijn er tot 30 eigenschappen in zes groepen.
- **Een risk assessment voor het labverslag.** Tijdens het werken zag ik dat de app ook nuttig kon zijn bij iets wat ik bij elke proef moet doen: een *Hazardous Substance Risk Assessment* invullen. Ik heb ons schoolsjabloon als voorbeeld gegeven. Nu maakt de app een ingevuld Word-document in dat format.
- **Documentatie in Word.** Het verslag en deze verantwoording heb ik als opgemaakte Word-documenten laten maken, zodat ze geschikt zijn om in te leveren.

### Keuzes die ik zelf heb gemaakt

- **Gemini in plaats van ChatGPT.** In mijn leerstory stond eerst "ChatGPT", maar de criteria noemden Gemini. Ik heb gekozen voor Gemini, vooral vanwege de gratis laag en Google AI Studio (onderbouwing in onderzoeksverslag §8).
- **PubChem als bron, AI alleen voor de formulering.** Alle feiten komen uit RDKit en PubChem, met bronvermelding. Voor de risk assessment heb ik bewust gekozen voor vaste regels in plaats van AI, omdat het een veiligheidsdocument is.
- **Scope bewaken.** De H- en P-zinnen staan in de officiële Engelse GHS-tekst. Een Nederlandse vertaling vond ik niet nodig, omdat de codes gelijk zijn en het sjabloon ook Engels is. Zo bleef er tijd over voor functies die meer opleverden.
- **Eigen hosting.** Ik wilde geen Streamlit-knop in de app, maar het project zelf beheren via GitHub en zelf online zetten.

### Problemen die ik heb opgelost

| Probleem | Wat ik deed | Wat ik ervan leerde |
|---|---|---|
| RDKit startte niet door een te lang Windows-pad | De Python-omgeving op een kort pad gezet | Foutmeldingen lezen in plaats van gokken; de omgeving telt ook mee |
| H225 (licht ontvlambaar) ontbrak bij ethanol | Oorzaak gevonden (de notatie `> 99.9%`) en een test toegevoegd | Uitvoer altijd controleren tegen de bron; een test voorkomt herhaling |
| Nederlandse namen zoals "cafeïne" niet gevonden | Vaste vertalingen plus een AI-vertaling die in PubChem wordt gecontroleerd | AI kan helpen, mits het resultaat wordt gecontroleerd |
| Gemini gaf HTTP 503 en 429 | Zelf de oorzaak laten uitzoeken: de gratis laag staat 5 verzoeken per minuut en 20 per dag toe. Daarna reservemodellen, quotumherkenning en een cache toegevoegd | Een gratis API heeft grenzen waar je in je ontwerp rekening mee moet houden |
| Git was nieuw voor mij | Git geïnstalleerd en geleerd. Ik maakte eerst een repository in de verkeerde map en gebruikte een verkeerde repositorynaam. Ik ben gestopt voordat er iets fout ging, heb het hersteld en het project op GitHub gezet | Bij een fout eerst stoppen en uitzoeken wat er gebeurde, dan pas verder |
| De app werkte niet op Vercel | Uitgezocht waarom (Vercel ondersteunt geen Streamlit) en overgestapt naar Streamlit Community Cloud. Daar de RDKit-fout opgelost met `packages.txt` | Eerst controleren of een platform past bij de technologie |

### Wat ik de volgende keer anders zou doen

1. **Het hostingplatform eerder kiezen.** Ik had vooraf moeten onderzoeken of Vercel Streamlit ondersteunt. Dat had een mislukte deployment gescheeld.
2. **Vanaf dag één in een vaste map met Git werken** en na elke werkende stap committen. Dan staat de geschiedenis van het project vast en is terugdraaien makkelijker.
3. **Zuinig zijn met het API-quotum.** Testen met de prompt alleen (`--droog`) en pas daarna echte aanroepen doen, of voor intensief gebruik een betaalde sleutel regelen.
4. **Volledige input meteen aanleveren.** Ik gaf maar een deel van het risk-assessmentsjabloon, waardoor de onderste helft is ingevuld met een eigen indeling. Met het hele sjabloon was dat in één keer goed gegaan.
5. **De AI-uitleg laten controleren door een vakdocent**, vooral op redeneringen. Daar zaten de laatste fouten in, niet in de getallen.

> **Let op bij het inleveren:** vermeld dat de code met hulp van Claude Code is gemaakt. Beschrijf daarbij wat jij zelf hebt bepaald, getest en beoordeeld. Dat is het eerlijkst en het is bovendien sterk bewijs voor LU 3 en LU 4.
