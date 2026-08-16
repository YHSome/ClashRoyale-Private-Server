#!/usr/bin/env python3
"""一个火枪手 (OneMusketeer) — 火枪手克隆。

效果：前 3 发子弹是火箭（无距离限制），随后变回普通火枪手。

实现：数据层没有“前 N 次攻击”计数机制，MorphCharacter 实测不生效；
改用 Frida 精确计数：
  * 数据默认 OneMusketeer = 只发射火箭、射程 40000（无 Frida 时的兜底行为）；
  * Frida 脚本在战斗里挂投射物 tick，数到第 3 发火箭后，把数据对象的
    Projectile 改回 MusketeerProjectile、Range 改回 6000 → 之后就是普通火枪手。
  * 本脚本只负责数据部分；mod51-gadget 由 gadget 构建流程注入 libfrida-gadget。
"""

import csv
import io
import lzma
import os
import zipfile

ROOT = r"C:\Users\YHSome\Projects\OtherProjects\ClashRoyal"
SERVER_CSV = os.path.join(ROOT, "HashRoyale", "app", "GameAssets", "csv_logic")
SRC_APK = os.path.join(ROOT, "clients", "retroroyale-1.9.2-phone-mod50-nogadget.apk")
OUT_APK = os.path.join(ROOT, "clients", "retroroyale-1.9.2-phone-mod51-nogadget-unsigned.apk")


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


def remove_row(text: str, name: str) -> str:
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines()
    out = [ln for ln in lines if not (ln.startswith('"%s",' % name) or ln.startswith(name + ","))]
    return newline.join(out) + newline


def build_character(ch_rows, ch_h):
    c = clone(ch_rows, "Musketeer")
    setf(c, ch_h, "Name", "OneMusketeer")
    setf(c, ch_h, "SightRange", "40000")
    setf(c, ch_h, "Range", "40000")
    setf(c, ch_h, "Projectile", "BoundaryOneMusketeerRocket")
    setf(c, ch_h, "MorphCharacter", "")
    setf(c, ch_h, "MorphTime", "")
    setf(c, ch_h, "MorphKeepTarget", "")
    setf(c, ch_h, "TID", "TID_SPELL_ONE_MUSKETEER")
    return c


def build_projectile(pr_rows, pr_h):
    p = clone(pr_rows, "RocketSpell")
    setf(p, pr_h, "Name", "BoundaryOneMusketeerRocket")
    return p


def build_card(sc_rows, sc_h):
    card = clone(sc_rows, "Musketeer")
    setf(card, sc_h, "Name", "OneMusketeer")
    setf(card, sc_h, "SummonCharacter", "OneMusketeer")
    setf(card, sc_h, "TID", "TID_SPELL_ONE_MUSKETEER")
    setf(card, sc_h, "TID_INFO", "TID_SPELL_INFO_ONE_MUSKETEER")
    return card


def build_texts(text: str):
    rows = parse(text)
    t_header = rows[0]

    def clone_text(tid):
        r = clone(rows, "TID_CHARACTER_MUSKETEER")
        r[0] = tid
        return r

    name_row = clone_text("TID_SPELL_ONE_MUSKETEER")
    name_row[t_header.index("EN")] = "One Musketeer"
    name_row[t_header.index("CN")] = "一个火枪手"
    name_row[t_header.index("CNT")] = "一個火槍手"

    info_row = clone_text("TID_SPELL_INFO_ONE_MUSKETEER")
    info_row[t_header.index("EN")] = "First 3 shots are unlimited-range rockets, then becomes a normal Musketeer."
    info_row[t_header.index("CN")] = "前 3 发为全图火箭，随后变回普通火枪手。"
    info_row[t_header.index("CNT")] = "前 3 發為全圖火箭，隨後變回普通火槍手。"
    return upsert(upsert(text, name_row), info_row)


def patch_server(character, projectile, card):
    for fn, rows, kind in (
        ("characters.csv", character, "character"),
        ("projectiles.csv", projectile, "projectile"),
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

    # 清理不再使用的变身阶段
    chars_path = os.path.join(SERVER_CSV, "characters.csv")
    with open(chars_path, "r", encoding="utf-8", newline="") as f:
        text = f.read()
    data = remove_row(text, "OneMusketeerNormal")
    if data != text:
        with open(chars_path, "w", encoding="utf-8", newline="") as f:
            f.write(data)
        print("removed server OneMusketeerNormal")

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


def patch_client(character, projectile, card):
    zin = zipfile.ZipFile(SRC_APK)
    out = {}
    file_text = {}
    for entry, row, kind in (
        ("assets/csv_logic/characters.csv", character, "character"),
        ("assets/csv_logic/projectiles.csv", projectile, "projectile"),
        ("assets/csv_logic/spells_characters.csv", card, "card"),
    ):
        if entry not in file_text:
            file_text[entry] = sc_decompress(zin.read(entry)).decode("utf-8")
        file_text[entry] = upsert(file_text[entry], row)
        print("patched client", entry, kind)
    entry = "assets/csv_logic/characters.csv"
    file_text[entry] = remove_row(file_text[entry], "OneMusketeerNormal")
    print("removed client OneMusketeerNormal")
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
    with open(os.path.join(SERVER_CSV, "projectiles.csv"), encoding="utf-8", newline="") as f:
        pr_rows = parse(f.read())
    with open(os.path.join(SERVER_CSV, "spells_characters.csv"), encoding="utf-8", newline="") as f:
        sc_rows = parse(f.read())

    character = build_character(ch_rows, ch_rows[0])
    projectile = build_projectile(pr_rows, pr_rows[0])
    card = build_card(sc_rows, sc_rows[0])

    instance_id = sum(1 for r in sc_rows[1:] if r and r[0]) + 1
    print("OneMusketeer instance id:", instance_id, "global:", 26000000 + instance_id)

    patch_server(character, projectile, card)
    patch_client(character, projectile, card)


if __name__ == "__main__":
    main()
