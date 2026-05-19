"""
Tests for the Flask routes in app.py.

requests.get is patched throughout so no real HTTP calls are made.
Mock METAR strings are passed as the API response body.
"""

import pytest
import requests as requests_lib
from unittest.mock import patch, MagicMock
from app import app as flask_app


@pytest.fixture
def client():
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as client:
        yield client


def mock_response(text, status_code=200):
    """Return a mock requests.Response with the given body text."""
    m = MagicMock()
    m.status_code = status_code
    m.text = text
    m.raise_for_status.return_value = None
    return m


# ---------------------------------------------------------------------------
# GET /
# ---------------------------------------------------------------------------

class TestIndexRoute:
    def test_homepage_returns_200(self, client):
        response = client.get("/")
        assert response.status_code == 200

    def test_homepage_contains_metar_heading(self, client):
        response = client.get("/")
        assert b"METAR" in response.data

    def test_homepage_contains_search_input(self, client):
        response = client.get("/")
        assert b"airport-input" in response.data


# ---------------------------------------------------------------------------
# GET /weather  — input validation
# ---------------------------------------------------------------------------

class TestWeatherValidation:
    def test_missing_airport_param_returns_error(self, client):
        data = client.get("/weather").get_json()
        assert "error" in data

    def test_empty_airport_param_returns_error(self, client):
        data = client.get("/weather?airport=").get_json()
        assert "error" in data

    def test_too_long_code_returns_error(self, client):
        data = client.get("/weather?airport=TOOLONG").get_json()
        assert "error" in data

    def test_special_characters_rejected(self, client):
        data = client.get("/weather?airport=KJ!K").get_json()
        assert "error" in data

    def test_two_letter_code_rejected(self, client):
        data = client.get("/weather?airport=KJ").get_json()
        assert "error" in data


# ---------------------------------------------------------------------------
# GET /weather  — successful responses
# ---------------------------------------------------------------------------

class TestWeatherSuccess:
    MOCK_METAR = "METAR KJFK 191751Z 17010KT 10SM FEW060 25/17 A3004"

    def test_returns_station(self, client):
        with patch("app.requests.get", return_value=mock_response(self.MOCK_METAR)):
            data = client.get("/weather?airport=KJFK").get_json()
        assert data["station"] == "KJFK"

    def test_returns_raw_metar(self, client):
        with patch("app.requests.get", return_value=mock_response(self.MOCK_METAR)):
            data = client.get("/weather?airport=KJFK").get_json()
        assert data["raw"] == self.MOCK_METAR

    def test_returns_summary(self, client):
        with patch("app.requests.get", return_value=mock_response(self.MOCK_METAR)):
            data = client.get("/weather?airport=KJFK").get_json()
        assert "summary" in data
        assert len(data["summary"]) > 0

    def test_returns_components(self, client):
        with patch("app.requests.get", return_value=mock_response(self.MOCK_METAR)):
            data = client.get("/weather?airport=KJFK").get_json()
        assert "components" in data
        assert "temperature" in data["components"]
        assert "wind" in data["components"]

    def test_airport_code_case_insensitive(self, client):
        with patch("app.requests.get", return_value=mock_response(self.MOCK_METAR)):
            data = client.get("/weather?airport=kjfk").get_json()
        assert data["station"] == "KJFK"

    def test_three_letter_code_accepted(self, client):
        metar = "KSFO 191751Z 27010KT 10SM CLR 18/10 A3002"
        with patch("app.requests.get", return_value=mock_response(metar)):
            data = client.get("/weather?airport=SFO").get_json()
        assert "error" not in data

    def test_european_metar_decoded(self, client):
        metar = "METAR EGLL 191820Z 22016KT 9999 SCT030 16/09 Q1009"
        with patch("app.requests.get", return_value=mock_response(metar)):
            data = client.get("/weather?airport=EGLL").get_json()
        assert "hPa" in data["components"]["pressure"]

    def test_overcast_low_cloud_metar(self, client):
        metar = "METAR KJFK 010000Z 00000KT 1SM FG OVC002 15/15 A2990"
        with patch("app.requests.get", return_value=mock_response(metar)):
            data = client.get("/weather?airport=KJFK").get_json()
        assert "fog" in data["components"]["weather"].lower()

    def test_thunderstorm_metar(self, client):
        metar = "METAR KJFK 010000Z 18015KT 3SM TSRA OVC010 22/20 A2980"
        with patch("app.requests.get", return_value=mock_response(metar)):
            data = client.get("/weather?airport=KJFK").get_json()
        assert "thunderstorm" in data["components"]["weather"].lower()

    def test_snow_metar(self, client):
        metar = "METAR CYYZ 010000Z 36010KT 2SM -SN OVC015 M02/M05 A2985"
        with patch("app.requests.get", return_value=mock_response(metar)):
            data = client.get("/weather?airport=CYYZ").get_json()
        assert "snow" in data["components"]["weather"].lower()


# ---------------------------------------------------------------------------
# GET /weather  — API failure handling
# ---------------------------------------------------------------------------

class TestWeatherAPIFailures:
    def test_empty_api_response_returns_error(self, client):
        with patch("app.requests.get", return_value=mock_response("")):
            data = client.get("/weather?airport=ZZZZ").get_json()
        assert "error" in data

    def test_connection_error_returns_error(self, client):
        with patch("app.requests.get", side_effect=requests_lib.RequestException("timeout")):
            data = client.get("/weather?airport=KJFK").get_json()
        assert "error" in data

    def test_http_error_returns_error(self, client):
        bad = mock_response("", status_code=500)
        bad.raise_for_status.side_effect = requests_lib.HTTPError("500")
        with patch("app.requests.get", return_value=bad):
            data = client.get("/weather?airport=KJFK").get_json()
        assert "error" in data
