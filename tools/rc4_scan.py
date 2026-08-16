from rc4_analyze import rc4_stream, dump_hex_ascii


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
        b"nonce",
        bytes.fromhex(
            "9efd367cd5795e2dd9df5ae3f448b150e54158ea272d119866576cc613ec5b496debde3cfd888e6b03be3acfc4f8a601bd52df365473bf3dff2624133f9bb8eda056a35c8b04bb8af3268c99a6e5c4cfc500039c8fb53a4c3b9b9ec31ff66cffe1dac7160f0d86e01874d79104385455796ec8d8b7c1fd037f1e68361224180601fd392089ed877d703b4a89c9a4c9aeb3e8c0eb043f7aa7677935f83aa65814495355b19be5bb1d89a04386e7f158ddc92f0a79739c97531e64bafb20717e3f9d4455f68167bb796ecc412f1e5f20b4a54c0dd2f74bead298d2aa4214c250e44fc81ab05457f68fdab783c3"
        ),
    ),
]


def looks_ok(data):
    if len(data) < 32:
        return False
    uid = int.from_bytes(data[0:8], "big")
    if uid not in (0, 1):
        return False
    tok = int.from_bytes(data[8:12], "big", signed=True)
    return tok in (-1, 0, 1, 4, 8, 16, 24, 32, 40, 64, 128)


def mt_keystream(seed, length):
    buf = [0] * 624
    buf[0] = seed
    for i in range(1, 624):
        buf[i] = (1812433253 * ((buf[i - 1] ^ (buf[i - 1] >> 30)) + 1)) & 0xFFFFFFFF

    def generate():
        for i in range(624):
            y = ((buf[i] & 0x80000000) + (buf[(i + 1) % 624] & 0x7FFFFFFF)) & 0xFFFFFFFF
            buf[i] = ((buf[(i + 397) % 624] ^ (y >> 1)) & 0xFFFFFFFF)
            if y & 1:
                buf[i] ^= 2567483615

    out = bytearray()
    ix = 0
    generate()
    while len(out) < length:
        if ix == 0:
            generate()
        y = buf[ix]
        y ^= y >> 11
        y ^= (y << 7) & 2636928640
        y ^= (y << 15) & 4022730752
        y ^= y >> 18
        if y & (1 << 31):
            y = (~y + 1) & 0xFFFFFFFF
        out.append(y % 256)
        ix = (ix + 1) % 624
    return bytes(out)


STATIC = b"fhsd6f86f67rt8fw78fw789we78r9789wer6re"
NONCE = b"nonce"

for name, session, payload in CASES:
    print("=" * 30, name, "sklen=%d payload=%d" % (len(session), len(payload)))
    key_candidates = {
        "static+nonce": STATIC + NONCE,
        "static": STATIC,
        "static+session": STATIC + session,
        "static+session+nonce": STATIC + session + NONCE,
    }
    for klabel, key in key_candidates.items():
        for prefix_len in {
            len(session) + 4,
            4 + len(session) + 4,
            len(session),
            4 + len(session),
            len(session) + 4 + 24,
            4 + len(session) + 4 + 24,
            0,
        }:
            if prefix_len >= len(payload):
                continue
            for discard in {0, len(key), 45, 40}:
                dec = rc4_stream(key, discard, payload[prefix_len:])
                if looks_ok(dec):
                    print("  HIT key=%s prefix=%d discard=%d" % (klabel, prefix_len, discard))
                    dump_hex_ascii(dec, 64)

    # UCS-style: session key prefix (raw or byteset) + 4-byte seed in clear, then
    # RC4(fields) with key = static + MT_transform(sessionKey, seed)
    for sk_prefix in (len(session), 4 + len(session)):
        seed_off = sk_prefix
        if seed_off + 4 >= len(payload):
            continue
        for endian in ("big", "little"):
            seed = int.from_bytes(payload[seed_off : seed_off + 4], endian)
            transformed = bytes(
                a ^ b for a, b in zip(session, mt_keystream(seed, len(session)))
            )
            for klabel, key in {
                "MT:static+tsession": STATIC + transformed,
                "MT:tsession": transformed,
                "MT:static+nonce+tsession": STATIC + NONCE + transformed,
            }.items():
                for discard in {len(key), 0, 45}:
                    dec = rc4_stream(key, discard, payload[seed_off + 4 :])
                    if looks_ok(dec):
                        print("  MT-HIT key=%s sk_prefix=%d endian=%s seed=%d discard=%d" % (klabel, sk_prefix, endian, seed, discard))
                        dump_hex_ascii(dec, 64)
