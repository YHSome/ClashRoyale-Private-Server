#!/usr/bin/env python3
"""界气球兵 (Boundary Balloon) — Balloon 克隆 + Assassin（幻影刺客）突刺特性。

  * spells_characters.csv  BoundaryBalloon 卡（克隆 Balloon）
  * characters.csv         BoundaryBalloon 角色（克隆 Balloon + 复制 Assassin 突刺字段）
  * texts.csv：TID_SPELL_BOUNDARY_BALLOON（CN: 界气球兵）

注意：客户端必须包含卡组中所有自定义卡（OneStopService、BoundaryZapMachine），
故从 mod19（含两者）构建。
"""

import csv
import io
import lzma
import os
import zipfile

ROOT = r"C:\Users\YHSome\Projects\OtherProjects\ClashRoyal"
SERVER_CSV = os.path.join(ROOT, "HashRoyale", "app", "GameAssets", "csv_logic")
SRC_APK = os.path.join(ROOT, "clients", "retroroyale-1.9.2-phone-mod19-nogadget.apk")
OUT_APK = os.path.join(ROOT, "clients", "retroroyale-1.9.2-phone-mod22-nogadget-unsigned.apk")


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


DASH_FIELDS = {
    "DashImmuneToDamageTime": "100",
    "DashStartEffect": "assassin_dash_start",
    "DashEffect": "assassin_dashing",
    "DashCooldown": "800",
    "DashDamage": "320",
    "DashFilter": "filter_bandit_charge",
    "LandingEffect": "assassin_dash_end",
    "DashMinRange": "4000",
    "DashMaxRange": "30000",
    "JumpSpeed": "500",
}


def build_card(sc_rows, sc_h):
    card = clone(sc_rows, "Balloon")
    setf(card, sc_h, "Name", "BoundaryBalloon")
    setf(card, sc_h, "SummonCharacter", "BoundaryBalloon")
    setf(card, sc_h, "TID", "TID_SPELL_BOUNDARY_BALLOON")
    setf(card, sc_h, "TID_INFO", "TID_SPELL_INFO_BOUNDARY_BALLOON")
    return card


def build_character(ch_rows, ch_h):
    c = clone(ch_rows, "Balloon")
    setf(c, ch_h, "Name", "BoundaryBalloon")
    setf(c, ch_h, "SightRange", "30000")
    setf(c, ch_h, "TID", "TID_CHARACTER_BOUNDARY_BALLOON")
    for f, v in DASH_FIELDS.items():
        setf(c, ch_h, f, v)
    return c


def build_texts(text: str):
    rows = parse(text)
    t_header = rows[0]
    if "TID_SPELL_BOUNDARY_BALLOON" in text:
        return text

    def clone_text(tid):
        r = clone(rows, "TID_SPELL_BALLOON")
        r[0] = tid
        return r

    name_row = clone_text("TID_SPELL_BOUNDARY_BALLOON")
    name_row[t_header.index("EN")] = "Boundary Balloon"
    name_row[t_header.index("CN")] = "界气球兵"
    name_row[t_header.index("CNT")] = "界氣球兵"

    info_row = clone_text("TID_SPELL_INFO_BOUNDARY_BALLOON")
    info_row[t_header.index("EN")] = "A Balloon that dashes like the Bandit."
    info_row[t_header.index("CN")] = "拥有幻影刺客突刺特性的气球兵。"
    info_row[t_header.index("CNT")] = "擁有幻影刺客突刺特性的氣球兵。"
    return upsert(upsert(text, name_row), info_row)


def patch_server(card, character):
    for fn, row in (("spells_characters.csv", card), ("characters.csv", character)):
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


def patch_client(card, character):
    zin = zipfile.ZipFile(SRC_APK)
    out = {}
    file_text = {}
    for entry, row in (
        ("assets/csv_logic/spells_characters.csv", card),
        ("assets/csv_logic/characters.csv", character),
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
    char_idx = sum(1 for r in ch_rows[1:] if r and r[0])
    print("BoundaryBalloon character row index (append):", char_idx)
    patch_server(card, character)
    patch_client(card, character)


if __name__ == "__main__":
    main()
