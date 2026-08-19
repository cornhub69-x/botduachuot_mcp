"""Tests for the investigation probes (app/tools/probes.py) using generated
artifacts: EXIF-GPS JPEG, a handcrafted PCAP, and minimal Windows containers.

External-tool tests skip when the tool is missing on the host so the suite
stays green on CI runners without the forensics toolchain.
"""

from __future__ import annotations

import shutil
import struct
import subprocess
from pathlib import Path

import pytest

from app.security import format_error_response
from app.tools.probes import (
    duachuot_disk_probe,
    duachuot_mem_probe,
    duachuot_media_probe,
    duachuot_ocr_probe,
    duachuot_pcap_probe,
    duachuot_stego_probe,
    duachuot_win_probe,
)

requires = pytest.mark.skipif


def _has(*tools: str) -> bool:
    return all(shutil.which(tool) for tool in tools)


# ---------------------------------------------------------------- artifacts


def _make_jpeg_with_gps(path: Path) -> None:
    subprocess.run(  # noqa: S603
        ["convert", "-size", "64x64", "xc:red", str(path)],
        check=True,
        capture_output=True,
        timeout=30,
    )
    subprocess.run(  # noqa: S603
        [
            "exiftool", "-overwrite_original",
            "-GPSLatitude=21.02906", "-GPSLatitudeRef=N",
            "-GPSLongitude=105.85367", "-GPSLongitudeRef=E",
            "-GPSAltitude=5", "-GPSDOP=1.5",
            str(path),
        ],
        check=True,
        capture_output=True,
        timeout=30,
    )


def _frame(payload: bytes, sport: int = 5353, dport: int = 53) -> bytes:
    eth = b"\x00\x11\x22\x33\x44\x55\x66\x77\x88\x99\xaa\xbb\x08\x00"
    udp = struct.pack(">HHHH", sport, dport, 8 + len(payload), 0) + payload
    ip = struct.pack(
        ">BBHHHBBH4s4s",
        0x45, 0, 20 + len(udp), 1, 0, 64, 17, 0,
        bytes([10, 0, 0, 2]),
        bytes([8, 8, 8, 8]),
    )
    return eth + ip + udp


def _dns_query(name: str) -> bytes:
    header = struct.pack(">HHHHHH", 0x1234, 0x0100, 1, 0, 0, 0)
    question = b"".join(
        bytes([len(label)]) + label.encode() for label in name.split(".")
    ) + b"\x00"
    return header + question + struct.pack(">HH", 1, 1)


def _make_pcap(path: Path) -> None:
    frames = [
        _frame(_dns_query("example.com")),
        _frame(b"$GPRMC,225446,A,4916.45,N,12311.12,W,000.5,054.7,191194,020.3,E*68", sport=4567, dport=4567),
    ]
    with open(path, "wb") as handle:
        handle.write(struct.pack("<IHHiIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 1))
        for ts, frame in enumerate(frames):
            handle.write(struct.pack("<IIII", ts, 0, len(frame), len(frame)))
            handle.write(frame)


def _make_lnk(path: Path) -> None:
    raw = bytearray(b"\x4c\x00\x00\x00" + b"\x00" * 76)
    raw[76:78] = struct.pack("<H", 4)
    raw += struct.pack("<I", 0x0000000C)
    for text in ("C:\\Windows\\notepad.exe", "flag_hint.txt"):
        encoded = text.encode("utf-16-le")
        raw += struct.pack("<H", len(encoded)) + encoded
    path.write_bytes(bytes(raw))


def _make_hive(path: Path) -> None:
    path.write_bytes(b"regf" + b"\x00" * 16 + b"SOFTWARE" + b"\x00" * 32)


def _make_prefetch(path: Path) -> None:
    path.write_bytes(b"MAM\x04" + b"\x00" * 32 + b"NOTEPAD.EXE" + b"\x00" * 32)


# ---------------------------------------------------------------- media + geo


@requires(not _has("convert", "exiftool"), reason="ImageMagick/exiftool missing")
def test_media_probe_extracts_exif_gps(tmp_path: Path) -> None:
    image = tmp_path / "gps.jpg"
    _make_jpeg_with_gps(image)
    result = duachuot_media_probe(str(image))
    assert result["ok"] is True
    assert result["exiftool"]["exit_code"] == 0
    assert "GPSLatitude" in result["metadata"]
    assert float(result["metadata"]["GPSLatitude"]) == pytest.approx(21.02906, abs=1e-4)


@requires(not _has("convert", "exiftool"), reason="ImageMagick/exiftool missing")
def test_geo_extract_roundtrip_from_generated_jpeg(tmp_path: Path) -> None:
    from app.tools.geo_tools import duachuot_geo_extract

    image = tmp_path / "gps.jpg"
    _make_jpeg_with_gps(image)
    result = duachuot_geo_extract(str(image), cross_check=True)
    assert result["ok"] is True
    gps = result["gps"]
    assert gps["lat"] == pytest.approx(21.02906, abs=1e-4)
    assert gps["lon"] == pytest.approx(105.85367, abs=1e-4)
    assert "accuracy" in result and "timezone" in result and "landmarks" in result


def test_media_probe_missing_tool_is_blocker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda name: None)
    result = duachuot_media_probe(str(tmp_path / "nope.jpg"))
    assert result["ok"] is False
    assert "not available" in str(result["error"])


# ---------------------------------------------------------------- pcap


@requires(not _has("tshark"), reason="tshark missing")
def test_pcap_probe_parses_crafted_capture(tmp_path: Path) -> None:
    capture = tmp_path / "capture.pcap"
    _make_pcap(capture)
    result = duachuot_pcap_probe(str(capture))
    assert result["ok"] is True
    assert result["file"]["exit_code"] == 0
    assert result["conversations"]["exit_code"] == 0
    assert "example.com" in result["dns_queries"]["stdout"]
    assert "GPRMC" in result["geo_hints"]["hits"]


# ---------------------------------------------------------------- disk + memory


@requires(not _has("fls", "fsstat"), reason="sleuthkit missing")
def test_disk_probe_structure(tmp_path: Path) -> None:
    bogus = tmp_path / "not-a-disk.img"
    bogus.write_bytes(b"\x00" * 4096)
    result = duachuot_disk_probe(str(bogus))
    assert result["ok"] is True
    assert {"file", "fsstat", "fls"} <= set(result)
    assert result["fls"]["exit_code"] != 0  # not a real image, but probe must not crash


def test_mem_probe_missing_vol_is_blocker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    real_which = shutil.which
    monkeypatch.setattr(shutil, "which", lambda name: None if name == "vol" else real_which(name))
    result = duachuot_mem_probe(str(tmp_path / "mem.raw"))
    assert result["ok"] is False
    assert result["error"]["code"] == "FILE_NOT_FOUND"
    assert "vol" in result["error"]["message"]


# ---------------------------------------------------------------- stego + ocr


@requires(not _has("binwalk"), reason="binwalk missing")
def test_stego_probe_structure(tmp_path: Path) -> None:
    carrier = tmp_path / "carrier.jpg"
    subprocess.run(  # noqa: S603
        ["convert", "-size", "64x64", "xc:blue", str(carrier)],
        check=True,
        capture_output=True,
        timeout=30,
    )
    result = duachuot_stego_probe(str(carrier))
    assert result["ok"] is True
    assert {"binwalk", "steghide_info"} <= set(result)


@requires(not _has("convert", "tesseract"), reason="ImageMagick/tesseract missing")
def _tesseract_has_eng() -> bool:
    if shutil.which("tesseract") is None:
        return False
    out = subprocess.run(  # noqa: S603
        ["tesseract", "--list-langs"], capture_output=True, text=True
    ).stdout.split()
    return "eng" in out


@pytest.mark.skipif(
    not _tesseract_has_eng(),
    reason="tesseract eng traineddata missing",
)
def test_ocr_probe_reads_rendered_text(tmp_path: Path) -> None:
    image = tmp_path / "text.png"
    subprocess.run(  # noqa: S603
        [
            "convert", "-size", "300x80", "xc:white",
            "-pointsize", "28", "-fill", "black",
            "-draw", "text 20,50 'HELLO CTF'",
            str(image),
        ],
        check=True,
        capture_output=True,
        timeout=30,
    )
    result = duachuot_ocr_probe(str(image))
    assert result["ok"] is True
    assert result["tesseract"]["exit_code"] == 0
    assert "HELLO" in result["tesseract"]["stdout"].upper()


# ---------------------------------------------------------------- windows


def test_win_probe_parses_lnk(tmp_path: Path) -> None:
    lnk = tmp_path / "shortcut.lnk"
    _make_lnk(lnk)
    result = duachuot_win_probe(str(lnk), kind="lnk")
    assert result["ok"] is True
    assert any("notepad" in s.lower() for s in result["lnk"]["link_strings"])


def test_win_probe_parses_hive(tmp_path: Path) -> None:
    hive = tmp_path / "SAM"
    _make_hive(hive)
    result = duachuot_win_probe(str(hive), kind="hive")
    assert result["ok"] is True
    assert result["hive"]["signature"] == "regf"
    assert "SOFTWARE" in result["hive"]["strings_hint"]


def test_win_probe_parses_prefetch(tmp_path: Path) -> None:
    prefetch = tmp_path / "NOTEPAD.EXE-1.pf"
    _make_prefetch(prefetch)
    result = duachuot_win_probe(str(prefetch), kind="prefetch")
    assert result["ok"] is True
    assert result["prefetch"]["signature"] == "MAM\\x04"
    assert isinstance(result["prefetch"]["strings_hint"], list)


def test_win_probe_unknown_container_notes_signature(tmp_path: Path) -> None:
    unknown = tmp_path / "random.bin"
    unknown.write_bytes(b"\xde\xad\xbe\xef" + b"\x00" * 16)
    result = duachuot_win_probe(str(unknown), kind="auto")
    assert result["ok"] is True
    assert "unknown container" in result["note"]


def test_format_error_response_contract() -> None:
    response = format_error_response(FileNotFoundError("missing tool 'vol'"))
    assert response["ok"] is False
    assert "vol" in str(response["error"])