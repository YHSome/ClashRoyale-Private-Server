#!/usr/bin/env python3
"""界地狱飞龙 (Boundary Inferno Dragon) — InfernoDragon 克隆。

特性：攻击伤害归 0；每次攻击在身后很远的地方发射火箭（把火箭设为攻击的基础
投射物 Projectile=BoundaryRocket + ProjectileStartRadius=-20000；地狱飞龙原本是
直接伤害光束、没有投射物，界炸弹兵的 MultipleProjectiles 机制对它不生效）。

  * spells_characters.csv  BoundaryInfernoDragon 卡（克隆 InfernoDragon）
  * characters.csv         BoundaryInfernoDragon 角色（克隆 InfernoDragon）
      Damage=0 / VariableDamage2=0（攻击无伤害）
      Projectile=BoundaryLogProjectile, ProjectileStartRadius=-20000（每次攻击从远处
      以随机角度发射复仇滚木）
  * projectiles.csv       BoundaryLogProjectile（克隆 LogProjectile + RandomAngle=360）
  * texts.csv：TID_SPELL_BOUNDARY_INFERNO_DRAGON（CN: 界地狱飞龙）

客户端必须包含卡组中所有自定义卡，故从 mod24（含一条龙服务/界电磁炮/界气球兵）构建。
"""

import csv
import io
import lzma
import os
import zipfile

ROOT = r"C:\Users\YHSome\Projects\OtherProjects\ClashRoyal"
SERVER_CSV = os.path.join(ROOT, "HashRoyale", "app", "GameAssets", "csv_logic")
SRC_APK = os.path.join(ROOT, "clients", "retroroyale-1.9.2-phone-mod31-nogadget.apk")
OUT_APK = os.path.join(ROOT, "clients", "retroroyale-1.9.2-phone-mod32-nogadget-unsigned.apk")


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


def build_card(sc_rows, sc_h):
    card = clone(sc_rows, "InfernoDragon")
    setf(card, sc_h, "Name", "BoundaryInfernoDragon")
    setf(card, sc_h, "SummonCharacter", "BoundaryInfernoDragon")
    setf(card, sc_h, "TID", "TID_SPELL_BOUNDARY_INFERNO_DRAGON")
    setf(card, sc_h, "TID_INFO", "TID_SPELL_INFO_BOUNDARY_INFERNO_DRAGON")
    return card


def build_character(ch_rows, ch_h):
    c = clone(ch_rows, "InfernoDragon")
    setf(c, ch_h, "Name", "BoundaryInfernoDragon")
    setf(c, ch_h, "Damage", "0")
    setf(c, ch_h, "VariableDamage2", "0")
    setf(c, ch_h, "Projectile", "BoundaryLogProjectileAir")
    setf(c, ch_h, "CustomFirstProjectile", "")
    setf(c, ch_h, "MultipleProjectiles", "")
    setf(c, ch_h, "ProjectileStartRadius", "-20000")
    setf(c, ch_h, "TID", "TID_CHARACTER_BOUNDARY_INFERNO_DRAGON")
    return c


def build_projectile(pr_rows, pr_h):
    p = clone(pr_rows, "LogProjectile")
    setf(p, pr_h, "Name", "BoundaryLogProjectileAir")
    setf(p, pr_h, "RandomAngle", "360")
    setf(p, pr_h, "RandomDistance", "")
    setf(p, pr_h, "Homing", "true")
    setf(p, pr_h, "AoeToAir", "true")
    setf(p, pr_h, "SpawnProjectile", "BoundaryLogProjectileRollingAir")
    return p


def build_rolling_air(pr_rows, pr_h):
    p = clone(pr_rows, "LogProjectileRolling")
    setf(p, pr_h, "Name", "BoundaryLogProjectileRollingAir")
    setf(p, pr_h, "AoeToAir", "true")
    return p


def build_texts(text: str):
    rows = parse(text)
    t_header = rows[0]
    if "TID_SPELL_BOUNDARY_INFERNO_DRAGON" in text:
        return text

    def clone_text(tid):
        r = clone(rows, "TID_SPELL_INFERNO_DRAGON")
        r[0] = tid
        return r

    name_row = clone_text("TID_SPELL_BOUNDARY_INFERNO_DRAGON")
    name_row[t_header.index("EN")] = "Boundary Inferno Dragon"
    name_row[t_header.index("CN")] = "界地狱飞龙"
    name_row[t_header.index("CNT")] = "界地獄飛龍"

    info_row = clone_text("TID_SPELL_INFO_BOUNDARY_INFERNO_DRAGON")
    info_row[t_header.index("EN")] = "Deals no direct damage; fires a rocket from far behind on each attack."
    info_row[t_header.index("CN")] = "攻击无伤害，每次攻击从身后远处发射火箭。"
    info_row[t_header.index("CNT")] = "攻擊無傷害，每次攻擊從身後遠處發射火箭。"
    return upsert(upsert(text, name_row), info_row)


def patch_server(card, character, projectile, rolling):
    for fn, row in (
        ("spells_characters.csv", card),
        ("characters.csv", character),
        ("projectiles.csv", projectile),
        ("projectiles.csv", rolling),
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


def patch_client(card, character, projectile, rolling):
    zin = zipfile.ZipFile(SRC_APK)
    out = {}
    file_text = {}
    for entry, row in (
        ("assets/csv_logic/spells_characters.csv", card),
        ("assets/csv_logic/characters.csv", character),
        ("assets/csv_logic/projectiles.csv", projectile),
        ("assets/csv_logic/projectiles.csv", rolling),
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
    with open(os.path.join(SERVER_CSV, "spells_characters.csv"), encoding="utf-8", newline="") as f:
        sc_rows = parse(f.read())
    with open(os.path.join(SERVER_CSV, "characters.csv"), encoding="utf-8", newline="") as f:
        ch_rows = parse(f.read())
    card = build_card(sc_rows, sc_rows[0])
    character = build_character(ch_rows, ch_rows[0])
    with open(os.path.join(SERVER_CSV, "projectiles.csv"), encoding="utf-8", newline="") as f:
        pr_rows = parse(f.read())
    projectile = build_projectile(pr_rows, pr_rows[0])
    rolling = build_rolling_air(pr_rows, pr_rows[0])
    char_idx = sum(1 for r in ch_rows[1:] if r and r[0])
    print("BoundaryInfernoDragon character row index (append):", char_idx)
    patch_server(card, character, projectile, rolling)
    patch_client(card, character, projectile, rolling)


if __name__ == "__main__":
    main()
