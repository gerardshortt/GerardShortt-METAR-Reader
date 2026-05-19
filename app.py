import re
import requests
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

WIND_DIRECTIONS = [
    "north", "north-northeast", "northeast", "east-northeast",
    "east", "east-southeast", "southeast", "south-southeast",
    "south", "south-southwest", "southwest", "west-southwest",
    "west", "west-northwest", "northwest", "north-northwest",
]

WEATHER_PHENOMENA = {
    "DZ": "drizzle", "RA": "rain", "SN": "snow", "SG": "snow grains",
    "IC": "ice crystals", "PL": "ice pellets", "GR": "hail",
    "GS": "small hail", "UP": "unknown precipitation",
    "BR": "mist", "FG": "fog", "FU": "smoke", "VA": "volcanic ash",
    "DU": "dust", "SA": "sand", "HZ": "haze", "PY": "spray",
    "PO": "dust/sand whirls", "SQ": "squalls", "FC": "funnel cloud",
    "SS": "sandstorm", "DS": "duststorm",
}

DESCRIPTORS = {
    "MI": "shallow", "BC": "patchy", "PR": "partial", "DR": "drifting",
    "BL": "blowing", "SH": "showers of", "TS": "thunderstorm with",
    "FZ": "freezing",
}

SKY_COVER = {
    "SKC": "clear sky", "CLR": "clear sky", "CAVOK": "ceiling and visibility OK",
    "NSC": "no significant clouds", "NCD": "no clouds detected",
    "FEW": "few clouds", "SCT": "scattered clouds",
    "BKN": "broken cloud layer", "OVC": "overcast", "VV": "vertical visibility",
}


def degrees_to_cardinal(deg):
    return WIND_DIRECTIONS[round(deg / 22.5) % 16]


def parse_temp(t):
    return -int(t[1:]) if t.startswith("M") else int(t)


def decode_wind(token):
    m = re.match(r"^(VRB|\d{3})(\d{2,3})(G(\d{2,3}))?(KT|MPS)$", token)
    if not m:
        return None
    direction_raw, speed_raw, _, gust_raw, unit = (
        m.group(1), m.group(2), m.group(3), m.group(4), m.group(5)
    )
    speed = int(speed_raw)
    gust = int(gust_raw) if gust_raw else None

    if unit == "MPS":
        speed = round(speed * 1.94384)
        gust = round(gust * 1.94384) if gust else None

    speed_mph = round(speed * 1.15078)
    gust_mph = round(gust * 1.15078) if gust else None

    if speed == 0:
        return {"text": "Calm winds", "speed_kt": 0, "speed_mph": 0, "direction": None}

    if direction_raw == "VRB":
        text = f"Variable winds at {speed} kt ({speed_mph} mph)"
    else:
        deg = int(direction_raw)
        cardinal = degrees_to_cardinal(deg)
        text = f"Wind from the {cardinal} ({deg}°) at {speed} kt ({speed_mph} mph)"

    if gust:
        text += f", gusting to {gust} kt ({gust_mph} mph)"

    return {
        "text": text,
        "speed_kt": speed,
        "speed_mph": speed_mph,
        "direction": None if direction_raw == "VRB" else int(direction_raw),
        "gust_kt": gust,
    }


def decode_visibility(parts, idx):
    part = parts[idx]
    if part == "M1/4SM":
        return "Less than ¼ mile", idx + 1
    if part == "9999":
        return "Visibility greater than 10 km", idx + 1
    if re.match(r"^\d+SM$", part):
        val = float(part[:-2])
        label = "Greater than 10 miles" if val >= 10 else f"{val:g} mile{'s' if val != 1 else ''}"
        return label, idx + 1
    # fraction visibility like "1 1/2SM"
    if re.match(r"^\d+$", part) and idx + 1 < len(parts) and re.match(r"^\d+/\d+SM$", parts[idx + 1]):
        whole = int(part)
        frac_str = parts[idx + 1][:-2]
        num, den = frac_str.split("/")
        val = whole + int(num) / int(den)
        return f"{val:g} miles", idx + 2
    if re.match(r"^\d+/\d+SM$", part):
        frac_str = part[:-2]
        num, den = frac_str.split("/")
        val = int(num) / int(den)
        return f"{val:g} miles", idx + 1
    return None, idx


def decode_weather(token):
    pattern = (
        r"^(\+|-|VC)?"
        r"(MI|BC|PR|DR|BL|SH|TS|FZ)?"
        r"(DZ|RA|SN|SG|IC|PL|GR|GS|UP|BR|FG|FU|VA|DU|SA|HZ|PY|PO|SQ|FC|SS|DS)+"
        r"$"
    )
    if not re.match(pattern, token):
        return None

    intensity_raw = re.match(r"^(\+|-|VC)", token)
    intensity_str = {"+": "heavy", "-": "light", "VC": "in the vicinity,"}.get(
        intensity_raw.group(1) if intensity_raw else "", "moderate"
    )
    if intensity_raw and intensity_raw.group(1) == "VC":
        intensity_str = "in the vicinity,"

    desc_match = re.match(r"^(\+|-|VC)?(MI|BC|PR|DR|BL|SH|TS|FZ)", token)
    descriptor = desc_match.group(2) if desc_match else ""
    desc_str = DESCRIPTORS.get(descriptor, "")

    phenomena_codes = re.findall(
        r"DZ|RA|SN|SG|IC|PL|GR|GS|UP|BR|FG|FU|VA|DU|SA|HZ|PY|PO|SQ|FC|SS|DS", token
    )
    phenom_str = " and ".join(WEATHER_PHENOMENA.get(c, c) for c in phenomena_codes)

    if descriptor == "TS" and not phenom_str:
        parts_wx = [intensity_str, "thunderstorm"] if intensity_raw else ["thunderstorm"]
    elif desc_str and phenom_str:
        parts_wx = [intensity_str, desc_str, phenom_str] if intensity_raw else [desc_str, phenom_str]
    elif phenom_str:
        parts_wx = [intensity_str, phenom_str] if intensity_raw else [phenom_str]
    else:
        return None

    return " ".join(p for p in parts_wx if p).strip().capitalize()


def decode_sky(token):
    m = re.match(r"^(SKC|CLR|CAVOK|NSC|NCD|FEW|SCT|BKN|OVC|VV)(\d{3})?(CB|TCU)?$", token)
    if not m:
        return None
    cover, height_raw, ctype = m.group(1), m.group(2), m.group(3)
    cover_str = SKY_COVER.get(cover, cover)
    if height_raw:
        height_ft = int(height_raw) * 100
        cloud_type = f" (cumulonimbus)" if ctype == "CB" else (" (towering cumulus)" if ctype == "TCU" else "")
        if cover in ("SKC", "CLR", "CAVOK", "NSC", "NCD"):
            return cover_str
        return f"{cover_str}{cloud_type} at {height_ft:,} ft"
    return cover_str


def decode_metar(raw):
    tokens = raw.strip().split()
    result = {"raw": raw.strip(), "components": {}}
    idx = 0

    if tokens[idx] in ("METAR", "SPECI"):
        idx += 1

    # Station
    result["station"] = tokens[idx]
    idx += 1

    # Date/time
    if idx < len(tokens) and re.match(r"^\d{6}Z$", tokens[idx]):
        t = tokens[idx]
        result["components"]["time"] = f"{t[2:4]}:{t[4:6]} UTC (day {int(t[:2])})"
        idx += 1

    # AUTO/COR
    if idx < len(tokens) and tokens[idx] in ("AUTO", "COR"):
        if tokens[idx] == "AUTO":
            result["components"]["note"] = "Automated station (no human observer)"
        idx += 1

    # Wind
    if idx < len(tokens) and re.match(r"^(VRB|\d{3})\d{2,3}(G\d{2,3})?(KT|MPS)$", tokens[idx]):
        wind = decode_wind(tokens[idx])
        if wind:
            result["components"]["wind"] = wind["text"]
            result["wind_data"] = wind
        idx += 1
        if idx < len(tokens) and re.match(r"^\d{3}V\d{3}$", tokens[idx]):
            var = tokens[idx]
            result["components"]["wind"] += f" (varying {var[:3]}° to {var[4:]}°)"
            idx += 1

    # Visibility
    vis_text, new_idx = decode_visibility(tokens, idx)
    if vis_text:
        result["components"]["visibility"] = vis_text
        idx = new_idx

    # RVR (runway visual range) — skip
    while idx < len(tokens) and re.match(r"^R\d{2}[LCR]?/", tokens[idx]):
        idx += 1

    # Weather phenomena
    wx_list = []
    while idx < len(tokens):
        wx = decode_weather(tokens[idx])
        if wx:
            wx_list.append(wx)
            idx += 1
        else:
            break
    if wx_list:
        result["components"]["weather"] = "; ".join(wx_list)

    # Sky conditions
    sky_list = []
    while idx < len(tokens):
        sky = decode_sky(tokens[idx])
        if sky:
            sky_list.append(sky)
            idx += 1
        else:
            break
    if sky_list:
        result["components"]["sky"] = "; ".join(sky_list).capitalize()

    # Temperature / dew point
    if idx < len(tokens) and re.match(r"^M?\d{2}/M?\d{0,2}$", tokens[idx]):
        parts_td = tokens[idx].split("/")
        temp_c = parse_temp(parts_td[0])
        temp_f = round(temp_c * 9 / 5 + 32)
        result["components"]["temperature"] = f"{temp_c}°C ({temp_f}°F)"
        if parts_td[1]:
            dew_c = parse_temp(parts_td[1])
            dew_f = round(dew_c * 9 / 5 + 32)
            result["components"]["dew_point"] = f"{dew_c}°C ({dew_f}°F)"
            rh = round(100 * (112 - 0.1 * temp_c + dew_c) / (112 + 0.9 * temp_c))
            result["components"]["humidity"] = f"{max(0, min(100, rh))}%"
        idx += 1

    # Altimeter
    if idx < len(tokens) and re.match(r"^A\d{4}$", tokens[idx]):
        val = int(tokens[idx][1:]) / 100
        hpa = round(val * 33.8639)
        result["components"]["pressure"] = f"{val:.2f} inHg ({hpa} hPa)"
        idx += 1
    elif idx < len(tokens) and re.match(r"^Q\d{4}$", tokens[idx]):
        hpa = int(tokens[idx][1:])
        inhg = round(hpa / 33.8639, 2)
        result["components"]["pressure"] = f"{hpa} hPa ({inhg:.2f} inHg)"
        idx += 1

    return result


def build_summary(decoded):
    c = decoded.get("components", {})
    parts = []

    sky = c.get("sky", "")
    weather = c.get("weather", "")

    if "clear sky" in sky.lower() or "ceiling and visibility ok" in sky.lower():
        parts.append("Clear skies")
    elif "overcast" in sky.lower():
        parts.append("Overcast")
    elif "broken" in sky.lower():
        parts.append("Mostly cloudy")
    elif "scattered" in sky.lower():
        parts.append("Partly cloudy")
    elif "few clouds" in sky.lower():
        parts.append("Mostly clear with a few clouds")

    if weather:
        parts.append(weather.lower())

    if "temperature" in c:
        parts.append(f"Temperature {c['temperature']}")

    if "wind" in c:
        wind = c["wind"].lower()
        if "calm" in wind:
            parts.append("calm winds")
        else:
            parts.append(c["wind"].lower())

    if "visibility" in c:
        vis = c["visibility"].lower()
        if "greater than 10" in vis:
            parts.append("excellent visibility")
        else:
            parts.append(f"visibility {vis}")

    if "humidity" in c:
        parts.append(f"humidity {c['humidity']}")

    if not parts:
        return "Weather data decoded — see details below."

    return ". ".join(p.capitalize() for p in parts) + "."


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/weather")
def get_weather():
    code = request.args.get("airport", "").strip().upper()
    if not code:
        return jsonify({"error": "Please enter an airport code."})
    if not re.match(r"^[A-Z0-9]{3,4}$", code):
        return jsonify({"error": "Invalid airport code format. Use ICAO codes like KJFK or EGLL."})

    try:
        url = f"https://aviationweather.gov/api/data/metar?ids={code}"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        raw = resp.text.strip()
    except requests.RequestException as e:
        return jsonify({"error": f"Could not reach the weather service: {e}"})

    if not raw:
        return jsonify({"error": f"No METAR data found for {code}. Check the airport code and try again."})

    decoded = decode_metar(raw)
    decoded["summary"] = build_summary(decoded)
    return jsonify(decoded)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")
