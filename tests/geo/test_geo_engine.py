"""Round-trip tests for the Geo Engine (deterministic, offline)."""

import math

import pytest

from app.geo.convert import (
    datum_transform,
    from_mgrs,
    from_utm,
    normalize_coordinate,
    parse_dms,
    to_dms,
    to_mgrs,
    to_utm,
)
from app.geo.geodesic import uncertainty_from_dop, vincenty_inverse
from app.geo.timezone import timezone_at


class TestDMS:
    def test_parse_dms_decimal(self):
        assert parse_dms(51.5074) == pytest.approx(51.5074)

    def test_parse_dms_string_north(self):
        assert parse_dms('51°30\'26.5"N') == pytest.approx(51.5073611, abs=1e-6)

    def test_parse_dms_string_west(self):
        assert parse_dms('0°7\'39.9"W') == pytest.approx(-0.12775, abs=1e-5)

    def test_parse_dms_hemisphere_south(self):
        assert parse_dms("-33.8568") == pytest.approx(-33.8568)

    def test_dms_round_trip(self):
        for decimal in (-33.8568, 51.5074, 21.0285, 90.0, -90.0, 0.0):
            dms = to_dms(decimal, axis="lat")
            assert parse_dms(dms["dms_string"]) == pytest.approx(decimal, abs=1e-6)

    def test_dms_rollover(self):
        dms = to_dms(60.0 - 1e-12, axis="lat")
        assert dms["degrees"] == 60 and dms["minutes"] == 0 and dms["seconds"] == 0.0


class TestUTM:
    @pytest.mark.parametrize(
        ("lat", "lon", "zone"),
        [
            (21.0285, 105.8542, 48),  # Hanoi
            (-33.8568, 151.2153, 56),  # Sydney
            (48.8566, 2.3522, 31),  # Paris
            (40.7128, -74.0060, 18),  # New York
            (0.0, 0.0, 31),  # Null island
        ],
    )
    def test_utm_round_trip(self, lat, lon, zone):
        utm = to_utm(lat, lon)
        assert utm["zone"] == zone
        back = from_utm(utm["zone"], utm["hemisphere"], utm["easting_m"], utm["northing_m"])
        assert back["lat"] == pytest.approx(lat, abs=1e-5)
        assert back["lon"] == pytest.approx(lon, abs=1e-5)


class TestMGRS:
    def test_paris_wikipedia_example(self):
        # Wikipedia canonical example: 31U DQ 48251 11932
        mgrs = to_mgrs(48.85837, 2.29449)
        assert mgrs["zone"] == 31
        assert mgrs["band"] == "U"
        assert mgrs["square"] == "DQ"
        assert int(mgrs["easting_m"]) in range(48200, 48300)
        assert int(mgrs["northing_m"]) in range(11900, 12000)

    def test_mgrs_round_trip_easting_northing(self):
        mgrs = to_mgrs(-33.8568, 151.2153)
        assert mgrs["zone"] == 56 and mgrs["band"] == "H"

    def test_mgrs_lat_band_limits(self):
        with pytest.raises(ValueError):
            to_mgrs(85.0, 0.0)

    @pytest.mark.parametrize(
        ("lat", "lon"),
        [
            (48.8566, 2.3522),
            (-33.8688, 151.2093),
            (21.0285, 105.8542),
            (0.0, 0.0),
            (64.0, -21.9),
            (-30.0, -150.0),
            (84.0, 45.0),
            (-80.0, 45.0),
            (72.0, 10.0),
        ],
    )
    def test_mgrs_round_trip(self, lat, lon):
        mgrs = to_mgrs(lat, lon)
        back = from_mgrs(mgrs["mgrs_string"])
        assert back["lat"] == pytest.approx(lat, abs=5e-5)
        assert back["lon"] == pytest.approx(lon, abs=5e-5)

    def test_mgrs_paris_wikipedia_example_round_trip(self):
        back = from_mgrs("31U DQ 48251 11932")
        assert back["lat"] == pytest.approx(48.85819, abs=5e-4)
        assert back["lon"] == pytest.approx(2.29449, abs=5e-4)

    def test_mgrs_unparseable(self):
        with pytest.raises(ValueError):
            from_mgrs("not-a-mgrs")


class TestDatum:
    def test_identity(self):
        out = datum_transform(21.0285, 105.8542, source="WGS84", target="WGS84")
        assert out["lat"] == pytest.approx(21.0285)
        assert out["lon"] == pytest.approx(105.8542)

    def test_ed50_shift_is_documented(self):
        out = datum_transform(21.0285, 105.8542, source="ED50", target="WGS84")
        drift = math.hypot(out["lat"] - 21.0285, out["lon"] - 105.8542)
        assert drift > 0.0005  # tens of meters minimum
        assert abs(drift) < 0.01  # but not absurd

    def test_unsupported_datum(self):
        with pytest.raises(ValueError):
            datum_transform(0.0, 0.0, source="MARS")


class TestGeodesic:
    def test_paris_london_distance(self):
        geo = vincenty_inverse(48.8566, 2.3522, 51.5074, -0.1278)
        assert geo["distance_m"] == pytest.approx(343_500, rel=0.01)

    def test_zero_distance(self):
        geo = vincenty_inverse(21.0285, 105.8542, 21.0285, 105.8542)
        assert geo["distance_m"] == 0.0

    def test_uncertainty_dop(self):
        out = uncertainty_from_dop(1.2)
        assert out["accuracy_m"] == pytest.approx(6.0)

    def test_uncertainty_hpe_preferred(self):
        out = uncertainty_from_dop(5.0, gps_hpe=2.4)
        assert out["accuracy_m"] == pytest.approx(2.4)
        assert out["source"] == "gps_hpe"


class TestNormalize:
    def test_dms_with_ref(self):
        out = normalize_coordinate('51°30\'26.5"', ref="N", axis="lat")
        assert out["decimal"] == pytest.approx(51.5073611, abs=1e-6)

    def test_ref_west_flips(self):
        out = normalize_coordinate("2.29449", ref="W", axis="lon")
        assert out["decimal"] == pytest.approx(-2.29449)

    def test_invalid(self):
        with pytest.raises(ValueError):
            normalize_coordinate("abc", axis="lat")


class TestTimezone:
    def test_hanoi(self):
        out = timezone_at(21.0285, 105.8542)
        assert out["timezone"] == "Asia/Ho_Chi_Minh"
        assert out["utc_offset_hours"] == 7.0

    def test_out_of_range(self):
        with pytest.raises(ValueError):
            timezone_at(95.0, 0.0)