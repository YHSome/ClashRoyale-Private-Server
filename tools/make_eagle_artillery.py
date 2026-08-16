#!/usr/bin/env python3
"""天鹰火炮 (EagleArtillery) —— 类似 CoC 天鹰火炮的迫击炮。

规格：攻击间隔 10 秒；发射一个无碰撞的引导探针（7 秒部署倒计时，跟随最近单位）；
开火时从身后很远处打出 3 发火箭，接近 7 秒时落在部署位置。

数据实现（1.9.2 无“同步倒计时/预判落点”机制，取最接近）：
  * buildings.csv   EagleArtillery（迫击炮克隆，HitSpeed/LoadTime=10000，
    MultipleProjectiles=4：第 1 发=EagleProbe 探针，后 3 发=EagleRocket 火箭；
    ProjectileStartRadius=-20000 让弹体从身后很远处出发）
  * projectiles.csv EagleProbe（Homing=true 跟随目标、慢速约 7 秒到达、无伤害）
  * projectiles.csv EagleRocket（RocketSpell 克隆，700 伤害）
  * spells_buildings.csv 天鹰火炮卡（Epic 8 费）
  * texts.csv TID_SPELL_EAGLE_ARTILLERY（CN: 天鹰火炮）

注意：火箭与探针同时发射，火箭按自身速度到达；“恰好 7 秒同点”需要
后续用 Frida 精确同步（可作为研究项），当前为数据近似。
"""

import csv
import io
import lzma
import os
import zipfile

ROOT = r"C:\Users\YHSome\Projects\OtherProjects\ClashRoyal"
SERVER_CSV = os.path.join(ROOT, "HashRoyale", "app", "GameAssets", "csv_logic")
SRC_APK = os.path.join(ROOT, "clients", "retroroyale-1.9.2-phone-mod53-gadget.apk")
OUT_APK = os.path.join(ROOT, "clients", "retroroyale-1.9.2-phone-mod54-gadget-unsigned.apk")


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


def build_building(bd_rows, bd_h):
    b = clone(bd_rows, "Mortar")
    setf(b, bd_h, "Name", "EagleArtillery")
    setf(b, bd_h, "HitSpeed", "10000")
    setf(b, bd_h, "LoadTime", "10000")
    setf(b, bd_h, "Projectile", "EagleRocket")
    setf(b, bd_h, "CustomFirstProjectile", "EagleProbe")
    setf(b, bd_h, "MultipleProjectiles", "4")
    setf(b, bd_h, "ProjectileStartRadius", "-20000")
    setf(b, bd_h, "TID", "TID_BUILDING_EAGLE_ARTILLERY")
    return b


def build_probe(pr_rows, pr_h):
    p = clone(pr_rows, "MortarProjectile")
    setf(p, pr_h, "Name", "EagleProbe")
    setf(p, pr_h, "Speed", "80")
    setf(p, pr_h, "Damage", "0")
    setf(p, pr_h, "Radius", "100")
    setf(p, pr_h, "Homing", "true")
    setf(p, pr_h, "OnlyEnemies", "true")
    setf(p, pr_h, "AoeToGround", "true")
    return p


def build_rocket(pr_rows, pr_h):
    p = clone(pr_rows, "RocketSpell")
    setf(p, pr_h, "Name", "EagleRocket")
    return p


def build_card(sb_rows, sb_h):
    card = clone(sb_rows, "Mortar")
    setf(card, sb_h, "Name", "EagleArtillery")
    setf(card, sb_h, "Rarity", "Epic")
    setf(card, sb_h, "ManaCost", "8")
    setf(card, sb_h, "SummonCharacter", "EagleArtillery")
    setf(card, sb_h, "TID", "TID_SPELL_EAGLE_ARTILLERY")
    setf(card, sb_h, "TID_INFO", "TID_SPELL_INFO_EAGLE_ARTILLERY")
    return card


def build_texts(text: str):
    rows = parse(text)
    t_header = rows[0]

    def clone_text(tid):
        r = clone(rows, "TID_SPELL_MORTAR")
        r[0] = tid
        return r

    name_row = clone_text("TID_SPELL_EAGLE_ARTILLERY")
    name_row[t_header.index("EN")] = "Eagle Artillery"
    name_row[t_header.index("CN")] = "天鹰火炮"
    name_row[t_header.index("CNT")] = "天鷹火炮"

    info_row = clone_text("TID_SPELL_INFO_EAGLE_ARTILLERY")
    info_row[t_header.index("EN")] = "Every 10s launches a homing probe (7s countdown) and 3 rockets."
    info_row[t_header.index("CN")] = "每 10 秒发射引导探针（7 秒部署倒计时）并同时打出 3 发火箭。"
    info_row[t_header.index("CNT")] = "每 10 秒發射引導探針（7 秒部署倒計時）並同時打出 3 發火箭。"
    return upsert(upsert(text, name_row), info_row)


def patch_server(building, probe, rocket, card):
    for fn, rows, kind in (
        ("buildings.csv", building, "building"),
        ("projectiles.csv", probe, "probe"),
        ("projectiles.csv", rocket, "rocket"),
        ("spells_buildings.csv", card, "card"),
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


def patch_client(building, probe, rocket, card):
    zin = zipfile.ZipFile(SRC_APK)
    out = {}
    file_text = {}
    for entry, row, kind in (
        ("assets/csv_logic/buildings.csv", building, "building"),
        ("assets/csv_logic/projectiles.csv", probe, "probe"),
        ("assets/csv_logic/projectiles.csv", rocket, "rocket"),
        ("assets/csv_logic/spells_buildings.csv", card, "card"),
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
    with open(os.path.join(SERVER_CSV, "buildings.csv"), encoding="utf-8", newline="") as f:
        bd_rows = parse(f.read())
    with open(os.path.join(SERVER_CSV, "projectiles.csv"), encoding="utf-8", newline="") as f:
        pr_rows = parse(f.read())
    with open(os.path.join(SERVER_CSV, "spells_buildings.csv"), encoding="utf-8", newline="") as f:
        sb_rows = parse(f.read())

    building = build_building(bd_rows, bd_rows[0])
    probe = build_probe(pr_rows, pr_rows[0])
    rocket = build_rocket(pr_rows, pr_rows[0])
    card = build_card(sb_rows, sb_rows[0])

    instance_id = sum(1 for r in sb_rows[1:] if r and r[0]) + 1
    print("EagleArtillery spells_buildings instance id:", instance_id, "global:", 27000000 + instance_id)

    patch_server(building, probe, rocket, card)
    patch_client(building, probe, rocket, card)


if __name__ == "__main__":
    main()
