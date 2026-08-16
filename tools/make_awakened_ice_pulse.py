#!/usr/bin/env python3
"""Awakened Ice Golem v2: periodic death-effect pulses.

The data-driven SpawnAreaObject+SpawnInterval only fires ONCE at deploy (the
client ignores SpawnInterval for area objects).  Instead we use the Witch-style
periodic SpawnCharacter mechanic:

  AwakenedIceGolem  -> SpawnCharacter=AwakenedIcePulse, SpawnInterval=1500
  AwakenedIcePulse  -> tiny invisible unit with SpawnAreaObject=AwakenedFreeze
                       (fires once at ITS spawn = at the golem's position)

Edits server GameAssets + client APK characters.csv:
  * update AwakenedIceGolem row  (SpawnCharacter fields, drop SpawnAreaObject)
  * append AwakenedIcePulse row  (clone of IceSpirits, harmless/invisible)
"""

import csv
import io
import lzma
import os
import sys
import zipfile

ROOT = r"C:\Users\YHSome\Projects\OtherProjects\ClashRoyal"
SERVER_CSV = os.path.join(ROOT, "HashRoyale", "app", "GameAssets", "csv_logic", "characters.csv")
SRC_APK = os.path.join(ROOT, "clients", "retroroyale-1.9.2-phone-mod2.apk")
OUT_APK = os.path.join(ROOT, "clients", "retroroyale-1.9.2-phone-mod3-unsigned.apk")


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
    """Fully-quoted CSV row, matching how the previous patch appended rows."""
    return '"' + '","'.join(row) + '"'


def patch_csv_text(text: str) -> str:
    """Modify the AwakenedIceGolem line and append the AwakenedIcePulse line."""
    rows = parse(text)
    header = rows[0]

    parent = clone(rows, "AwakenedIceGolem")
    setf(parent, header, "SpawnCharacter", "AwakenedIcePulse")
    setf(parent, header, "SpawnCharacterLevelIndex", "1")
    setf(parent, header, "SpawnNumber", "1")
    setf(parent, header, "SpawnPauseTime", "1500")
    setf(parent, header, "SpawnRadius", "0")
    setf(parent, header, "SpawnAreaObject", "")
    setf(parent, header, "SpawnAreaObjectLevelIndex", "")

    spirit = clone(rows, "IceSpirits")
    pulse = spirit
    setf(pulse, header, "Name", "AwakenedIcePulse")
    setf(pulse, header, "SightRange", "0")
    setf(pulse, header, "DeployTime", "0")
    setf(pulse, header, "Speed", "0")
    setf(pulse, header, "Hitpoints", "1")
    setf(pulse, header, "HitSpeed", "0")
    setf(pulse, header, "LoadTime", "0")
    setf(pulse, header, "Projectile", "")
    setf(pulse, header, "Range", "0")
    setf(pulse, header, "AttacksGround", "")
    setf(pulse, header, "AttacksAir", "")
    setf(pulse, header, "LifeTime", "100")
    setf(pulse, header, "ProjectileEffect", "")
    setf(pulse, header, "DeathEffect", "")
    setf(pulse, header, "MoveEffect", "")
    setf(pulse, header, "SpawnEffect", "")
    setf(pulse, header, "ShadowScaleX", "10")
    setf(pulse, header, "ShadowScaleY", "10")
    setf(pulse, header, "ShadowX", "0")
    setf(pulse, header, "ShadowY", "0")
    setf(pulse, header, "ShadowSkew", "0")
    setf(pulse, header, "Scale", "1")
    setf(pulse, header, "CollisionRadius", "100")
    setf(pulse, header, "Mass", "0")
    setf(pulse, header, "HealthBarOffsetY", "")
    setf(pulse, header, "DamageExportName", "")
    setf(pulse, header, "ContinuousEffect", "")
    setf(pulse, header, "SpawnRadius", "0")
    setf(pulse, header, "Kamikaze", "")
    setf(pulse, header, "SpawnAreaObject", "AwakenedFreeze")
    setf(pulse, header, "SpawnAreaObjectLevelIndex", "1")
    setf(pulse, header, "DeployDelay", "0")

    # Rewrite the parent line in place; append the pulse line at the end.
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines()
    out_lines = []
    parent_done = False
    for ln in lines:
        if ln.startswith('"AwakenedIceGolem",') or ln.startswith("AwakenedIceGolem,"):
            out_lines.append(fmt_row(parent))
            parent_done = True
        else:
            out_lines.append(ln)
    if not parent_done:
        raise SystemExit("AwakenedIceGolem line not found in CSV")
    out_lines.append(fmt_row(pulse))
    return newline.join(out_lines) + newline


def patch_server():
    with open(SERVER_CSV, "r", encoding="utf-8", newline="") as f:
        text = f.read()
    if "AwakenedIcePulse" in text:
        # Idempotent re-run: force the parent's spawn timing fields to the
        # desired values (SpawnPauseTime 0 was ambiguous -> 1500).
        rows = parse(text)
        header = rows[0]
        parent = clone(rows, "AwakenedIceGolem")
        parent[header.index("SpawnPauseTime")] = "1500"
        parent[header.index("SpawnInterval")] = "1500"
        parent[header.index("SpawnStartTime")] = "0"
        parent[header.index("SpawnNumber")] = "1"
        parent[header.index("SpawnRadius")] = "0"
        newline = "\r\n" if "\r\n" in text else "\n"
        lines = text.splitlines()
        out_lines = []
        for ln in lines:
            if ln.startswith('"AwakenedIceGolem",') or ln.startswith("AwakenedIceGolem,"):
                out_lines.append(fmt_row(parent))
            else:
                out_lines.append(ln)
        with open(SERVER_CSV, "w", encoding="utf-8", newline="") as f:
            f.write(newline.join(out_lines) + newline)
        print("updated server characters.csv (SpawnPauseTime=1500)")
        return
    data = patch_csv_text(text)
    with open(SERVER_CSV, "w", encoding="utf-8", newline="") as f:
        f.write(data)
    print("patched server characters.csv")


def patch_client():
    zin = zipfile.ZipFile(SRC_APK)
    entry = "assets/csv_logic/characters.csv"
    text = sc_decompress(zin.read(entry)).decode("utf-8")
    if "AwakenedIcePulse" in text:
        rows = parse(text)
        header = rows[0]
        parent = clone(rows, "AwakenedIceGolem")
        parent[header.index("SpawnPauseTime")] = "1500"
        parent[header.index("SpawnInterval")] = "1500"
        parent[header.index("SpawnStartTime")] = "0"
        parent[header.index("SpawnNumber")] = "1"
        parent[header.index("SpawnRadius")] = "0"
        newline = "\r\n" if "\r\n" in text else "\n"
        lines = text.splitlines()
        out_lines = []
        for ln in lines:
            if ln.startswith('"AwakenedIceGolem",') or ln.startswith("AwakenedIceGolem,"):
                out_lines.append(fmt_row(parent))
            else:
                out_lines.append(ln)
        data = newline.join(out_lines) + newline
        payload = sc_compress(data.encode("utf-8"))

        zout = zipfile.ZipFile(OUT_APK, "w")
        for info in zin.infolist():
            if info.filename == entry:
                zout.writestr(info, payload, compress_type=info.compress_type)
            else:
                zout.writestr(info, zin.read(info.filename), compress_type=info.compress_type)
        zout.close()
        zin.close()
        print("updated client characters.csv (SpawnPauseTime=1500)")
        return
    data = patch_csv_text(text)
    payload = sc_compress(data.encode("utf-8"))

    zout = zipfile.ZipFile(OUT_APK, "w")
    for info in zin.infolist():
        if info.filename == entry:
            zout.writestr(info, payload, compress_type=info.compress_type)
        else:
            zout.writestr(info, zin.read(info.filename), compress_type=info.compress_type)
    zout.close()
    zin.close()
    print("wrote", OUT_APK)


if __name__ == "__main__":
    patch_server()
    patch_client()
