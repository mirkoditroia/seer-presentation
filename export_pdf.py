#!/usr/bin/env python3
"""
Esporta la presentazione THE DIGITAL SEER in PDF (una pagina per slide).

Uso:
  python export_pdf.py
  python export_pdf.py -o mio_deck.pdf
  python export_pdf.py --wait 2500 --width 1920 --height 1080

Prima esecuzione (solo una volta):
  pip install playwright
  playwright install chromium
"""

from __future__ import annotations

import argparse
import http.server
import socket
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULT_OUT = ROOT / "THE_DIGITAL_SEER_presentazione.pdf"


def _need_playwright() -> None:
    try:
        import playwright  # noqa: F401
    except ImportError:
        print("Manca playwright. Installa con:")
        print("  pip install playwright")
        print("  playwright install chromium")
        sys.exit(1)


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _start_server(port: int) -> http.server.ThreadingHTTPServer:
    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(ROOT), **kwargs)

        def log_message(self, *_args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def _wait_for_deck(page, timeout_ms: int = 15000) -> int:
    page.wait_for_function(
        "() => window.PresentationDeck && window.PresentationDeck.ready",
        timeout=timeout_ms,
    )
    return page.evaluate("() => window.PresentationDeck.count")


def _screenshot_slides(
    output: Path,
    wait_ms: int,
    width: int,
    height: int,
    keep_png: bool,
) -> None:
    from playwright.sync_api import sync_playwright
    from PIL import Image

    port = _find_free_port()
    server = _start_server(port)
    base_url = f"http://127.0.0.1:{port}/index.html?export=1"

    png_dir = output.parent / f".export_{output.stem}_png" if keep_png else Path(tempfile.mkdtemp(prefix="deck_export_"))
    png_dir.mkdir(parents=True, exist_ok=True)
    png_paths: list[Path] = []

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page(viewport={"width": width, "height": height})
            page.goto(base_url, wait_until="networkidle")
            slide_count = _wait_for_deck(page)

            print(f"Cattura {slide_count} slide @ {width}x{height} …")
            for i in range(slide_count):
                page.evaluate(f"() => window.PresentationDeck.go({i})")
                page.wait_for_timeout(wait_ms)
                png_path = png_dir / f"slide_{i + 1:02d}.png"
                page.locator(".deck").screenshot(path=str(png_path))
                png_paths.append(png_path)
                print(f"  [{i + 1:02d}/{slide_count:02d}] {png_path.name}")

            browser.close()

        images = [Image.open(p).convert("RGB") for p in png_paths]
        output.parent.mkdir(parents=True, exist_ok=True)
        images[0].save(
            output,
            "PDF",
            save_all=True,
            append_images=images[1:],
            resolution=150.0,
        )
        print(f"\nPDF salvato: {output.resolve()}")
        if keep_png:
            print(f"PNG intermedi: {png_dir.resolve()}")

    finally:
        server.shutdown()
        if not keep_png:
            for p in png_paths:
                p.unlink(missing_ok=True)
            try:
                png_dir.rmdir()
            except OSError:
                pass


def main() -> int:
    _need_playwright()

    parser = argparse.ArgumentParser(description="Esporta la presentazione in PDF.")
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=DEFAULT_OUT,
        help=f"Percorso PDF di output (default: {DEFAULT_OUT.name})",
    )
    parser.add_argument(
        "--wait",
        type=int,
        default=1800,
        metavar="MS",
        help="Attesa per slide in ms, per animazioni/barre (default: 1800)",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=1280,
        help="Larghezza viewport (default: 1280)",
    )
    parser.add_argument(
        "--height",
        type=int,
        default=720,
        help="Altezza viewport (default: 720)",
    )
    parser.add_argument(
        "--keep-png",
        action="store_true",
        help="Conserva le PNG accanto al PDF (cartella .export_<nome>_png/)",
    )
    args = parser.parse_args()

    t0 = time.perf_counter()
    _screenshot_slides(args.output, args.wait, args.width, args.height, args.keep_png)
    print(f"Completato in {time.perf_counter() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
