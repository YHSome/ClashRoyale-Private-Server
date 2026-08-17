#!/usr/bin/env python3
"""一个火枪手 (OneMusketeer) — 火枪手克隆（纯数据版）。

效果：
  * 攻击距离与公主相同（Range=9000 / SightRange=9500）；
  * 每次攻击向目标发射一枚迫击炮弹（伤害 1）；
  * 炮弹落点召唤一个治疗法术（SpawnAreaEffectObject=Heal，半径 3000）。

实现（全部为已验证的纯数据路径）：
  * characters.csv OneMusketeer：克隆 Musketeer，射程改成公主值，
    Projectile=BoundaryOneMusketeerShell；
  * projectiles.csv BoundaryOneMusketeerShell：克隆 MortarProjectile，
    Damage=1 + SpawnAreaEffectObject=Heal（界电磁炮同款“落点放法术”字段）；
    不设 Homing/RandomAngle/RandomDistance，炮弹朝目标直射、落点放治疗。
  * 数据引用图无环（投射物→区域效果叶子节点），加载期安全。
"""

import csv
import io
import lzma
import os
import zipfile

ROOT = r"C:\Users\YHSome\Projects\OtherProjects\ClashRoyal"
SERVER_CSV = os.path.join(ROOT, "HashRoyale", "app", "GameAssets", "csv_logic")
SRC_APK = os.path.join(ROOT, "clients", "retroroyale-1.9.2-phone-mod55-gadget.apk")
OUT_APK = os.path.join(ROOT, "clients", "retroroyale-1.9.2-phone-mod56-gadget-unsigned.apk")


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
    # 公主：Range=9000 / SightRange=9500
    setf(c, ch_h, "SightRange", "9500")
    setf(c, ch_h, "Range", "9000")
    setf(c, ch_h, "Projectile", "BoundaryOneMusketeerShell")
    setf(c, ch_h, "MorphCharacter", "")
    setf(c, ch_h, "MorphTime", "")
    setf(c, ch_h, "MorphKeepTarget", "")
    setf(c, ch_h, "TID", "TID_SPELL_ONE_MUSKETEER")
    return c


def build_projectile(pr_rows, pr_h):
    p = clone(pr_rows, "MortarProjectile")
    setf(p, pr_h, "Name", "BoundaryOneMusketeerShell")
    setf(p, pr_h, "Speed", "600")
    setf(p, pr_h, "Gravity", "50")
    setf(p, pr_h, "Homing", "")
    setf(p, pr_h, "MinDistance", "")
    # 直射目标：不设 RandomAngle/RandomDistance
    setf(p, pr_h, "RandomAngle", "")
    setf(p, pr_h, "RandomDistance", "")
    # 伤害 1；落点施放治疗法术（界电磁炮同款 SpawnAreaEffectObject）
    setf(p, pr_h, "Damage", "1")
    setf(p, pr_h, "SpawnAreaEffectObject", "Heal")
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
    info_row[t_header.index("EN")] = "Princess-like range. Fires 1-damage mortar shells at targets; each shell casts Heal where it lands."
    info_row[t_header.index("CN")] = "射程与公主相同。向目标发射伤害 1 的迫击炮弹，落点施放治疗法术。"
    info_row[t_header.index("CNT")] = "射程與公主相同。向目標發射傷害 1 的迫擊砲彈，落點施放治療法術。"
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

    # 清理不再使用的旧变身阶段
    chars_path = os.path.join(SERVER_CSV, "characters.csv")
    with open(chars_path, "r", encoding="utf-8", newline="") as f:
        text = f.read()
    data = remove_row(text, "OneMusketeerNormal")
    if data != text:
        with open(chars_path, "w", encoding="utf-8", newline="") as f:
            f.write(data)
        print("removed server OneMusketeerNormal")

    # 清理旧的全图火箭投射物（新设计不再使用）
    pr_path = os.path.join(SERVER_CSV, "projectiles.csv")
    with open(pr_path, "r", encoding="utf-8", newline="") as f:
        text = f.read()
    data = remove_row(text, "BoundaryOneMusketeerRocket")
    if data != text:
        with open(pr_path, "w", encoding="utf-8", newline="") as f:
            f.write(data)
        print("removed server BoundaryOneMusketeerRocket")

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
    entry = "assets/csv_logic/projectiles.csv"
    file_text[entry] = remove_row(file_text[entry], "BoundaryOneMusketeerRocket")
    print("removed client BoundaryOneMusketeerRocket")
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
