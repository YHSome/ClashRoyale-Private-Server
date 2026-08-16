def rc4_stream(key: bytes, discard: int, data: bytes) -> bytes:
    s = list(range(256))
    j = 0
    for i in range(256):
        j = (j + s[i] + key[i % len(key)]) & 0xFF
        s[i], s[j] = s[j], s[i]
    i = j = 0
    out = bytearray()
    for _ in range(discard):
        i = (i + 1) & 0xFF
        j = (j + s[i]) & 0xFF
        s[i], s[j] = s[j], s[i]
    for b in data:
        i = (i + 1) & 0xFF
        j = (j + s[i]) & 0xFF
        s[i], s[j] = s[j], s[i]
        out.append(b ^ s[(s[i] + s[j]) & 0xFF])
    return bytes(out)


STATIC = b"fhsd6f86f67rt8fw78fw789we78r9789wer6re"
NONCE = b"nonce"

CASES = [
    (
        "A",
        bytes.fromhex("74794de40d62a03ac6f6e86a9815c6262aa12bedd518f883"),
        bytes.fromhex(
            "a7678906f923c4c1e5c3324558ed15be5ab7cd2eb02e8e3fe9de29a4fba47d36855854ad062f5a793c40a4fbe4d4a3aee71ee5f352a92e91ffd9a7920e8fd94b97bbbc9d777e49698b6a8c669591694f5256c9e26feaaf5ed1ce8ad01b1cfbad429ef5e2137f2c99069d3281aba559f5f7e8e7ab49377213e60e221601525c9080f6e61c39b0ebc96668819a0fba176440b2b51995e35caf193b5d378b312339b429567f9da60e430f240c8da6e507b32e4d35b7d41078e1b82b6f34ea93f96c9e7a3100d8fd95f3f9ced551b582c8f8a477627f068ebcde71626c2a24488567b880c9dccba88e69e90b64644d98db446f58159495d8840746f5b74e9e8de7"
        ),
    ),
    (
        "B",
        bytes(range(24)),
        bytes.fromhex(
            "f67d498a8b656a670a63b532e5367d5a31be8a755de6f34ac673a5f5fdf36a650eb1753b239eadd0a167ad61be663a37b43273e8e5944d594a7719061cca8cedef997b12e3631527f29545a25154dec7729e7e657d1b2d360fb3a93fef38bb96c7b340681c53f24da934f18879b5a8aec2a791530121de51f2efa55edf3580aeefc1e804d7908d4b5660d45a2d80d8cad199cc8284ee0cbc197baf166266a78246a6ce0ce30620ea76fa31f0a42cd504062ab696b646420556fd9853346de25fbac02ed305803f7dcb2347ab97b08a1418e0e775449dfe52df7614aa8859f05712c1d16daa892db60f96e9e440c15c3cb977ee71704e08a6a25b7d5d994cf5"
        ),
    ),
    (
        "F",
        NONCE,
        bytes.fromhex(
            "9efd367cd5795e2dd9df5ae3f448b150e54158ea272d119866576cc613ec5b496debde3cfd888e6b03be3acfc4f8a601bd52df365473bf3dff2624133f9bb8eda056a35c8b04bb8af3268c99a6e5c4cfc500039c8fb53a4c3b9b9ec31ff66cffe1dac7160f0d86e01874d79104385455796ec8d8b7c1fd037f1e68361224180601fd392089ed877d703b4a89c9a4c9aeb3e8c0eb043f7aa7677935f83aa65814495355b19be5bb1d89a04386e7f158ddc92f0a79739c97531e64bafb20717e3f9d4455f68167bb796ecc412f1e5f20b4a54c0dd2f74bead298d2aa4214c250e44fc81ab05457f68fdab783c3"
        ),
    ),
]


def looks_like_login(data: bytes) -> bool:
    if len(data) < 40:
        return False
    # Login starts with a qword user id (usually 0), then a scstring token.
    uid = int.from_bytes(data[0:8], "big")
    if uid not in (0, 1):
        return False
    tok_len = int.from_bytes(data[8:12], "big", signed=True)
    if tok_len not in (-1, 0, 4, 8, 16, 32, 64, 128, 256):
        return False
    # version vints: 3, 0, 377 -> each <= 2 bytes
    return True


def dump_hex_ascii(data: bytes, n: int = 96):
    for i in range(0, min(len(data), n), 16):
        chunk = data[i : i + 16]
        hx = " ".join("%02x" % b for b in chunk)
        asc = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        print("    %04x  %-47s  %s" % (i, hx, asc))


import itertools


def pad24(b: bytes) -> bytes:
    return (b + b"\x00" * 24)[:24]


def hits(name, session, payload):
    parts = {
        "static": STATIC,
        "nonce": NONCE,
        "session": session,
        "session24": pad24(session),
    }
    keys = {}
    # single
    for k, v in parts.items():
        keys[k] = v
    # pairs and triples in all orders
    for r in (2, 3):
        for combo in itertools.permutations(parts.keys(), r):
            key = b"".join(parts[c] for c in combo)
            keys["+".join(combo)] = key
    print("=" * 20, name, "testing %d keys" % len(keys))
    for label, key in keys.items():
        for discard in {0, len(key), 45, 40, 44, 43}:
            for prefix_len in {0, len(session), len(session) + 24, 24, 4 + len(session) + 24, 4}:
                if prefix_len >= len(payload):
                    continue
                dec = rc4_stream(key, discard, payload[prefix_len:])
                uid = int.from_bytes(dec[0:8], "big")
                tok = int.from_bytes(dec[8:12], "big", signed=True)
                good = uid in (0, 1) and tok in (-1, 0, 4, 8, 16, 24, 32, 40, 64)
                if good or dec.startswith(session) or dec[:8] == b"\x00" * 8:
                    print("  HIT [%s] discard=%d prefix=%d uid=%d tok=%d" % (label, discard, prefix_len, uid, tok))
                    dump_hex_ascii(dec, 80)


for name, session, payload in CASES:
    hits(name, session, payload)
