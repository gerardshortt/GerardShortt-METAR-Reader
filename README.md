# METAR Reader

A Flask web application that fetches live aviation weather reports (METARs) and decodes them into plain English.

METAR is the international standard format for reporting weather at airports. It is compact and cryptic by design — intended for pilots, not the general public. This app translates reports like:

```
METAR KJFK 191751Z 17010KT 10SM FEW060 FEW250 25/17 A3004
```

into a friendly, readable summary:

> **Mostly clear with a few clouds. Temperature 25°C (77°F). Wind from the south (170°) at 10 kt (12 mph). Excellent visibility. Humidity 94%.**

Live data is sourced from the [Aviation Weather Center](https://aviationweather.gov) — the official NOAA service used by pilots worldwide.

---

## Features

- Works with any ICAO airport code worldwide (e.g. `KJFK`, `EGLL`, `YSSY`)
- Decodes wind direction, speed, and gusts — in both knots and mph
- Translates sky conditions, cloud layers, and heights in feet
- Identifies precipitation types: rain, snow, fog, haze, thunderstorms, and more
- Displays temperature and dew point in both °C and °F
- Calculates relative humidity
- Shows barometric pressure in both inHg and hPa
- Handles both US (inHg) and international (QNH/hPa) altimeter formats
- Shows the raw METAR alongside the decoded output

---

## Requirements

- Python 3.8+
- pip

---

## Installation

**1. Clone the repository**

```bash
git clone https://github.com/gerardshortt/GerardShortt-METAR-Reader.git
cd GerardShortt-METAR-Reader
```

**2. (Optional) Create a virtual environment**

```bash
python -m venv venv
source venv/bin/activate        # macOS / Linux
venv\Scripts\activate           # Windows
```

**3. Install dependencies**

```bash
pip install -r requirements.txt
```

---

## Running the App

```bash
python app.py
```

Then open your browser and go to:

```
http://127.0.0.1:5000
```

Type any ICAO airport code into the search box and click **Get Weather**.

---

## ICAO Airport Codes

ICAO codes are 4-letter identifiers used by aviation authorities worldwide. A few examples:

| Code | Airport |
|------|---------|
| KJFK | New York JFK, USA |
| KLAX | Los Angeles, USA |
| EGLL | London Heathrow, UK |
| EIDW | Dublin, Ireland |
| YSSY | Sydney, Australia |
| RJTT | Tokyo Haneda, Japan |

You can look up any airport's ICAO code at [ourairports.com](https://ourairports.com).

---

## Running the Tests

The test suite uses [pytest](https://pytest.org) and covers 103 cases across two files — no network calls are made (the Aviation Weather API is mocked throughout).

**Install dev dependencies**

```bash
pip install -r requirements-dev.txt
```

**Run all tests**

```bash
pytest tests/
```

**Run with verbose output**

```bash
pytest tests/ -v
```

### Test structure

| File | What it tests |
|------|---------------|
| `tests/test_decoder.py` | Pure decoder functions — wind, visibility, weather phenomena, sky conditions, temperature, full METAR strings, and summary generation |
| `tests/test_routes.py` | Flask routes — input validation, successful responses with mocked METAR data, and API failure handling |

---

## Data Source

Weather data is fetched in real time from the [Aviation Weather Center API](https://aviationweather.gov/api/data/metar), operated by NOAA. No API key is required.

---

## License

MIT
