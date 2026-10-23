#!/usr/bin/env python3
"""Install the same tool launchers in user installs and Linux packages."""
import argparse
from pathlib import Path
import shutil
import subprocess

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--data-dir", type=Path, required=True)
parser.add_argument("--bin-dir", type=Path)
parser.add_argument("--desktop-dir", type=Path)
parser.add_argument("--uninstall", action="store_true")
args = parser.parse_args()


def executable(path):
    # Desktop Entry Exec quoting has an additional escaping layer.
    value = str(path).replace("\\", "\\\\\\\\").replace('"', '\\\\"')
    value = value.replace("`", "\\\\`").replace("$", "\\\\$").replace("%", "%%")
    return '"' + value + '"'


for source in sorted((root / "packaging/linux").glob("xyz.waozi.werk*.desktop")):
    destinations = [args.data_dir / "applications" / source.name]
    if args.desktop_dir:
        destinations.append(args.desktop_dir / source.name)
    content = source.read_text()
    if args.bin_dir:
        content = content.replace("Exec=werk ", "Exec=" + executable(args.bin_dir / "werk") + " ")
        content = content.replace("TryExec=werk", "TryExec=" + str(args.bin_dir / "werk"))
        # Local launchers resolve their installed icon directly, including
        # custom data directories and paths containing spaces.
        for line in content.splitlines():
            if line.startswith("Icon="):
                name = line.removeprefix("Icon=")
                icon = args.data_dir / "icons/hicolor/512x512/apps" / (name + ".png")
                content = content.replace(line, "Icon=" + str(icon.resolve()))
    for target in destinations:
        if args.uninstall:
            target.unlink(missing_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
            target.chmod(0o755 if target.parent == args.desktop_dir else 0o644)
            if target.parent == args.desktop_dir and shutil.which("gio"):
                subprocess.run(["gio", "set", str(target), "metadata::trusted", "true"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

icons = {"werk": root / "assets/app/icon.png"}
icons.update({path.stem: path for path in (root / "packaging/linux/icons").glob("*.png")})
for name, source in icons.items():
    target = args.data_dir / "icons/hicolor/512x512/apps" / (name + ".png")
    if args.uninstall:
        target.unlink(missing_ok=True)
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        target.chmod(0o644)

notice = args.data_dir / "doc/werk/MingCute-LICENSE.txt"
if args.uninstall:
    notice.unlink(missing_ok=True)
else:
    notice.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(root / "packaging/linux/icons/LICENSE-MingCute.txt", notice)
    notice.chmod(0o644)
