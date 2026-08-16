#!/usr/bin/env python3
"""Awakened Ice Golem v3: death-effect pulse bombs.

v2 (character puppet + SpawnAreaObject) spawned the puppet every 1.5s but the
spawn-time area object never fired for SpawnCharacter-created units (and the
unit was just removed by LifeTime, so nothing showed).

v3 uses the proven RageBarbarianBottle / GiantSkeletonBomb pattern:
  * AwakenedIcePulse is a no-HP BUILDING with DeployTime as a fuse.
  * When the fuse ends the unit DIES, firing the original ice-golem death
    effect: DeathDamage=40, DeathDamageRadius=2000 and
    DeathAreaEffect=FreezeIceGolemite (2s ice slow, radius 2000).
  * The parent AwakenedIceGolem keeps SpawnCharacter=AwakenedIcePulse with
    SpawnInterval/SpawnPauseTime=1500 -> one pulse every 1.5s.

Edits server GameAssets + client APK:
  * characters.csv : drop the old AwakenedIcePulse character row
  * buildings.csv  : add AwakenedIcePulse (clone of RageBarbarianBottle)
"""

import csv
import io
import lzma
import os
import zipfile

ROOT = r"C:\Users\YHSome\Projects\OtherProjects\ClashRoyal"
SERVER_CHAR = os.path.join(ROOT, "HashRoyale", "app", "GameAssets", "csv_logic", "characters.csv")
SERVER_BUILD = os.path.join(ROOT, "HashRoyale", "app", "GameAssets", "csv_logic", "buildings.csv")
SRC_APK = os.path.join(ROOT, "clients", "retroroyale-1.9.2-phone-mod3.apk")
OUT_APK = os.path.join(ROOT, "clients", "retroroyale-1.9.2-phone-mod4-unsigned.apk")


def sc_decompress(data: bytes) -> bytes:
    return lzma.LZMADecompressor().decompress(data[:5] + b"\xff" * 8 + data[9:])


def sc_compress(text: bytes) -> bytes:
    raw = lzma.compress(
        text,
        format=lzma.FORMAT_RAW,
        filters=[{"id": lzma.FILTER_LZMA1, "dict_size": 262144, "lc": 3, "lp": 0, "pb": 2}],
    )
    header = bytes([0x5D]) + (262144).to_bytes(4, "little") + len(text).to_bytes(4, "little")
    return header + raw


def parse(text: str):
    return list(csv.reader(io.StringIO(text)))


def clone(rows, name):
    for r in rows[1:]:
        if r and r[0] == name:
            return list(r)
    raise SystemExit("row not found: " + name)


def setf(row, header, field, value):
    row[header.index(field)] = value


def fmt_row(row) -> str:
    return '"' + '","'.join(row) + '"'


def patch_characters(text: str) -> str:
    """Remove the old AwakenedIcePulse character row; keep parent as-is."""
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines()
    out = [ln for ln in lines if not ln.startswith('"AwakenedIcePulse",')]
    if len(out) == len(lines):
        print("note: no AwakenedIcePulse character row to remove")
    return newline.join(out) + newline


def patch_buildings(text: str) -> str:
    """Add AwakenedIcePulse building (clone RageBarbarianBottle + death fields)."""
    if "AwakenedIcePulse" in text:
        rows = parse(text)
        header = rows[0]
        pulse = clone(rows, "AwakenedIcePulse")
        pulse[header.index("CollisionRadius")] = "0"
        newline = "\r\n" if "\r\n" in text else "\n"
        lines = text.splitlines()
        out = []
        for ln in lines:
            if ln.startswith('"AwakenedIcePulse",') or ln.startswith("AwakenedIcePulse,"):
                out.append(fmt_row(pulse))
            else:
                out.append(ln)
        print("note: updated existing AwakenedIcePulse (CollisionRadius=0)")
        return newline.join(out) + newline
    rows = parse(text)
    header = rows[0]
    bottle = clone(rows, "RageBarbarianBottle")
    pulse = bottle
    setf(pulse, header, "Name", "AwakenedIcePulse")
    setf(pulse, header, "Rarity", "Epic")
    setf(pulse, header, "DeployTime", "100")
    setf(pulse, header, "AttacksGround", "")
    setf(pulse, header, "AttacksAir", "")
    setf(pulse, header, "DeathDamage", "40")
    setf(pulse, header, "DeathDamageRadius", "2000")
    setf(pulse, header, "DeathPushBack", "")
    setf(pulse, header, "DeathEffect", "snowman_die")
    setf(pulse, header, "SpawnEffect", "")
    setf(pulse, header, "Scale", "1")
    setf(pulse, header, "CollisionRadius", "0")
    setf(pulse, header, "DeathAreaEffect", "FreezeIceGolemite")
    setf(pulse, header, "TID", "TID_CHARACTER_SMALL_GOLEM")

    newline = "\r\n" if "\r\n" in text else "\n"
    return text.rstrip("\r\n") + newline + fmt_row(pulse) + newline


def patch_server():
    with open(SERVER_CHAR, "r", encoding="utf-8", newline="") as f:
        ctext = f.read()
    cdata = patch_characters(ctext)
    with open(SERVER_CHAR, "w", encoding="utf-8", newline="") as f:
        f.write(cdata)

    with open(SERVER_BUILD, "r", encoding="utf-8", newline="") as f:
        btext = f.read()
    bdata = patch_buildings(btext)
    with open(SERVER_BUILD, "w", encoding="utf-8", newline="") as f:
        f.write(bdata)
    print("patched server characters.csv / buildings.csv")


def patch_client():
    zin = zipfile.ZipFile(SRC_APK)
    char_text = sc_decompress(zin.read("assets/csv_logic/characters.csv")).decode("utf-8")
    build_text = sc_decompress(zin.read("assets/csv_logic/buildings.csv")).decode("utf-8")
    char_data = patch_characters(char_text).encode("utf-8")
    build_data = patch_buildings(build_text).encode("utf-8")

    zout = zipfile.ZipFile(OUT_APK, "w")
    for info in zin.infolist():
        if info.filename == "assets/csv_logic/characters.csv":
            zout.writestr(info, sc_compress(char_data), compress_type=info.compress_type)
        elif info.filename == "assets/csv_logic/buildings.csv":
            zout.writestr(info, sc_compress(build_data), compress_type=info.compress_type)
        else:
            zout.writestr(info, zin.read(info.filename), compress_type=info.compress_type)
    zout.close()
    zin.close()
    print("wrote", OUT_APK)


if __name__ == "__main__":
    patch_server()
    patch_client()
