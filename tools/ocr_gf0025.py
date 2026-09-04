#!/usr/bin/env python3
"""OCR only the vocabulary pages of the image-only GF0025-2021 PDF.

The output deliberately contains positioned observations, not interpreted
vocabulary rows.  ``hsk_data.py`` remains responsible for parsing and
canonical validation.  Keeping those stages separate makes OCR mistakes
visible and reviewable.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import sys
from pathlib import Path

import fitz
import numpy as np
from rapidocr_onnxruntime import RapidOCR


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_bytes(data)
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--first-page", type=int, required=True, help="one-based inclusive page")
    parser.add_argument("--last-page", type=int, required=True, help="one-based inclusive page")
    parser.add_argument("--scale", type=float, default=1.5)
    args = parser.parse_args()

    if args.first_page < 1 or args.last_page < args.first_page or args.scale <= 0:
        parser.error("invalid page range or scale")

    document = fitz.open(args.pdf)
    if args.last_page > document.page_count:
        parser.error(f"PDF has only {document.page_count} pages")

    engine = RapidOCR()
    observations: list[dict[str, object]] = []
    matrix = fitz.Matrix(args.scale, args.scale)
    for page_number in range(args.first_page, args.last_page + 1):
        page = document[page_number - 1]
        pixmap = page.get_pixmap(matrix=matrix, alpha=False)
        image = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(
            pixmap.height, pixmap.width, pixmap.n
        )
        result, _ = engine(image)
        page_rows = [] if result is None else result
        for box, text, confidence in page_rows:
            xs = [float(point[0]) / pixmap.width for point in box]
            ys = [float(point[1]) / pixmap.height for point in box]
            observations.append(
                {
                    "box": [min(xs), min(ys), max(xs), max(ys)],
                    "confidence": round(float(confidence), 8),
                    "page": page_number,
                    "text": text,
                }
            )
        print(f"OCR page {page_number}: {len(page_rows)} observations", file=sys.stderr, flush=True)

    payload = b"".join(
        (json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode(
            "utf-8"
        )
        for row in observations
    )
    atomic_write(args.output, payload)
    metadata = {
        "document_sha256": sha256(args.pdf),
        "first_page": args.first_page,
        "last_page": args.last_page,
        "observation_count": len(observations),
        "output_sha256": hashlib.sha256(payload).hexdigest(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "renderer": f"PyMuPDF {importlib.metadata.version('PyMuPDF')}",
        "ocr_engine": f"rapidocr-onnxruntime {importlib.metadata.version('rapidocr-onnxruntime')}",
        "onnxruntime": importlib.metadata.version("onnxruntime"),
        "scale": args.scale,
    }
    atomic_write(
        args.output.with_suffix(args.output.suffix + ".metadata.json"),
        (json.dumps(metadata, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
