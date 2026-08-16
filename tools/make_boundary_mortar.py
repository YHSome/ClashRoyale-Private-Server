#!/usr/bin/env python3
"""界迫击炮 (Boundary Mortar) — A/B 交替增殖版。

特性：
  * 玩家下的界迫击炮 A（BoundaryMortar，蓝色外观）发射 A 炮弹；
  * A 炮弹落地造成 108 范围伤害，并在落点生成一个容器 BoundaryMortarSpawner；
  * 容器 100ms 后死亡，在距离落点 3000（3 格）的随机方向生成界迫击炮 B
    （BoundaryMortar2，红色外观，作为“下一只”的视觉区分）；
  * B 发射 B 炮弹，落地后同样经容器在 3 格偏移处生成 A；
  * A↔B 无限交替增殖（不做数量上限，场地放满后自然停止）。

数据链（避免 A 召唤 A 的自我引用崩溃）：
  BoundaryMortar(A) --Projectile--> BoundaryMortarProjectile --SpawnCharacter--> BoundaryMortarSpawner
      --DeathSpawnCharacter--> BoundaryMortar2(B)
  BoundaryMortar2(B) --Projectile--> BoundaryMortarProjectile2 --SpawnCharacter--> BoundaryMortarSpawner2
      --DeathSpawnCharacter--> BoundaryMortar(A)

客户端必须包含卡组中所有自定义卡，故从 mod35（已含界迫击炮与全部自定义卡）构建。
"""

import csv
import io
import lzma
import os
import zipfile

ROOT = r"C:\Users\YHSome\Projects\OtherProjects\ClashRoyal"
SERVER_CSV = os.path.join(ROOT, "HashRoyale", "app", "GameAssets", "csv_logic")
SRC_APK = os.path.join(ROOT, "clients", "retroroyale-1.9.2-phone-mod35-nogadget.apk")
OUT_APK = os.path.join(ROOT, "clients", "retroroyale-1.9.2-phone-mod36-nogadget-unsigned.apk")

# 1 tile = 1000（迫击炮射程 11500 = 11.5 格）；3 格 = 3000
OFFSET_3_TILES = "3000"


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


def build_building_a(bd_rows, bd_h):
    b = clone(bd_rows, "Mortar")
    setf(b, bd_h, "Name", "BoundaryMortar")
    setf(b, bd_h, "Projectile", "BoundaryMortarProjectile")
    setf(b, bd_h, "TID", "TID_BUILDING_BOUNDARY_MORTAR")
    return b


def build_building_b(bd_rows, bd_h):
    b = clone(bd_rows, "Mortar")
    setf(b, bd_h, "Name", "BoundaryMortar2")
    setf(b, bd_h, "Projectile", "BoundaryMortarProjectile2")
    # 用敌方外观渲染，肉眼区分 A/B
    setf(b, bd_h, "BlueExportName", "building_mortar1_enemy")
    setf(b, bd_h, "RedExportName", "building_mortar1_enemy")
    setf(b, bd_h, "TID", "TID_BUILDING_BOUNDARY_MORTAR")
    return b


def build_container(bd_rows, bd_h, name, spawns):
    c = clone(bd_rows, "OneStopBarrelSpawner")
    setf(c, bd_h, "Name", name)
    setf(c, bd_h, "DeployTime", "100")
    # 清掉飞桶容器的产兵/狂暴逻辑，只保留死亡生成
    setf(c, bd_h, "SpawnStartTime", "")
    setf(c, bd_h, "SpawnInterval", "")
    setf(c, bd_h, "SpawnNumber", "")
    setf(c, bd_h, "SpawnLimit", "")
    setf(c, bd_h, "SpawnPauseTime", "")
    setf(c, bd_h, "SpawnCharacter", "")
    setf(c, bd_h, "SpawnRadius", "")
    setf(c, bd_h, "DeathSpawnCount", "1")
    setf(c, bd_h, "DeathSpawnCharacter", spawns)
    setf(c, bd_h, "DeathSpawnRadius", OFFSET_3_TILES)
    setf(c, bd_h, "DeathSpawnMinRadius", OFFSET_3_TILES)
    setf(c, bd_h, "DeathSpawnDeployTime", "0")
    setf(c, bd_h, "DeathAreaEffect", "")
    return c


def build_projectile(pr_rows, pr_h, name, container):
    p = clone(pr_rows, "MortarProjectile")
    setf(p, pr_h, "Name", name)
    setf(p, pr_h, "SpawnCharacterLevelIndex", "1")
    setf(p, pr_h, "SpawnCharacterDeployTime", "0")
    setf(p, pr_h, "SpawnCharacter", container)
    setf(p, pr_h, "SpawnConstPriority", "TRUE")
    setf(p, pr_h, "SpawnCharacterCount", "1")
    return p


def build_texts(text: str):
    rows = parse(text)
    t_header = rows[0]
    if "TID_SPELL_BOUNDARY_MORTAR" in text:
        return text

    def clone_text(tid):
        r = clone(rows, "TID_SPELL_MORTAR")
        r[0] = tid
        return r

    name_row = clone_text("TID_SPELL_BOUNDARY_MORTAR")
    name_row[t_header.index("EN")] = "Boundary Mortar"
    name_row[t_header.index("CN")] = "界迫击炮"
    name_row[t_header.index("CNT")] = "界迫擊砲"

    info_row = clone_text("TID_SPELL_INFO_BOUNDARY_MORTAR")
    info_row[t_header.index("EN")] = "A mortar shell that summons another mortar at the landing point."
    info_row[t_header.index("CN")] = "炮弹落地后，在落点旁 3 格召唤界迫击炮，A/B 交替无限增殖。"
    info_row[t_header.index("CNT")] = "砲彈落地後，在落點旁 3 格召喚界迫擊砲，A/B 交替無限增殖。"
    return upsert(upsert(text, name_row), info_row)


def patch_server(card, b_a, b_b, c_ab, c_ba, p_a, p_b):
    for fn, rows, kind in (
        ("spells_buildings.csv", card, "card"),
        ("buildings.csv", b_a, "b_a"),
        ("buildings.csv", b_b, "b_b"),
        ("buildings.csv", c_ab, "c_ab"),
        ("buildings.csv", c_ba, "c_ba"),
        ("projectiles.csv", p_a, "p_a"),
        ("projectiles.csv", p_b, "p_b"),
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

    # 清理不再使用的旧行
    for fn, name in (
        ("buildings.csv", "BoundaryMortarSummoned"),
        ("projectiles.csv", "BoundaryMortarShell"),
    ):
        path = os.path.join(SERVER_CSV, fn)
        with open(path, "r", encoding="utf-8", newline="") as f:
            text = f.read()
        data = remove_row(text, name)
        if data != text:
            with open(path, "w", encoding="utf-8", newline="") as f:
                f.write(data)
            print("removed server", fn, name)


def patch_client(card, b_a, b_b, c_ab, c_ba, p_a, p_b):
    zin = zipfile.ZipFile(SRC_APK)
    out = {}
    file_text = {}
    for entry, row, kind in (
        ("assets/csv_logic/spells_buildings.csv", card, "card"),
        ("assets/csv_logic/buildings.csv", b_a, "b_a"),
        ("assets/csv_logic/buildings.csv", b_b, "b_b"),
        ("assets/csv_logic/buildings.csv", c_ab, "c_ab"),
        ("assets/csv_logic/buildings.csv", c_ba, "c_ba"),
        ("assets/csv_logic/projectiles.csv", p_a, "p_a"),
        ("assets/csv_logic/projectiles.csv", p_b, "p_b"),
    ):
        if entry not in file_text:
            file_text[entry] = sc_decompress(zin.read(entry)).decode("utf-8")
        file_text[entry] = upsert(file_text[entry], row)
        print("patched client", entry, kind)
    for entry, name in (
        ("assets/csv_logic/buildings.csv", "BoundaryMortarSummoned"),
        ("assets/csv_logic/projectiles.csv", "BoundaryMortarShell"),
    ):
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
    b_a = build_building_a(bd_rows, bd_rows[0])
    b_b = build_building_b(bd_rows, bd_rows[0])
    c_ab = build_container(bd_rows, bd_rows[0], "BoundaryMortarSpawner", "BoundaryMortar2")
    c_ba = build_container(bd_rows, bd_rows[0], "BoundaryMortarSpawner2", "BoundaryMortar")
    p_a = build_projectile(pr_rows, pr_rows[0], "BoundaryMortarProjectile", "BoundaryMortarSpawner")
    p_b = build_projectile(pr_rows, pr_rows[0], "BoundaryMortarProjectile2", "BoundaryMortarSpawner2")

    patch_server(card, b_a, b_b, c_ab, c_ba, p_a, p_b)
    patch_client(card, b_a, b_b, c_ab, c_ba, p_a, p_b)


if __name__ == "__main__":
    main()
