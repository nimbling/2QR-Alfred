#!/usr/bin/env python3
import os, sys, subprocess, re, datetime, shlex
try:
    from qrcodegen import QrCode, QrSegment
except Exception:
    print("qrcodegen.py not found next to main.py", file=sys.stderr)
    sys.exit(2)
    
dbg = lambda m: None  # will be redefined later; placeholder so early calls are safe
print("2qr-main v3 loaded", file=sys.stderr)


def notify(title: str, text: str):
    try:
        subprocess.run(['/usr/bin/osascript','-e', f'display notification "{text}" with title "{title}"'], check=False)
    except Exception as e:
        print(f"notify failed: {e}", file=sys.stderr)


def reveal(path: str):
    subprocess.run(["/usr/bin/open", "-R", path])


def copy_svg_text_to_clipboard(svg_text: str):
    p = subprocess.Popen(["/usr/bin/pbcopy"], stdin=subprocess.PIPE)
    p.communicate(svg_text.encode("utf-8"))


def copy_png_to_clipboard(path: str):
    osa = f'set the clipboard to (read (POSIX file "{path}") as «class PNGf»)'  
    subprocess.run(["/usr/bin/osascript", "-e", osa], check=False)


HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def parse_int(name: str, val: str, lo: int, hi: int, default: int) -> int:
    try:
        n = int(val)
        if lo <= n <= hi:
            return n
    except Exception:
        pass
    return default


def ensure_hex(val: str, default: str) -> str:
    return val.upper() if HEX_RE.match(val or "") else default


def make_svg(qr: 'QrCode', border: int, light_hex: str, dark_hex: str) -> str:
    if border < 0:
        raise ValueError("Border must be non-negative")
    size = qr.get_size()
    dim = size + border * 2
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {dim} {dim}" shape-rendering="crispEdges">',
             f'<rect width="100%" height="100%" fill="{light_hex}"/>']
    for y in range(size):
        for x in range(size):
            if qr.get_module(x, y):
                parts.append(f'<rect x="{x+border}" y="{y+border}" width="1" height="1" fill="{dark_hex}"/>')
    parts.append("</svg>")
    return "\n".join(parts)


def make_png(qr: 'QrCode', border: int, scale: int, light_hex: str = "#FFFFFF", dark_hex: str = "#000000") -> bytes:
    import struct, zlib
    if border < 0 or scale <= 0:
        raise ValueError("Border>=0, scale>0 required")
    size = qr.get_size()
    dim = (size + border * 2) * scale
    def rgb(h):
        return tuple(int(h[i:i+2], 16) for i in (1,3,5))
    light = rgb(light_hex); dark = rgb(dark_hex)
    rows = []
    for y in range(size + border*2):
        base = bytearray([0])
        for x in range(size + border*2):
            inside = (border <= x < border+size) and (border <= y < border+size)
            idx = 1 if (qr.get_module(x-border, y-border) if inside else False) else 0
            base.extend([idx]*scale)
        for _ in range(scale):
            rows.append(bytes(base))
    raw = zlib.compress(b"".join(rows), 9)
    def chunk(tag, data):
        return struct.pack('>I', len(data)) + tag + data + struct.pack('>I', zlib.crc32(tag+data) & 0xffffffff)
    png = [b"\x89PNG\r\n\x1a\n"]
    ihdr = __import__('struct').pack('>IIBBBBB', dim, dim, 8, 3, 0, 0, 0)
    png.append(chunk(b'IHDR', ihdr))
    png.append(chunk(b'PLTE', bytes(light + dark)))
    png.append(chunk(b'tRNS', b'\xff\xff'))
    png.append(chunk(b'IDAT', raw))
    png.append(chunk(b'IEND', b''))
    return b"".join(png)


def _parse_inline_options(argv_list):
    """Parse minimal inline options from a single {query} string.
    Supported keys: fmt (svg|png), border (int), scale (int), light (#RRGGBB), dark (#RRGGBB), ecl (l|m|q|h|names)
    Everything that is not key:value or key=value is considered data.
    """
    joined = " ".join(a for a in argv_list if isinstance(a, str))
    tokens = shlex.split(joined)
    allowed = {"fmt","border","scale","light","dark","ecl"}
    data_tokens, opts = [], {}
    for tok in tokens:
        if (":" in tok or "=" in tok):
            sep = ":" if ":" in tok else "="
            k, v = tok.split(sep, 1)
            k = k.strip().lower()
            if k in allowed:
                opts[k] = v.strip()
                continue
        data_tokens.append(tok)
    data = " ".join(t for t in data_tokens if t.strip())
    return data.strip(), opts


def _dbg_path():
    return "/tmp/2qr.log"


def dbg(msg: str):
    try:
        from datetime import datetime as _dt
        ts = _dt.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(_dbg_path(), "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {msg}\n")
    except Exception:
        pass

dbg("version: v3")


def main():
    dbg(f"argv={sys.argv!r}")
    data, opts = _parse_inline_options(sys.argv[1:])
    dbg(f"data='{data}', opts={opts}")
    if not data:
        print("Usage: 2qr <text-or-url> [fmt:svg|png border:4 scale:10 light:#FFFFFF dark:#000000 ecl:high]", file=sys.stderr)
        dbg("No data parsed")
        sys.exit(1)

    # Defaults
    err_choice = opts.get("ecl", "high").lower()
    out_choice = opts.get("fmt", "svg").lower()
    border = parse_int("Border", opts.get("border", "4"), 0, 100, 4)
    scale = parse_int("Scale", opts.get("scale", "10"), 1, 200, 10)

    light = ensure_hex(opts.get("light", "#FFFFFF"), "#FFFFFF")
    dark  = ensure_hex(opts.get("dark",  "#000000"), "#000000")

    dbg(f"resolved: ecl={err_choice}, fmt={out_choice}, border={border}, light={light}, dark={dark}, scale={scale}")

    # Map ECC
    ecl_map = {
        "l": "low", "low": "low",
        "m": "medium", "med": "medium", "medium": "medium",
        "q": "quartile", "quartile": "quartile",
        "h": "high", "hi": "high", "high": "high",
    }
    err_choice = ecl_map.get(err_choice, "high")
    ecc = {"low": QrCode.Ecc.LOW, "medium": QrCode.Ecc.MEDIUM, "quartile": QrCode.Ecc.QUARTILE, "high": QrCode.Ecc.HIGH}[err_choice]

    # Build QR (Nayuki simple API)
    try:
        qr = QrCode.encode_text(data, ecc)
        dbg(f"QR built. size={qr.get_size()}")
    except Exception:
        import traceback
        tb = traceback.format_exc()
        dbg("QR encode failed:\n" + tb)
        print(tb, file=sys.stderr)
        sys.exit(2)

    # Output
    # Derive a safe filename from input text
    safe_base = re.sub(r"[^A-Za-z0-9._-]+", "_", data.strip())[:80] or "QR"
    desktop = os.path.expanduser("~/Desktop")
    if not os.path.isdir(desktop):
        dbg(f"Desktop missing or not a dir: {desktop}. Falling back to /tmp")
        desktop = "/tmp"

    if out_choice in ("svg",):
        svg = make_svg(qr, border=border, light_hex=light, dark_hex=dark)
        outpath = os.path.join(desktop, f"{safe_base}.svg")
        try:
            with open(outpath, "w", encoding="utf-8") as f:
                f.write(svg)
            dbg(f"wrote SVG: {outpath}")
            copy_svg_text_to_clipboard(svg)
            notify("2qr", "SVG saved and copied to clipboard")
            print(f"2qr: wrote {outpath}")
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            dbg("SVG write failed:\n" + tb)
            print(tb, file=sys.stderr)
            notify("2qr", "Failed to write SVG")
            sys.exit(3)
    else:
        png = make_png(qr, border=border, scale=scale, light_hex="#FFFFFF", dark_hex="#000000")
        outpath = os.path.join(desktop, f"{safe_base}.png")
        try:
            with open(outpath, "wb") as f:
                f.write(png)
            dbg(f"wrote PNG: {outpath}")
            copy_png_to_clipboard(outpath)
            notify("2qr", "PNG saved and copied to clipboard")
            print(f"2qr: wrote {outpath}")
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            dbg("PNG write failed:\n" + tb)
            print(tb, file=sys.stderr)
            notify("2qr", "Failed to write PNG")
            sys.exit(3)

    dbg(f"reveal: {outpath}")
    reveal(outpath)

if __name__ == "__main__":
    main()
