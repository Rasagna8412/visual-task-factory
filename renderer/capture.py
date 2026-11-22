"""Batch capture module using Playwright for Visual Task Factory (Milestone 1).

Renders a batch of generated HTML files to 1024x1024 PNG images using
ONE shared headless Chromium instance for optimal performance.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple, Union

from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright

DEFAULT_VIEWPORT = {"width": 1024, "height": 1024}


class BatchRenderer:
    """Manages a single headless Chromium browser instance to batch render HTML files to PNGs."""

    def __init__(
        self,
        viewport_width: int = 1024,
        viewport_height: int = 1024,
        device_scale_factor: float = 1.0,
    ) -> None:
        self.viewport = {"width": viewport_width, "height": viewport_height}
        self.device_scale_factor = device_scale_factor
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

    def __enter__(self) -> "BatchRenderer":
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def start(self) -> None:
        """Launches the single headless Chromium browser instance and initializes a page."""
        if self._browser is not None:
            return

        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(
            headless=True,
            args=[
                "--disable-gpu",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        self._context = self._browser.new_context(
            viewport=self.viewport,
            device_scale_factor=self.device_scale_factor,
        )
        self._page = self._context.new_page()

    def close(self) -> None:
        """Closes browser context and Playwright process cleanly."""
        try:
            if self._page is not None:
                self._page.close()
                self._page = None
        except Exception:
            pass

        try:
            if self._context is not None:
                self._context.close()
                self._context = None
        except Exception:
            pass

        try:
            if self._browser is not None:
                self._browser.close()
                self._browser = None
        except Exception:
            pass

        try:
            if self._playwright is not None:
                self._playwright.stop()
                self._playwright = None
        except Exception:
            pass

    def render(self, html_path: Union[str, Path], output_png_path: Union[str, Path]) -> Path:
        """Renders a single HTML file to PNG using the active browser page."""
        if self._page is None:
            self.start()

        html_file = Path(html_path).resolve()
        out_file = Path(output_png_path).resolve()
        out_file.parent.mkdir(parents=True, exist_ok=True)

        if not html_file.exists():
            raise FileNotFoundError(f"HTML source file not found: {html_file}")

        file_uri = html_file.as_uri()
        self._page.goto(file_uri, wait_until="load")
        self._page.wait_for_selector("svg", state="attached", timeout=10000)

        self._page.screenshot(
            path=str(out_file),
            type="png",
            clip={"x": 0, "y": 0, "width": self.viewport["width"], "height": self.viewport["height"]},
        )

        if not out_file.exists() or out_file.stat().st_size == 0:
            raise RuntimeError(f"Rendering failed or generated 0-byte file: {out_file}")

        return out_file

    def render_batch(
        self,
        items: Sequence[Tuple[Union[str, Path], Union[str, Path]]],
        verbose: bool = True,
    ) -> List[Path]:
        """Renders a batch of (html_path, output_png_path) pairs reusing the single browser instance."""
        if self._page is None:
            self.start()

        results: List[Path] = []
        start_time = time.time()

        if verbose:
            print(f"[BatchRenderer] Starting batch capture of {len(items)} items using 1 Chromium instance...")

        for idx, (html_path, png_path) in enumerate(items, 1):
            t0 = time.time()
            rendered_path = self.render(html_path, png_path)
            dt = time.time() - t0
            results.append(rendered_path)
            if verbose:
                print(f"  [{idx}/{len(items)}] Rendered -> {rendered_path.name} ({dt*1000:.1f}ms, {rendered_path.stat().st_size} bytes)")

        total_time = time.time() - start_time
        if verbose:
            print(f"[BatchRenderer] Successfully rendered {len(results)} images in {total_time:.2f}s ({total_time / max(len(results), 1):.2f}s/img).")

        return results


def render_batch(
    items: Sequence[Tuple[Union[str, Path], Union[str, Path]]],
    viewport_width: int = 1024,
    viewport_height: int = 1024,
    verbose: bool = True,
) -> List[Path]:
    """Convenience function that launches ONE headless Chromium instance to render all items."""
    with BatchRenderer(viewport_width=viewport_width, viewport_height=viewport_height) as renderer:
        return renderer.render_batch(items, verbose=verbose)


def main():
    parser = argparse.ArgumentParser(description="Batch capture HTML scenes to 1024x1024 PNGs using Playwright")
    parser.add_argument(
        "--html-dir",
        type=str,
        help="Directory to recursively search for scene.html files to render next to their sources",
    )
    parser.add_argument("--html-file", type=str, help="Single HTML file to render")
    parser.add_argument("--output-png", type=str, help="Output PNG path for single file rendering")
    parser.add_argument("--width", type=int, default=1024, help="Viewport width")
    parser.add_argument("--height", type=int, default=1024, help="Viewport height")

    args = parser.parse_args()

    items: List[Tuple[Path, Path]] = []

    if args.html_file:
        html_p = Path(args.html_file)
        out_p = Path(args.output_png) if args.output_png else html_p.with_name("scene.png")
        items.append((html_p, out_p))
    elif args.html_dir:
        base_dir = Path(args.html_dir)
        html_files = sorted(list(base_dir.rglob("scene.html")))
        for h in html_files:
            items.append((h, h.with_name("scene.png")))
    else:
        print("Please provide --html-dir or --html-file.")
        sys.exit(1)

    if not items:
        print("No HTML files found to render.")
        sys.exit(0)

    render_batch(items, viewport_width=args.width, viewport_height=args.height, verbose=True)


if __name__ == "__main__":
    main()
