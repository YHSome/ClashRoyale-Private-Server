#!/usr/bin/env python3
"""Capture libg.so allocations during a battle to locate projectile creation."""

import frida
import time

SCRIPT = r"""
'use strict';

const g = Process.findModuleByName('libg.so');
send('libg base=' + g.base);

const seen = {};
let total = 0;
const MAX = 4000;

function record(size, bt) {
  if (total >= MAX) return;
  const frames = [];
  for (const f of bt) {
    const m = Process.findModuleByAddress(f);
    if (m && m.name === 'libg.so') frames.push('0x' + f.sub(g.base).toString(16));
  }
  if (frames.length === 0) return;
  const key = size + '|' + frames.join(',');
  if (!seen[key]) {
    seen[key] = { size, frames, count: 0 };
    total++;
  }
  seen[key].count++;
}

const malloc = Module.findExportByName('libc.so', 'malloc');
const calloc = Module.findExportByName('libc.so', 'calloc');
send('malloc=' + malloc + ' calloc=' + calloc);

Interceptor.attach(malloc, {
  onEnter(args) {
    const size = args[0].toUInt32();
    if (size >= 0x40 && size <= 0x1000) {
      const bt = Thread.backtrace(this.context, Backtracer.ACCURATE);
      record(size, bt);
    }
  }
});
Interceptor.attach(calloc, {
  onEnter(args) {
    const size = args[0].toUInt32() * args[1].toUInt32();
    if (size >= 0x40 && size <= 0x1000) {
      const bt = Thread.backtrace(this.context, Backtracer.ACCURATE);
      record(size, bt);
    }
  }
});

// dump on demand via rpc
rpc.exports = {
  dump() {
    const out = [];
    for (const k in seen) out.push(seen[k]);
    out.sort((a, b) => b.count - a.count);
    return out;
  }
};
send('ready');
"""


def main():
    import sys
    duration = int(sys.argv[1]) if len(sys.argv) > 1 else 90
    dev = frida.get_device_manager().add_remote_device("127.0.0.1:27042")
    session = dev.attach("Gadget")
    script = session.create_script(SCRIPT)

    def on_message(message, data):
        if message["type"] == "send":
            print(message["payload"])
        elif message["type"] == "error":
            print("ERROR:", message.get("stack") or message.get("description"))

    script.on("message", on_message)
    script.load()
    print("Capturing allocations for %ds." % duration)
    time.sleep(duration)
    result = script.exports_sync.dump()
    print("=== unique allocation sites (size | libg backtrace) ===")
    for item in result[:120]:
        print("%5d x%-5d  %s" % (item["size"], item["count"], " <- ".join(item["frames"])))
    session.detach()


if __name__ == "__main__":
    main()
