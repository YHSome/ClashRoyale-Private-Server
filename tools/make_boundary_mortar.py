#!/usr/bin/env python3
"""界迫击炮 (Boundary Mortar) — 快速乱射骷髅版。

效果：
  * 攻击时间 0.3 秒（HitSpeed=LoadTime=300ms）；
  * 每次攻击发射一枚迫击炮弹，落点随机方向偏移 3000（3 格）——
    Homing=true + RandomAngle=360 + MinDistance=3000（界地狱龙滚木同款已验证机制）；
  * 炮弹落地造成 108 伤害，并在落点生成 1 只小骷髅（Skeleton）
    —— 投射物 SpawnCharacter=角色，哥布林飞桶同款已验证路径。

数据图无环（骷髅是角色叶子节点），加载期安全。
"""

import csv
import io
import lzma
import os
import zipfile

ROOT = r"C:\Users\YHSome\Projects\OtherProjects\ClashRoyal"
SERVER_CSV = os.path.join(ROOT, "HashRoyale", "app", "GameAssets", "csv_logic")
SRC_APK = os.path.join(ROOT, "clients", "retroroyale-1.9.2-phone-mod41-nogadget.apk")
OUT_APK = os.path.join(ROOT, "clients", "retroroyale-1.9.2-phone-mod42-nogadget-unsigned.apk")

ATTACK_MS = "300"
RANDOM_OFFSET = "3000"


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


def build_card(sb_rows, sb_h):
    card = clone(sb_rows, "Mortar")
    setf(card, sb_h, "Name", "BoundaryMortar")
    setf(card, sb_h, "SummonCharacter", "BoundaryMortar")
    setf(card, sb_h, "TID", "TID_SPELL_BOUNDARY_MORTAR")
    setf(card, sb_h, "TID_INFO", "TID_SPELL_INFO_BOUNDARY_MORTAR")
    return card


def build_building(bd_rows, bd_h):
    b = clone(bd_rows, "Mortar")
    setf(b, bd_h, "Name", "BoundaryMortar")
    setf(b, bd_h, "HitSpeed", ATTACK_MS)
    setf(b, bd_h, "LoadTime", ATTACK_MS)
    setf(b, bd_h, "Projectile", "BoundaryMortarProjectile")
    setf(b, bd_h, "TID", "TID_BUILDING_BOUNDARY_MORTAR")
    return b


def build_projectile(pr_rows, pr_h):
    p = clone(pr_rows, "MortarProjectile")
    setf(p, pr_h, "Name", "BoundaryMortarProjectile")
    setf(p, pr_h, "Homing", "true")
    setf(p, pr_h, "RandomAngle", "360")
    setf(p, pr_h, "MinDistance", RANDOM_OFFSET)
    setf(p, pr_h, "SpawnCharacterLevelIndex", "1")
    setf(p, pr_h, "SpawnCharacterDeployTime", "0")
    setf(p, pr_h, "SpawnCharacter", "Skeleton")
    setf(p, pr_h, "SpawnConstPriority", "TRUE")
    setf(p, pr_h, "SpawnCharacterCount", "1")
    return p


def build_texts(text: str):
    rows = parse(text)
    t_header = rows[0]

    def clone_text(tid):
        r = clone(rows, "TID_SPELL_MORTAR")
        r[0] = tid
        return r

    name_row = clone_text("TID_SPELL_BOUNDARY_MORTAR")
    name_row[t_header.index("EN")] = "Boundary Mortar"
    name_row[t_header.index("CN")] = "界迫击炮"
    name_row[t_header.index("CNT")] = "界迫擊砲"

    info_row = clone_text("TID_SPELL_INFO_BOUNDARY_MORTAR")
    info_row[t_header.index("EN")] = "Fast-firing mortar; shells land at random directions and spawn a Skeleton."
    info_row[t_header.index("CN")] = "0.3秒快速攻击，随机方向发射炮弹，落点生成一只小骷髅。"
    info_row[t_header.index("CNT")] = "0.3秒快速攻擊，隨機方向發射砲彈，落點生成一隻小骷髏。"
    return upsert(upsert(text, name_row), info_row)


def patch_server(card, building, projectile):
    for fn, rows, kind in (
        ("spells_buildings.csv", card, "card"),
        ("buildings.csv", building, "building"),
        ("projectiles.csv", projectile, "projectile"),
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

    for fn, name in (
        ("buildings.csv", "BoundaryMortar2"),
        ("buildings.csv", "BoundaryMortarSpawner2"),
        ("projectiles.csv", "BoundaryMortarProjectile2"),
        ("projectiles.csv", "BoundaryMortarProbe2"),
        ("area_effect_objects.csv", "BoundaryMortarSummonAOE"),
    ):
        path = os.path.join(SERVER_CSV, fn)
        with open(path, "r", encoding="utf-8", newline="") as f:
            text = f.read()
        data = remove_row(text, name)
        if data != text:
            with open(path, "w", encoding="utf-8", newline="") as f:
                f.write(data)
            print("removed server", fn, name)


def patch_client(card, building, projectile):
    zin = zipfile.ZipFile(SRC_APK)
    out = {}
    file_text = {}
    for entry, row, kind in (
        ("assets/csv_logic/spells_buildings.csv", card, "card"),
        ("assets/csv_logic/buildings.csv", building, "building"),
        ("assets/csv_logic/projectiles.csv", projectile, "projectile"),
    ):
        if entry not in file_text:
            file_text[entry] = sc_decompress(zin.read(entry)).decode("utf-8")
        file_text[entry] = upsert(file_text[entry], row)
        print("patched client", entry, kind)
    for entry, name in (
        ("assets/csv_logic/buildings.csv", "BoundaryMortar2"),
        ("assets/csv_logic/buildings.csv", "BoundaryMortarSpawner2"),
        ("assets/csv_logic/projectiles.csv", "BoundaryMortarProjectile2"),
        ("assets/csv_logic/projectiles.csv", "BoundaryMortarProbe2"),
        ("assets/csv_logic/area_effect_objects.csv", "BoundaryMortarSummonAOE"),
    ):
        if entry not in file_text:
            file_text[entry] = sc_decompress(zin.read(entry)).decode("utf-8")
        file_text[entry] = remove_row(file_text[entry], name)
        print("removed client", entry, name)
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
    with open(os.path.join(SERVER_CSV, "spells_buildings.csv"), encoding="utf-8", newline="") as f:
        sb_rows = parse(f.read())
    with open(os.path.join(SERVER_CSV, "buildings.csv"), encoding="utf-8", newline="") as f:
        bd_rows = parse(f.read())
    with open(os.path.join(SERVER_CSV, "projectiles.csv"), encoding="utf-8", newline="") as f:
        pr_rows = parse(f.read())

    card = build_card(sb_rows, sb_rows[0])
    building = build_building(bd_rows, bd_rows[0])
    projectile = build_projectile(pr_rows, pr_rows[0])

    patch_server(card, building, projectile)
    patch_client(card, building, projectile)


if __name__ == "__main__":
    main()
