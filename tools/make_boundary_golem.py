#!/usr/bin/env python3
"""界戈仑石人 (Boundary Golem) — 戈仑石人克隆。

效果：每 0.5 秒（HitSpeed=LoadTime=500）在自身召唤一个法术。
当前用 SpawnAreaObject=Zap（电法同款：攻击时在自身/目标施放 Zap，实测确认落点）。
数据层没有“随机法术池”战斗机制（RandomSpell 仅活动/征召 UI），如需随机需要 Frida。

实现：
  * characters.csv        BoundaryGolem（克隆 Golem，HitSpeed/LoadTime=500，SpawnAreaObject=Zap）
  * spells_characters.csv BoundaryGolem 卡（克隆 Golem 卡，8 费）
  * texts.csv             TID_SPELL_BOUNDARY_GOLEM（CN: 界戈仑石人）
"""

import csv
import io
import lzma
import os
import zipfile

ROOT = r"C:\Users\YHSome\Projects\OtherProjects\ClashRoyal"
SERVER_CSV = os.path.join(ROOT, "HashRoyale", "app", "GameAssets", "csv_logic")
SRC_APK = os.path.join(ROOT, "clients", "retroroyale-1.9.2-phone-mod44-nogadget.apk")
OUT_APK = os.path.join(ROOT, "clients", "retroroyale-1.9.2-phone-mod45-nogadget-unsigned.apk")


def sc_decompress(data: bytes) -> bytes:
    return lzma.LZMADecompressor().decompress(data[:5] + b"\xff" * 8 + data[9:])


def sc_compress(text: bytes) -> bytes:
    raw = lzma.compress(
        text,
        format=lzma.FORMAT_RAW,
        filters=[{"id": lzma.FILTER_LZMA1, "dict_size": 262144, "lc": 3, "lp": 0, "pb": 2}],
    )
    return bytes([0x5D]) + (262144).to_bytes(4, "little") + len(text).to_bytes(4, "little") + raw


def parse(text: str):
    return list(csv.reader(io.StringIO(text)))


def clone(rows, name):
    for r in rows[1:]:
        if r and r[0] == name:
            return list(r)
    raise SystemExit("row not found: " + name)


def setf(row, header, field, value):
    row[header.index(field)] = value


def fmt(row) -> str:
    return '"' + '","'.join(row) + '"'


def upsert(text: str, row) -> str:
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


def build_character(ch_rows, ch_h):
    c = clone(ch_rows, "Golem")
    setf(c, ch_h, "Name", "BoundaryGolem")
    setf(c, ch_h, "HitSpeed", "500")
    setf(c, ch_h, "LoadTime", "500")
    setf(c, ch_h, "SpawnAreaObject", "Zap")
    setf(c, ch_h, "SpawnAreaObjectLevelIndex", "1")
    setf(c, ch_h, "TID", "TID_SPELL_BOUNDARY_GOLEM")
    return c


def build_card(sc_rows, sc_h):
    card = clone(sc_rows, "Golem")
    setf(card, sc_h, "Name", "BoundaryGolem")
    setf(card, sc_h, "SummonCharacter", "BoundaryGolem")
    setf(card, sc_h, "TID", "TID_SPELL_BOUNDARY_GOLEM")
    setf(card, sc_h, "TID_INFO", "TID_SPELL_INFO_BOUNDARY_GOLEM")
    return card


def build_texts(text: str):
    rows = parse(text)
    t_header = rows[0]

    def clone_text(tid):
        r = clone(rows, "TID_SPELL_GOLEM")
        r[0] = tid
        return r

    name_row = clone_text("TID_SPELL_BOUNDARY_GOLEM")
    name_row[t_header.index("EN")] = "Boundary Golem"
    name_row[t_header.index("CN")] = "界戈仑石人"
    name_row[t_header.index("CNT")] = "界戈侖石人"

    info_row = clone_text("TID_SPELL_INFO_BOUNDARY_GOLEM")
    info_row[t_header.index("EN")] = "Every 0.5s summons a spell at itself."
    info_row[t_header.index("CN")] = "每 0.5 秒在自身召唤一个法术。"
    info_row[t_header.index("CNT")] = "每 0.5 秒在自身召喚一個法術。"
    return upsert(upsert(text, name_row), info_row)


def patch_server(character, card):
    for fn, rows, kind in (
        ("characters.csv", character, "character"),
        ("spells_characters.csv", card, "card"),
    ):
        path = os.path.join(SERVER_CSV, fn)
        with open(path, "r", encoding="utf-8", newline="") as f:
            text = f.read()
        data = upsert(text, rows)
        if data != text:
            with open(path, "w", encoding="utf-8", newline="") as f:
                f.write(data)
            print("patched server", fn, kind)
        else:
            print("skip server", fn, kind)

    texts_path = os.path.join(SERVER_CSV, "..", "csv_client", "texts.csv")
    with open(texts_path, "r", encoding="utf-8", newline="") as f:
        text = f.read()
    data = build_texts(text)
    if data != text:
        with open(texts_path, "w", encoding="utf-8", newline="") as f:
            f.write(data)
        print("patched server texts.csv")
    else:
        print("skip server texts.csv")


def patch_client(character, card):
    zin = zipfile.ZipFile(SRC_APK)
    out = {}
    file_text = {}
    for entry, row, kind in (
        ("assets/csv_logic/characters.csv", character, "character"),
        ("assets/csv_logic/spells_characters.csv", card, "card"),
    ):
        if entry not in file_text:
            file_text[entry] = sc_decompress(zin.read(entry)).decode("utf-8")
        file_text[entry] = upsert(file_text[entry], row)
        print("patched client", entry, kind)
    for entry, text in file_text.items():
        out[entry] = sc_compress(text.encode("utf-8"))

    texts = sc_decompress(zin.read("assets/csv_client/texts.csv")).decode("utf-8")
    t_data = build_texts(texts)
    if t_data != texts:
        out["assets/csv_client/texts.csv"] = sc_compress(t_data.encode("utf-8"))
        print("patched client texts.csv")
    else:
        print("skip client texts.csv")

    zout = zipfile.ZipFile(OUT_APK, "w")
    for info in zin.infolist():
        payload = out.get(info.filename)
        zout.writestr(info, payload if payload is not None else zin.read(info.filename), compress_type=info.compress_type)
    zout.close()
    zin.close()
    print("wrote", OUT_APK)


def main():
    with open(os.path.join(SERVER_CSV, "characters.csv"), encoding="utf-8", newline="") as f:
        ch_rows = parse(f.read())
    with open(os.path.join(SERVER_CSV, "spells_characters.csv"), encoding="utf-8", newline="") as f:
        sc_rows = parse(f.read())

    character = build_character(ch_rows, ch_rows[0])
    card = build_card(sc_rows, sc_rows[0])

    # 新卡在 spells_characters.csv 中的行号（1-based，卡组 InstanceId 用）
    instance_id = sum(1 for r in sc_rows[1:] if r and r[0])
    print("BoundaryGolem spells_characters instance id:", instance_id)
    print("global id: 26000000 +", instance_id, "=", 26000000 + instance_id)

    patch_server(character, card)
    patch_client(character, card)


if __name__ == "__main__":
    main()
