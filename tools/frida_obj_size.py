#!/usr/bin/env python3
"""Pair operator new/delete to find the allocation size of objects with a
given vtable. Safe: map lookup only, no backtraces."""

import argparse
import json
import time

import frida

SCRIPT_TMPL = r"""
'use strict';
const g = Process.findModuleByName('libg.so');
const base = g.base;
const VTS = new Set(%s.map(x => parseInt(x, 0)));
const sizes = new Map();
const found = {};
let inCb = false;
let newCount = 0;

const newAddr = Module.findExportByName('libg.so', '_Znwj');
const delAddr = Module.findExportByName('libg.so', '_ZdlPv');

if (newAddr) {
  Interceptor.attach(newAddr, {
    onEnter(args) {
      if (inCb) return;
      this.sz = args[0].toInt32();
      if (this.sz < 0x40 || this.sz > 0x2000) this.sz = 0;
    },
    onLeave(ret) {
      if (inCb) return;
      if (this.sz && !ret.isNull()) {
        inCb = true;
        try {
          if (sizes.size < 200000) {
            sizes.set(ret.toString(), this.sz);
            newCount++;
          }
        } catch (e) {}
        inCb = false;
      }
    },
  });
}

if (delAddr) {
  Interceptor.attach(delAddr, {
    onEnter(args) {
      if (inCb) return;
      const p = args[0];
      if (p.isNull()) return;
      inCb = true;
      try {
        const v = p.readPointer().sub(base).toUInt32();
        if (VTS.has(v)) {
          const sz = sizes.get(p.toString());
          const key = '0x' + v.toString(16) + ':size=' + (sz === undefined ? '?' : '0x' + sz.toString(16));
          found[key] = (found[key] || 0) + 1;
        }
        sizes.delete(p.toString());
      } catch (e) {}
      inCb = false;
    },
  });
}

rpc.exports = {
  dump() {
    return JSON.stringify({type: 'dump', newCount: newCount, found: found});
  },
};
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vtables", required=True)
    ap.add_argument("--seconds", type=float, default=10.0)
    args = ap.parse_args()

    vts = [s.strip() for s in args.vtables.split(",") if s.strip()]
    dev = frida.get_device_manager().add_remote_device("127.0.0.1:27042")
    session = dev.attach("Gadget")
    script = session.create_script(SCRIPT_TMPL % json.dumps(vts))
    script.on("message", lambda m, d: print(m.get("payload") if m["type"] == "send" else m, flush=True))
    script.load()
    time.sleep(args.seconds)
    try:
        print(script.exports_sync.dump(), flush=True)
    except Exception as e:
        print("dump failed:", e, flush=True)
    session.detach()


if __name__ == "__main__":
    main()
