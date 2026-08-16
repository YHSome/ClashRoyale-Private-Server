#!/usr/bin/env python3
"""Build bisect APKs from mod1 (elixir collector) to isolate which change
breaks the client loading.

  --texts   : add only the texts.csv card name rows
  --cards   : add only the card/character/area-object csv_logic rows
"""

import csv
import io
import lzma
import os
import sys
import zipfile

ROOT = r"C:\Users\YHSome\Projects\OtherProjects\ClashRoyal"
SRC_APK = os.path.join(ROOT, "clients", "retroroyale-1.9.2-phone-mod.apk")


def sc_decompress(data):
    return lzma.LZMADecompressor().decompress(data[:5] + b"\xff" * 8 + data[9:])


def sc_compress(text):
    raw = lzma.compress(
        text,
        format=lzma.FORMAT_RAW,
        filters=[{"id": lzma.FILTER_LZMA1, "dict_size": 262144, "lc": 3, "lp": 0, "pb": 2}],
    )
    return bytes([0x5D]) + (262144).to_bytes(4, "little") + len(text).to_bytes(4, "little") + raw


def parse(text):
    return list(csv.reader(io.StringIO(text)))


def clone(rows, name):
    for r in rows[1:]:
        if r and r[0] == name:
            return list(r)
    raise SystemExit("not found " + name)


def append_rows(text, rows):
    newline = "\r\n" if "\r\n" in text else "\n"
    if not text.endswith(newline):
        text += newline
    for r in rows:
        text += '"' + '","'.join(r) + '"' + newline
    return text.encode("utf-8")


def setf(row, header, field, value):
    row[header.index(field)] = value


def main():
    do_texts = "--texts" in sys.argv
    do_cards = "--cards" in sys.argv
    if not do_texts and not do_cards:
        raise SystemExit("specify --texts and/or --cards")

    zin = zipfile.ZipFile(SRC_APK)
    out = {}

    if do_cards:
        def load_csv(name):
            return sc_decompress(zin.read(name)).decode("utf-8")

        sc_text = load_csv("assets/csv_logic/spells_characters.csv")
        ch_text = load_csv("assets/csv_logic/characters.csv")
        ao_text = load_csv("assets/csv_logic/area_effect_objects.csv")
        sc_rows, ch_rows, ao_rows = parse(sc_text), parse(ch_text), parse(ao_text)

        card = clone(sc_rows, "IceGolemite")
        setf(card, sc_rows[0], "Name", "AwakenedIceGolem")
        setf(card, sc_rows[0], "SummonCharacter", "AwakenedIceGolem")
        setf(card, sc_rows[0], "TID", "TID_SPELL_AWAKENED_ICE_GOLEM")
        setf(card, sc_rows[0], "TID_INFO", "TID_SPELL_INFO_AWAKENED_ICE_GOLEM")

        char = clone(ch_rows, "IceGolemite")
        setf(char, ch_rows[0], "Name", "AwakenedIceGolem")
        setf(char, ch_rows[0], "SpawnStartTime", "0")
        setf(char, ch_rows[0], "SpawnInterval", "1500")
        setf(char, ch_rows[0], "SpawnAreaObject", "AwakenedFreeze")
        setf(char, ch_rows[0], "SpawnAreaObjectLevelIndex", "1")

        area = clone(ao_rows, "FreezeIceGolemite")
        setf(area, ao_rows[0], "Name", "AwakenedFreeze")
        setf(area, ao_rows[0], "Damage", "40")

        out["assets/csv_logic/spells_characters.csv"] = sc_compress(append_rows(sc_text, [card]))
        out["assets/csv_logic/characters.csv"] = sc_compress(append_rows(ch_text, [char]))
        out["assets/csv_logic/area_effect_objects.csv"] = sc_compress(append_rows(ao_text, [area]))

    if do_texts:
        t_text = sc_decompress(zin.read("assets/csv_client/texts.csv")).decode("utf-8")
        t_rows = parse(t_text)
        h = t_rows[0]

        def clone_text(tid):
            r = clone(t_rows, "TID_SPELL_ICEGOLEMITE")
            r[0] = tid
            return r

        name_row = clone_text("TID_SPELL_AWAKENED_ICE_GOLEM")
        name_row[h.index("EN")] = "Awakened Ice Golem"
        name_row[h.index("CN")] = "觉醒冰人"
        name_row[h.index("CNT")] = "覺醒冰人"
        info_row = clone_text("TID_SPELL_INFO_AWAKENED_ICE_GOLEM")
        info_row[h.index("EN")] = "Releases the Ice Golem's death effect every 1.5s."
        info_row[h.index("CN")] = "每隔1.5秒在当前位置释放戈仑冰人的亡语效果。"
        info_row[h.index("CNT")] = "每隔1.5秒在當前位置釋放戈侖冰人的亡語效果。"
        out["assets/csv_client/texts.csv"] = sc_compress(append_rows(t_text, [name_row, info_row]))

    tag = []
    if do_cards:
        tag.append("cards")
    if do_texts:
        tag.append("texts")
    out_apk = os.path.join(ROOT, "clients", "retroroyale-1.9.2-phone-bisect-%s-unsigned.apk" % "-".join(tag))
    zout = zipfile.ZipFile(out_apk, "w")
    for info in zin.infolist():
        data = out.get(info.filename)
        if data is None:
            data = zin.read(info.filename)
        zout.writestr(info, data, compress_type=info.compress_type)
    zout.close()
    zin.close()
    print("wrote", out_apk)


if __name__ == "__main__":
    main()
