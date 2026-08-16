import socket
import time

HOST = "0.0.0.0"
PORT = 9339
OUT = r"C:\Users\YHSome\Projects\OtherProjects\ClashRoyal\clients\capture6.bin"


def main():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((HOST, PORT))
    srv.listen(5)
    srv.settimeout(65)
    print("listening on 9339", flush=True)
    t0 = time.time()
    while time.time() - t0 < 60:
        try:
            conn, addr = srv.accept()
        except socket.timeout:
            break
        conn.settimeout(45)
        print("[%6.2f] CONNECT %s" % (time.time() - t0, addr), flush=True)
        buf = b""
        try:
            while True:
                chunk = conn.recv(4096)
                if not chunk:
                    print("[%6.2f] EOF after %d bytes" % (time.time() - t0, len(buf)), flush=True)
                    break
                buf += chunk
                print("[%6.2f] RECV +%d total=%d" % (time.time() - t0, len(chunk), len(buf)), flush=True)
                print(buf[-len(chunk):].hex(" "), flush=True)
        except socket.timeout:
            print("[%6.2f] TIMEOUT after %d bytes" % (time.time() - t0, len(buf)), flush=True)
        except Exception as exc:  # noqa: BLE001
            print("[%6.2f] ERR %s" % (time.time() - t0, exc), flush=True)
        finally:
            conn.close()
        if buf:
            with open(OUT, "wb") as fh:
                fh.write(buf)
            print("saved %d bytes" % len(buf), flush=True)
    print("done", flush=True)


if __name__ == "__main__":
    main()
