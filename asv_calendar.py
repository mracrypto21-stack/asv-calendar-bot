import os
import re
import json
import urllib.request
import ssl
from datetime import datetime, timedelta
import requests

# Infografikas/dashboard ģenerators (vienā direktorijā ar šo skriptu)
try:
    import asv_dashboard
    HAS_INFOGRAPHIC = True
except Exception as _e:  # pragma: no cover
    asv_dashboard = None
    HAS_INFOGRAPHIC = False

def load_token() -> str:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        with open("/root/.hermes/.env", "r", encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith("TELEGRAM_BOT_TOKEN="):
                    token = line.strip().split("=", 1)[1].strip().strip("'").strip('"')
                    break
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN nav atrasts .env failā")
    return token

TELEGRAM_BOT_TOKEN = load_token()
TELEGRAM_CHAT_ID = "1494676964"

DESCRIPTIONS = {
    # Rūpniecība un biznesa indeksi
    "Empire State Manufacturing Index": "Ņujorkas reģiona rūpniecības aktivitātes indekss. Vērtība virs 0 norāda uz nozares izaugsmi, bet zem 0 — uz kontrakciju; tas bieži ir pirmais mēneša signāls par ražošanas sektora stāvokli.",
    "Philly Fed Manufacturing Index": "Filadelfijas reģiona ražošanas sektora indekss. Vērtība virs 0 nozīmē aktivitātes pieaugumu, zem 0 — sarukumu; indekss kalpo kā visas ASV rūpniecības veselības barometrs.",
    "Chicago PMI": "Čikāgas reģiona biznesa vides indekss, kas kalpo kā indikators visas valsts rūpniecībai. Vērtība virs 50 nozīmē izaugsmi, zem 50 — sarukumu.",
    "ISM Manufacturing PMI": "Svarīgākais ASV rūpniecības indekss. Vērtība virs 50 nozīmē, ka nozare paplašinās, zem 50 — ka sarūk; spēcīgs rādītājs parasti atbalsta dolāru.",
    "ISM Services PMI": "Pakalpojumu sektora aktivitātes rādītājs, kas veido lielāko daļu no ASV ekonomikas. Virs 50 nozīmē izaugsmi, zem 50 — sarukumu.",
    "S&P Global Manufacturing PMI": "Privātā sektora ražošanas aktivitātes indekss. Virs 50 nozīmē ekspansiju, zem 50 — kontrakciju; tā ir pirmā mēneša signāls par rūpniecību.",
    "S&P Global Services PMI": "Pakalpojumu sektora aktivitātes indekss no privātā sektora skata. Virs 50 nozīmē ekspansiju, zem 50 — kontrakciju.",
    "Final Manufacturing PMI": "Precizētais rūpniecības aktivitātes indekss. Virs 50 nozīmē izaugsmi, zem 50 — sarukumu.",
    "Final Services PMI": "Precizētais pakalpojumu sektora aktivitātes indekss. Virs 50 nozīmē izaugsmi, zem 50 — sarukumu.",
    "Flash Manufacturing PMI": "Rūpniecības sektora provizoriskais aktivitātes vērtējums. Virs 50 nozīmē ekspansiju, zem 50 — kontrakciju.",
    "Flash Services PMI": "Pakalpojumu sektora provizoriskais aktivitātes vērtējums. Virs 50 nozīmē ekspansiju, zem 50 — kontrakciju.",
    "Factory Orders": "Rūpniecības pasūtījumu apjoma izmaiņas, kas raksturo pieprasījumu ražošanas sektorā. Pieaugums liecina par ekonomikas izaugsmi un var stiprināt dolāru.",
    "Durable Goods Orders": "Ilgtermiņa preču pasūtījumi. Atspoguļo uzņēmumu pieprasījumu un investīciju noskaņojumu ekonomikā.",
    "Industrial Production": "Rūpniecības produkcijas apjoma izmaiņas. Pieaugums liecina par ražošanas sektora izaugsmi un ekonomikas tempu.",

    # Nodarbinātība un darba tirgus
    "Non-Farm Employment Change": "Jauno darba vietu skaits ārpus lauksaimniecības — ietekmīgākais darba tirgus rādītājs. Spēcīgs pieaugums stiprina dolāru un dod Fed iespēju noturēt augstākas likmes.",
    "ADP Non-Farm Employment Change": "Privātā sektora nodarbinātības ziņojums. Analītiķi to uztver kā priekšskatījumu oficiālajam NFP skaitlim.",
    "ADP Weekly Employment Change": "Privātā sektora iknedēļas nodarbinātības izmaiņas. Rāda darba tirgus tempu nedēļas griezumā un palīdz prognozēt oficiālos datus.",
    "Unemployment Rate": "ASV bezdarba līmenis. Zemāks par gaidīto liecina par stipru darba tirgu un var mudināt Fed saglabāt augstākas procentu likmes.",
    "Unemployment Claims": "Iknedēļas jauno bezdarbnieku pieteikumu skaits. Pieteikumi zem aptuveni 250 000 nozīmē stabilu darba tirgu, savukārt straujš pieaugums var liecināt par tā vājināšanos.",
    "Initial Jobless Claims": "Iknedēļas jauno bezdarbnieku pieteikumu skaits. Rādītājs, kas uzrauga ASV darba tirgus stabilitāti un iespējamo vājināšanos — pieteikumi zem aptuveni 250 000 liecina par stabilu tirgu.",
    "Continuing Jobless Claims": "Ilgstoši bezdarbnieku pieteikumi. Pieaugums liecina, ka bezdarbniekiem arvien grūtāk atrast darbu.",

    # Mājokļu tirgus
    "NAHB Housing Market Index": "Būvnieku konfidences indekss. Vērtība zem 50 norāda uz pesimistisku būvniecības nozares vērtējumu, virs 50 — uz optimistisku.",
    "Building Permits": "Izsniegto būvatļauju skaits. Apjoms virs aptuveni 1,3 miljona liecina par stabilu būvniecības tirgu; rāda nākotnes aktivitāti un investīcijas.",
    "Housing Starts": "Jaunu mājokļu būvniecības sākumu skaits. Apjoms virs aptuveni 1,4 miljona norāda uz veselīgu mājokļu tirgu un būvnieku pārliecību.",
    "Pending Home Sales": "Noslēgto mājokļu pirkuma līgumu skaits. Pieaugums norāda uz aktivitāti nekustamā īpašuma tirgū un parasti apsteidz faktiskos pārdošanas rādītājus.",
    "Existing Home Sales": "Esošo mājokļu pārdošanas apjoms. Rāda reālo pieprasījumu mājokļu tirgū un tā ietekmi uz ekonomiku.",
    "New Home Sales": "Jauno mājokļu pārdošanas apjoms. Sensitīvs rādītājs par mājokļu tirgus pieprasījumu un patērētāju pirktspēju.",

    # Inflācija un Centrālā banka
    "FOMC Meeting Minutes": "ASV Federālās rezerves sanāksmes protokols. Atklāj amatpersonu diskusijas par procentu likmēm — tirgi meklē signālus par turpmāko monetārās politikas virzienu.",
    "CPI": "Patēriņa cenu indekss — galvenais ASV inflācijas rādītājs. Augstāks par prognozēm var pamudināt Fed celt procentu likmes, kas parasti stiprina dolāru.",
    "Core CPI": "Pamatinflācija bez pārtikas un enerģijas cenām. Rāda stabilāku cenu tendenci un ir galvenais Fed likmju lēmumu atslēgas rādītājs.",
    "PPI": "Ražotāju cenu indekss — cenu izmaiņas ražošanas līmenī. Pieaugums bieži tiek pārnests uz patēriņa cenām un var signalizēt par inflācijas spiedienu.",
    "Core PPI": "Ražotāju pamatinflācija bez pārtikas un enerģijas. Kalpo kā priekšlaicīgs inflācijas signāls un ietekmē Fed likmju gaidas.",
    "PCE Price Index": "Personīgo patēriņa izdevumu cenu indekss — Federālās rezerves iecienītais inflācijas rādītājs likmju lēmumiem.",
    "Core PCE Price Index": "Pamata PCE inflācija bez pārtikas un enerģijas — Fed galvenais mērķa rādītājs likmju politikā.",
    "Crude Oil Inventories": "Jēlnaftas krājumu izmaiņas ASV. Ietekmē energoresursu un degvielas cenas, kā arī naftas uzņēmumu akcijas.",
    "10-Year Treasury Auction": "ASV 10 gadu obligāciju izsole. Rāda investoru pieprasījumu pēc valsts parāda un netieši ilgtermiņa procentu likmju gaidas.",

    # Runas un paziņojumi
    "FOMC Member Barr Speaks": "Fed pārstāvja Bara uzruna par ekonomikas stāvokli un banku regulējumu. Tirgi vēro jebkādas norādes par monetārās politikas virzienu.",
    "FOMC Member Waller Speaks": "Fed pārstāvja Vollera viedoklis par procentu likmēm un monetārās politikas virzienu. Jebkurš paziņojums var kustināt tirgus.",
    "Fed Chair Powell Speaks": "ASV Centrālās bankas vadītāja Džeroma Pauela uzruna par ekonomiku un monetāro politiku — viens no ietekmīgākajiem notikumiem tirgos.",

    # Patērētāji un ekonomikas izaugsme
    "Retail Sales": "Mazumtirdzniecības apjomu izmaiņas — galvenais patērētāju tēriņu rādītājs. Stiprs pieaugums liecina par ekonomikas izaugsmi un var stiprināt dolāru.",
    "Core Retail Sales": "Mazumtirdzniecība bez automašīnām un degvielas. Rāda stabilāku patērētāju tēriņu tendenci un kopējo patēriņa veselību.",
    "Consumer Confidence": "Patērētāju konfidences indekss. Augstāka pārliecība parasti nozīmē lielākus tēriņus un ekonomikas atbalstu; indekss ietekmē arī tirgus noskaņojumu.",
    "Michigan Consumer Sentiment": "Patērētāju noskaņojuma galējais indekss, kas raksturo mājsaimniecību gatavību tērēt un ekonomikas uztveri.",
    "Consumer Credit": "Patēriņa kredītu apjoma izmaiņas. Pieaugums norāda, ka patērētāji ir gatavi tērēt ar aizņemto līdzekļu palīdzību.",
    "NFIB Small Business Index": "Mazo uzņēmumu optimismu indekss. Rāda mazo biznesu noskaņojumu — svarīgu darba vietu radītāju ASV ekonomikā.",
    "GDP": "Iekšzemes kopprodukta izmaiņas — visaptverošākais ekonomikas izaugsmes rādītājs. Spēcīgs pieaugums stiprina dolāru un samazina Fed stimulu nepieciešamību.",
    "Trade Balance": "Ārējās tirdzniecības bilance. Lielāks eksports pret importu atbalsta dolāru un ekonomikas izaugsmi.",
    "Wholesale Inventories": "Vairumtirdzniecības krājumu izmaiņas. Rāda pieprasījumu un ražošanas tempu; lieli krājumi var liecināt par pieprasījuma vājināšanos.",
    "Business Inventories": "Uzņēmumu krājumu izmaiņas. Rāda, vai pieprasījums seko ražošanai, un palīdz novērtēt GDP komponenti.",
    "Jobless Claims": "Bezdarba pieteikumi. Zems skaits liecina par stabilu darba tirgu, pieaugums — par vājināšanos.",
}

def fetch_forexfactory_calendar():
    url = "https://r.jina.ai/https://www.forexfactory.com/calendar"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    ctx = ssl._create_unverified_context()
    r = urllib.request.urlopen(req, context=ctx, timeout=30)
    return r.read().decode("utf-8", errors="replace")

def parse_us_events(text):
    lines = text.split('\n')
    us_events = {}
    current_date = None

    for line in lines:
        date_match = re.search(r'(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+(Aug|Sep|Oct|Nov|Dec|Jan|Feb|Mar|Apr|May|Jun|Jul)\s+\d+', line)
        if date_match:
            current_date = date_match.group(0)
            continue

        if not line.startswith('|') or not current_date:
            continue

        parts = [p.strip() for p in line.split('|')]
        if len(parts) < 5:
            continue

        currency = parts[2].strip()
        event_raw = parts[4].strip()

        if currency == 'USD' and event_raw:
            event_clean = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', event_raw)
            event_clean = re.sub(r'!\[\]\([^\)]+\)', '', event_clean).strip()

            if event_clean and event_clean not in ['', 'Actual', 'Forecast', 'Previous']:
                if current_date not in us_events:
                    us_events[current_date] = []
                us_events[current_date].append(event_clean)

    return us_events

IMPORTANT_KEYWORDS = [
    'FOMC', 'CPI', 'PMI', 'NFP', 'Employment', 'GDP', 'Fed',
    'Empire State', 'Housing', 'Permits', 'Philly Fed', 'Jobless',
    'Claims', 'Unemployment', 'Retail Sales', 'Durable Goods',
    'Consumer Confidence', 'Pending Home Sales', 'Building', 'Speaks'
]

# Kanoniskās notikumu saimes: globāla grupa, kas pārvērš vairākus scrape
# notikumus vienā rindiņā. (family_key, display_name, is_headline, [match_substrings])
# Formāts: visi notikumi, kas atbilst 'match_substrings', tiek apvienoti vienā
# "display_name" rindā ar vienu prioritāti un HEADLINE statusu.
CANONICAL_FAMILIES = [
    # FOMC lēmuma pašas dienas galvenie ieraksti (nevis vispārīgi 'fomc',
    # lai "FOMC Member X Speaks" netiktu sajaukts ar pašu likmju lēmumu)
    ("fomc", "ASV Federālo rezervju sistēmas (Fed) likmju lēmums un FOMC sanāksme", True,
     ["federal funds rate", "fomc statement", "fomc press conference",
      "fomc economic projections"]),
    ("inflacija_core", "Core CPI", False, ["core cpi"]),
    ("inflacija", "CPI", False, ["cpi"]),
    ("ppi_core", "Core PPI", False, ["core ppi"]),
    ("ppi", "PPI", False, ["ppi", "producer price"]),
    ("pce", "PCE", False, ["pce"]),
    ("darba_tirgus_nfp", "Non-Farm Payrolls m/m", False,
     ["non-farm payrolls", "nonfarm payrolls", "non farm payrolls"]),
    ("bezdarbs", "Unemployment Rate", False, ["unemployment rate"]),
    ("jobless", "Initial Jobless Claims", False, ["jobless claims", "initial claims", "unemployment claims"]),
    ("ikp", "GDP", False, ["gdp"]),
    ("retail", "Retail Sales m/m", False, ["retail sales", "core retail sales"]),
    ("rūpn_empire", "Empire State Manufacturing Index", False, ["empire state"]),
    ("rūpn_philly", "Philly Fed Manufacturing Index", False, ["philly"]),
    ("housing_starts", "Housing Starts", False, ["housing starts"]),
    ("permits", "Building Permits", False, ["building permits"]),
    ("pending_home", "Pending Home Sales m/m", False, ["pending home sales"]),
    ("conf", "Consumer Confidence", False, ["consumer confidence"]),
    ("sentiment", "U. of Michigan Consumer Sentiment", False,
     ["michigan", "uom", "consumer sentiment"]),
    ("pmi", "S&P Global / Flash PMI", False, ["pmi"]),
    ("capacity", "Capacity Utilization Rate", False, ["capacity utilization"]),
    ("indprod", "Industrial Production m/m", False, ["industrial production"]),
    ("dur", "Durable Goods Orders", False, ["durable goods"]),
    ("factory", "Factory Orders m/m", False, ["factory orders"]),
    # Fed amatpersonu runas (FOMC Member X Speaks) — NAV iekļautas atlases saimēs.
    # Atsevišķas Fed amatpersonu uzstāšanās nav monetārās politikas paziņojums un
    # netiek rādītas kā atsevišķi notikumi (lietotāja prasība 2026-09-20).
]

# Prioritātes (augstāks = pirmāks) pa saimju atslēgām; headline vienmēr pirmā.
FAMILY_PRIORITY = {
    "fomc": 100, "ikp": 78, "darba_tirgus_nfp": 78, "bezdarbs": 74,
    "inflacija_core": 76, "inflacija": 72, "pce": 70, "ppi_core": 66, "ppi": 62,
    "pmi": 60, "retail": 58, "capacity": 56, "indprod": 56, "dur": 54, "factory": 52,
    "housing_starts": 52, "permits": 52, "pending_home": 50, "conf": 50,
    "sentiment": 50, "rūpn_empire": 46, "rūpn_philly": 46, "jobless": 50,
}

def _match_family(ev):
    """Scrape notikums -> (family_key, display_name, is_headline) vai None."""
    low = " " + ev.lower() + " "
    for key_, disp, hl, pats in CANONICAL_FAMILIES:
        if any(p in low for p in pats):
            return (key_, disp, hl)
    return None

def select_top_events(us_events, max_per_day=2):
    selected = {}
    for date, events in sorted(us_events.items()):
        # 1) apvieno notikumus pa saimēm (kārtības saglabāšana nav svarīga — prio rindos)
        fam_order, chosen = [], {}
        for ev in events:
            if ev.startswith("🏖️") or ev == "Nav svarīgu ekonomisko datu":
                continue
            m = _match_family(ev)
            if m:
                key_, disp, hl = m
                if key_ in chosen:
                    continue  # jau apvienots citā burtā no tās pašas saimes
                chosen[key_] = (disp, hl)
                fam_order.append(key_)
        # 2) vilkšana pa prioritāti: headline pirmā, tad prio, tad secība
        ranked = []
        used_names = set()
        for key_ in fam_order:
            disp, hl = chosen[key_]
            prio = FAMILY_PRIORITY.get(key_, 10)
            score = (50_000 if hl else 0) + prio
            marker = (0 if hl else 1, -prio, len(ranked))
            ranked.append((score, marker, disp))
        ranked.sort(key=lambda x: -x[0])
        top = [disp for _, _, disp in ranked[:max_per_day]]
        if not top:
            top = ["Nav svarīgu ekonomisko datu"]
        selected[date] = top
    return selected

DATE_MAP = [
    ("Pirmdiena", "Mon"),
    ("Otrdiena", "Tue"),
    ("Trešdiena", "Wed"),
    ("Ceturtiena", "Thu"),
    ("Piektdiena", "Fri"),
]

def get_event_description(event_name):
    if event_name in DESCRIPTIONS:
        return DESCRIPTIONS[event_name]
    for key, desc in DESCRIPTIONS.items():
        if key.lower() in event_name.lower() or event_name.lower() in key.lower():
            return desc
    name = event_name.lower()
    # Kanonisko (apvienoto) nosaukumu apraksti
    if "likmju lēmums" in name or "fomc" in name:
        return ("Nedēļas un mēneša galvenais notikums — ASV centrālās bankas (Fed) "
                "lēmums par procentu likmēm un monetārās politikas virzienu. "
                "Tirgi gaidīs signālus par turpmāko likmju gaitu un izmaiņām 2026. gadā.")
    if "retail sales" in name:
        return ("Mazumtirdzniecības apjomi — galvenais patērētāju tēriņu rādītājs, kas "
                "ietekmē dolāra kursu un inflācijas gaidas. Pamata rādītājs (Core) neietver "
                "auto tirdzniecību.")
    if name in ("jobless claims", "initial jobless claims") or "claims" in name:
        return ("Iknedēļas jauno bezdarbnieku pieteikumu skaits. Rādītājs, kas uzrauga "
                "ASV darba tirgus stabilitāti un iespējamo vājināšanos — pieteikumi zem "
                "aptuveni 250 000 liecina par stabilu tirgu.")
    if "empire state" in name:
        return "Ņujorkas reģiona rūpniecības aktivitātes indekss. Vērtība virs 0 norāda uz izaugsmi, zem 0 — uz lejupslīdi."
    if "philly" in name:
        return "Filadelfijas reģiona ražošanas sektora indekss — ASV rūpniecības veselības barometrs."
    if "capacity utilization" in name:
        return ("Rūpniecisko jaudu noslodzes līmenis. Parāda ražošanas sektora efektivitāti, "
                "jaudu pārkaršanas riskus un inflācijas spiedienu.")
    if "industrial production" in name:
        return "Rūpnieciskās ražošanas apjoma izmaiņas — ekonomikas ražošanas sektora temps."
    if "building permits" in name:
        return "Izsniegto būvatļauju skaits — nākotnes būvniecības aktivitātes rādītājs."
    if "housing starts" in name:
        return "Jaunu mājokļu būvniecības sākumu skaits — mājokļu tirgus veselības rādītājs."
    if "pending home sales" in name:
        return "Noslēgto mājokļu pirkuma līgumu skaits — aktivitāte nekustamā īpašuma tirgū."
    if "retail" in name or "sales" in name:
        return "Pārdošanas apjomu izmaiņas. Stiprs pieaugums liecina par patērētāju tēriņiem un ekonomikas izaugsmi."
    if "consumer confidence" in name or "michigan" in name or "uom" in name or "consumer sentiment" in name:
        return ("Patērētāju noskaņojuma galējais indekss, kas raksturo mājsaimniecību "
                "gatavību tērēt un ekonomikas uztveri.")
    if "durable goods" in name:
        return ("Ilgtermiņa preču pasūtījumi. Atspoguļo uzņēmumu pieprasījumu un "
                "investīciju noskaņojumu ekonomikā.")
    if "factory orders" in name:
        return "Rūpniecības pasūtījumu izmaiņas — pieprasījuma rādītājs ražošanas sektorā."
    if "non-farm payrolls" in name or "nonfarm payrolls" in name:
        return ("Jauno darba vietu skaits ārpus lauksaimniecības — ietekmīgākais mēneša "
                "darba tirgus rādītājs, kas ietekmē dolāru un Fed likmju gaidas.")
    if "unemployment rate" in name:
        return "Bezdarba līmenis — būtisks darba tirgus un Fed likmju lēmumu rādītājs."
    if "gdp" in name:
        return "Iekšzemes kopprodukta izmaiņas — galvenais ekonomikas izaugsmes rādītājs."
    if "fomc" in name or "fed" in name or "powell" in name or "speaks" in name:
        return ("ASV Centrālās bankas (Fed) sanāksme vai paziņojums par monetāro politiku. "
                "Tirgi vēro jebkādas norādes par procentu likmju izmaiņām.")
    if "cpi" in name or "inflation" in name or "price index" in name:
        return "Inflācijas rādītājs. Augstāka inflācija par prognozēm var pamudināt Fed celt procentu likmes un stiprina dolāru."
    if "pmi" in name:
        return ("Svarīgi ekonomikas veselības rādītāji, kas parāda biznesa aktivitātes "
                "un inflācijas spiediena dinamiku. Vērtība virs 50 nozīmē izaugsmi, zem 50 — sarukumu.")
    if "housing" in name or "home" in name or "mortgage" in name or "permits" in name or "building" in name:
        return "Mājokļu vai būvniecības tirgus rādītājs. Pieaugums norāda uz aktivitāti nekustamā īpašuma sektorā."
    if "inventories" in name or "stock" in name:
        return "Krājumu izmaiņas. Rāda pieprasījumu un ražošanas tempu ekonomikā."
    if "trade" in name or "import" in name or "export" in name:
        return "Ārējās tirdzniecības rādītājs. Lielāks eksports pret importu atbalsta dolāru."
    if "confidence" in name or "sentiment" in name or "optimism" in name:
        return "Uzņēmēju vai patērētāju noskaņojuma indekss. Augstāks līmenis parasti nozīmē lielāku ekonomisko aktivitāti."
    if "oil" in name or "energy" in name or "gas" in name:
        return "Enerģijas vai naftas krājumu/cenu rādītājs. Ietekmē enerģijas cenas un inflācijas gaidas."
    if "durable" in name or "orders" in name or "factory" in name or "production" in name or "industrial" in name or "capacity" in name:
        return "Rūpniecības pasūtījumu vai produkcijas rādītājs. Pieaugums liecina par ražošanas sektora izaugsmi."
    if "consumer" in name:
        return "Patērētāju aktivitātes vai kredītu rādītājs. Rāda patērētāju pirktspēju un tēriņu tendenci."
    return None

def build_message(selected_events, next_monday):
    week_end = next_monday + timedelta(days=4)
    lines = [f"📊 Nākamās nedēļas ASV ekonomikas dati ({next_monday.strftime('%d.%m.')} — {week_end.strftime('%d.%m.')})", ""]

    HOLIDAYS = {"Sep 7": "🏖️ Labor Day — biržas slēgta"}

    scraped_dates = {}
    for dk in selected_events.keys():
        parts = dk.split()
        if len(parts) >= 2:
            scraped_dates[parts[0]] = dk

    for i, (lv_name, en_abbr) in enumerate(DATE_MAP):
        date_obj = next_monday + timedelta(days=i)
        date_str = date_obj.strftime("%d.%m.")
        month_day = date_obj.strftime("%b %-d")
        holiday = HOLIDAYS.get(month_day)
        if holiday:
            events = [holiday]
        else:
            date_key = scraped_dates.get(en_abbr, "")
            events = selected_events.get(date_key, ["Nav svarīgu ekonomisko datu"]) if date_key else ["Nav svarīgu ekonomisko datu"]

        lines.append(f"📅 {lv_name}, {date_str}")
        for ev in events:
            if ev.startswith("🏖️") or ev == "Nav svarīgu ekonomisko datu":
                lines.append(f"✅ {ev}")
            else:
                desc = get_event_description(ev)
                # Headline (Fed likmju lēmums / FOMC) — izcelts ar 🔥
                is_headline = "likmju lēmums" in ev.lower() or "fomc" in ev.lower()
                bullet = "🔥 " if is_headline else "✅ "
                if desc:
                    lines.append(f"{bullet}{ev} — {desc}")
                else:
                    lines.append(f"{bullet}{ev}")
        lines.append("")

    lines.append('🌐 <a href="https://kriptonr1.xyz">Kripto Nr.1 ekosistēma</a>')
    return "\n".join(lines)

def self_check(text):
    errors = []
    if text.count('📅') != 5:
        errors.append(f"Nav 5 dienu ierakstu: {text.count('📅')}")
    for line in text.split('\n'):
        line = line.strip()
        if line and not line.startswith(('📅', '✅', '📊', '---')):
            if line.endswith(('Sāk', 'un ', 'par ', 'uz ', 'no ', 'un')):
                errors.append(f"Iespējama nepilnīga teikuma: {line}")
    words = text.lower().split()
    for i in range(len(words) - 1):
        if words[i] == words[i + 1] and words[i] not in ['un', 'ar', 'no', 'par', 'uz', 'ja', 'kas']:
            errors.append(f"Vārdu atkārtojums: {words[i]}")
    for artifact in ['influences', ' the ', ' and ', ' to ', ' is ', ' for ']:
        if artifact in text.lower():
            errors.append(f"Tenglish fragments: {artifact}")
    return errors

def send_telegram(text):
    url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': text,
        'parse_mode': 'HTML',
        'disable_web_page_preview': True,
    }
    resp = requests.post(url, json=payload, timeout=15)
    resp.raise_for_status()
    result = resp.json()
    if result.get('ok'):
        print(f'Sent message_id={result["result"]["message_id"]}')
    else:
        print(f'Kļūda sūtot ziņu: {result}')
        exit(1)

def send_alert(text):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print(f"ALERT: {text}")
        return
    url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': f"⚠️ ASV kalendāra brīdinājums: {text}",
        'disable_web_page_preview': True,
    }
    requests.post(url, json=payload, timeout=15)

def send_photo(image_path, caption=None):
    """Nosūta infografikas bildi (sendPhoto). Caption opcionāls (parasti tekstu sūta atsevišķi)."""
    url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto'
    data = {'chat_id': TELEGRAM_CHAT_ID}
    if caption:
        data['caption'] = caption
    with open(image_path, 'rb') as f:
        files = {'photo': f}
        resp = requests.post(url, data=data, files=files, timeout=30)
    resp.raise_for_status()
    result = resp.json()
    if result.get('ok'):
        print(f'Sent photo message_id={result["result"]["message_id"]}')
    else:
        print(f'Kļūda sūtot bildi: {result}')
        exit(1)

def main():
    today = datetime.now()
    days_until_monday = (7 - today.weekday()) % 7
    if days_until_monday == 0:
        days_until_monday = 7
    next_monday = today + timedelta(days=days_until_monday)

    print(f"Next week starts: {next_monday.strftime('%Y-%m-%d')}")

    try:
        body = fetch_forexfactory_calendar()
        us_events = parse_us_events(body)
        total_us = sum(len(v) for v in us_events.values())
        print(f"Parsed USD events: {total_us}")

        if total_us < 3:
            send_alert(f"Pārāk maz ASV notikumu atrasti: {total_us}. Iespējams, avots ir mainījies.")
            exit(1)

        selected = select_top_events(us_events)
        message = build_message(selected, next_monday)

        errors = self_check(message)
        if errors:
            send_alert(f"Self-check kļūdas: {errors}")
            exit(1)

        output = {
            "next_monday": next_monday.strftime("%Y-%m-%d"),
            "us_events_count": total_us,
            "selected_events": selected,
            "message": message,
            "self_check_errors": errors,
        }
        print(json.dumps(output, indent=2, ensure_ascii=False))
        print("✅ Self-check passed")

        if os.environ.get("SEND_TELEGRAM", "0") == "1":
            # 1) Dashboard bilde — tikai rādītāji, kas atbilst nedēļas notikumiem
            send_image = False  # bilde izslegta (2026-09-13) — suta tikai tekstu, lidz HTML bilde apstiprinata
            # Pirms bildes pārbauda kie.ai kredītus — ja beigušies, sūta tikai tekstu
            try:
                import kie_bg
                credits = kie_bg.check_credits()
                if credits < 6:
                    print(f"⚠️ kie.ai kredīti nepietiekami ({credits}) — sūtu tikai ziņu bez bildes")
                    send_image = False
                else:
                    print(f"ℹ️ kie.ai kredīti: {credits}")
            except Exception as ce:
                print(f"ℹ️ Nevar pārbaudīt kie.ai kredītus ({ce}) — mēģinu ģenerēt")
            if send_image and HAS_INFOGRAPHIC:
                try:
                    ind_keys = asv_dashboard.select_indicators(selected)
                    if ind_keys:
                        img_path = os.path.join(
                            os.path.dirname(os.path.abspath(__file__)),
                            f"asv_dashboard_{next_monday.strftime('%Y%m%d')}.png")
                        # Premium dashboard: kie.ai fons (vērsis/lācis, neona svečturi,
                        # kāpjošs tirgus grafiks u.c.) + HTML dati virsū (pikseļprecīzs
                        # teksts). asv_dashboard_html.py jāpalaiž ar /usr/bin/python3,
                        # jo tam ir playwright.
                        import subprocess
                        html_script = os.path.join(
                            os.path.dirname(os.path.abspath(__file__)), "asv_dashboard_html.py")
                        cmd = ["/usr/bin/python3", html_script, img_path] + ind_keys
                        try:
                            subprocess.run(cmd, check=True, timeout=300)
                            print(f"✅ Premium dashboard (kie.ai + HTML) ģenerēts: {img_path} ({ind_keys})")
                        except Exception as ke:
                            print(f"⚠️ HTML dashboard neizdevās, atkāpjas uz matplotlib: {ke}")
                            asv_dashboard.generate_dashboard(ind_keys, img_path)
                            print(f"✅ Dashboard (matplotlib) ģenerēts: {img_path} ({ind_keys})")
                        send_photo(img_path)
                    else:
                        print("ℹ️ Šai nedēļai nav atbilstošu FRED rādītāju — bildi nesūta")
                except Exception as e:
                    print(f"⚠️ Dashboard attēlu neizdevās ģenerēt (turpinu ar tekstu): {e}")
            elif send_image:
                print("⚠️ Dashboard modulis nav pieejams — sūtu tikai tekstu")
            # 2) Nosūta teksta ziņu kā parasti
            send_telegram(message)
            print("✅ Ziņa nosūtīta veiksmīgi")

    except Exception as e:
        send_alert(f"Kļūda: {e}")
        exit(1)

if __name__ == '__main__':
    main()
