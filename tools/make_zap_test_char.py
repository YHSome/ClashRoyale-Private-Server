#!/usr/bin/env python3
"""Bisection: character clone only (no custom projectile/container)."""

import csv
import io
import lzma
import os
import zipfile

ROOT = r"C:\Users\YHSome\Projects\OtherProjects\ClashRoyal"
SERVER_CSV = os.path.join(ROOT, "HashRoyale", "app", "GameAssets", "csv_logic")
SRC_APK = os.path.join(ROOT, "clients", "retroroyale-1.9.2-phone-mod6.apk")
OUT_APK = os.path.join(ROOT, "clients", "retroroyale-1.9.2-phone-mod17-nogadget-unsigned.apk")


def sc_decompress(data):
    return lzma.LZMADecompressor().decompress(data[:5] + b"\xff" * 8 + data[9:])


def sc_compress(text):
    raw = lzma.compress(text, format=lzma.FORMAT_RAW, filters=[{"id": lzma.FILTER_LZMA1, "dict_size": 262144, "lc": 3, "lp": 0, "pb": 2}])
    return bytes([0x5D]) + (262144).to_bytes(4, "little") + len(text).to_bytes(4, "little") + raw


def parse(text):
    return list(csv.reader(io.StringIO(text)))


def clone(rows, name):
    for r in rows[1:]:
        if r and r[0] == name:
            return list(r)
    raise SystemExit("row not found: " + name)


def setf(row, header, field, value):
    row[header.index(field)] = value


def fmt(row):
    return '"' + '","'.join(row) + '"'


def upsert(text, row):
    name = row[0]
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines()
    out = []
    found = False
    for ln in lines:
        if ln.startswith('"%s",' % name) or ln.startswith(name + ","):
            out.append(fmt(row))
            found = True
        else:
            out.append(ln)
    if found:
        return newline.join(out) + newline
    if not text.endswith(newline):
        text += newline
    return text + fmt(row) + newline


def build():
    with open(os.path.join(SERVER_CSV, "spells_characters.csv"), encoding="utf-8", newline="") as f:
        sc_rows = parse(f.read())
    with open(os.path.join(SERVER_CSV, "characters.csv"), encoding="utf-8", newline="") as f:
        ch_rows = parse(f.read())
    sc_h, ch_h = sc_rows[0], ch_rows[0]

    card = clone(sc_rows, "ZapMachine")
    setf(card, sc_h, "Name", "BoundaryZapMachine")
    setf(card, sc_h, "SummonCharacter", "BoundaryZapMachine")
    setf(card, sc_h, "TID", "TID_SPELL_BOUNDARY_ZAP_MACHINE")
    setf(card, sc_h, "TID_INFO", "TID_SPELL_INFO_BOUNDARY_ZAP_MACHINE")

    char = clone(ch_rows, "ZapMachine")
    setf(char, ch_h, "Name", "BoundaryZapMachine")
    setf(char, ch_h, "TID", "TID_CHARACTER_BOUNDARY_ZAP_MACHINE")

    for fn, row in (("spells_characters.csv", card), ("characters.csv", char)):
        path = os.path.join(SERVER_CSV, fn)
        with open(path, encoding="utf-8", newline="") as f:
            text = f.read()
        data = upsert(text, row)
        if data != text:
            with open(path, "w", encoding="utf-8", newline="") as f:
                f.write(data)
            print("server patched", fn)

    zin = zipfile.ZipFile(SRC_APK)
    out = {}
    for entry, row in (("assets/csv_logic/spells_characters.csv", card), ("assets/csv_logic/characters.csv", char)):
        text = sc_decompress(zin.read(entry)).decode("utf-8")
        out[entry] = sc_compress(upsert(text, row).encode("utf-8"))
    zout = zipfile.ZipFile(OUT_APK, "w")
    for info in zin.infolist():
        payload = out.get(info.filename)
        zout.writestr(info, payload if payload is not None else zin.read(info.filename), compress_type=info.compress_type)
    zout.close()
    zin.close()
    print("wrote", OUT_APK)


if __name__ == "__main__":
    build()
