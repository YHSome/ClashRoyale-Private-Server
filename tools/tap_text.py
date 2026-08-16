import re
import subprocess
import sys

ADB = r"C:\Users\YHSome\AppData\Local\Android\Sdk\platform-tools\adb.exe"


def sh(*args):
    return subprocess.run([ADB, *args], capture_output=True).stdout


def main():
    text = sys.argv[1]
    sh("shell", "uiautomator", "dump", "/sdcard/ui_tap.xml")
    xml = sh("shell", "cat", "/sdcard/ui_tap.xml").decode("utf-8", errors="replace")
    # find node whose text attribute equals the target
    pattern = re.compile(r'text="%s"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"' % re.escape(text))
    m = pattern.search(xml)
    if not m:
        # try with bounds appearing before text
        pattern2 = re.compile(r'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"[^>]*text="%s"' % re.escape(text))
        m = pattern2.search(xml)
    if not m:
        print("NOT FOUND: %s" % text)
        return 1
    x = (int(m.group(1)) + int(m.group(3))) // 2
    y = (int(m.group(2)) + int(m.group(4))) // 2
    print("tap %s at %d,%d" % (text, x, y))
    sh("shell", "input", "tap", str(x), str(y))
    return 0


if __name__ == "__main__":
    sys.exit(main())
