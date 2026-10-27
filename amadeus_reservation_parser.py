
import re
import csv
import io
import html
import json
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from urllib.request import urlopen

import streamlit as st
import airportsdata
import streamlit.components.v1 as components


st.set_page_config(
    page_title="Amadeus – Reservation Parser",
    page_icon="✈️",
    layout="wide",
)


# ---------------------------------------------------------
# LETALIŠČA
# Ključ: IATA koda; vrednost: slovensko ime mesta in časovni pas
# ---------------------------------------------------------

AIRPORTS = {
    "LJU": ("Ljubljana", "Europe/Ljubljana"),
    "ZAG": ("Zagreb", "Europe/Zagreb"),
    "VIE": ("Dunaj", "Europe/Vienna"),
    "TRS": ("Trst", "Europe/Rome"),
    "VCE": ("Benetke", "Europe/Rome"),
    "MXP": ("Milano Malpensa", "Europe/Rome"),
    "LIN": ("Milano Linate", "Europe/Rome"),
    "FCO": ("Rim Fiumicino", "Europe/Rome"),
    "CIA": ("Rim Ciampino", "Europe/Rome"),
    "NAP": ("Neapelj", "Europe/Rome"),
    "BLQ": ("Bologna", "Europe/Rome"),
    "CDG": ("Pariz Charles de Gaulle", "Europe/Paris"),
    "ORY": ("Pariz Orly", "Europe/Paris"),
    "AMS": ("Amsterdam", "Europe/Amsterdam"),
    "FRA": ("Frankfurt", "Europe/Berlin"),
    "MUC": ("München", "Europe/Berlin"),
    "ZRH": ("Zürich", "Europe/Zurich"),
    "BRU": ("Bruselj", "Europe/Brussels"),
    "LHR": ("London Heathrow", "Europe/London"),
    "LGW": ("London Gatwick", "Europe/London"),
    "IST": ("Istanbul", "Europe/Istanbul"),
    "SAW": ("Istanbul Sabiha Gökçen", "Europe/Istanbul"),
    "ATH": ("Atene", "Europe/Athens"),
    "MAD": ("Madrid", "Europe/Madrid"),
    "BCN": ("Barcelona", "Europe/Madrid"),
    "LIS": ("Lizbona", "Europe/Lisbon"),
    "JFK": ("New York JFK", "America/New_York"),
    "EWR": ("Newark", "America/New_York"),
    "ORD": ("Chicago", "America/Chicago"),
    "LAX": ("Los Angeles", "America/Los_Angeles"),
    "DXB": ("Dubaj", "Asia/Dubai"),
    "DOH": ("Doha", "Asia/Qatar"),
    "AUH": ("Abu Dabi", "Asia/Dubai"),
    "SIN": ("Singapur", "Asia/Singapore"),
    "HKG": ("Hongkong", "Asia/Hong_Kong"),
    "HND": ("Tokio Haneda", "Asia/Tokyo"),
    "NRT": ("Tokio Narita", "Asia/Tokyo"),
    "PEK": ("Peking", "Asia/Shanghai"),
    "PVG": ("Šanghaj Pudong", "Asia/Shanghai"),
    "BKK": ("Bangkok", "Asia/Bangkok"),
    "DEL": ("Delhi", "Asia/Kolkata"),
    "BOM": ("Mumbai", "Asia/Kolkata"),
    "SYD": ("Sydney", "Australia/Sydney"),
    "MEL": ("Melbourne", "Australia/Melbourne"),
    "YYZ": ("Toronto", "America/Toronto"),
    "YUL": ("Montreal", "America/Toronto"),
    "GRU": ("São Paulo", "America/Sao_Paulo"),
    "CPT": ("Cape Town", "Africa/Johannesburg"),
    "JNB": ("Johannesburg", "Africa/Johannesburg"),
    "MEX": ("Mexico City", "America/Mexico City"),
    "GDL": ("Guadalajara", "America/Guadalajara"),
    "ATL": ("Atlanta", "America/Atlanta"),
    "BSL": ("Basel Mulhouse", "Europe/Zurich"),
    "GGZ": ("Železniška postaja Gradec", "Europe/Graz"),
    "ZWS": ("Zürich železniška postaja", "Europe/Zurich"),
}


# ---------------------------------------------------------
# POMOŽNE FUNKCIJE
# ---------------------------------------------------------

# Naložimo celotno bazo IATA kod iz knjižnice airportsdata.
# Ključi slovarja so trimestne IATA kode.
try:
    AIRPORT_DATABASE = airportsdata.load("IATA")
except Exception:
    # Če se knjižnica ali njeni podatki iz kakršnegakoli razloga ne naložijo,
    # aplikacija še vedno lahko uporabi spodnji lasten slovar.
    AIRPORT_DATABASE = {}


def airport_info(code):
    code = (code or "").strip().upper()

    # Najprej poiščemo podatke v obsežni bazi.
    airport = AIRPORT_DATABASE.get(code, {})

    # Nato ohranimo naša ročno določena imena, ki imajo prednost
    # pred privzetimi angleškimi imeni iz baze.
    local_name, fallback_timezone = AIRPORTS.get(code, ("", "UTC"))

    city = (
        local_name
        or airport.get("city")
        or airport.get("name")
        or code
    )

    timezone_name = airport.get("tz") or fallback_timezone or "UTC"

    # Preverimo, ali je časovni pas veljaven. Napačen ali manjkajoč podatek
    # ne sme povzročiti sesutja aplikacije.
    try:
        ZoneInfo(timezone_name)
    except Exception:
        timezone_name = "UTC"

    return city, timezone_name


@st.cache_data(ttl=86400, show_spinner=False)
def load_airline_database():
    """
    Naloži javni seznam letalskih družb z OpenFlights.
    Če internetni vir ni dosegljiv, aplikacija še vedno deluje z našim seznamom.
    """
    url = "https://raw.githubusercontent.com/jpatokal/openflights/master/data/airlines.dat"

    try:
        with urlopen(url, timeout=5) as response:
            content = response.read().decode("utf-8", errors="replace")

        airlines = {}
        reader = csv.reader(io.StringIO(content))
        for row in reader:
            # OpenFlights format: ID, Name, Alias, IATA, ICAO, Callsign, Country, Active
            if len(row) < 8:
                continue

            code = row[3].strip().upper()
            name = row[1].strip()

            if code and code != r"\\N" and name and name != r"\\N":
                # Prva najdena veljavna vrednost za kodo ostane v slovarju.
                airlines.setdefault(code, name)

        return airlines
    except Exception:
        return {}


# Naša imena imajo vedno prednost pred imeni iz spletne baze.
# Seznam lahko kadarkoli razširimo z dodatnimi kodami.
AIRLINE_NAMES = {
    "KL": "KLM",
    "AF": "Air France",
    "LH": "Lufthansa",
    "AZ": "ITA Airways",
    "BA": "British Airways",
    "IB": "Iberia",
    "LX": "SWISS",
    "OS": "Austrian Airlines",
    "SN": "Brussels Airlines",
    "TK": "Turkish Airlines",
    "QR": "Qatar Airways",
    "EK": "Emirates",
    "EY": "Etihad Airways",
    "LO": "LOT Polish Airlines",
    "SK": "SAS",
    "AY": "Finnair",
    "TP": "TAP Air Portugal",
    "UA": "United Airlines",
    "AA": "American Airlines",
    "DL": "Delta Air Lines",
    "AC": "Air Canada",
    "QF": "Qantas",
    "SQ": "Singapore Airlines",
    "CX": "Cathay Pacific",
    "NH": "ANA",
    "JL": "Japan Airlines",
    "CA": "Air China",
    "MU": "China Eastern Airlines",
    "CZ": "China Southern Airlines",
    "TG": "Thai Airways",
    "AI": "Air India",
    "ET": "Ethiopian Airlines",
    "MS": "Egyptair",
    "AT": "Royal Air Maroc",
    "RJ": "Royal Jordanian",
    "JU": "Air Serbia",
    "OU": "Croatia Airlines",
    "JP": "Adria Airways",
    "W6": "Wizz Air",
    "FR": "Ryanair",
    "U2": "easyJet",
    "VY": "Vueling",
    "PC": "Pegasus Airlines",
    "A3": "Aegean Airlines",
    "FZ": "flydubai",
    "WY": "Oman Air",
    "GF": "Gulf Air",
    "ME": "Middle East Airlines",
}


AIRLINE_DATABASE = load_airline_database()


def airline_name(code):
    """Naše ime → ime iz spletne baze → sama koda kot varnostna rezerva."""
    code = (code or "").strip().upper()
    if code in AIRLINE_NAMES:
        return AIRLINE_NAMES[code]
    return AIRLINE_DATABASE.get(code) or code


def parse_date(token, year):
    """Prebere datum v obliki 24SEP, 7OCT itd."""
    token = token.upper().strip()
    match = re.fullmatch(r"(\d{1,2})([A-Z]{3})", token)

    if not match:
        return None

    day = int(match.group(1))
    month_text = match.group(2)

    months = {
        "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4,
        "MAY": 5, "JUN": 6, "JUL": 7, "AUG": 8,
        "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
    }

    month = months.get(month_text)

    if not month:
        return None

    try:
        return date(year, month, day)
    except ValueError:
        return None


def format_duration(minutes):
    if minutes is None or minutes < 0:
        return "—"

    hours, mins = divmod(minutes, 60)

    if hours and mins:
        return f"{hours} h {mins} min"
    if hours:
        return f"{hours} h"

    return f"{mins} min"


def time_difference_minutes(
    start_date,
    start_time,
    start_tz,
    end_date,
    end_time,
    end_tz,
):
    """Izračuna trajanje med lokalnima časoma ob upoštevanju časovnih pasov."""
    try:
        start_dt = datetime.strptime(
            f"{start_date.isoformat()} {start_time}",
            "%Y-%m-%d %H%M",
        ).replace(tzinfo=ZoneInfo(start_tz))

        end_dt = datetime.strptime(
            f"{end_date.isoformat()} {end_time}",
            "%Y-%m-%d %H%M",
        ).replace(tzinfo=ZoneInfo(end_tz))

        return int((end_dt - start_dt).total_seconds() // 60)

    except (ValueError, KeyError, Exception):
        return None


# ---------------------------------------------------------
# PARSANJE AMADEUS SEGMENTOV
# ---------------------------------------------------------

def parse_segments(raw):
    """Prepozna standardne in razširjene Amadeus vrstice segmentov."""
    raw_lines = [line.strip() for line in raw.splitlines() if line.strip()]
    parsed = []

    # Segmentna glava: številka segmenta je lahko prisotna ali odsotna;
    # številka leta je lahko zapisana kot AZ1358 ali AZ  60.
    header_pattern = re.compile(
        r"^\s*(?:\d+\s+)?\*?\s*"
        r"(?P<airline>[A-Z0-9]{2})\s*"
        r"(?P<flight>\d{1,4})\s+"
        r"(?P<class>[A-Z])\s+"
        r"(?P<date>\d{1,2}[A-Z]{3})\s+"
        r"(?:(?P<dow>\d)\s+)?"
        r"(?P<route_rest>.*)$",
        re.IGNORECASE,
    )

    # Letališči sta lahko zapisani skupaj (LJUAMS) ali ločeno (FCO MAD),
    # za njima pa se lahko pojavijo številke terminalov (npr. FCO 1 MAD 2).
    spaced_route_pattern = re.compile(
        r"^\s*(?P<origin>[A-Z]{3})\s+(?:\d+\s+)?"
        r"(?P<destination>[A-Z]{3})(?:\s+\d+)?\s+(?P<rest>.*)$",
        re.IGNORECASE,
    )
    compact_route_pattern = re.compile(
        r"^\s*(?P<route>[A-Z]{6})(?P<rest>.*)$",
        re.IGNORECASE,
    )

    matched_lines = []
    for line in raw_lines:
        header = header_pattern.match(line)
        if not header:
            continue

        route_rest = header.group("route_rest")
        route_match = spaced_route_pattern.match(route_rest)
        if route_match:
            origin = route_match.group("origin").upper()
            destination = route_match.group("destination").upper()
            rest = route_match.group("rest")
        else:
            route_match = compact_route_pattern.match(route_rest)
            if route_match:
                route = route_match.group("route").upper()
                origin, destination = route[:3], route[3:]
                rest = route_match.group("rest")
                # Kompaktna relacija lahko vsebuje terminal za ciljnim letališčem.
                rest = re.sub(r"^\s+\d+\b", "", rest, count=1)
            else:
                # V nekaterih kopiranih prikazih je zadnji cilj izpuščen.
                # Cilj dopolnimo samo, če gre očitno za povratni let:
                # trenutni odhod = prejšnji cilj, cilj = prvi odhod.
                one_airport = re.match(
                    r"^\s*(?P<origin>[A-Z]{3})\s+(?P<rest>.*)$",
                    route_rest,
                    re.IGNORECASE,
                )
                if not one_airport or not matched_lines:
                    continue
                origin = one_airport.group("origin").upper()
                rest = one_airport.group("rest")
                first_origin = matched_lines[0]["origin"]
                previous_destination = matched_lines[-1]["destination"]
                if origin != previous_destination or origin == first_origin:
                    continue
                destination = first_origin

        # Status (npr. HK1) ni obvezen v vseh Amadeus prikazih.
        # Vzamemo prva dva časovna zapisa, ki se pojavita za relacijo.
        times = re.findall(r"(?<!\d)(\d{4})(?!\d)", rest)
        if len(times) < 2:
            continue

        matched_lines.append({
            "airline": header.group("airline").upper(),
            "airline_name": airline_name(header.group("airline")),
            "flight_number": header.group("flight").upper(),
            "date_token": header.group("date").upper(),
            "origin": origin,
            "destination": destination,
            "departure_time": times[0],
            "arrival_time": times[1],
        })

    if not matched_lines:
        return []

    # Samodejna ocena leta:
    # če je prvi datum že mimo, predpostavimo naslednje leto.
    today = date.today()
    current_year = today.year

    first_date = parse_date(
        matched_lines[0]["date_token"],
        current_year,
    )

    if first_date and first_date < today:
        base_year = current_year + 1
    else:
        base_year = current_year

    previous_date = None

    for item in matched_lines:
        flight_date = parse_date(item["date_token"], base_year)

        if not flight_date:
            continue

        # Če se datum v zaporedju premakne nazaj, gre praviloma
        # za prehod v naslednje koledarsko leto.
        if previous_date and flight_date < previous_date:
            base_year += 1
            flight_date = parse_date(item["date_token"], base_year)

        if not flight_date:
            continue

        previous_date = flight_date

        origin = item["origin"]
        destination = item["destination"]

        origin_city, origin_tz = airport_info(origin)
        destination_city, destination_tz = airport_info(destination)

        departure_time = item["departure_time"]
        arrival_time = item["arrival_time"]

        arrival_date = flight_date

        duration = time_difference_minutes(
            flight_date,
            departure_time,
            origin_tz,
            arrival_date,
            arrival_time,
            destination_tz,
        )

        # Če je trajanje negativno, preverimo prihod naslednji dan.
        if duration is not None and duration < 0:
            next_day = flight_date + timedelta(days=1)

            next_day_duration = time_difference_minutes(
                flight_date,
                departure_time,
                origin_tz,
                next_day,
                arrival_time,
                destination_tz,
            )

            if next_day_duration is not None and next_day_duration >= 0:
                arrival_date = next_day
                duration = next_day_duration

        parsed.append({
            "date": flight_date,
            "flight": (
                f"{item['airline_name']} {item['airline']}{item['flight_number']}"
            ),
            # Keep the raw airline code and flight number for matching TST baggage.
            "airline": item["airline"],
            "flight_number": item["flight_number"],
            "origin": origin,
            "destination": destination,
            "origin_city": origin_city,
            "destination_city": destination_city,
            "departure": (
                departure_time[:2] + ":" + departure_time[2:]
            ),
            "arrival": (
                arrival_time[:2] + ":" + arrival_time[2:]
            ),
            "duration_minutes": duration,
            "arrival_date": arrival_date,
        })

    # Izračun prestopov med zaporednimi segmenti.
    for i, segment in enumerate(parsed):
        segment["layover_minutes"] = None

        if i >= len(parsed) - 1:
            continue

        next_segment = parsed[i + 1]

        # Prestop izračunamo le, kadar naslednji let odleti
        # z letališča, na katerem se prejšnji konča.
        if segment["destination"] != next_segment["origin"]:
            continue

        _, timezone_name = airport_info(segment["destination"])

        try:
            arrival_dt = datetime.strptime(
                f"{segment['arrival_date'].isoformat()} "
                f"{segment['arrival']}",
                "%Y-%m-%d %H:%M",
            ).replace(tzinfo=ZoneInfo(timezone_name))

            next_departure_dt = datetime.strptime(
                f"{next_segment['date'].isoformat()} "
                f"{next_segment['departure']}",
                "%Y-%m-%d %H:%M",
            ).replace(tzinfo=ZoneInfo(timezone_name))

            layover_minutes = int(
                (next_departure_dt - arrival_dt).total_seconds() // 60
            )

            if 0 <= layover_minutes <= 18 * 60:
                segment["layover_minutes"] = layover_minutes

        except Exception:
            segment["layover_minutes"] = None

    return parsed




# ---------------------------------------------------------
# RESERVATION PARSER – PODATKI IZ PNR + TST
# ---------------------------------------------------------

MONTHS_SL = {
    1: "januar", 2: "februar", 3: "marec", 4: "april",
    5: "maj", 6: "junij", 7: "julij", 8: "avgust",
    9: "september", 10: "oktober", 11: "november", 12: "december",
}

NAME_TITLES = {
    "MR", "MRS", "MS", "MISS", "MSTR", "DR", "PROF",
    "M", "F", "CHD", "INF",
}

def nice_name(raw_name):
    """BASTARDA/ANDREJ MR -> Andrej Bastarda (Mr)."""
    raw_name = raw_name.strip().upper()
    if "/" not in raw_name:
        return raw_name.title()
    surname, given = raw_name.split("/", 1)
    given_parts = [p for p in re.split(r"[\s-]+", given.strip()) if p]
    title_codes = {"MR", "MRS", "MS", "MISS", "MSTR", "DR", "PROF", "M", "F", "CHD", "INF"}
    title = next((p for p in reversed(given_parts) if p in title_codes), "")
    given_parts = [p for p in given_parts if p not in title_codes]
    surname_parts = [p for p in re.split(r"[\s-]+", surname.strip()) if p]
    name = " ".join(given_parts + surname_parts).title()
    title_labels = {"MR": "Mr", "MRS": "Mrs", "MS": "Ms", "MISS": "Miss", "MSTR": "Master", "DR": "Dr", "PROF": "Prof", "M": "M", "F": "F", "CHD": "Child", "INF": "Infant"}
    return f"{name} ({title_labels.get(title, title.title())})" if title else name


def parse_passenger_details(raw):
    """Prepozna potnike, številko v PNR-ju in kategorijo (adult/child/infant)."""
    found = []
    seen = set()
    for line in raw.splitlines():
        # Passenger lines are numbered, e.g. 1.NOVAK/DREJC(INS/24JUN25)
        match = re.match(r"^\s*(\d+)\.\s*([A-Z][A-Z' -]*/[A-Z][A-Z' -]+?)(?=\s*\(|\s{2,}|$)", line, re.I)
        if not match:
            continue
        number = int(match.group(1))
        raw_name = re.sub(r"\s+", " ", match.group(2)).strip().rstrip()
        # Keep name clean if the PNR has a child/infant marker directly after it.
        raw_name = re.sub(r"\s+", " ", raw_name)
        upper_line = line.upper()
        if re.search(r"\bCHD(?:/|\b)", upper_line):
            category = "child"
            label = "otrok"
        elif re.search(r"\bINS(?:/|\b)", upper_line):
            category = "infant_seat"
            label = "dojenček na svojem sedežu"
        elif re.search(r"\bINF(?:/|\b)", upper_line):
            category = "infant_lap"
            label = "dojenček v naročju"
        else:
            category = "adult"
            label = "odrasli"
        key = (number, raw_name)
        if key in seen:
            continue
        seen.add(key)
        found.append({
            "number": number,
            "raw_name": raw_name,
            "name": nice_name(raw_name),
            "category": category,
            "category_label": label,
        })
    return found


def parse_passengers(raw):
    """Vrne prikazna imena potnikov; ohranja združljivost s preostalim parserjem."""
    return [p["name"] for p in parse_passenger_details(raw)]


def parse_tst_category_prices(raw, passenger_details):
    """Poveže cene iz TST-blokov s kategorijami potnikov, ne glede na vrstni red TST-jev."""
    category_by_number = {p["number"]: p["category"] for p in passenger_details}
    amounts = {"adult": [], "child": [], "infant": []}
    # A TST block may contain one or more PC.<passenger number> references.
    blocks = re.split(r"(?=\bTST\s*\d+\b)", raw, flags=re.I)
    for block in blocks:
        if not re.search(r"\bTST\s*\d+\b", block, re.I):
            continue
        pcs = [int(x) for x in re.findall(r"\bPC\.(\d+)\b", block, re.I)]
        money = re.search(r"\bEUR\s+([\d,]+(?:\.\d{2})?)", block, re.I)
        if not money:
            money = re.search(r"\b([A-Z]{3})\s+([\d,]+(?:\.\d{2})?)", block, re.I)
            if money:
                currency, amount_text = money.group(1).upper(), money.group(2)
            else:
                continue
        else:
            currency, amount_text = "EUR", money.group(1)
        try:
            amount = float(amount_text.replace(",", ""))
        except ValueError:
            continue
        for passenger_number in pcs:
            category = category_by_number.get(passenger_number)
            if category == "adult":
                amounts["adult"].append((amount, currency))
            elif category == "child":
                amounts["child"].append((amount, currency))
            elif category in {"infant_seat", "infant_lap"}:
                amounts["infant"].append((amount, currency))
    result = {}
    for category, values in amounts.items():
        # Only display a single reference price when the category's TST prices agree.
        unique = list(dict.fromkeys(values))
        if len(unique) == 1:
            amount, currency = unique[0]
            display = f"{amount:,.2f} {currency}".replace(",", "X").replace(".", ",").replace("X", ".")
            result[category] = {"amount": amount, "currency": currency, "display": display}
        elif len(unique) > 1:
            result[category] = {"display": "Več različnih cen v TST-ju"}
    return result


def parse_record_locator(raw):
    """Najprej išče 6-mestno oznako na RP-vrstici, nato varnostno po celotnem PNR."""
    for line in raw.splitlines():
        if line.strip().upper().startswith("RP/"):
            tokens = re.findall(r"\b[A-Z0-9]{6}\b", line.upper())
            if tokens:
                return tokens[-1]
    # Fallback: običajno je locator v glavi PNR, za datumom/časom.
    for line in raw.splitlines()[:8]:
        if "RP/" in line.upper():
            match = re.search(r"\b([A-Z0-9]{6})\s*$", line.strip().upper())
            if match:
                return match.group(1)
    return ""


def parse_tst_price(raw):
    """Vrne ceno iz GRAND TOTAL, sicer TOTAL; nikoli ne ugiba."""
    patterns = [
        r"GRAND\s+TOTAL\s+([A-Z]{3})\s+([\d,]+(?:\.\d{2})?)",
        r"(?m)^\s*TOTAL\s+([A-Z]{3})\s+([\d,]+(?:\.\d{2})?)\s*$",
    ]
    for pattern in patterns:
        match = re.search(pattern, raw, re.I | re.M)
        if match:
            currency = match.group(1).upper()
            amount_text = match.group(2).replace(",", "")
            try:
                amount = float(amount_text)
                return {"currency": currency, "amount": amount, "display": f"{amount:,.2f} {currency}".replace(",", "X").replace(".", ",").replace("X", ".")}
            except ValueError:
                pass
    return None


def parse_tst_baggage(raw):
    """Prebere dovoljene kose/težo iz TST vrstic po posameznem letu."""
    baggage_by_flight = {}
    # TST segment lines can appear as either "1   VCE CA  974 ..." or
    # "2 X PEK CA  783 ..." / "4 O MEL CA  166 ...". The optional
    # one-letter indicator (X/O, etc.) must not prevent baggage detection.
    row_pattern = re.compile(
        r"^\s*\d+\s+(?:[A-Z]\s+)?[A-Z]{3}\s+([A-Z0-9]{2})\s+(\d{1,4})\b",
        re.I,
    )
    baggage_pattern = re.compile(r"\b(\d{1,2}\s*PC|\d{1,3}\s*KG)\b", re.I)

    for line in raw.splitlines():
        match = row_pattern.match(line)
        if not match:
            continue
        flight_key = (match.group(1).upper(), match.group(2))
        baggage_match = baggage_pattern.search(line)
        if baggage_match:
            value = re.sub(r"\s+", "", baggage_match.group(1).upper())
            baggage_by_flight[flight_key] = value

    return baggage_by_flight


def baggage_summary(segments, baggage_by_flight):
    if not segments:
        return "Oddana prtljaga ni potrjena."
    values = []
    for segment in segments:
        key = (segment["airline"], segment["flight_number"])
        value = baggage_by_flight.get(key)
        if value:
            values.append(value)
        else:
            values.append(None)

    if not any(values):
        return "Oddana prtljaga ni potrjena iz predloženega TST-ja."

    if all(v == values[0] for v in values) and values[0]:
        value = values[0]
        if value.endswith("PC"):
            count = int(value[:-2])
            unit = "kos" if count == 1 else "kosa" if count == 2 else "kosov"
            return f"{count} {unit} oddane prtljage."
        if value.endswith("KG"):
            return f"{value[:-2]} kg oddane prtljage."

    parts = []
    for segment, value in zip(segments, values):
        label = f"{segment['airline']}{segment['flight_number']}"
        if value and value.endswith("PC"):
            count = int(value[:-2])
            unit = "kos" if count == 1 else "kosa" if count == 2 else "kosov"
            parts.append(f"{label}: {count} {unit}")
        elif value and value.endswith("KG"):
            parts.append(f"{label}: {value[:-2]} kg")
        else:
            parts.append(f"{label}: ni potrjeno")
    return "Oddana prtljaga – " + "; ".join(parts) + "."


def parse_reservation(raw):
    segments = parse_segments(raw)
    passenger_details = parse_passenger_details(raw)
    passengers = [p["name"] for p in passenger_details]
    locator = parse_record_locator(raw)
    price = parse_tst_price(raw)
    category_prices = parse_tst_category_prices(raw, passenger_details)
    baggage = parse_tst_baggage(raw)
    return {
        "segments": segments,
        "passengers": passengers,
        "passenger_details": passenger_details,
        "locator": locator,
        "price": price,
        "category_prices": category_prices,
        "baggage_by_flight": baggage,
    }



def build_flight_table_html(rows):
    """Tabela letov z enakim modro-rumenim slogom kot obstoječi potovalni parser."""
    if not rows:
        return ""
    headers = list(rows[0].keys())
    table_style = (
        "border-collapse:collapse;width:auto;max-width:100%;"
        "font-family:Arial,Helvetica,sans-serif;font-size:13px;color:#263445;"
    )
    th_style = (
        "background-color:#004899;color:#FFFFFF;font-weight:700;text-align:left;"
        "padding:7px 9px;border:0;border-bottom:4px solid #FBB900;white-space:nowrap;"
    )
    td_base = "padding:7px 9px;border:0;vertical-align:top;"
    nowrap_columns = {"Datum", "Let", "Odhod", "Prihod", "Trajanje leta", "Čas prestopa"}
    html_rows = [f'<table style="{table_style}"><thead><tr>']
    for header in headers:
        html_rows.append(f'<th style="{th_style}">{html.escape(header)}</th>')
    html_rows.append("</tr></thead><tbody>")
    for row_index, row in enumerate(rows):
        background = "#FFF9E9" if row_index % 2 else "#FFFFFF"
        html_rows.append("<tr>")
        layover_value = str(row.get("Čas prestopa", "")).strip()
        ends_connection = row_index < len(rows) - 1 and layover_value in {"", "—", "–", "-"}
        for header in headers:
            value = html.escape(str(row.get(header, "")))
            cell_style = td_base + f"background-color:{background};"
            if ends_connection:
                cell_style += "border-bottom:1px solid #FBB900;"
            if header in nowrap_columns:
                cell_style += "white-space:nowrap;"
            else:
                cell_style += "white-space:normal;overflow-wrap:anywhere;max-width:280px;"
            html_rows.append(f'<td style="{cell_style}">{value}</td>')
        html_rows.append("</tr>")
    html_rows.append("</tbody></table>")
    return "".join(html_rows)


def render_copyable_flight_table(rows):
    """Prikaže tabelo v slogu starega parserja in ponuja kopiranje tabele."""
    if not rows:
        return
    table_html = build_flight_table_html(rows)
    headers = list(rows[0].keys())
    tsv_text = "\n".join(["\t".join(headers)] + ["\t".join(str(row.get(h, "")) for h in headers) for row in rows])
    safe_html = json.dumps(table_html, ensure_ascii=False)
    safe_tsv = json.dumps(tsv_text, ensure_ascii=False)
    components.html(f"""
      <div style="font-family:Arial,Helvetica,sans-serif;">
        <button id="copyFlightTable" style="background:#23476A;color:#FFFFFF;border:0;border-radius:5px;padding:8px 13px;font-size:13px;font-weight:600;cursor:pointer;margin:0 0 10px 0;">📋 Kopiraj tabelo letov</button>
        <span id="copyFlightStatus" style="font-size:12px;color:#526579;margin-left:8px;"></span>
        <div style="overflow-x:auto;">{table_html}</div>
      </div>
      <script>
        const htmlTable = {safe_html};
        const plainText = {safe_tsv};
        document.getElementById("copyFlightTable").addEventListener("click", async () => {{
          const status = document.getElementById("copyFlightStatus");
          try {{
            if (navigator.clipboard && window.ClipboardItem) {{
              const item = new ClipboardItem({{"text/html": new Blob([htmlTable], {{type:"text/html"}}), "text/plain": new Blob([plainText], {{type:"text/plain"}})}});
              await navigator.clipboard.write([item]); status.textContent = "Tabela je kopirana.";
            }} else if (navigator.clipboard && navigator.clipboard.writeText) {{
              await navigator.clipboard.writeText(plainText); status.textContent = "Kopirano kot besedilo.";
            }} else {{ status.textContent = "Kopiranje ni podprto. Označi tabelo in jo kopiraj."; }}
          }} catch (err) {{ status.textContent = "Kopiranje ni uspelo. Poskusi ponovno."; }}
        }});
      </script>
    """, height=max(190, 65 + 39 * len(rows)), scrolling=True)

def format_money_input(value):
    """Dovoljuje vnos z decimalno vejico ali piko; vrača uporabniku prijazen zapis."""
    value = (value or "").strip()
    if not value:
        return ""
    return value


def build_summary_text(passengers, locator, segments, baggage_text, cabin_baggage,
                       final_prices, currency, change_fee, cancellation_fee):
    lines = ["POVZETEK LETALSKE REZERVACIJE", ""]
    lines.append("Potnik(i): " + (", ".join(passengers) if passengers else "Ni prepoznano"))
    lines.append("Številka rezervacije: " + (locator or "Ni prepoznana"))
    lines.append("")
    lines.append("REZERVIRANI LETI")
    if not segments:
        lines.append("Leti niso bili prepoznani iz prilepljenih podatkov.")
    for segment in segments:
        date_text = segment["date"].strftime("%d.%m.%Y")
        route = f"{segment['origin_city']} ({segment['origin']}) – {segment['destination_city']} ({segment['destination']})"
        arrival_suffix = " (+1 dan)" if segment["arrival_date"] > segment["date"] else ""
        lines.append(f"{date_text} | {segment['flight']} | {route} | {segment['departure']}–{segment['arrival']}{arrival_suffix}")
    lines.extend(["", "PRTLJAGA", "Ročna prtljaga: vključena." if cabin_baggage else "Ročna prtljaga: ni vključena.", baggage_text, "", "KONČNA CENA"])
    labels = {"adult": "Odrasli", "child": "Otrok", "infant": "Dojenček"}
    populated = False
    for key, label in labels.items():
        value = final_prices.get(key, "").strip()
        if value:
            lines.append(f"{label}: {value} {currency}".strip())
            populated = True
    if not populated:
        lines.append("Ni vnesena.")
    fee_lines = []
    if change_fee.strip(): fee_lines.append("Strošek spremembe: " + change_fee.strip())
    if cancellation_fee.strip(): fee_lines.append("Strošek odpovedi: " + cancellation_fee.strip())
    if fee_lines:
        lines.extend(["", "POGOJI VOZOVNICE", *fee_lines])
    return "\n".join(lines)


def render_copy_all_button(summary_text, summary_html):
    safe_text = json.dumps(summary_text, ensure_ascii=False)
    safe_html = json.dumps(summary_html, ensure_ascii=False)
    components.html(
        f"""
        <div style="font-family:Roboto,Arial,sans-serif;">
          <button id="copyAll"
            style="background:#004899;color:#fff;border:0;border-bottom:4px solid #FBB900;
                   border-radius:7px;padding:11px 18px;font-family:Roboto,Arial,sans-serif;
                   font-size:14px;font-weight:700;cursor:pointer;">
            📋 Kopiraj celoten povzetek
          </button>
          <span id="copyStatus" style="font-size:12px;color:#004899;margin-left:10px;"></span>
        </div>
        <script>
          const htmlSummary = {safe_html};
          const plainText = {safe_text};
          document.getElementById("copyAll").addEventListener("click", async () => {{
            const status = document.getElementById("copyStatus");
            try {{
              if (navigator.clipboard && window.ClipboardItem) {{
                const item = new ClipboardItem({{
                  "text/html": new Blob([htmlSummary], {{type:"text/html"}}),
                  "text/plain": new Blob([plainText], {{type:"text/plain"}})
                }});
                await navigator.clipboard.write([item]);
                status.textContent = "Celoten povzetek je kopiran.";
              }} else if (navigator.clipboard && navigator.clipboard.writeText) {{
                await navigator.clipboard.writeText(plainText);
                status.textContent = "Povzetek je kopiran kot besedilo.";
              }} else {{
                status.textContent = "Kopiranje ni podprto v tem brskalniku.";
              }}
            }} catch (err) {{
              status.textContent = "Kopiranje ni uspelo. Poskusi znova.";
            }}
          }});
        </script>
        """,
        height=62,
    )


# ---------------------------------------------------------
# VIZUALNI SLOG
# ---------------------------------------------------------

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700&display=swap');
    html, body, [class*="css"], [data-testid="stAppViewContainer"] {
        font-family: 'Roboto', Arial, sans-serif !important;
    }
    .stApp { background: #F7F9FC; }
    [data-testid="stHeader"] { background: rgba(247,249,252,0.95); }
    h1, h2, h3 { color: #004899 !important; font-family: 'Roboto', Arial, sans-serif !important; }
    .hero {
        background: #004899; color: white; border-radius: 10px; padding: 13px 18px;
        border-bottom: 6px solid #FBB900; margin-bottom: 10px;
    }
    .hero h1 { color: white !important; margin: 0; font-size: 24px; }
    .hero p { color: #EAF1FA; margin: 7px 0 0 0; }
    .section-card {
        background: white; border: 1px solid #E2E8F0; border-radius: 12px;
        padding: 10px 12px; margin: 5px 0 9px 0;
    }
    .section-title {
        color: #004899; font-weight: 700; font-size: 15px;
        border-bottom: 2px solid #FBB900; padding-bottom: 5px; margin-bottom: 7px;
    }
    .pill {
        display:inline-block; background:#FFF4CC; color:#004899; border-radius:20px;
        padding:4px 10px; font-size:12px; font-weight:700; margin:2px 4px 2px 0;
    }
    div.stButton > button[kind="primary"] {
        background: #004899; color: white; border: 0; border-bottom: 4px solid #FBB900;
        border-radius: 7px; font-family: 'Roboto', Arial, sans-serif; font-weight: 700;
    }
    div.stButton > button[kind="primary"]:hover { background: #003875; color: white; }
    [data-testid="stTextArea"] textarea, [data-testid="stTextInput"] input {
        font-size: 13px !important;
        font-family: 'Roboto', Arial, sans-serif !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="hero">
      <h1>✈️ Amadeus Reservation Parser</h1>
      <p>Iz PNR-ja in TST-ja do preglednega povzetka rezervacije za stranko.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown("#### Vnos rezervacije")
st.caption("Prilepi celoten PNR in TST skupaj v eno polje. Parser bo sam poiskal podatke, ki jih zna prepoznati.")

raw_input = st.text_area(
    "PNR + TST",
    height=115,
    placeholder=(
        "Prilepi sem celoten zapis iz Amadeusa, vključno s PNR-jem in TST-jem.\n\n"
        "Primer: RP/LJUS... AB12CD\n"
        "1.NOVAK/JANEZ MR\n"
        "3 CA 974 T 07MAR 7 VCEPEK HK2 2115 1415+1 *1A/E*\n"
        "...\n"
        "GRAND TOTAL EUR 875.20"
    ),
    key="reservation_raw",
)

if st.button("Analiziraj rezervacijo", type="primary", use_container_width=False):
    result = parse_reservation(raw_input)
    st.session_state["reservation_result"] = result
    st.session_state["reservation_raw_saved"] = raw_input

result = st.session_state.get("reservation_result")

if result:
    segments = result["segments"]
    passengers = result["passengers"]
    locator = result["locator"]
    price = result["price"]
    baggage_text = baggage_summary(segments, result["baggage_by_flight"])

    st.markdown("#### Prepoznani podatki")

    # Kompakten prikaz podatkov za agenta: brez ponavljanja imen, PNR-ja in letov.
    # Naslovi so oblikovani enako kot »Pogoji vozovnice«, brez kartic.
    st.markdown("#### Prtljaga")
    st.markdown(
        f"<div style='margin:0;padding:0;font-size:14px;'>Oddana prtljaga: "
        f"<span style='font-weight:600;'>{html.escape(baggage_text)}</span></div>",
        unsafe_allow_html=True,
    )
    cabin_baggage = st.checkbox("Ročna prtljaga vključena", value=True, key="cabin_baggage")

    st.markdown("#### Cena")
    category_prices = result.get("category_prices", {})
    passenger_details = result.get("passenger_details", [])
    present_categories = {p["category"] for p in passenger_details}
    infant_present = bool(present_categories & {"infant_seat", "infant_lap"})
    if category_prices:
        price_lines = []
        for key, label in (("adult", "Odrasli"), ("child", "Otrok"), ("infant", "Dojenček")):
            if key in category_prices:
                price_lines.append(f"{label}: {category_prices[key]['display']}")
        if price_lines:
            st.markdown(
                "<div style='margin:0;padding:0;font-size:14px;font-weight:600;color:#004899;'>" +
                "<br>".join(html.escape(line) for line in price_lines) +
                "</div><div style='font-size:12px;font-weight:400;color:#666;margin:0;padding:0;'>(prebrano iz TST-ja)</div>",
                unsafe_allow_html=True,
            )
    elif price:
        st.markdown(
            f"<div style='margin:0;padding:0;font-size:16px;font-weight:600;color:#004899;'>{html.escape(price['display'])}</div>"
            "<div style='font-size:12px;font-weight:400;color:#666;margin:0;padding:0;'>(prebrano iz TST-ja; kategorije niso razločene)</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown("<div style='font-size:14px;margin:0;padding:0;'>Cena ni bila prepoznana iz TST-ja.</div>", unsafe_allow_html=True)

    final_prices = {}
    if "adult" in present_categories:
        final_prices["adult"] = st.text_input("Cena za stranko – odrasli", placeholder="Cena za odraslega", key="final_price_adult")
    if "child" in present_categories:
        final_prices["child"] = st.text_input("Cena za stranko – otrok", placeholder="Cena za otroka", key="final_price_child")
    if infant_present:
        final_prices["infant"] = st.text_input("Cena za stranko – dojenček", placeholder="Cena za dojenčka", key="final_price_infant")
    currency = st.selectbox("Valuta", ["EUR", "USD", "GBP", "CHF", "Other"], index=0, key="final_currency")

    st.markdown("#### Pogoji vozovnice")
    change_fee = st.text_input("Strošek spremembe", placeholder="Pusti prazno, če ne želiš prikaza", key="change_fee")
    cancellation_fee = st.text_input("Strošek odpovedi", placeholder="Pusti prazno, če ne želiš prikaza", key="cancellation_fee")

    st.markdown("#### Končni povzetek")
    summary_text = build_summary_text(
        passengers, locator, segments, baggage_text, cabin_baggage,
        final_prices, currency, change_fee, cancellation_fee,
    )

    # Lep HTML predložek za prikaz in kopiranje v e-pošto/Word.
    # Plain-text različica ostane alternativa za odložišče, ki ne podpira HTML-ja.
    passenger_text = ", ".join(passengers) if passengers else "Ni prepoznano"
    locator_text = locator or "Ni prepoznana"
    price_label_map = {"adult": "Odrasli", "child": "Otrok", "infant": "Dojenček"}
    final_price_lines = [f"{html.escape(price_label_map[k])}: {html.escape(v.strip())} {html.escape(currency)}".strip()
                         for k, v in final_prices.items() if v.strip()]
    final_price_text = "<br>".join(final_price_lines) if final_price_lines else "Ni vnesena"
    cabin_text = "Vključena" if cabin_baggage else "Ni vključena"

    flight_rows = []
    for segment in segments:
        flight_rows.append({
            "Datum": segment["date"].strftime("%d.%m.%Y"),
            "Let": segment["flight"],
            "Relacija": f"{segment['origin_city']} ({segment['origin']}) – {segment['destination_city']} ({segment['destination']})",
            "Odhod": segment["departure"],
            "Prihod": segment["arrival"] + (" (+1 dan)" if segment["arrival_date"] > segment["date"] else ""),
            "Trajanje leta": format_duration(segment["duration_minutes"]),
            "Čas prestopa": format_duration(segment["layover_minutes"]),
        })
    flight_table_html = build_flight_table_html(flight_rows)

    summary_html_lines = [
        '<div style="font-family:Roboto,Arial,sans-serif;color:#233044;max-width:100%;line-height:1.45;">',
        '<div style="padding:16px 18px 13px;background:#004899;border-radius:10px 10px 0 0;color:#ffffff;border-bottom:5px solid #FBB900;">',
        '<div style="font-size:22px;font-weight:700;color:#FFFFFF;">Povzetek letalske rezervacije</div>',
        '</div>',
        '<div style="border:1px solid #DCE3EC;border-top:0;padding:12px 14px 14px;border-radius:0 0 10px 10px;">',
        '<table style="border-collapse:collapse;width:100%;font-size:13px;margin-bottom:14px;">',
        '<tr>',
        f'<td style="width:68%;vertical-align:top;padding:6px 10px 6px 0;border-bottom:2px solid #FBB900;"><div style="font-size:10px;color:#64748B;text-transform:uppercase;letter-spacing:.7px;">Potnik(i)</div><div style="font-size:13px;font-weight:700;color:#004899;">{html.escape(passenger_text)}</div></td>',
        f'<td style="width:32%;vertical-align:top;padding:6px 0 6px 10px;border-bottom:2px solid #FBB900;"><div style="font-size:10px;color:#64748B;text-transform:uppercase;letter-spacing:.7px;">Številka rezervacije</div><div style="font-size:13px;font-weight:700;color:#004899;">{html.escape(locator_text)}</div></td>',
        '</tr></table>',
        '<div style="font-size:15px;font-weight:700;color:#004899;margin:0 0 7px;">Rezervirani leti</div>',
        '<div style="overflow-x:auto;margin-bottom:14px;">', flight_table_html, '</div>',
        '<div style="font-size:15px;font-weight:700;color:#004899;margin:0 0 7px;">Prtljaga</div>',
        '<table style="border-collapse:collapse;width:100%;font-size:13px;margin-bottom:14px;">',
        f'<tr><td style="padding:7px 9px;background:#F5F8FC;border-bottom:1px solid #E2E8F0;width:38%;font-weight:700;">Ročna prtljaga</td><td style="padding:7px 9px;border-bottom:1px solid #E2E8F0;">{html.escape(cabin_text)}</td></tr>',
        f'<tr><td style="padding:7px 9px;background:#F5F8FC;font-weight:700;">Oddana prtljaga</td><td style="padding:7px 9px;">{html.escape(baggage_text.removesuffix("."))}</td></tr>',
        '</table>',
        '<div style="font-size:15px;font-weight:700;color:#004899;margin:0 0 7px;">Cena in pogoji vozovnice</div>',
        '<table style="border-collapse:collapse;width:100%;font-size:13px;">',
        f'<tr><td style="padding:8px 9px;background:#FFF7DF;border-left:4px solid #FBB900;font-weight:700;width:38%;">Končna cena</td><td style="padding:8px 9px;background:#FFF7DF;color:#004899;font-size:16px;font-weight:700;">{final_price_text}</td></tr>',
        *([f'<tr><td style="padding:7px 9px;background:#F5F8FC;border-bottom:1px solid #E2E8F0;font-weight:700;">Strošek spremembe</td><td style="padding:7px 9px;border-bottom:1px solid #E2E8F0;">{html.escape(change_fee.strip())}</td></tr>'] if change_fee.strip() else []),
        *([f'<tr><td style="padding:7px 9px;background:#F5F8FC;font-weight:700;">Strošek odpovedi</td><td style="padding:7px 9px;">{html.escape(cancellation_fee.strip())}</td></tr>'] if cancellation_fee.strip() else []),
        '</table>',
        '</div></div>',
    ]
    summary_html = "".join(summary_html_lines)

    st.markdown(summary_html, unsafe_allow_html=True)
    render_copy_all_button(summary_text, summary_html)

    st.download_button(
        "⬇️ Prenesi povzetek (.txt)",
        data=summary_text,
        file_name=f"rezervacija_{locator or 'povzetek'}.txt",
        mime="text/plain",
    )

    with st.expander("Tehnični pregled – kaj je parser prepoznal"):
        st.write(f"Prepoznani leti: {len(segments)}")
        st.write(f"Prepoznani potniki: {len(passengers)}")
        st.write(f"Številka rezervacije: {locator or 'ni prepoznana'}")
        st.write(f"Cena iz TST-ja: {price['display'] if price else 'ni prepoznana'}")
        if not segments:
            st.code(st.session_state.get("reservation_raw_saved", ""), language=None)
else:
    st.info("Prilepi PNR in TST skupaj, nato klikni »Analiziraj rezervacijo«.")
