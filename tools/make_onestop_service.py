#!/usr/bin/env python3
"""一条龙服务 (OneStopService) — 完全套用原版哥布林飞桶逻辑。

原版飞桶（1.9.2 数据）：
  spells_other.csv  GoblinBarrel  法术卡：Projectile=GoblinBarrelSpell
  projectiles.csv   GoblinBarrelSpell  投射物（sc/spell_goblin_barrel.sc 真桶模型）
      命中时 SpawnCharacter=Goblin x3, SpawnCharacterDeployTime=1200

本卡（v5）：
  spells_other.csv  OneStopService（克隆 GoblinBarrel）
      Projectile = OneStopBarrelSpell，OnlyEnemies，Effect=goblin_barrel_spawn
  projectiles.csv  OneStopBarrelSpell（克隆 GoblinBarrelSpell，真桶模型）
      命中时 SpawnCharacter = OneStopBarrelSpawner x1（隐形容器）
  buildings.csv    OneStopBarrelSpawner（克隆 AwakenedIcePulse 隐形容器）
      SpawnCharacter=AngryBarbarian x2（落地瞬间刷出，SpawnStartTime=0）
      DeployTime=100 引信 -> 死亡
      DeathSpawnCharacter=FireSpirits x3（引信结束爆出）
      DeathAreaEffect=BarbarianRage（狂暴，与狂暴樵夫同款）
  texts.csv：TID_SPELL_ONE_STOP_SERVICE（CN: 一条龙服务）

客户端卡组条目：spells_other classId=28，行号见运行输出（追加后 = 18）。
"""

import csv
import io
import lzma
import os
import zipfile

ROOT = r"C:\Users\YHSome\Projects\OtherProjects\ClashRoyal"
SERVER_CSV = os.path.join(ROOT, "HashRoyale", "app", "GameAssets", "csv_logic")
SRC_APK = os.path.join(ROOT, "clients", "retroroyale-1.9.2-phone-mod6.apk")
OUT_APK = os.path.join(ROOT, "clients", "retroroyale-1.9.2-phone-mod15-nogadget-unsigned.apk")


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


def build_card(so_rows, so_h):
    card = clone(so_rows, "GoblinBarrel")
    setf(card, so_h, "Name", "OneStopService")
    setf(card, so_h, "IconFile", "goblin_barrel")
    setf(card, so_h, "UnlockArena", "Arena7")
    setf(card, so_h, "Rarity", "Epic")
    setf(card, so_h, "ManaCost", "6")
    setf(card, so_h, "Projectile", "OneStopBarrelSpell")
    setf(card, so_h, "Effect", "goblin_barrel_spawn")
    setf(card, so_h, "OnlyEnemies", "true")
    setf(card, so_h, "CastSound", "sound_goblin_barrel_spawn")
    setf(card, so_h, "TID", "TID_SPELL_ONE_STOP_SERVICE")
    setf(card, so_h, "TID_INFO", "TID_SPELL_INFO_ONE_STOP_SERVICE")
    return card


def build_projectile(pr_rows, pr_h):
    p = clone(pr_rows, "GoblinBarrelSpell")
    setf(p, pr_h, "Name", "OneStopBarrelSpell")
    setf(p, pr_h, "SpawnCharacterLevelIndex", "5")
    setf(p, pr_h, "SpawnCharacterDeployTime", "1200")
    setf(p, pr_h, "SpawnCharacter", "OneStopBarrelSpawner")
    setf(p, pr_h, "SpawnConstPriority", "TRUE")
    setf(p, pr_h, "SpawnCharacterCount", "1")
    return p


def build_container(bd_rows, bd_h):
    b = clone(bd_rows, "AwakenedIcePulse")
    setf(b, bd_h, "Name", "OneStopBarrelSpawner")
    setf(b, bd_h, "DeployTime", "100")
    setf(b, bd_h, "DeathDamageRadius", "")
    setf(b, bd_h, "DeathDamage", "")
    setf(b, bd_h, "DeathEffect", "")
    setf(b, bd_h, "SpawnStartTime", "0")
    setf(b, bd_h, "SpawnInterval", "1")
    setf(b, bd_h, "SpawnNumber", "2")
    setf(b, bd_h, "SpawnLimit", "2")
    setf(b, bd_h, "SpawnPauseTime", "1")
    setf(b, bd_h, "SpawnCharacter", "AngryBarbarian")
    setf(b, bd_h, "SpawnRadius", "350")
    setf(b, bd_h, "DeathSpawnCount", "3")
    setf(b, bd_h, "DeathSpawnCharacter", "FireSpirits")
    setf(b, bd_h, "DeathSpawnRadius", "400")
    setf(b, bd_h, "DeathSpawnMinRadius", "150")
    setf(b, bd_h, "DeathSpawnDeployTime", "0")
    setf(b, bd_h, "DeathSpawnPushback", "")
    setf(b, bd_h, "DeathAreaEffect", "BarbarianRage")
    return b


def build_texts(text: str):
    rows = parse(text)
    t_header = rows[0]
    if "TID_SPELL_ONE_STOP_SERVICE" in text:
        return text

    def clone_text(tid):
        r = clone(rows, "TID_SPELL_GOBLIN_BARREL")
        r[0] = tid
        return r

    name_row = clone_text("TID_SPELL_ONE_STOP_SERVICE")
    name_row[t_header.index("EN")] = "One-Stop Service"
    name_row[t_header.index("CN")] = "一条龙服务"
    name_row[t_header.index("CNT")] = "一條龍服務"

    info_row = clone_text("TID_SPELL_INFO_ONE_STOP_SERVICE")
    info_row[t_header.index("EN")] = "A flying barrel that bursts into 2 Elite Barbarians, 3 Fire Spirits and Rage."
    info_row[t_header.index("CN")] = "飞桶落地爆出两只野蛮人精锐、三只烈焰精灵，并施加狂暴法术。"
    info_row[t_header.index("CNT")] = "飛桶落地爆出兩隻野蠻人精銳、三隻烈焰精靈，並施加狂暴法術。"
    return upsert(upsert(text, name_row), info_row)


def patch_server(card, projectile, container):
    for fn, row in (
        ("spells_other.csv", card),
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


def patch_client(card, projectile, container):
    zin = zipfile.ZipFile(SRC_APK)
    out = {}
    for entry, row in (
        ("assets/csv_logic/spells_other.csv", card),
        ("assets/csv_logic/projectiles.csv", projectile),
        ("assets/csv_logic/buildings.csv", container),
    ):
        text = sc_decompress(zin.read(entry)).decode("utf-8")
        data = upsert(text, row)
        out[entry] = sc_compress(data.encode("utf-8"))
        print("patched client", entry)

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
    with open(os.path.join(SERVER_CSV, "spells_other.csv"), encoding="utf-8", newline="") as f:
        so_rows = parse(f.read())
    with open(os.path.join(SERVER_CSV, "projectiles.csv"), encoding="utf-8", newline="") as f:
        pr_rows = parse(f.read())
    with open(os.path.join(SERVER_CSV, "buildings.csv"), encoding="utf-8", newline="") as f:
        bd_rows = parse(f.read())
    card = build_card(so_rows, so_rows[0])
    projectile = build_projectile(pr_rows, pr_rows[0])
    container = build_container(bd_rows, bd_rows[0])
    # report the card row index (for the collection entry)
    idx = sum(1 for r in so_rows[1:] if r and r[0])  # 0-based among data rows before append
    print("OneStopService spells_other row index (append):", idx)
    patch_server(card, projectile, container)
    patch_client(card, projectile, container)


if __name__ == "__main__":
    main()
