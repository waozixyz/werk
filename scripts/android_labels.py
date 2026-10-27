"""Locate visible labels in screenshots from the private Android emulator."""
import csv
import io
import subprocess

from PIL import Image


def label_position(path, word, min_y=0):
    for scale in (1, 3):
        screenshot = path
        if scale == 3:
            # Tesseract misses white labels on small, dark theme buttons.
            # Separate those glyphs from the background before enlarging.
            with Image.open(path) as source:
                contrast = source.convert("L").point(lambda value: 0 if value > 160 else 255)
                contrast = contrast.resize((source.width * scale, source.height * scale),
                                           Image.Resampling.BICUBIC)
                screenshot = path.with_name(path.stem + "-contrast.png")
                contrast.save(screenshot)
        data = subprocess.check_output(
            ["tesseract", str(screenshot), "stdout", "--psm", "11", "-c", "tessedit_create_tsv=1"],
            stderr=subprocess.DEVNULL, text=True)
        for item in csv.DictReader(io.StringIO(data), delimiter="\t"):
            if item["text"].strip().lower() == word.lower():
                position = ((int(item["left"]) + int(item["width"]) // 2) // scale,
                            (int(item["top"]) + int(item["height"]) // 2) // scale)
                if position[1] >= min_y:
                    return position
    return None
