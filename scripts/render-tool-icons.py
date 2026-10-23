#!/usr/bin/env python3
"""Render the tools' existing MingCute vector icons as Linux launcher PNGs."""
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET
import cairosvg

root = Path(__file__).resolve().parents[1]
mingcute = Path(subprocess.check_output([str(root / "scripts/ziran.sh"), "pkg", "path", "mingcute"], text=True).strip())
output = root / "packaging/linux/icons"
output.mkdir(exist_ok=True)
icons = {
    "pass": ("regular/system/keyhole.svg", "#6750A4"),
    "auth": ("regular/system/shield.svg", "#146B58"),
    "calculator": ("regular/education/counter.svg", "#245F9B"),
    "clock": ("regular/system/time.svg", "#9A4F19"),
    "workbook": ("extra/table_row_add.svg", "#356B30"),
}
for app, (relative, color) in icons.items():
    source = ET.parse(mingcute / "svg" / relative).getroot()
    for node in source.iter():
        for attribute in ("stroke", "fill"):
            if node.get(attribute) not in (None, "none"):
                node.set(attribute, "#FFFFFF")
    body = "".join(ET.tostring(node, encoding="unicode") for node in source)
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512"><rect x="16" y="16" width="480" height="480" rx="112" fill="{color}"/><g transform="translate(88 88) scale(14)">{body}</g></svg>'
    cairosvg.svg2png(bytestring=svg.encode(), write_to=str(output / f"werk-{app}.png"))
(output / "LICENSE-MingCute.txt").write_bytes((mingcute / "LICENSE").read_bytes())
