"""Geo Engine — offline country resolution from coordinates.

Compact bounding-box dataset (no network, deterministic). Resolution is a
heuristic: a point inside a country bbox is reported with ``method``
``bbox-heuristic``. Over-coverage is possible for non-convex countries
(e.g. a point over the Pacific matches Russia's bbox); combine with the
landmark and timezone facts before drawing conclusions.
"""

from __future__ import annotations

from typing import Any

# ISO 3166-1 alpha-2 -> (name, lat_min, lat_max, lon_min, lon_max)
# Entries with lon_min > lon_max cross the antimeridian.
_COUNTRIES: dict[str, tuple[str, float, float, float, float]] = {
    "AD": ("Andorra", 42.4, 42.7, 1.4, 1.8),
    "AE": ("United Arab Emirates", 22.6, 26.1, 51.5, 56.4),
    "AF": ("Afghanistan", 29.4, 38.5, 60.5, 74.9),
    "AG": ("Antigua and Barbuda", 16.9, 17.7, -61.9, -61.6),
    "AL": ("Albania", 39.6, 42.7, 19.3, 21.1),
    "AM": ("Armenia", 38.8, 41.3, 43.4, 46.6),
    "AO": ("Angola", -18.0, -4.4, 11.7, 24.1),
    "AR": ("Argentina", -55.1, -21.8, -73.6, -53.6),
    "AT": ("Austria", 46.4, 49.0, 9.5, 17.2),
    "AU": ("Australia", -43.6, -10.7, 112.9, 153.6),
    "AZ": ("Azerbaijan", 38.4, 41.9, 44.7, 50.4),
    "BA": ("Bosnia and Herzegovina", 42.6, 45.3, 15.7, 19.6),
    "BB": ("Barbados", 13.0, 13.3, -59.7, -59.4),
    "BD": ("Bangladesh", 20.6, 26.6, 88.0, 92.7),
    "BE": ("Belgium", 49.5, 51.5, 2.5, 6.4),
    "BF": ("Burkina Faso", 9.4, 15.1, -5.5, 2.4),
    "BG": ("Bulgaria", 41.2, 44.2, 22.4, 28.6),
    "BH": ("Bahrain", 25.5, 26.3, 50.4, 50.8),
    "BI": ("Burundi", -4.5, -2.3, 29.0, 30.8),
    "BJ": ("Benin", 6.2, 12.4, 0.8, 3.9),
    "BN": ("Brunei", 4.0, 5.1, 114.1, 115.4),
    "BO": ("Bolivia", -22.9, -9.7, -69.6, -57.5),
    "BR": ("Brazil", -33.8, 5.3, -74.0, -34.8),
    "BS": ("Bahamas", 20.9, 27.0, -80.5, -72.7),
    "BT": ("Bhutan", 26.7, 28.4, 88.7, 92.1),
    "BW": ("Botswana", -26.9, -17.8, 20.0, 29.4),
    "BY": ("Belarus", 51.3, 56.2, 23.2, 32.8),
    "BZ": ("Belize", 15.9, 18.5, -89.2, -87.8),
    "CA": ("Canada", 41.7, 83.1, -141.0, -52.6),
    "CD": ("DR Congo", -13.5, 5.4, 12.2, 31.3),
    "CF": ("Central African Republic", 2.2, 11.0, 14.4, 27.5),
    "CG": ("Republic of Congo", -5.0, 3.7, 11.2, 18.6),
    "CH": ("Switzerland", 45.8, 47.8, 5.9, 10.5),
    "CI": ("Cote d'Ivoire", 4.4, 10.7, -8.6, -2.5),
    "CL": ("Chile", -56.0, -17.5, -75.6, -66.0),
    "CM": ("Cameroon", 1.7, 13.1, 8.5, 16.2),
    "CN": ("China", 18.0, 53.6, 73.5, 134.8),
    "CO": ("Colombia", -4.2, 13.4, -79.0, -66.9),
    "CR": ("Costa Rica", 8.0, 11.2, -85.9, -82.5),
    "CU": ("Cuba", 19.8, 23.3, -85.0, -74.1),
    "CV": ("Cape Verde", 14.8, 17.2, -25.4, -22.6),
    "CY": ("Cyprus", 34.6, 35.7, 32.3, 34.6),
    "CZ": ("Czech Republic", 48.6, 51.1, 12.1, 18.9),
    "DE": ("Germany", 47.3, 55.1, 5.9, 15.0),
    "DJ": ("Djibouti", 10.9, 12.7, 41.8, 43.4),
    "DK": ("Denmark", 54.6, 57.8, 8.0, 15.2),
    "DM": ("Dominica", 15.2, 15.6, -61.5, -61.2),
    "DO": ("Dominican Republic", 17.5, 19.9, -72.0, -68.3),
    "DZ": ("Algeria", 18.9, 37.1, -8.7, 12.0),
    "EC": ("Ecuador", -5.0, 1.4, -81.0, -75.2),
    "EE": ("Estonia", 57.5, 59.7, 21.8, 28.2),
    "EG": ("Egypt", 22.0, 31.7, 24.7, 37.0),
    "EH": ("Western Sahara", 20.8, 27.7, -17.1, -8.7),
    "ER": ("Eritrea", 12.4, 18.0, 36.4, 43.1),
    "ES": ("Spain", 27.6, 43.8, -18.2, 4.3),
    "ET": ("Ethiopia", 3.4, 14.9, 32.9, 48.0),
    "FI": ("Finland", 59.8, 70.1, 20.6, 31.6),
    "FJ": ("Fiji", -19.1, -12.5, 177.2, -178.4),
    "FK": ("Falkland Islands", -52.4, -51.0, -61.5, -57.7),
    "FM": ("Micronesia", 0.9, 10.1, 137.4, 163.0),
    "FR": ("France", 41.3, 51.1, -5.1, 9.6),
    "GA": ("Gabon", -3.9, 2.3, 8.7, 14.5),
    "GB": ("United Kingdom", 49.9, 60.9, -8.2, 1.8),
    "GD": ("Grenada", 11.9, 12.5, -61.8, -61.4),
    "GE": ("Georgia", 41.1, 43.6, 40.0, 46.7),
    "GF": ("French Guiana", 2.1, 5.8, -54.5, -51.6),
    "GH": ("Ghana", 4.7, 11.2, -3.3, 1.2),
    "GL": ("Greenland", 59.8, 83.6, -73.0, -12.0),
    "GM": ("Gambia", 13.1, 13.8, -16.8, -13.8),
    "GN": ("Guinea", 7.2, 12.7, -15.1, -7.6),
    "GQ": ("Equatorial Guinea", 1.0, 3.8, 5.6, 11.3),
    "GR": ("Greece", 34.8, 41.7, 19.6, 28.2),
    "GT": ("Guatemala", 13.7, 17.8, -92.2, -88.2),
    "GU": ("Guam", 13.2, 13.7, 144.6, 145.0),
    "GW": ("Guinea-Bissau", 10.9, 12.7, -16.7, -13.6),
    "GY": ("Guyana", 1.2, 8.6, -61.4, -56.5),
    "HN": ("Honduras", 12.9, 16.5, -89.4, -83.1),
    "HR": ("Croatia", 42.4, 46.6, 13.5, 19.4),
    "HT": ("Haiti", 18.0, 20.1, -74.5, -71.6),
    "HU": ("Hungary", 45.7, 48.6, 16.1, 22.9),
    "ID": ("Indonesia", -11.0, 6.1, 95.0, 141.0),
    "IE": ("Ireland", 51.4, 55.4, -10.5, -6.0),
    "IL": ("Israel", 29.5, 33.3, 34.2, 35.9),
    "IN": ("India", 6.7, 35.5, 68.2, 97.4),
    "IQ": ("Iraq", 29.1, 37.4, 38.8, 48.6),
    "IR": ("Iran", 25.1, 39.8, 44.0, 63.3),
    "IS": ("Iceland", 63.3, 66.6, -24.5, -13.5),
    "IT": ("Italy", 35.5, 47.1, 6.6, 18.5),
    "JM": ("Jamaica", 17.7, 18.5, -78.4, -76.2),
    "JO": ("Jordan", 29.2, 33.4, 34.9, 39.3),
    "JP": ("Japan", 24.0, 45.5, 122.9, 145.8),
    "KE": ("Kenya", -4.7, 5.0, 33.9, 41.9),
    "KG": ("Kyrgyzstan", 39.2, 43.3, 69.3, 80.2),
    "KH": ("Cambodia", 10.4, 14.7, 102.3, 107.6),
    "KI": ("Kiribati", -11.5, 4.7, -179.8, 179.5),
    "KM": ("Comoros", -12.4, -11.4, 43.2, 44.6),
    "KN": ("Saint Kitts and Nevis", 17.1, 17.4, -62.9, -62.5),
    "KP": ("North Korea", 37.7, 43.0, 124.4, 130.9),
    "KR": ("South Korea", 33.1, 38.6, 126.0, 129.6),
    "KW": ("Kuwait", 28.5, 30.1, 46.6, 48.4),
    "KZ": ("Kazakhstan", 40.6, 55.4, 46.5, 87.4),
    "LA": ("Laos", 13.9, 22.5, 100.1, 107.7),
    "LB": ("Lebanon", 33.0, 34.7, 35.1, 36.6),
    "LC": ("Saint Lucia", 13.7, 14.1, -61.1, -60.9),
    "LI": ("Liechtenstein", 47.1, 47.3, 9.5, 9.6),
    "LK": ("Sri Lanka", 5.9, 9.8, 79.7, 81.9),
    "LR": ("Liberia", 4.3, 8.6, -11.5, -7.4),
    "LS": ("Lesotho", -30.7, -28.6, 27.0, 29.5),
    "LT": ("Lithuania", 53.9, 56.5, 20.9, 26.8),
    "LU": ("Luxembourg", 49.4, 50.2, 5.7, 6.5),
    "LV": ("Latvia", 55.7, 58.1, 21.0, 28.2),
    "LY": ("Libya", 19.5, 33.2, 9.3, 25.2),
    "MA": ("Morocco", 27.7, 35.9, -13.2, -1.0),
    "MC": ("Monaco", 43.7, 43.8, 7.4, 7.4),
    "MD": ("Moldova", 45.5, 48.5, 26.6, 30.1),
    "ME": ("Montenegro", 41.9, 43.6, 18.4, 20.4),
    "MG": ("Madagascar", -25.6, -12.0, 43.2, 50.5),
    "MH": ("Marshall Islands", 4.6, 14.7, 160.8, 172.0),
    "MK": ("North Macedonia", 40.8, 42.4, 20.4, 23.0),
    "ML": ("Mali", 10.2, 25.0, -12.2, 4.3),
    "MM": ("Myanmar", 9.8, 28.5, 92.2, 101.2),
    "MN": ("Mongolia", 41.6, 52.1, 87.7, 119.9),
    "MR": ("Mauritania", 14.7, 27.3, -17.1, -4.8),
    "MT": ("Malta", 35.8, 36.1, 14.2, 14.6),
    "MU": ("Mauritius", -21.4, -19.3, 57.3, 63.5),
    "MV": ("Maldives", -0.7, 7.1, 72.6, 73.8),
    "MW": ("Malawi", -17.1, -9.4, 32.7, 35.9),
    "MX": ("Mexico", 14.5, 32.7, -118.4, -86.7),
    "MY": ("Malaysia", 0.9, 7.4, 99.6, 119.3),
    "MZ": ("Mozambique", -26.9, -10.4, 30.2, 40.8),
    "NA": ("Namibia", -28.9, -16.9, 11.7, 25.3),
    "NC": ("New Caledonia", -22.7, -19.5, 164.0, 167.4),
    "NE": ("Niger", 11.7, 23.5, 0.2, 16.0),
    "NG": ("Nigeria", 4.3, 13.9, 2.7, 14.7),
    "NI": ("Nicaragua", 11.0, 15.0, -87.7, -83.1),
    "NL": ("Netherlands", 50.8, 53.6, 3.4, 7.2),
    "NO": ("Norway", 57.9, 71.2, 4.6, 31.1),
    "NP": ("Nepal", 26.3, 30.4, 80.0, 88.2),
    "NZ": ("New Zealand", -47.3, -34.4, 166.4, 178.6),
    "OM": ("Oman", 16.6, 26.5, 52.0, 59.9),
    "PA": ("Panama", 7.2, 9.7, -83.1, -77.2),
    "PE": ("Peru", -18.3, -0.0, -81.4, -68.7),
    "PG": ("Papua New Guinea", -11.7, -1.3, 141.0, 156.0),
    "PH": ("Philippines", 4.6, 21.1, 116.9, 126.6),
    "PK": ("Pakistan", 23.7, 37.1, 60.9, 77.8),
    "PL": ("Poland", 49.0, 54.8, 14.1, 24.2),
    "PR": ("Puerto Rico", 17.9, 18.5, -67.3, -65.2),
    "PS": ("Palestine", 31.2, 32.6, 34.2, 35.6),
    "PT": ("Portugal", 36.9, 42.2, -9.5, -6.2),
    "PW": ("Palau", 2.8, 8.1, 131.1, 134.7),
    "PY": ("Paraguay", -27.6, -19.3, -62.6, -54.3),
    "QA": ("Qatar", 24.5, 26.2, 50.7, 51.6),
    "RO": ("Romania", 43.6, 48.3, 20.3, 29.7),
    "RS": ("Serbia", 42.2, 46.2, 18.8, 23.0),
    "RU": ("Russia", 41.2, 81.9, 19.6, 179.9),
    "RW": ("Rwanda", -2.8, -1.0, 28.9, 30.9),
    "SA": ("Saudi Arabia", 16.3, 32.2, 34.5, 55.7),
    "SB": ("Solomon Islands", -11.9, -5.9, 155.5, 166.9),
    "SC": ("Seychelles", -10.2, -3.7, 46.2, 56.3),
    "SD": ("Sudan", 8.7, 22.2, 21.8, 38.6),
    "SE": ("Sweden", 55.3, 69.1, 11.1, 24.2),
    "SG": ("Singapore", 1.2, 1.5, 103.6, 104.1),
    "SI": ("Slovenia", 45.4, 46.9, 13.4, 16.6),
    "SK": ("Slovakia", 47.7, 49.6, 16.8, 22.6),
    "SL": ("Sierra Leone", 6.9, 10.0, -13.3, -10.3),
    "SM": ("San Marino", 43.9, 44.0, 12.4, 12.5),
    "SN": ("Senegal", 12.3, 16.7, -17.5, -11.3),
    "SO": ("Somalia", -1.7, 11.9, 41.0, 51.4),
    "SR": ("Suriname", 1.8, 6.0, -58.1, -54.0),
    "SS": ("South Sudan", 3.5, 12.2, 24.1, 36.0),
    "ST": ("Sao Tome and Principe", 0.0, 1.7, 6.4, 7.5),
    "SV": ("El Salvador", 13.1, 14.4, -90.1, -87.7),
    "SY": ("Syria", 32.3, 37.3, 35.7, 42.4),
    "SZ": ("Eswatini", -27.3, -25.7, 30.8, 32.1),
    "TD": ("Chad", 7.4, 23.5, 13.5, 24.0),
    "TG": ("Togo", 6.1, 11.1, -0.2, 1.8),
    "TH": ("Thailand", 5.6, 20.5, 97.3, 105.6),
    "TJ": ("Tajikistan", 36.7, 41.0, 67.3, 75.2),
    "TL": ("Timor-Leste", -9.5, -8.1, 124.0, 127.3),
    "TM": ("Turkmenistan", 35.1, 42.8, 52.5, 66.7),
    "TN": ("Tunisia", 30.2, 37.5, 7.5, 11.6),
    "TO": ("Tonga", -22.4, -15.6, -175.4, -173.9),
    "TR": ("Turkey", 35.8, 42.1, 26.0, 44.8),
    "TT": ("Trinidad and Tobago", 10.0, 11.3, -61.9, -60.5),
    "TV": ("Tuvalu", -8.6, -7.9, 176.0, 179.9),
    "TW": ("Taiwan", 21.9, 25.3, 120.0, 122.0),
    "TZ": ("Tanzania", -11.7, -1.0, 29.3, 40.4),
    "UA": ("Ukraine", 44.4, 52.4, 22.1, 40.2),
    "UG": ("Uganda", -1.5, 4.2, 29.6, 35.0),
    "US": ("United States", 18.9, 71.4, -179.2, 179.9),
    "UY": ("Uruguay", -35.0, -30.1, -58.4, -53.1),
    "UZ": ("Uzbekistan", 37.2, 45.6, 56.0, 73.1),
    "VC": ("Saint Vincent and the Grenadines", 12.8, 13.4, -61.5, -61.1),
    "VE": ("Venezuela", 0.6, 12.2, -73.4, -59.8),
    "VG": ("British Virgin Islands", 18.3, 18.8, -64.9, -64.3),
    "VI": ("US Virgin Islands", 17.7, 18.4, -65.1, -64.6),
    "VN": ("Vietnam", 8.6, 23.4, 102.1, 109.5),
    "VU": ("Vanuatu", -20.3, -13.0, 166.0, 170.2),
    "WS": ("Samoa", -14.1, -13.4, -172.8, -171.4),
    "XK": ("Kosovo", 41.8, 43.3, 20.0, 21.8),
    "YE": ("Yemen", 12.1, 19.0, 42.5, 54.5),
    "ZA": ("South Africa", -34.8, -22.1, 16.5, 32.9),
    "ZM": ("Zambia", -18.1, -8.2, 22.0, 33.7),
    "ZW": ("Zimbabwe", -22.4, -15.6, 25.2, 33.1),
}

# Fiji spans 177.2E .. 180 / -178.4 (antimeridian wrap).
_ANTIMERIDIAN: set[str] = {"FJ"}


def resolve_country(lat: float, lon: float) -> dict[str, Any]:
    """Return the best country match for a coordinate (bbox heuristic).

    Only returns ``ok=True`` for a definite in-bbox match; otherwise reports
    ``ok=False`` with the closest country for reference.
    """
    matches: list[tuple[float, str, str]] = []
    for code, (name, lat_min, lat_max, lon_min, lon_max) in _COUNTRIES.items():
        if not (lat_min <= lat <= lat_max):
            continue
        if code in _ANTIMERIDIAN:
            inside = lon >= lon_min or lon <= lon_max
        else:
            inside = lon_min <= lon <= lon_max
        if not inside:
            continue
        area = (lat_max - lat_min) * (lon_max - lon_min)
        matches.append((area, code, name))
    if not matches:
        return {"ok": False, "matched": False, "method": "bbox-heuristic", "countries": []}
    matches.sort(key=lambda item: item[0])
    best_area, best_code, best_name = matches[0]
    return {
        "ok": True,
        "matched": True,
        "method": "bbox-heuristic",
        "iso2": best_code,
        "name": best_name,
        "ambiguous": len(matches) > 1,
        "alternatives": [
            {"iso2": code, "name": name, "relative_area": round(area / best_area, 1)}
            for area, code, name in matches[1:4]
        ],
    }


def country_count() -> int:
    return len(_COUNTRIES)