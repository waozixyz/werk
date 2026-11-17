"""Locate visible labels in screenshots from the private Android emulator."""
import csv
import io
import subprocess

from PIL import Image


def label_position(path, word, psm=11):
    def normalized(value):
        return "".join(character for character in value.casefold() if character.isalnum())

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
            ["tesseract", str(screenshot), "stdout", "--psm", str(psm), "-c", "tessedit_create_tsv=1"],
            stderr=subprocess.DEVNULL, text=True)
        rows = [item for item in csv.DictReader(io.StringIO(data), delimiter="\t")
                if item["text"].strip()]
        count = len(word.split())
        for index in range(len(rows) - count + 1):
            group = rows[index:index + count]
            if normalized(" ".join(item["text"] for item in group)) != normalized(word):
                continue
            # Sparse-text OCR may split a button's words into separate blocks.
            # Require one visual line and left-to-right order instead.
            top = max(int(item["top"]) for item in group)
            bottom = min(int(item["top"]) + int(item["height"]) for item in group)
            if bottom <= top or any(int(left["left"]) >= int(right["left"])
                                    for left, right in zip(group, group[1:])):
                continue
            return ((int(group[0]["left"]) + int(group[-1]["left"]) +
                     int(group[-1]["width"])) // 2 // scale,
                    (top + bottom) // 2 // scale)
    return None
