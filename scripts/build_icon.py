"""Render the cyan scissors logo to PNG sizes and a multi-size .ico.

Uses QPainter primitives directly so the cyan gradient renders reliably
across Qt builds (QSvgRenderer was inconsistent with linearGradient on
the offscreen platform).
"""

from __future__ import annotations

import os
import struct
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ICON_DIR = Path(__file__).resolve().parents[1] / "resources" / "icons"


def _draw_icon(size: int):
    from PySide6.QtCore import QPointF, QRectF, Qt
    from PySide6.QtGui import (
        QColor,
        QImage,
        QLinearGradient,
        QPainter,
        QPainterPath,
        QPen,
    )

    img = QImage(size, size, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)

    painter = QPainter(img)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

    radius = size * 52 / 256
    rect = QRectF(0, 0, size, size)
    grad = QLinearGradient(QPointF(0, 0), QPointF(size, size))
    grad.setColorAt(0.0, QColor("#22D3EE"))
    grad.setColorAt(1.0, QColor("#0891B2"))
    rounded = QPainterPath()
    rounded.addRoundedRect(rect, radius, radius)
    painter.fillPath(rounded, grad)

    # Subtle glossy overlay
    gloss = QLinearGradient(QPointF(0, 0), QPointF(0, size))
    gloss.setColorAt(0.0, QColor(255, 255, 255, 36))
    gloss.setColorAt(0.6, QColor(255, 255, 255, 0))
    painter.fillPath(rounded, gloss)

    # Scissors glyph (from spec: two circles + paths). Scaled to size.
    s = size / 24.0
    pen = QPen(QColor("#FFFFFF"))
    pen.setWidthF(max(1.6 * s, 1.6))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)

    # Position: design draws glyph in 24×24 viewBox; we want it centered.
    # Centering offset (the design centers it on the 256x256 canvas at
    # translate(46,46) scale(6.875) which keeps the same 24-unit glyph
    # at the canvas centre).
    off_x = (size - 24 * s) / 2
    off_y = (size - 24 * s) / 2

    def pt(x: float, y: float) -> QPointF:
        return QPointF(off_x + x * s, off_y + y * s)

    # Circle (6, 6, r=3)
    painter.drawEllipse(pt(6, 6), 3 * s, 3 * s)
    # Circle (6, 18, r=3)
    painter.drawEllipse(pt(6, 18), 3 * s, 3 * s)
    # path M8.12 8.12 L 12 12
    painter.drawLine(pt(8.12, 8.12), pt(12, 12))
    # path M20 4 L 8.12 15.88
    painter.drawLine(pt(20, 4), pt(8.12, 15.88))
    # path M14.8 14.8 L 20 20
    painter.drawLine(pt(14.8, 14.8), pt(20, 20))

    painter.end()
    return img


def main() -> int:
    from PySide6.QtWidgets import QApplication

    QApplication.instance() or QApplication([])

    sizes = [16, 24, 32, 48, 64, 128, 256]
    pngs: list[Path] = []
    for size in sizes:
        img = _draw_icon(size)
        out_png = ICON_DIR / f"app-{size}.png"
        img.save(str(out_png), "PNG")
        pngs.append(out_png)
        print(f"wrote {out_png}")

    # Canonical app.png at 256
    pngs[-1].read_bytes()
    (ICON_DIR / "app.png").write_bytes(pngs[-1].read_bytes())

    _write_multi_size_ico(ICON_DIR / "app.ico", pngs)
    print(f"wrote {ICON_DIR / 'app.ico'}")
    return 0


def _write_multi_size_ico(out_path: Path, pngs: list[Path]) -> None:
    """Pack each PNG as an ICONDIRENTRY pointing at the PNG bytes verbatim."""
    entries: list[tuple[int, int, bytes]] = []
    for png in pngs:
        size = int(png.stem.split("-")[-1])
        data = png.read_bytes()
        entries.append((size, size, data))

    n = len(entries)
    header = struct.pack("<HHH", 0, 1, n)
    dir_entries: list[bytes] = []
    offset = 6 + n * 16
    for w, h, data in entries:
        dir_entries.append(
            struct.pack(
                "<BBBBHHII",
                0 if w >= 256 else w,
                0 if h >= 256 else h,
                0,
                0,
                1,
                32,
                len(data),
                offset,
            )
        )
        offset += len(data)

    with out_path.open("wb") as fh:
        fh.write(header)
        for de in dir_entries:
            fh.write(de)
        for _w, _h, data in entries:
            fh.write(data)


if __name__ == "__main__":
    raise SystemExit(main())
