"""Tests for coordinate discovery: text scanner, structured file extraction,
and offline country resolution."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.geo.countries import country_count, resolve_country
from app.geo.extract import extract_file_coordinates
from app.geo.scanner import scan_text
from app.tools.geo_tools import (
    duachuot_geo_reverse,
    duachuot_geo_scan,
    duachuot_geo_verify,
)


def _formats(result: dict) -> set[str]:
    return {hit["format"] for hit in result["hits"]}


def test_scan_decimal_pair() -> None:
    result = scan_text("meeting point: 21.0294, 105.8525 after sunset")
    assert result["count"] == 1
    hit = result["hits"][0]
    assert hit["format"] == "decimal_pair"
    assert hit["lat"] == pytest.approx(21.0294)
    assert hit["lon"] == pytest.approx(105.8525)


def test_scan_decimal_pair_lon_lat_swap() -> None:
    result = scan_text("coords 105.8525, 21.0294 recorded")
    hit = result["hits"][0]
    assert hit["lat"] == pytest.approx(21.0294)
    assert hit["lon"] == pytest.approx(105.8525)


def test_scan_dms_with_hemispheres() -> None:
    result = scan_text("21°01'45.8\"N 105°51'08.9\"E confirmed")
    hit = result["hits"][0]
    assert hit["format"] == "dms"
    assert hit["lat"] == pytest.approx(21.02939, abs=1e-4)
    assert hit["lon"] == pytest.approx(105.85247, abs=1e-4)
    assert hit["confidence"] == "high"


def test_scan_labelled_values() -> None:
    result = scan_text('{"latitude": 48.8566, "longitude": 2.3522}')
    hit = result["hits"][0]
    assert hit["format"] == "labelled"
    assert hit["lat"] == pytest.approx(48.8566)
    assert hit["lon"] == pytest.approx(2.3522)


def test_scan_nmea_sentence() -> None:
    result = scan_text(
        "$GPRMC,123519,A,4807.038,N,01131.000,E,022.4,084.4,230394,003.1,W*6A"
    )
    hit = result["hits"][0]
    assert hit["format"] == "nmea"
    assert hit["lat"] == pytest.approx(48.1173, abs=1e-3)
    assert hit["lon"] == pytest.approx(11.5167, abs=1e-3)


def test_scan_mgrs_grid() -> None:
    from app.geo.convert import from_mgrs, to_mgrs

    mgrs = to_mgrs(21.0294, 105.8525)["mgrs_string"]
    result = scan_text(f"stash under grid {mgrs}")
    hit = result["hits"][0]
    assert hit["format"] == "mgrs"
    assert hit["lat"] == pytest.approx(21.0294, abs=1e-4)
    assert hit["lon"] == pytest.approx(105.8525, abs=1e-4)
    assert from_mgrs(mgrs)["lat"] == pytest.approx(21.0294, abs=1e-4)


def test_scan_utm_grid() -> None:
    result = scan_text("UTM zone 48N 663213 2318927 handoff")
    assert result["count"] >= 1
    hit = result["hits"][0]
    assert hit["format"] == "utm"
    assert hit["lat"] == pytest.approx(20.9, abs=0.5)
    assert hit["lon"] == pytest.approx(106.6, abs=0.8)


def test_scan_dji_srt_telemetry() -> None:
    result = scan_text(
        "[00:05:23] GPS (21.0294,105.8525) altitude 120.0m\n"
        "[00:05:25] GPS (21.0295,105.8528) altitude 120.5m"
    )
    assert result["count"] == 2
    assert {hit["format"] for hit in result["hits"]} == {"decimal_pair"}


def test_scan_empty_and_noise() -> None:
    assert scan_text("")["count"] == 0
    assert scan_text("nothing here but 42 and 108")["count"] == 0


@pytest.fixture()
def gpx_file(tmp_path: Path) -> Path:
    content = """<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="test">
  <wpt lat="21.0294" lon="105.8525"><name>Hoan Kiem</name></wpt>
  <trk><trkseg>
    <trkpt lat="21.0300" lon="105.8530"/>
  </trkseg></trk>
</gpx>"""
    path = tmp_path / "track.gpx"
    path.write_text(content, encoding="utf-8")
    return path


def test_extract_gpx(gpx_file: Path) -> None:
    result = extract_file_coordinates(str(gpx_file))
    assert result["count"] == 2
    assert {hit["format"] for hit in result["hits"]} == {"gpx"}
    assert result["best"]["lat"] == pytest.approx(21.0294)


def test_extract_kml(tmp_path: Path) -> None:
    content = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Placemark><Point><coordinates>105.8525,21.0294,0</coordinates></Point></Placemark>
</kml>"""
    path = tmp_path / "place.kml"
    path.write_text(content, encoding="utf-8")
    result = extract_file_coordinates(str(path))
    assert result["count"] == 1
    assert result["best"]["lat"] == pytest.approx(21.0294)
    assert result["best"]["lon"] == pytest.approx(105.8525)


def test_extract_geojson(tmp_path: Path) -> None:
    data = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [105.8525, 21.0294]},
            }
        ],
    }
    path = tmp_path / "points.geojson"
    path.write_text(json.dumps(data), encoding="utf-8")
    result = extract_file_coordinates(str(path))
    assert result["count"] == 1
    assert result["best"]["lat"] == pytest.approx(21.0294)


def test_extract_json_keys(tmp_path: Path) -> None:
    path = tmp_path / "meta.json"
    path.write_text(
        json.dumps({"drone": {"latitude": 48.8566, "longitude": 2.3522}}),
        encoding="utf-8",
    )
    result = extract_file_coordinates(str(path))
    assert result["count"] == 1
    assert result["best"]["format"] == "json_keys"
    assert result["best"]["lat"] == pytest.approx(48.8566)


def test_extract_srt(tmp_path: Path) -> None:
    path = tmp_path / "flight.srt"
    path.write_text("GPS (21.0294,105.8525) home point", encoding="utf-8")
    result = extract_file_coordinates(str(path))
    assert result["count"] == 1


def test_extract_missing_file() -> None:
    with pytest.raises(FileNotFoundError):
        extract_file_coordinates("/nonexistent/file.gpx")


@pytest.mark.parametrize(
    ("lat", "lon", "expected"),
    [
        (21.0294, 105.8525, "VN"),
        (48.8566, 2.3522, "FR"),
        (40.7128, -74.0060, "US"),
        (64.1466, -21.9426, "IS"),
        (-41.2865, 174.7762, "NZ"),
        (55.7558, 37.6173, "RU"),
        (1.3521, 103.8198, "SG"),
    ],
)
def test_resolve_country(lat: float, lon: float, expected: str) -> None:
    result = resolve_country(lat, lon)
    assert result["ok"]
    alternatives = {item["iso2"] for item in result["alternatives"]}
    assert expected in {result["iso2"]} | alternatives


def test_country_dataset_populated() -> None:
    assert country_count() >= 180


def test_geo_reverse_includes_country() -> None:
    result = duachuot_geo_reverse(21.0294, 105.8525)
    assert result["ok"]
    assert "country" in result
    assert "matches" in result


def test_geo_verify_country_fact_and_disambiguation() -> None:
    result = duachuot_geo_verify(21.0294, 105.8525)
    kinds = [fact["kind"] for fact in result["facts"]]
    assert "country" in kinds
    country_fact = next(f for f in result["facts"] if f["kind"] == "country")
    assert "VN" in country_fact["detail"]
    assert result["blocked"] is False
    assert result["confidence"] >= 0.99


def test_mcp_tool_scan_available() -> None:
    result = duachuot_geo_scan("drop at 10.7727,106.6983", source="test")
    assert result["ok"]
    assert result["count"] == 1