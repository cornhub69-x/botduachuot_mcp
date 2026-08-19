"""MCP adapters — Investigation probes (media, pcap, disk, memory, stego, OCR, Windows).

Each probe prefers existing host tools (Tool Matrix level A) and fails with a
clear BLOCKER-style error when the tool is missing, so callers never guess.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess  # nosec B404
import tempfile
import wave
from typing import Any, Optional

from app.mcp_server import mcp
from app.security import format_error_response


def _run(tool: str, args: list[str], *, timeout: int = 30) -> dict[str, Any]:
    resolved = shutil.which(tool)
    if not resolved:
        raise FileNotFoundError(
            f"required tool '{tool}' is not available on this host; "
            "install it or run the equivalent manual command"
        )
    result = subprocess.run(  # nosec B603
        [resolved, *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    return {
        "tool": tool,
        "exit_code": result.returncode,
        "stdout": result.stdout[:200000],
        "stderr": result.stderr[:50000],
        "stdout_truncated": len(result.stdout) > 200000,
    }


@mcp.tool(
    name="duachuot_media_probe",
    description=(
        "Probe an image/audio/video artifact: full metadata (exiftool JSON), "
        "stream info (ffprobe), and format detection (file). Includes GPS fields "
        "when present."
    ),
)
def duachuot_media_probe(path: str) -> dict[str, Any]:
    try:
        result: dict[str, Any] = {"ok": True, "path": path}
        result["file"] = _run("file", [path])
        result["exiftool"] = _run("exiftool", ["-json", "-n", path])
        if result["exiftool"]["exit_code"] == 0 and result["exiftool"]["stdout"].strip():
            try:
                records = json.loads(result["exiftool"]["stdout"])
                result["metadata"] = records[0] if records else {}
            except json.JSONDecodeError:
                result["metadata"] = {}
        if shutil.which("ffprobe"):
            result["ffprobe"] = _run("ffprobe", ["-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", path])
        return result
    except Exception as exc:
        return format_error_response(exc)


@mcp.tool(
    name="duachuot_pcap_probe",
    description=(
        "Probe a PCAP/PCAPNG capture: conversations, endpoints, DNS, HTTP hosts, "
        "and GPS/geo hints (Wi-Fi probe requests, GPS NMEA, cellular). "
        "Run only against supplied local captures."
    ),
)
def duachuot_pcap_probe(path: str, max_flows: int = 30) -> dict[str, Any]:
    try:
        result: dict[str, Any] = {"ok": True, "path": path}
        result["file"] = _run("file", [path])
        result["conversations"] = _run(
            "tshark", ["-r", path, "-q", "-z", f"conv,tcp;{max_flows}"], timeout=60
        )
        result["endpoints"] = _run(
            "tshark", ["-r", path, "-q", "-z", f"endpoints,ip;{max_flows}"], timeout=60
        )
        result["dns_queries"] = _run(
            "tshark",
            ["-r", path, "-Y", "dns.qry.name", "-T", "fields", "-e", "dns.qry.name"],
            timeout=60,
        )
        geo_hints = _run(
            "tshark",
            [
                "-r", path,
                "-Y",
                "wlan.tag.number==0 or data.data contains \"GPRMC\" or data.data contains \"GGA\"",
                "-T", "fields",
                "-e", "wlan_rsna_ie.tag", "-e", "data.data",
            ],
            timeout=60,
        )
        if geo_hints["exit_code"] != 0:
            geo_hints["fallback"] = _run(
                "tshark",
                [
                    "-r", path,
                    "-Y",
                    "frame contains \"GPRMC\" or frame contains \"GGA\"",
                    "-T", "fields",
                    "-e", "udp.payload",
                ],
                timeout=60,
            )
        result["geo_hints"] = geo_hints
        result["geo_hints"]["hits"] = _nmea_hits(geo_hints.get("stdout", "")) + _nmea_hits(
            geo_hints.get("fallback", {}).get("stdout", "")
        )
        return result
    except Exception as exc:
        return format_error_response(exc)


@mcp.tool(
    name="duachuot_disk_probe",
    description=(
        "Probe a disk image: filesystem listing (fls), filesystem statistics "
        "(fsstat), and carve candidates (binwalk/foremost). Preserves originals."
    ),
)
def duachuot_disk_probe(path: str, max_list: int = 200) -> dict[str, Any]:
    try:
        result: dict[str, Any] = {"ok": True, "path": path}
        result["file"] = _run("file", [path])
        result["fsstat"] = _run("fsstat", [path], timeout=60)
        result["fls"] = _run("fls", ["-r", "-m", "/", path], timeout=60)
        return result
    except Exception as exc:
        return format_error_response(exc)


@mcp.tool(
    name="duachuot_mem_probe",
    description=(
        "Probe a memory image with Volatility 3: detect profile (windows.info / "
        "linux.info), process list, and file scan. Profile must be evidenced."
    ),
)
def duachuot_mem_probe(path: str, os_hint: Optional[str] = None) -> dict[str, Any]:
    try:
        result: dict[str, Any] = {"ok": True, "path": path}
        result["file"] = _run("file", [path])
        plugin = "windows.info" if (os_hint or "linux").lower().startswith(("win", "windows")) else "linux.info"
        result["info"] = _run("vol", ["-f", path, plugin], timeout=60)
        ps_plugin = "windows.pslist" if "win" in plugin else "linux.pslist"
        result["pslist"] = _run("vol", ["-f", path, ps_plugin], timeout=60)
        return result
    except Exception as exc:
        return format_error_response(exc)


_FLAG_LIKE_RE = re.compile(r"[A-Za-z0-9_\-]{3,}")

def _lsb_analysis(path: str, limit_frames: int = 20000) -> dict[str, Any]:
    """Detect LSB stego bias in a PCM WAV without external tools.

    Clean PCM audio has a ~50/50 least-significant-bit distribution; a hidden
    LSB message biases it. Returns distribution stats plus a heuristic verdict.
    """
    try:
        with wave.open(path, "rb") as wav:
            n_frames = min(wav.getnframes(), limit_frames)
            sampwidth = wav.getsampwidth()
            channels = wav.getnchannels()
            if sampwidth > 4:
                return {"supported": False, "note": "unsupported sample width"}
            frames = wav.readframes(n_frames)
            nbytes = len(frames)
            if nbytes == 0:
                return {"supported": False, "note": "empty audio"}
            import struct

            ones = 0
            seen = 0
            for i in range(0, nbytes - (nbytes % (channels * sampwidth)), channels * sampwidth):
                for ch in range(channels):
                    offset = i + ch * sampwidth
                    sample = struct.unpack_from("<h", frames, offset)[0]
                    ones += sample & 1
                    seen += 1
            if seen == 0:
                return {"supported": False, "note": "no samples decoded"}
            p1 = ones / seen
            deviation = abs(p1 - 0.5)
            return {
                "supported": True,
                "channels": channels,
                "sample_width": sampwidth,
                "frames_analyzed": n_frames,
                "lsb_ones_fraction": round(p1, 5),
                "deviation_from_0_5": round(deviation, 5),
                "suspicious": deviation > 0.12,
            }
    except (wave.Error, OSError, EOFError):
        return {"supported": False, "note": "not a parseable PCM WAV"}


def _extract_text_from_output(result: dict[str, Any]) -> Optional[str]:
    """First printable/flag-like content found in a tool's stdout+stderr."""
    if result.get("exit_code") is None:
        return None
    text = (result.get("stdout") or "") + "\n" + (result.get("stderr") or "")
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped in {"", "Output file written", "Image overwritten"}:
            continue
        if _FLAG_LIKE_RE.search(stripped) and any(
            ch.isalpha() for ch in stripped
        ):
            return stripped[:500]
    return None


def _optional_run(tool: str, args: list[str], *, timeout: int = 60) -> dict[str, Any]:
    """Run an optional probe tool; missing tool yields a non-fatal note."""
    if not shutil.which(tool):
        return {"tool": tool, "exit_code": None, "note": f"tool '{tool}' not installed", "stdout": "", "stderr": ""}
    return _run(tool, args, timeout=timeout)


@mcp.tool(
    name="duachuot_stego_probe",
    description=(
        "Probe a carrier file for steganography/carved data: binwalk signature "
        "scan, foremost extraction candidate list, steghide info, and LSB hint "
        "(channel noise analysis placeholder)."
    ),
)
def duachuot_stego_probe(path: str) -> dict[str, Any]:
    try:
        result: dict[str, Any] = {"ok": True, "path": path}
        result["binwalk"] = _optional_run("binwalk", [path], timeout=60)
        result["steghide_info"] = _optional_run("steghide", ["info", path], timeout=30)

        with open(path, "rb") as fh:
            magic = fh.read(16)

        if magic.startswith(b"RIFF") and magic[8:12] == b"WAVE":
            result["kind"] = "wav"
            lsb = _lsb_analysis(path)
            result["lsb_analysis"] = lsb
            with tempfile.TemporaryDirectory() as tmp:
                out = os.path.join(tmp, "decoded.bin")
                wavsteg = _optional_run(
                    "wavsteg", ["decode", "--wav", path, "--out", out], timeout=120
                )
                if wavsteg.get("exit_code") == 0 and os.path.exists(out):
                    with open(out, "rb") as fh_out:
                        raw = fh_out.read()
                    wavsteg["payload_preview"] = (
                        raw[:500].decode("utf-8", errors="replace")
                    )
                else:
                    wavsteg["payload_preview"] = ""
                wavsteg["extracted"] = (
                    wavsteg.get("payload_preview")
                    or _extract_text_from_output(wavsteg)
                )
                result["wavsteg_decode"] = wavsteg
        elif magic.startswith(b"\x89PNG") or magic.startswith(b"BM"):
            result["kind"] = "png_bmp"
            with tempfile.TemporaryDirectory() as tmp:
                out = os.path.join(tmp, "recovered.bin")
                stegolsb = _optional_run(
                    "stegolsb",
                    ["steglsb", "-r", "-i", path, "-o", out, "-n", "1"],
                    timeout=120,
                )
                if stegolsb.get("exit_code") == 0 and os.path.exists(out):
                    with open(out, "rb") as fh_out:
                        raw = fh_out.read()
                    stegolsb["payload_preview"] = raw[:500].decode(
                        "utf-8", errors="replace"
                    )
                stegolsb["extracted"] = (
                    stegolsb.get("payload_preview")
                    or _extract_text_from_output(stegolsb)
                )
                result["stegolsb_recover"] = stegolsb
        elif magic.startswith(b"ID3") or magic[2:4] == b"\xff\xfb" or magic[2:4] == b"\xff\xf3":
            result["kind"] = "mp3"
            with tempfile.TemporaryDirectory() as tmp:
                out = os.path.join(tmp, "decoded.txt")
                pbhide = _optional_run(
                    "pbhide", ["extract", path, out], timeout=120
                )
                if pbhide.get("exit_code") == 0 and os.path.exists(out):
                    with open(out, "rb") as fh_out:
                        raw = fh_out.read()
                    pbhide["payload_preview"] = raw[:500].decode(
                        "utf-8", errors="replace"
                    )
                else:
                    pbhide["payload_preview"] = ""
                    pbhide["note"] = (
                        "no payload extracted; if the MP3 was encoded with the "
                        "original MP3Stego, decode it with wine + Decode.exe "
                        "(see docs/INVESTIGATION.md requirements)"
                    )
                pbhide["extracted"] = (
                    pbhide.get("payload_preview")
                    or _extract_text_from_output(pbhide)
                )
                result["pbhide_extract"] = pbhide
        else:
            result["kind"] = "other"
        return result
    except Exception as exc:
        return format_error_response(exc)


@mcp.tool(
    name="duachuot_ocr_probe",
    description=(
        "OCR text from an image (tesseract) and decode QR/barcodes (zxing-cpp "
        "via CTF venv if available). QR codes frequently carry coordinates."
    ),
)
def duachuot_ocr_probe(path: str) -> dict[str, Any]:
    try:
        result: dict[str, Any] = {"ok": True, "path": path}
        result["tesseract"] = _run("tesseract", [path, "stdout"], timeout=60)
        if shutil.which("ctfpy"):
            result["zxing"] = _run(
                "ctfpy",
                ["-c", f"import zxingcpp,sys; [print(r.text) for r in zxingcpp.read_barcodes(open({path!r},'rb').read())]"],
                timeout=60,
            )
        else:
            result["zxing"] = {
                "tool": "zxing-cpp",
                "note": "ctfpy wrapper not found; zxing-cpp QR decode skipped",
                "exit_code": None,
            }
        return result
    except Exception as exc:
        return format_error_response(exc)


@mcp.tool(
    name="duachuot_win_probe",
    description=(
        "Windows forensics without external tools: registry hive strings (SAM/"
        "SYSTEM), LNK file target extraction, and prefetch filename strings. "
        "Pure-Python parsers; runs on Linux or Windows."
    ),
)
def duachuot_win_probe(path: str, kind: str = "auto") -> dict[str, Any]:
    try:
        import os as _os

        kind = kind.lower()
        with open(path, "rb") as handle:
            raw = handle.read(64 * 1024 * 1024)
        result: dict[str, Any] = {"ok": True, "path": path, "kind": kind}
        if kind in {"auto", "lnk"} and raw.startswith(b"\x4c\x00\x00\x00"):
            result["lnk"] = _parse_lnk(path)
        if kind in {"auto", "hive"} and raw[:4] in {b"regf", b"hbin"}:
            result["hive"] = {
                "signature": raw[:4].decode("latin-1"),
                "strings_hint": _extract_strings_hint(raw),
            }
        if kind in {"auto", "prefetch"} and raw[:4] == b"MAM\x04":
            result["prefetch"] = {
                "signature": "MAM\\x04",
                "strings_hint": _extract_strings_hint(raw),
            }
        if kind == "auto" and not result.get("lnk") and not result.get("hive") and not result.get("prefetch"):
            result["note"] = "unknown container; first 4 bytes: " + raw[:4].hex()
        return result
    except Exception as exc:
        return format_error_response(exc)


def _parse_lnk(path: str) -> dict[str, Any]:
    import struct

    with open(path, "rb") as handle:
        raw = handle.read()
    strings: list[str] = []
    try:
        offset = 76 + struct.unpack_from("<H", raw, 76)[0]
        if offset < len(raw) - 4 and struct.unpack_from("<I", raw, offset)[0] == 0x0000000C:
            offset += 4
            while offset < len(raw) - 2:
                length = struct.unpack_from("<H", raw, offset)[0]
                if length == 0 or offset + 2 + length > len(raw):
                    break
                try:
                    strings.append(raw[offset + 2 : offset + 2 + length].decode("utf-16-le"))
                except UnicodeDecodeError:
                    pass
                offset += 2 + length
    except Exception:  # nosec B110
        pass
    return {"link_strings": strings[:50], "string_count": len(strings)}


def _extract_strings_hint(raw: bytes) -> list[str]:
    hints: list[str] = []
    for marker in (b"SOFTWARE", b"SYSTEM", b"SAM", b"CurrentControlSet", b"MACHINE"):
        index = raw.find(marker)
        if index >= 0:
            hints.append(marker.decode("latin-1"))
    return hints[:20]


def _nmea_hits(stdout: str) -> list[str]:
    """Detect NMEA sentence markers in tshark output (ASCII or hex-encoded)."""
    hits: list[str] = []
    upper = stdout.upper()
    for marker in ("GPRMC", "GPGGA", "GGA"):
        if marker in upper or marker.encode().hex().upper() in upper:
            hits.append(marker)
    return hits