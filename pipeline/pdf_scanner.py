"""Real post-render PDF content extractor + leak scanner.

Defeats FlateDecode compression that defeats raw-byte scans: decompresses every
stream, pulls visible text operators (Tj/TJ), metadata (/Info), and hyperlink
annotations (/URI). This is the authoritative scanner used to enforce
HARD_FAIL = INTERNAL_PATH_LEAK -> DELIVERY_BLOCKED on rendered PDF bytes.
"""
import re
import zlib


def extract_pdf_content(pdf: bytes) -> dict:
    """Return {text, uris, metadata, stream_hits} decompressed from a PDF."""
    text_parts = []
    uris = []

    # 1) every stream object (FlateDecode compressed) -> decompress
    raw_text = b""
    streams = re.findall(rb"stream\r?\n(.*?)\r?\nendstream", pdf, re.S)
    for s in streams:
        try:
            d = zlib.decompress(s)
        except Exception:
            try:
                import base64 as _b
                d = _b.b64decode(s)  # ASCII85/LZW unlikely, but try base64 as last resort
            except Exception:
                d = b""
        if d:
            raw_text += d + b"\n"
            # hyperlink URIs can live inside content streams too
            uris += re.findall(rb"/URI\s*\((.*?)\)", d)

    # 2) visible text operators Tj/TJ appear in decompressed streams
    #    example: (visible string) Tj  or  [( a) 12 (b)] TJ
    #    PDF strings can be ( ) parenthesised, hex <...>, with escapes.
    #    We decode parenthesised strings and strip control/escape noise.
    def _decode_pdf_string(s: bytes):
        if s.startswith(b"(") and s.endswith(b")"):
            inner = s[1:-1]
            inner = inner.replace(rb"\(", b"(").replace(rb"\)", b")").replace(rb"\\", b"\\")
            inner = inner.replace(rb"\n", b"\n").replace(rb"\r", b"\r").replace(rb"\t", b"\t")
            return inner
        return b""

    toks = re.findall(rb"(\((?:\\.|[^()\\])*\)|\[[^\]]*\])Tj|(\[(?:\\.|[^()\\\[\]])*\])TJ", raw_text)
    # simpler robust pass: find parenthesised tokens adjacent to Tj/TJ
    for m in re.finditer(rb"(\((?:\\.|[^()\\])*\))\s*Tj", raw_text):
        text_parts.append(_decode_pdf_string(m.group(1)))
    for m in re.finditer(rb"\[((?:\((?:\\.|[^()\\])*\)|\s|[0-9.+-]*)\s*)\]\s*TJ", raw_text):
        segs = re.findall(rb"\((?:\\.|[^()\\])*\)", m.group(1))
        text_parts.append(b"".join(_decode_pdf_string(x) for x in segs))

    # 3) annotations /URI that live in the object tree (outside streams)
    uris += re.findall(rb"/URI\s*\((.*?)\)", pdf)
    # 3b) any /Launch or /FileSpec (file-action hyperlinks) + their targets, even uncompressed
    uris += re.findall(rb"/Launch\s*[^>]{0,90}", pdf)[:20]
    uris += re.findall(rb"/F\s*\(([^)]*)\)", pdf)[:20]
    uris += re.findall(rb"/EmbeddedFile\s*\(([^)]*)\)", pdf)[:20]
    # 3c) also scan the decompressed stream bytes directly for URI/Launch/FileSpec targets
    uris += re.findall(rb"/URI\s*\((.*?)\)", raw_text)
    uris += re.findall(rb"/Launch\s*[^>]{0,60}", raw_text)
    uris += re.findall(rb"/F\s*\(([^)]*)\)", raw_text)
    # 4) metadata /Info + /Title /Author /Subject /Keywords
    info_vals = re.findall(rb"/(?:Title|Author|Subject|Keywords)\s*\((.*?)\)", pdf)

    text = b"\n".join(text_parts)
    # also append the decompressed stream text so file:// /Launch targets are never missed
    raw_scan_src = raw_text + b"\n" + b"\n".join(uris)
    return {
        "text": text,
        "text_str": text.decode("utf-8", "replace"),
        "raw_text_str": raw_scan_src.decode("utf-8", "replace"),
        "uris": [u.decode("utf-8", "replace") for u in uris],
        "metadata": [v.decode("utf-8", "replace") for v in info_vals],
        "stream_hits": len(streams),
        "raw": pdf,
    }


BLOCKLIST_PATTERNS = [
    r"file:///app", r"file://", r"/app/pipeline", r"/app/output", r"/pipeline/",
    r"/opt/", r"/home/", r"/tmp/", r"localhost", r"127\.0\.0\.1",
    r"ORD-[A-F0-9]{6,}", r"sk_live_", r"rk_live_", r"whsec_",
    r"api[_-]?key", r"secret[_-]?token", r"password\s*[:=]",  # secrets (report content should not have)
]


def scan_pdf_for_leaks(pdf: bytes) -> dict:
    """Scan decompressed visible text + metadata + hyperlink URIs. Returns hits.

    Exact user-specified string file:///app/pipeline/out/...html MUST trigger
    INTERNAL_PATH_LEAK (it matches 'file://' and '/app/pipeline').
    """
    ex = extract_pdf_content(pdf)
    hay = " || ".join([ex["text_str"], ex["raw_text_str"], " ".join(ex["uris"]), " ".join(ex["metadata"])])
    hits = []
    for pat in BLOCKLIST_PATTERNS:
        m = re.findall(pat, hay)
        if m:
            hits.append({"pattern": pat, "count": len(m)})
    blocked = any(h["count"] > 0 for h in hits) or ex["stream_hits"] == 0
    return {
        "hits": hits,
        "blocked": blocked,
        "samples": ex["text_str"][:400],
        "uris": ex["uris"][:20],
        "metadata": ex["metadata"][:20],
        "stream_hits": ex["stream_hits"],
        "hard_fail": "INTERNAL_PATH_LEAK" if hits else None,
    }


if __name__ == "__main__":
    # self-test: craft a fake PDF whose content stream has the exact leak string
    import io, sys
    leak = b"file:///app/pipeline/out/SEO-Opportunity-Diagnostic-apple-2026-09-13.html"
    body = b"BT (" + leak + b") Tj ET"
    stream = zlib.compress(body)
    header = b"%PDF-1.4\n1 0 obj<</Length " + str(len(stream)).encode() + b"/Filter /FlateDecode>>stream\n"
    trailer = b"\nendstream\nendobj\ntrailer<</Root 1 0 R>>\n%%EOF"
    pdf = header + stream + trailer
    r = scan_pdf_for_leaks(pdf)
    print("TEST-BLOCKED:", r["blocked"], "HITS:", r["hits"])
    assert r["blocked"] is True, "MUST be blocked"
    assert any(h["pattern"] in ("file://", "/app/pipeline") for h in r["hits"]), "must flag exact string"
    print("SELF-TEST-PASS")