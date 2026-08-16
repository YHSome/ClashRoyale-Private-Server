#!/usr/bin/env python3
"""Boundary Bomber (界炸弹兵): Bomber clone + rocket-on-every-throw.

Trait: every attack throws the normal bomb AND fires a rocket to the target.
Implemented with the Princess-style multi-projectile mechanic:

  * characters.csv      BoundaryBomber (clone Bomber)
        Projectile = BombSkeletonProjectile   (the normal bomb)
        CustomFirstProjectile = BoundaryRocket (first projectile = rocket)
        MultipleProjectiles = 2                (rocket + bomb per attack)
  * projectiles.csv     BoundaryRocket (clone RocketSpell, Damage matched to
        the bomb so the card keeps Bomber-level damage per projectile)
  * spells_characters.csv BoundaryBomber card (3 elixir, clone Bomber)
  * texts.csv (client)  CN: 界炸弹兵

NOTE: with 1.9.2 data fields a character projectile always originates at the
unit (ProjectileStartRadius). A true "fires from the king tower" origin would
require a native libg.so engine patch; the rocket here launches from the
bomber toward the target.
"""

import csv
import io
import lzma
import os
import zipfile

ROOT = r"C:\Users\YHSome\Projects\OtherProjects\ClashRoyal"
SERVER_CSV = os.path.join(ROOT, "HashRoyale", "app", "GameAssets", "csv_logic")
SRC_APK = os.path.join(ROOT, "clients", "retroroyale-1.9.2-phone-mod4.apk")
OUT_APK = os.path.join(ROOT, "clients", "retroroyale-1.9.2-phone-mod5-unsigned.apk")


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


def append_row(text: str, row) -> str:
    newline = "\r\n" if "\r\n" in text else "\n"
    if not text.endswith(newline):
        text += newline
    return text + fmt_row(row) + newline


def patch_csv_text(text: str, table: str) -> str:
    """Return patched CSV text for the given table ('card'/'char'/'proj'/'texts')."""
    rows = parse(text)
    header = rows[0]
    if table == "card":
        if "BoundaryBomber" in text:
            return text
        card = clone(rows, "Bomber")
        setf(card, header, "Name", "BoundaryBomber")
        setf(card, header, "SummonCharacter", "BoundaryBomber")
        setf(card, header, "TID", "TID_SPELL_BOUNDARY_BOMBER")
        setf(card, header, "TID_INFO", "TID_SPELL_INFO_BOUNDARY_BOMBER")
        return append_row(text, card)
    if table == "char":
        ch = clone(rows, "Bomber")
        setf(ch, header, "Name", "BoundaryBomber")
        setf(ch, header, "CustomFirstProjectile", "BoundaryRocket")
        setf(ch, header, "MultipleProjectiles", "2")
        # TEST: spawn projectiles 20000 units BEHIND the bomber (negative
        # ProjectileStartRadius) so the launch point lands near the own
        # king tower side. Applies to both the rocket and the bomb.
        setf(ch, header, "ProjectileStartRadius", "-20000")
        if "BoundaryBomber" in text:
            # update the existing row in place (idempotent re-run)
            newline = "\r\n" if "\r\n" in text else "\n"
            lines = text.splitlines()
            out = []
            for ln in lines:
                if ln.startswith('"BoundaryBomber",') or ln.startswith("BoundaryBomber,"):
                    out.append(fmt_row(ch))
                else:
                    out.append(ln)
            return newline.join(out) + newline
        return append_row(text, ch)
    if table == "proj":
        if "BoundaryRocket" in text:
            return text
        pr = clone(rows, "RocketSpell")
        setf(pr, header, "Name", "BoundaryRocket")
        setf(pr, header, "Damage", "128")
        return append_row(text, pr)
    if table == "texts":
        if "TID_SPELL_BOUNDARY_BOMBER" in text:
            return text
        t_rows = rows
        t_header = t_rows[0]

        def clone_text(tid):
            r = clone(t_rows, "TID_SPELL_BOMBER")
            r[0] = tid
            return r

        name_row = clone_text("TID_SPELL_BOUNDARY_BOMBER")
        name_row[t_header.index("EN")] = "Boundary Bomber"
        name_row[t_header.index("CN")] = "界炸弹兵"
        name_row[t_header.index("CNT")] = "界炸彈兵"

        info_row = clone_text("TID_SPELL_INFO_BOUNDARY_BOMBER")
        info_row[t_header.index("EN")] = "Every bomb throw also launches a rocket at the target."
        info_row[t_header.index("CN")] = "每次丢出炸弹时，还会向目标发射一发火箭。"
        info_row[t_header.index("CNT")] = "每次丟出炸彈時，還會向目標發射一發火箭。"
        return append_row(append_row(text, name_row), info_row)
    raise SystemExit("unknown table " + table)


def patch_server():
    targets = {
        "spells_characters.csv": "card",
        "characters.csv": "char",
        "projectiles.csv": "proj",
    }
    for fname, table in targets.items():
        path = os.path.join(SERVER_CSV, fname)
        with open(path, "r", encoding="utf-8", newline="") as f:
            text = f.read()
        data = patch_csv_text(text, table)
        if data != text:
            with open(path, "w", encoding="utf-8", newline="") as f:
                f.write(data)
            print("patched server", fname)
        else:
            print("skip server", fname, "(already patched)")


def patch_client():
    zin = zipfile.ZipFile(SRC_APK)
    out = {}
    targets = {
        "assets/csv_logic/spells_characters.csv": "card",
        "assets/csv_logic/characters.csv": "char",
        "assets/csv_logic/projectiles.csv": "proj",
        "assets/csv_client/texts.csv": "texts",
    }
    for entry, table in targets.items():
        text = sc_decompress(zin.read(entry)).decode("utf-8")
        data = patch_csv_text(text, table)
        if data != text:
            out[entry] = sc_compress(data.encode("utf-8"))
            print("patched client", entry)
        else:
            print("skip client", entry, "(already patched)")

    zout = zipfile.ZipFile(OUT_APK, "w")
    for info in zin.infolist():
        if info.filename in out:
            zout.writestr(info, out[info.filename], compress_type=info.compress_type)
        else:
            zout.writestr(info, zin.read(info.filename), compress_type=info.compress_type)
    zout.close()
    zin.close()
    print("wrote", OUT_APK)


if __name__ == "__main__":
    patch_server()
    patch_client()
