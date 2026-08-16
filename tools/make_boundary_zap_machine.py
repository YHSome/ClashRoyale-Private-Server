#!/usr/bin/env python3
"""界电磁炮 (Boundary Zap Machine) — ZapMachine 克隆。

特性：每次攻击命中目标后，在目标点召唤雷电法术 + 电击法术。

实现（复用已验证机制）：
  * spells_characters.csv  BoundaryZapMachine 卡（克隆 ZapMachine）
  * characters.csv         BoundaryZapMachine 角色（克隆 ZapMachine，攻击不变）
  * projectiles.csv        BoundaryZapMachineProjectile（克隆 ZapMachineProjectile）
      命中时 SpawnCharacter=BoundaryZapContainer x1
  * buildings.csv          BoundaryZapContainer（隐形容器，仅负责电击）
      DeployTime=100 引信 -> 死亡 -> DeathAreaEffect=Zap（电击）
  * 雷电：由子弹自身的 SpawnAreaEffectObject=Lightning 在命中时直接释放
  * texts.csv：TID_SPELL_BOUNDARY_ZAP_MACHINE（CN: 界电磁炮）
"""

import csv
import io
import lzma
import os
import zipfile

ROOT = r"C:\Users\YHSome\Projects\OtherProjects\ClashRoyal"
SERVER_CSV = os.path.join(ROOT, "HashRoyale", "app", "GameAssets", "csv_logic")
SRC_APK = os.path.join(ROOT, "clients", "retroroyale-1.9.2-phone-mod22-nogadget.apk")
OUT_APK = os.path.join(ROOT, "clients", "retroroyale-1.9.2-phone-mod24-nogadget-unsigned.apk")


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
    card = clone(sc_rows, "ZapMachine")
    setf(card, sc_h, "Name", "BoundaryZapMachine")
    setf(card, sc_h, "SummonCharacter", "BoundaryZapMachine")
    setf(card, sc_h, "TID", "TID_SPELL_BOUNDARY_ZAP_MACHINE")
    setf(card, sc_h, "TID_INFO", "TID_SPELL_INFO_BOUNDARY_ZAP_MACHINE")
    return card


def build_character(ch_rows, ch_h):
    c = clone(ch_rows, "ZapMachine")
    setf(c, ch_h, "Name", "BoundaryZapMachine")
    setf(c, ch_h, "Projectile", "BoundaryZapMachineProjectile")
    setf(c, ch_h, "LoadTime", "2250")
    setf(c, ch_h, "HitSpeed", "2500")
    setf(c, ch_h, "TID", "TID_CHARACTER_BOUNDARY_ZAP_MACHINE")
    return c


def build_projectile(pr_rows, pr_h):
    p = clone(pr_rows, "ZapMachineProjectile")
    setf(p, pr_h, "Name", "BoundaryZapMachineProjectile")
    setf(p, pr_h, "SpawnAreaEffectObject", "Lightning")
    setf(p, pr_h, "Damage", "0")
    setf(p, pr_h, "SpawnCharacterLevelIndex", "1")
    setf(p, pr_h, "SpawnCharacterDeployTime", "0")
    setf(p, pr_h, "SpawnCharacter", "BoundaryZapContainer")
    setf(p, pr_h, "SpawnConstPriority", "TRUE")
    setf(p, pr_h, "SpawnCharacterCount", "1")
    return p


def build_container(bd_rows, bd_h):
    b = clone(bd_rows, "AwakenedIcePulse")
    setf(b, bd_h, "Name", "BoundaryZapContainer")
    setf(b, bd_h, "DeployTime", "100")
    setf(b, bd_h, "DeathDamageRadius", "")
    setf(b, bd_h, "DeathDamage", "")
    setf(b, bd_h, "DeathEffect", "")
    setf(b, bd_h, "SpawnAreaObject", "")
    setf(b, bd_h, "SpawnAreaObjectLevelIndex", "")
    setf(b, bd_h, "DeathSpawnCount", "")
    setf(b, bd_h, "DeathSpawnCharacter", "")
    setf(b, bd_h, "DeathSpawnRadius", "")
    setf(b, bd_h, "DeathSpawnMinRadius", "")
    setf(b, bd_h, "DeathSpawnDeployTime", "")
    setf(b, bd_h, "DeathAreaEffect", "Zap")
    return b


def build_texts(text: str):
    rows = parse(text)
    t_header = rows[0]
    if "TID_SPELL_BOUNDARY_ZAP_MACHINE" in text:
        return text

    def clone_text(tid):
        r = clone(rows, "TID_SPELL_ZAPMACHINE")
        r[0] = tid
        return r

    name_row = clone_text("TID_SPELL_BOUNDARY_ZAP_MACHINE")
    name_row[t_header.index("EN")] = "Boundary Zap Machine"
    name_row[t_header.index("CN")] = "界电磁炮"
    name_row[t_header.index("CNT")] = "界電磁砲"

    info_row = clone_text("TID_SPELL_INFO_BOUNDARY_ZAP_MACHINE")
    info_row[t_header.index("EN")] = "After each attack, calls Lightning and Zap at the target."
    info_row[t_header.index("CN")] = "每次攻击后，在目标点召唤雷电与电击法术。"
    info_row[t_header.index("CNT")] = "每次攻擊後，在目標點召喚雷電與電擊法術。"
    return upsert(upsert(text, name_row), info_row)


def patch_server(card, character, projectile, container):
    for fn, row in (
        ("spells_characters.csv", card),
        ("characters.csv", character),
        ("projectiles.csv", projectile),
        ("buildings.csv", container),
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


def patch_client(card, character, projectile, container):
    zin = zipfile.ZipFile(SRC_APK)
    out = {}
    file_text = {}
    for entry, row in (
        ("assets/csv_logic/spells_characters.csv", card),
        ("assets/csv_logic/characters.csv", character),
        ("assets/csv_logic/projectiles.csv", projectile),
        ("assets/csv_logic/buildings.csv", container),
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
    with open(os.path.join(SERVER_CSV, "projectiles.csv"), encoding="utf-8", newline="") as f:
        pr_rows = parse(f.read())
    with open(os.path.join(SERVER_CSV, "buildings.csv"), encoding="utf-8", newline="") as f:
        bd_rows = parse(f.read())
    card = build_card(sc_rows, sc_rows[0])
    character = build_character(ch_rows, ch_rows[0])
    projectile = build_projectile(pr_rows, pr_rows[0])
    container = build_container(bd_rows, bd_rows[0])
    char_idx = sum(1 for r in ch_rows[1:] if r and r[0])
    print("BoundaryZapMachine character row index (append):", char_idx)
    patch_server(card, character, projectile, container)
    patch_client(card, character, projectile, container)


if __name__ == "__main__":
    main()
