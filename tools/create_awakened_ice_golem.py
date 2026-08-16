#!/usr/bin/env python3
"""Create the "Awakened Ice Golem" (觉醒冰人) card.

Clones the Ice Golem (data name IceGolemite): same cost (2) and stats, plus a
trait: every 1500ms release the original death effect (40 damage + ice slow in
a 2000-radius area) at its current position. Implemented with the client's
data-driven SpawnAreaObject + SpawnInterval mechanism.

Edits (server GameAssets + client APK):
  * spells_characters.csv   : new card  AwakenedIceGolem
  * characters.csv          : new char  AwakenedIceGolem (clone + spawn fields)
  * area_effect_objects.csv : new area  AwakenedFreeze (damage 40 + ice slow)
  * texts.csv (client)      : card name TIDs (CN: 觉醒冰人)
"""

import csv
import io
import lzma
import os
import zipfile

ROOT = r"C:\Users\YHSome\Projects\OtherProjects\ClashRoyal"
SERVER_CSV = os.path.join(ROOT, "HashRoyale", "app", "GameAssets", "csv_logic")
SRC_APK = os.path.join(ROOT, "clients", "retroroyale-1.9.2-phone-mod.apk")
OUT_APK = os.path.join(ROOT, "clients", "retroroyale-1.9.2-phone-mod2-unsigned.apk")


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


def parse_rows(text: str):
    return list(csv.reader(io.StringIO(text)))


def clone_row(rows, name):
    for r in rows[1:]:
        if r and r[0] == name:
            return list(r)
    raise SystemExit("row not found: " + name)


def set_field(row, header, field, value):
    row[header.index(field)] = value


def append_rows(text: str, new_rows) -> bytes:
    """Append fully-quoted CRLF rows, preserving the original text."""
    newline = "\r\n" if "\r\n" in text else "\n"
    if not text.endswith(newline):
        text += newline
    for r in new_rows:
        text += '"' + '","'.join(r) + '"' + newline
    return text.encode("utf-8")


# ---------------------------------------------------------------- build rows
def build_new_rows():
    with open(os.path.join(SERVER_CSV, "spells_characters.csv"), newline="", encoding="utf-8") as f:
        sc_rows = parse_rows(f.read())
    with open(os.path.join(SERVER_CSV, "characters.csv"), newline="", encoding="utf-8") as f:
        ch_rows = parse_rows(f.read())
    with open(os.path.join(SERVER_CSV, "area_effect_objects.csv"), newline="", encoding="utf-8") as f:
        ao_rows = parse_rows(f.read())

    sc_header = sc_rows[0]
    ch_header = ch_rows[0]
    ao_header = ao_rows[0]

    # 1) New card: clone IceGolemite card
    card = clone_row(sc_rows, "IceGolemite")
    set_field(card, sc_header, "Name", "AwakenedIceGolem")
    set_field(card, sc_header, "SummonCharacter", "AwakenedIceGolem")
    set_field(card, sc_header, "TID", "TID_SPELL_AWAKENED_ICE_GOLEM")
    set_field(card, sc_header, "TID_INFO", "TID_SPELL_INFO_AWAKENED_ICE_GOLEM")

    # 2) New character: clone IceGolemite + periodic spawn fields
    char = clone_row(ch_rows, "IceGolemite")
    set_field(char, ch_header, "Name", "AwakenedIceGolem")
    set_field(char, ch_header, "SpawnStartTime", "0")
    set_field(char, ch_header, "SpawnInterval", "1500")
    set_field(char, ch_header, "SpawnAreaObject", "AwakenedFreeze")
    set_field(char, ch_header, "SpawnAreaObjectLevelIndex", "1")

    # 3) New area object: clone FreezeIceGolemite + damage 40
    area = clone_row(ao_rows, "FreezeIceGolemite")
    set_field(area, ao_header, "Name", "AwakenedFreeze")
    set_field(area, ao_header, "Damage", "40")

    return card, char, area


# ---------------------------------------------------------------- server CSV
def patch_server(card, char, area):
    targets = {
        "spells_characters.csv": card,
        "characters.csv": char,
        "area_effect_objects.csv": area,
    }
    for fname, row in targets.items():
        path = os.path.join(SERVER_CSV, fname)
        with open(path, "r", encoding="utf-8", newline="") as f:
            text = f.read()
        if row[0] in text:
            print("skip server", fname, "(already patched)")
            continue
        data = append_rows(text, [row])
        with open(path, "wb") as f:
            f.write(data)
        print("patched server", fname)


# ---------------------------------------------------------------- client APK
def patch_client(card, char, area):
    zin = zipfile.ZipFile(SRC_APK)
    out = {}

    # csv_logic replacements (SC compressed)
    for entry, row in [
        ("assets/csv_logic/spells_characters.csv", card),
        ("assets/csv_logic/characters.csv", char),
        ("assets/csv_logic/area_effect_objects.csv", area),
    ]:
        text = sc_decompress(zin.read(entry)).decode("utf-8")
        data = append_rows(text, [row])
        out[entry] = sc_compress(data)
        print("patched client", entry)

    # texts.csv: add card name TIDs (SC compressed, plain csv inside)
    texts = sc_decompress(zin.read("assets/csv_client/texts.csv")).decode("utf-8")
    t_rows = parse_rows(texts)
    t_header = t_rows[0]

    def clone_text(tid):
        r = clone_row(t_rows, "TID_SPELL_ICEGOLEMITE")
        r[0] = tid
        # language columns: EN(1), CN(14), CNT(15)
        return r

    name_row = clone_text("TID_SPELL_AWAKENED_ICE_GOLEM")
    name_row[t_header.index("EN")] = "Awakened Ice Golem"
    name_row[t_header.index("CN")] = "觉醒冰人"
    name_row[t_header.index("CNT")] = "覺醒冰人"

    info_row = clone_text("TID_SPELL_INFO_AWAKENED_ICE_GOLEM")
    info_row[t_header.index("EN")] = "Releases the Ice Golem's death effect every 1.5s."
    info_row[t_header.index("CN")] = "每隔1.5秒在当前位置释放戈仑冰人的亡语效果。"
    info_row[t_header.index("CNT")] = "每隔1.5秒在當前位置釋放戈侖冰人的亡語效果。"

    texts_data = append_rows(texts, [name_row, info_row])
    out["assets/csv_client/texts.csv"] = sc_compress(texts_data)
    print("patched client texts.csv")

    # write new apk preserving all other entries
    zout = zipfile.ZipFile(OUT_APK, "w")
    for info in zin.infolist():
        data = out.get(info.filename)
        if data is None:
            data = zin.read(info.filename)
        zout.writestr(info, data, compress_type=info.compress_type)
    zout.close()
    zin.close()
    print("wrote", OUT_APK)


if __name__ == "__main__":
    card, char, area = build_new_rows()
    patch_server(card, char, area)
    patch_client(card, char, area)
