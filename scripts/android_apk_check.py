#!/usr/bin/env python3
"""Reject app-owned bytecode; permit shared Kryon account consent and resource constants."""
import re
import struct
import sys
from zipfile import ZipFile


def dex_classes(data):
    assert data.startswith(b"dex\n"), "Invalid DEX header"
    word = lambda offset: struct.unpack_from("<I", data, offset)[0]
    strings, types = word(60), word(68)
    count, definitions = word(96), word(100)
    for index in range(count):
        descriptor = word(types + word(definitions + index * 32) * 4)
        offset = word(strings + descriptor * 4)
        # Skip the ULEB128 string length, then read its ASCII descriptor.
        while data[offset] & 128:
            offset += 1
        offset += 1
        yield data[offset:data.index(0, offset)].decode("ascii")


def elf_section_names(data):
    assert data[:4] == b"\x7fELF" and data[5] == 1, "Expected a little-endian ELF library"
    wide = data[4] == 2
    assert data[4] in (1, 2), "Unsupported ELF class"
    table = struct.unpack_from("<Q" if wide else "<I", data, 40 if wide else 32)[0]
    size, count, strings_index = struct.unpack_from("<HHH", data, 58 if wide else 46)
    strings_entry = table + strings_index * size
    offset, length = struct.unpack_from("<QQ" if wide else "<II", data, strings_entry + (24 if wide else 16))
    strings = data[offset:offset + length]
    for index in range(count):
        name = struct.unpack_from("<I", data, table + index * size)[0]
        yield strings[name:strings.index(0, name)].decode("ascii")


def elf_exports(data):
    wide = data[4] == 2
    table = struct.unpack_from("<Q" if wide else "<I", data, 40 if wide else 32)[0]
    size, count = struct.unpack_from("<HH", data, 58 if wide else 46)
    sections = []
    for index in range(count):
        entry = table + index * size
        kind = struct.unpack_from("<I", data, entry + 4)[0]
        offset, length = struct.unpack_from("<QQ" if wide else "<II", data, entry + (24 if wide else 16))
        link = struct.unpack_from("<I", data, entry + (40 if wide else 24))[0]
        stride = struct.unpack_from("<Q" if wide else "<I", data, entry + (56 if wide else 36))[0]
        sections.append((kind, offset, length, link, stride))
    for kind, offset, length, link, stride in sections:
        if kind != 11:  # SHT_DYNSYM: symbols visible to Android's loader.
            continue
        _, strings_offset, strings_length, _, _ = sections[link]
        strings = data[strings_offset:strings_offset + strings_length]
        for entry in range(offset, offset + length, stride):
            name = struct.unpack_from("<I", data, entry)[0]
            info, other, defined = struct.unpack_from("<BBH", data, entry + (4 if wide else 12))
            if info >> 4 in (1, 2) and other & 3 == 0 and defined != 0:
                yield strings[name:strings.index(0, name)].decode("ascii")


def check_apk(path):
    with ZipFile(path) as archive:
        names = archive.namelist()
        # Account policy stays in Ziran. Kryon's consent flow is the only
        # platform Java allowed alongside Android's resource constants.
        handoff = {
            "Lorg/kryonlabs/platform/" + name
            for name in ("AccountHandoff", "AccountHandoffConsentActivity",
                         "AccountHandoffNameProvider", "AccountHandoffRequestActivity")
        }
        packaged_classes = set()
        for name in names:
            if name.endswith(".dex"):
                classes = list(dex_classes(archive.read(name)))
                packaged_classes.update(classes)
                allowed = lambda item: bool(re.fullmatch(r"Lxyz/waozi/pass/R(?:\$[^;]+)?;", item)) or any(
                    item == base + ";" or re.fullmatch(re.escape(base) + r"\$\$ExternalSyntheticLambda[0-9]+;", item)
                    for base in handoff)
                unexpected = [item for item in classes if not allowed(item)]
                assert not unexpected, f"{path}: packaged application bytecode: {unexpected}"
        assert {base + ";" for base in handoff} <= packaged_classes, f"{path}: missing shared account consent classes"
        for font in ["ui.ttf", "emoji.ttf"]:
            assert "assets/fonts/" + font in names, f"{path}: missing {font}"
        bundles = {f"assets/apps/{app}.zx" for app in ["apps", "entity", "pass", "auth", "calculator", "clock", "workbook"]}
        packaged = {name for name in names if name.startswith("assets/apps/") and not name.endswith("/")}
        assert packaged == bundles, f"{path}: stale or missing app bundles: {packaged ^ bundles}"
        for name in bundles:
            assert archive.read(name)[:4] == b"ZX\0\0", f"{path}: {name} has an obsolete bundle format"
        assert "assets/pfp.png" in names, f"{path}: missing profile pictures"
        native = [name for name in names if name.endswith("/libmain.so")]
        assert native, f"{path}: no NativeActivity payload"
        for name in native:
            assert "JNI_OnLoad" in set(elf_exports(archive.read(name))), f"{path}: {name} hides account JNI registration"
            assert ".note.gnu.build-id" not in set(elf_section_names(archive.read(name))), \
                f"{path}: {name} contains a build-path-dependent build ID"
    print(f"{path}: native Ziran app with shared Kryon account consent")


if __name__ == "__main__":
    for path in sys.argv[1:]:
        check_apk(path)
