#!/usr/bin/env python3
"""界地狱塔 (Boundary Inferno Tower) — InfernoTower 克隆。

特性：每次攻击向随机位置发射火球（火球 = FireballSpell 克隆 +
RandomAngle=360 + RandomDistance=4000，落点随机；塔本身无直接伤害）。

  * spells_buildings.csv  BoundaryInfernoTower 卡（克隆 InfernoTower）
  * buildings.csv         BoundaryInfernoTower 建筑（克隆 InfernoTower）
      Projectile=BoundaryFireballProjectile, Damage=0（攻击=随机火球）
  * projectiles.csv       BoundaryFireballProjectile（克隆 FireballSpell + 随机角度/距离）
  * texts.csv：TID_SPELL_BOUNDARY_INFERNO_TOWER（CN: 界地狱塔）

客户端必须包含卡组中所有自定义卡，故从 mod30（含全部 5 张自定义卡）构建。
"""

import csv
import io
import lzma
import os
import zipfile

ROOT = r"C:\Users\YHSome\Projects\OtherProjects\ClashRoyal"
SERVER_CSV = os.path.join(ROOT, "HashRoyale", "app", "GameAssets", "csv_logic")
SRC_APK = os.path.join(ROOT, "clients", "retroroyale-1.9.2-phone-mod30-nogadget.apk")
OUT_APK = os.path.join(ROOT, "clients", "retroroyale-1.9.2-phone-mod31-nogadget-unsigned.apk")


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


def build_card(sb_rows, sb_h):
    card = clone(sb_rows, "InfernoTower")
    setf(card, sb_h, "Name", "BoundaryInfernoTower")
    setf(card, sb_h, "SummonCharacter", "BoundaryInfernoTower")
    setf(card, sb_h, "TID", "TID_SPELL_BOUNDARY_INFERNO_TOWER")
    setf(card, sb_h, "TID_INFO", "TID_SPELL_INFO_BOUNDARY_INFERNO_TOWER")
    return card


def build_building(bd_rows, bd_h):
    b = clone(bd_rows, "InfernoTower")
    setf(b, bd_h, "Name", "BoundaryInfernoTower")
    setf(b, bd_h, "Projectile", "BoundaryFireballProjectile")
    setf(b, bd_h, "Damage", "0")
    setf(b, bd_h, "VariableDamage2", "0")
    setf(b, bd_h, "TID", "TID_BUILDING_BOUNDARY_INFERNO_TOWER")
    return b


def build_projectile(pr_rows, pr_h):
    p = clone(pr_rows, "FireballSpell")
    setf(p, pr_h, "Name", "BoundaryFireballProjectile")
    setf(p, pr_h, "RandomAngle", "360")
    setf(p, pr_h, "RandomDistance", "4000")
    return p


def build_texts(text: str):
    rows = parse(text)
    t_header = rows[0]
    if "TID_SPELL_BOUNDARY_INFERNO_TOWER" in text:
        return text

    def clone_text(tid):
        r = clone(rows, "TID_SPELL_INFERNO")
        r[0] = tid
        return r

    name_row = clone_text("TID_SPELL_BOUNDARY_INFERNO_TOWER")
    name_row[t_header.index("EN")] = "Boundary Inferno Tower"
    name_row[t_header.index("CN")] = "界地狱塔"
    name_row[t_header.index("CNT")] = "界地獄塔"

    info_row = clone_text("TID_SPELL_INFO_BOUNDARY_INFERNO_TOWER")
    info_row[t_header.index("EN")] = "Fires a Fireball at a random position with every attack."
    info_row[t_header.index("CN")] = "每次攻击向随机位置发射火球。"
    info_row[t_header.index("CNT")] = "每次攻擊向隨機位置發射火球。"
    return upsert(upsert(text, name_row), info_row)


def patch_server(card, building, projectile):
    for fn, row in (
        ("spells_buildings.csv", card),
        ("buildings.csv", building),
        ("projectiles.csv", projectile),
    ):
        path = os.path.join(SERVER_CSV, fn)
        with open(path, "r", encoding="utf-8", newline="") as f:
            text = f.read()
        data = upsert(text, row)
        if data != text:
            with open(path, "w", encoding="utf-8", newline="") as f:
                f.write(data)
            print("patched server", fn)
        else:
            print("skip server", fn)


def patch_client(card, building, projectile):
    zin = zipfile.ZipFile(SRC_APK)
    out = {}
    file_text = {}
    for entry, row in (
        ("assets/csv_logic/spells_buildings.csv", card),
        ("assets/csv_logic/buildings.csv", building),
        ("assets/csv_logic/projectiles.csv", projectile),
    ):
        if entry not in file_text:
            file_text[entry] = sc_decompress(zin.read(entry)).decode("utf-8")
        file_text[entry] = upsert(file_text[entry], row)
        print("patched client", entry)
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
    bd_idx = sum(1 for r in sb_rows[1:] if r and r[0])
    print("BoundaryInfernoTower spells_buildings row index (append):", bd_idx)
    patch_server(card, building, projectile)
    patch_client(card, building, projectile)


if __name__ == "__main__":
    main()
