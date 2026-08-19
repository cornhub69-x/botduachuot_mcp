"""Tests for the stego probe: LSB bias detection (pure Python) and optional
tool-based extraction (wavsteg / stegolsb / pbhide), skipped when the tools
are not installed (e.g. CI)."""

from __future__ import annotations

import random
import shutil
import struct
import subprocess  # nosec B404
import tempfile
import wave
import zlib
from pathlib import Path

import pytest

from app.tools.probes import _lsb_analysis, _optional_run, duachuot_stego_probe


def _write_noise_wav(path: Path, frames: int = 8000, seed: int = 7) -> Path:
    rng = random.Random(seed)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(8000)
        wav.writeframes(b"".join(struct.pack("<h", rng.randrange(-20000, 20000)) for _ in range(frames)))
    return path


def _write_lsb_forced_wav(path: Path, lsb: int, frames: int = 8000) -> Path:
    rng = random.Random(3)
    samples = []
    for _ in range(frames):
        value = rng.randrange(-20000, 20000)
        samples.append(struct.pack("<h", (value & ~1) | lsb))
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(8000)
        wav.writeframes(b"".join(samples))
    return path


def _minimal_png(path: Path, size: int = 64) -> Path:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    row = b"\x00" + b"\x00\x00\x00" * size
    raw = zlib.compress(row * size)
    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", raw)
        + chunk(b"IEND", b"")
    )
    path.write_bytes(png)
    return path


def test_lsb_analysis_clean_wav_not_suspicious() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        wav = _write_noise_wav(Path(tmp) / "clean.wav")
        result = _lsb_analysis(str(wav))
    assert result["supported"] is True
    assert result["suspicious"] is False
    assert result["lsb_ones_fraction"] == pytest.approx(0.5, abs=0.05)


def test_lsb_analysis_forced_bias_suspicious() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        wav = _write_lsb_forced_wav(Path(tmp) / "biased.wav", lsb=1)
        result = _lsb_analysis(str(wav))
    assert result["supported"] is True
    assert result["suspicious"] is True
    assert result["lsb_ones_fraction"] == pytest.approx(1.0)


def test_lsb_analysis_non_wav_unsupported() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "notaudio.bin"
        path.write_bytes(b"RIFF\x00\x00\x00\x00XXXX")
        result = _lsb_analysis(str(path))
    assert result["supported"] is False


def test_optional_run_missing_tool_graceful() -> None:
    result = _optional_run("definitely-not-a-real-tool-xyz", ["x"])
    assert result["exit_code"] is None
    assert "not installed" in result["note"]


@pytest.mark.skipif(
    not shutil.which("wavsteg"), reason="wavsteg not installed on this host"
)
def test_probe_extracts_wav_lsb_payload() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        clean = _write_noise_wav(tmp / "carrier.wav")
        payload = tmp / "payload.txt"
        payload.write_text("CTF{wav_lsb_probe_check}", encoding="utf-8")
        stego = tmp / "stego.wav"
        subprocess.run(  # nosec B603
            ["wavsteg", "encode", "--wav", str(clean), "--data", str(payload), "--out", str(stego)],
            check=True,
            capture_output=True,
            timeout=120,
        )
        result = duachuot_stego_probe(str(stego))
    assert result["ok"] is True
    assert result["kind"] == "wav"
    assert "CTF{wav_lsb_probe_check}" in result["wavsteg_decode"]["extracted"]


@pytest.mark.skipif(
    not shutil.which("stegolsb"), reason="stegolsb not installed on this host"
)
def test_probe_extracts_png_lsb_payload() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        png = _minimal_png(tmp / "img.png")
        payload = tmp / "payload.txt"
        payload.write_text("CTF{png_lsb_probe_check}", encoding="utf-8")
        stego = tmp / "stego.png"
        subprocess.run(  # nosec B603
            ["stegolsb", "steglsb", "-h", "-i", str(png), "-s", str(payload), "-o", str(stego), "-n", "1"],
            check=True,
            capture_output=True,
            timeout=120,
        )
        result = duachuot_stego_probe(str(stego))
    assert result["ok"] is True
    assert result["kind"] == "png_bmp"
    assert "CTF{png_lsb_probe_check}" in result["stegolsb_recover"]["extracted"]


def test_probe_mp3_no_crash_and_note() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "audio.mp3"
        path.write_bytes(b"ID3\x03\x00\x00\x00\x00\x00\x00" + b"\x00" * 64)
        result = duachuot_stego_probe(str(path))
    assert result["ok"] is True
    assert result["kind"] == "mp3"
    assert "pbhide_extract" in result
    pbhide = result["pbhide_extract"]
    if pbhide["exit_code"] is None:
        assert "not installed" in pbhide["note"] or "no payload extracted" in pbhide["note"]


def test_probe_missing_file_error() -> None:
    result = duachuot_stego_probe("/nonexistent/nope.wav")
    assert result["ok"] is False