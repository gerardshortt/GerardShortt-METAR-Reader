"""
Unit tests for the METAR decoder functions in app.py.

All tests use hardcoded mock METAR strings — no network calls are made.
Each test class targets a single decoder function.
"""

import pytest
from app import (
    degrees_to_cardinal,
    parse_temp,
    decode_wind,
    decode_visibility,
    decode_weather,
    decode_sky,
    decode_metar,
    build_summary,
)


# ---------------------------------------------------------------------------
# degrees_to_cardinal
# ---------------------------------------------------------------------------

class TestDegreesToCardinal:
    def test_north(self):
        assert degrees_to_cardinal(0) == "north"

    def test_north_at_360(self):
        assert degrees_to_cardinal(360) == "north"

    def test_east(self):
        assert degrees_to_cardinal(90) == "east"

    def test_south(self):
        assert degrees_to_cardinal(180) == "south"

    def test_west(self):
        assert degrees_to_cardinal(270) == "west"

    def test_northeast(self):
        assert degrees_to_cardinal(45) == "northeast"

    def test_southwest(self):
        assert degrees_to_cardinal(225) == "southwest"

    def test_northwest(self):
        assert degrees_to_cardinal(315) == "northwest"


# ---------------------------------------------------------------------------
# parse_temp
# ---------------------------------------------------------------------------

class TestParseTemp:
    def test_positive(self):
        assert parse_temp("15") == 15

    def test_zero(self):
        assert parse_temp("00") == 0

    def test_below_zero(self):
        assert parse_temp("M03") == -3

    def test_below_zero_double_digit(self):
        assert parse_temp("M15") == -15


# ---------------------------------------------------------------------------
# decode_wind
# ---------------------------------------------------------------------------

class TestDecodeWind:
    def test_calm(self):
        result = decode_wind("00000KT")
        assert result["text"] == "Calm winds"
        assert result["speed_kt"] == 0
        assert result["direction"] is None

    def test_steady_wind_knots(self):
        result = decode_wind("27015KT")
        assert result["speed_kt"] == 15
        assert result["direction"] == 270
        assert "west" in result["text"]

    def test_south_wind(self):
        result = decode_wind("18010KT")
        assert result["direction"] == 180
        assert "south" in result["text"]

    def test_wind_with_gusts(self):
        result = decode_wind("18020G35KT")
        assert result["gust_kt"] == 35
        assert "gusting" in result["text"]

    def test_variable_direction(self):
        result = decode_wind("VRB05KT")
        assert "Variable" in result["text"]
        assert result["direction"] is None

    def test_mps_converted_to_knots(self):
        result = decode_wind("09010MPS")
        assert result["speed_kt"] == round(10 * 1.94384)

    def test_three_digit_speed(self):
        # Winds >= 100 kt use a 3-digit speed field, e.g. "360100KT"
        result = decode_wind("360100KT")
        assert result["speed_kt"] == 100

    def test_invalid_token_returns_none(self):
        assert decode_wind("INVALID") is None

    def test_sky_token_not_matched(self):
        assert decode_wind("BKN025") is None


# ---------------------------------------------------------------------------
# decode_visibility
# ---------------------------------------------------------------------------

class TestDecodeVisibility:
    def test_10sm_or_more(self):
        text, idx = decode_visibility(["10SM"], 0)
        assert "Greater than 10" in text
        assert idx == 1

    def test_6_miles(self):
        text, _ = decode_visibility(["6SM"], 0)
        assert "6 miles" in text

    def test_1_mile_singular(self):
        text, _ = decode_visibility(["1SM"], 0)
        assert text == "1 mile"

    def test_below_quarter_mile(self):
        text, idx = decode_visibility(["M1/4SM"], 0)
        assert "Less than" in text
        assert idx == 1

    def test_9999_icao_unrestricted(self):
        text, _ = decode_visibility(["9999"], 0)
        assert "10 km" in text

    def test_half_mile_single_token(self):
        text, idx = decode_visibility(["1/2SM"], 0)
        assert "0.5" in text
        assert idx == 1

    def test_fractional_two_tokens(self):
        text, idx = decode_visibility(["1", "1/2SM", "FEW050"], 0)
        assert "1.5" in text
        assert idx == 2

    def test_no_match_returns_none(self):
        text, idx = decode_visibility(["SKC"], 0)
        assert text is None
        assert idx == 0

    def test_index_advances_correctly(self):
        tokens = ["BKN020", "10SM", "FEW050"]
        _, idx = decode_visibility(tokens, 1)
        assert idx == 2


# ---------------------------------------------------------------------------
# decode_weather
# ---------------------------------------------------------------------------

class TestDecodeWeather:
    def test_light_rain(self):
        assert decode_weather("-RA") == "Light rain"

    def test_heavy_snow(self):
        assert decode_weather("+SN") == "Heavy snow"

    def test_moderate_rain(self):
        assert decode_weather("RA") == "Rain"

    def test_fog(self):
        assert decode_weather("FG") == "Fog"

    def test_mist(self):
        assert decode_weather("BR") == "Mist"

    def test_haze(self):
        assert decode_weather("HZ") == "Haze"

    def test_thunderstorm_alone(self):
        assert decode_weather("TS") == "Thunderstorm"

    def test_thunderstorm_with_rain(self):
        result = decode_weather("TSRA")
        assert "thunderstorm" in result.lower()
        assert "rain" in result.lower()

    def test_freezing_rain(self):
        result = decode_weather("FZRA")
        assert "freezing" in result.lower()
        assert "rain" in result.lower()

    def test_heavy_blowing_snow(self):
        result = decode_weather("+BLSN")
        assert "heavy" in result.lower()
        assert "snow" in result.lower()

    def test_shower_rain(self):
        result = decode_weather("SHRA")
        assert "rain" in result.lower()

    def test_vicinity_shower(self):
        result = decode_weather("VCSH")
        assert result is not None

    def test_sky_token_not_matched(self):
        assert decode_weather("BKN025") is None

    def test_wind_token_not_matched(self):
        assert decode_weather("27015KT") is None


# ---------------------------------------------------------------------------
# decode_sky
# ---------------------------------------------------------------------------

class TestDecodeSky:
    def test_skc_clear(self):
        assert decode_sky("SKC") == "clear sky"

    def test_clr_clear(self):
        assert decode_sky("CLR") == "clear sky"

    def test_cavok(self):
        assert decode_sky("CAVOK") == "ceiling and visibility OK"

    def test_few_clouds_with_height(self):
        result = decode_sky("FEW050")
        assert "few clouds" in result
        assert "5,000 ft" in result

    def test_scattered_clouds(self):
        result = decode_sky("SCT025")
        assert "scattered clouds" in result
        assert "2,500 ft" in result

    def test_broken_layer(self):
        result = decode_sky("BKN010")
        assert "broken" in result
        assert "1,000 ft" in result

    def test_overcast(self):
        result = decode_sky("OVC008")
        assert "overcast" in result
        assert "800 ft" in result

    def test_cumulonimbus_suffix(self):
        result = decode_sky("BKN025CB")
        assert "cumulonimbus" in result
        assert "2,500 ft" in result

    def test_towering_cumulus_suffix(self):
        result = decode_sky("SCT030TCU")
        assert "towering cumulus" in result

    def test_vertical_visibility(self):
        result = decode_sky("VV010")
        assert result is not None

    def test_wind_token_not_matched(self):
        assert decode_sky("27015KT") is None

    def test_temp_token_not_matched(self):
        assert decode_sky("15/08") is None


# ---------------------------------------------------------------------------
# decode_metar  (full-string integration of the above functions)
# ---------------------------------------------------------------------------

class TestDecodeMetar:
    def test_station_extracted(self):
        result = decode_metar("METAR KJFK 191751Z 17010KT 10SM FEW060 25/17 A3004")
        assert result["station"] == "KJFK"

    def test_time_extracted(self):
        result = decode_metar("METAR KJFK 191751Z 17010KT 10SM FEW060 25/17 A3004")
        assert "17:51" in result["components"]["time"]

    def test_wind_decoded(self):
        result = decode_metar("METAR KJFK 191751Z 17010KT 10SM FEW060 25/17 A3004")
        assert "south" in result["components"]["wind"]

    def test_calm_winds(self):
        result = decode_metar("METAR KHIO 191753Z 00000KT 10SM OVC060 16/08 A3028")
        assert result["components"]["wind"] == "Calm winds"

    def test_temperature_celsius_and_fahrenheit(self):
        result = decode_metar("METAR KJFK 191751Z 17010KT 10SM FEW060 25/17 A3004")
        assert result["components"]["temperature"] == "25°C (77°F)"

    def test_negative_temperature(self):
        result = decode_metar("METAR CYYZ 010000Z 36010KT 15SM BKN020 M05/M10 A2990")
        assert result["components"]["temperature"] == "-5°C (23°F)"
        assert result["components"]["dew_point"] == "-10°C (14°F)"

    def test_dew_point_and_humidity_present(self):
        result = decode_metar("METAR KJFK 191751Z 17010KT 10SM FEW060 25/17 A3004")
        assert "dew_point" in result["components"]
        assert "humidity" in result["components"]

    def test_us_altimeter_inhg(self):
        result = decode_metar("METAR KJFK 191751Z 17010KT 10SM FEW060 25/17 A3004")
        assert "30.04 inHg" in result["components"]["pressure"]

    def test_european_qnh_hpa(self):
        result = decode_metar("METAR EGLL 191820Z 22016KT 9999 SCT030 16/09 Q1009")
        assert "1009 hPa" in result["components"]["pressure"]

    def test_auto_station_note(self):
        result = decode_metar("METAR EGLL 191820Z AUTO 22016KT 9999 SCT030 16/09 Q1009")
        assert "Automated" in result["components"]["note"]

    def test_variable_wind_range(self):
        result = decode_metar("METAR EGLL 191820Z 22016KT 180V260 9999 SCT030 16/09 Q1009")
        assert "varying" in result["components"]["wind"]

    def test_weather_phenomena_decoded(self):
        result = decode_metar("METAR KJFK 191751Z 17010KT 5SM -RA BKN020 20/18 A2990")
        assert "weather" in result["components"]
        assert "rain" in result["components"]["weather"].lower()

    def test_thunderstorm_decoded(self):
        result = decode_metar("METAR KJFK 010000Z 18015KT 3SM TSRA OVC010 22/20 A2980")
        assert "thunderstorm" in result["components"]["weather"].lower()

    def test_multiple_sky_layers(self):
        result = decode_metar("METAR KHIO 191753Z 00000KT 10SM BKN031 BKN040 OVC060 16/08 A3028")
        sky = result["components"]["sky"]
        assert sky.count("ft") == 3

    def test_raw_string_preserved(self):
        raw = "METAR KJFK 191751Z 17010KT 10SM FEW060 25/17 A3004"
        result = decode_metar(raw)
        assert result["raw"] == raw

    def test_metar_prefix_optional(self):
        with_prefix    = decode_metar("METAR KJFK 191751Z 00000KT 10SM CLR 20/10 A3000")
        without_prefix = decode_metar("KJFK 191751Z 00000KT 10SM CLR 20/10 A3000")
        assert with_prefix["station"] == without_prefix["station"]


# ---------------------------------------------------------------------------
# build_summary
# ---------------------------------------------------------------------------

class TestBuildSummary:
    def test_clear_sky_summary(self):
        decoded = {"components": {"sky": "clear sky", "temperature": "20°C (68°F)"}}
        assert "Clear skies" in build_summary(decoded)

    def test_overcast_summary(self):
        decoded = {"components": {"sky": "Overcast at 1,000 ft"}}
        assert "Overcast" in build_summary(decoded)

    def test_broken_clouds_summary(self):
        decoded = {"components": {"sky": "Broken cloud layer at 3,000 ft"}}
        assert "Mostly cloudy" in build_summary(decoded)

    def test_scattered_clouds_summary(self):
        decoded = {"components": {"sky": "Scattered clouds at 5,000 ft"}}
        assert "Partly cloudy" in build_summary(decoded)

    def test_few_clouds_summary(self):
        decoded = {"components": {"sky": "Few clouds at 8,000 ft"}}
        assert "Mostly clear" in build_summary(decoded)

    def test_calm_winds_in_summary(self):
        decoded = {"components": {"wind": "Calm winds"}}
        assert "calm winds" in build_summary(decoded).lower()

    def test_excellent_visibility_label(self):
        decoded = {"components": {"visibility": "Greater than 10 miles"}}
        assert "excellent visibility" in build_summary(decoded).lower()

    def test_limited_visibility_shown(self):
        decoded = {"components": {"visibility": "3 miles"}}
        assert "3 miles" in build_summary(decoded)

    def test_empty_components_fallback(self):
        assert build_summary({"components": {}}) == "Weather data decoded — see details below."

    def test_summary_ends_with_period(self):
        decoded = {"components": {"sky": "clear sky", "temperature": "15°C (59°F)"}}
        assert build_summary(decoded).endswith(".")
