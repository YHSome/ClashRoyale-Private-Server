import socket
import struct
import threading
import time

HOST = "0.0.0.0"
PORT = 9339


def read_frame(conn):
    """Read one CR frame: [id:2][len:3][ver:2][payload] where len counts payload only."""
    head = b""
    while len(head) < 7:
        chunk = conn.recv(7 - len(head))
        if not chunk:
            return None
        head += chunk
    mid = struct.unpack(">H", head[0:2])[0]
    length = int.from_bytes(head[2:5], "big")
    ver = struct.unpack(">H", head[5:7])[0]
    body = b""
    need = length  # payload bytes after version
    while len(body) < need:
        chunk = conn.recv(need - len(body))
        if not chunk:
            return None
        body += chunk
    return mid, length, ver, body


def send_frame(conn, mid, payload, ver=0):
    length = len(payload)  # payload only
    frame = struct.pack(">H", mid) + length.to_bytes(3, "big") + struct.pack(">H", ver) + payload
    conn.sendall(frame)
    print("  -> sent %d (%s)" % (mid, payload.hex()), flush=True)


def handle(conn, addr, variant):
    conn.settimeout(10)
    frame = read_frame(conn)
    if frame is None:
        print("[%s] closed before ClientHello" % addr, flush=True)
        conn.close()
        return
    mid, length, ver, body = frame
    print("[%s] ClientHello id=%d len=%d ver=%d payload=%s" % (addr, mid, length, ver, body.hex()), flush=True)

    session = bytes.fromhex("74794DE40D62A03AC6F6E86A9815C6262AA12BEDD518F883")
    if variant == "A_byteset16":
        payload = struct.pack(">I", len(session)) + session
    elif variant == "B_byteset24":
        s24 = bytes(range(24))
        payload = struct.pack(">I", 24) + s24
    elif variant == "C_raw24":
        payload = bytes(range(24))
    elif variant == "F_string_nonce":
        payload = struct.pack(">I", 5) + b"nonce"
    elif variant == "G_string_key":
        payload = struct.pack(">I", len(b"fhsd6f86f67rt8fw78fw789we78r9789wer6re")) + b"fhsd6f86f67rt8fw78fw789we78r9789wer6re"
    elif variant == "D_empty":
        payload = b""
    elif variant == "E_login_failed":
        # LoginFailed: ErrorCode byte + scstring fingerprint + scstring + scstring + scstring + scstring + vint
        payload = b"\x00" + b"\xff\xff\xff\xff" * 5 + b"\x00"
        send_frame(conn, 20103, payload)
        conn.close()
        return
    else:
        payload = b""

    send_frame(conn, 20100, payload)

    # now wait for LoginMessage
    while True:
        try:
            f = read_frame(conn)
        except socket.timeout:
            print("[%s] timeout waiting for next frame" % addr, flush=True)
            break
        if f is None:
            print("[%s] closed" % addr, flush=True)
            break
        m, ln, vv, bd = f
        print("[%s] got id=%d len=%d ver=%d payload=%s" % (addr, m, ln, vv, bd.hex()), flush=True)
        if m == 10101:
            print("!!! CLIENT SENT LOGIN after variant %s !!!" % variant, flush=True)
            break
    conn.close()


def main():
    variants = [
        "A_byteset16",
        "C_raw24",
        "B_byteset24",
        "F_string_nonce",
        "G_string_key",
        "D_empty",
    ]
    idx = [0]
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((HOST, PORT))
    srv.listen(5)
    srv.settimeout(120)
    deadline = time.time() + 200
    while time.time() < deadline:
        try:
            conn, addr = srv.accept()
        except socket.timeout:
            break
        variant = variants[idx[0] % len(variants)]
        idx[0] += 1
        print("CONNECT %s variant=%s" % (addr, variant), flush=True)
        t = threading.Thread(target=handle, args=(conn, addr, variant), daemon=True)
        t.start()
    print("done", flush=True)


if __name__ == "__main__":
    main()
