import os
import shutil
import sys
import zipfile

SRC = r"C:\Users\YHSome\Projects\OtherProjects\ClashRoyal\clients\retroroyale-1.9.2.apk"
OUT = r"C:\Users\YHSome\Projects\OtherProjects\ClashRoyal\clients\retroroyale-1.9.2-phone-unsigned.apk"
OLD = b"cluster.retroroyale.xyz"
NEW = b"192.168.3.65" + b"\x00" * (len(OLD) - len(b"192.168.3.65"))


def patch_lib(data: bytes, path: str) -> bytes:
    count = data.count(OLD)
    if count == 0:
        print("WARN: pattern not found in %s" % path)
        return data
    data = data.replace(OLD, NEW)
    print("patched %d occurrence(s) in %s" % (count, path))
    return data


def main():
    libs = {}
    with zipfile.ZipFile(SRC) as zin:
        for info in zin.infolist():
            if info.filename in (
                "lib/armeabi-v7a/libg.so",
                "lib/x86/libg.so",
            ):
                libs[info.filename] = patch_lib(zin.read(info.filename), info.filename)
    if not libs:
        print("no libs found")
        return 1
    with zipfile.ZipFile(SRC) as zin, zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as zout:
        for info in zin.infolist():
            data = zin.read(info.filename)
            if info.filename in libs:
                data = libs[info.filename]
            zout.writestr(info, data)
    print("wrote", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
