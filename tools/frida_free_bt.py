#!/usr/bin/env python3
"""Capture backtraces of operator delete for objects with candidate vtables."""

import argparse
import json
import time

import frida

SCRIPT_TMPL = r"""
'use strict';
const g = Process.findModuleByName('libg.so');
const base = g.base;
const VTS = new Set(%s.map(x => parseInt(x, 0)));
const MAX = %d;
let recs = [];
let inCb = false;
const t0 = Date.now();

const delAddr = Module.findExportByName('libg.so', '_ZdlPv');
if (delAddr) {
  Interceptor.attach(delAddr, {
    onEnter(args) {
      if (inCb || recs.length >= MAX) return;
      const p = args[0];
      if (p.isNull()) return;
      inCb = true;
      try {
        const v = p.readPointer().sub(base).toUInt32();
        if (VTS.has(v)) {
          const bt = Thread.backtrace(this.context, Backtracer.ACCURATE);
          recs.push({
            v: '0x' + v.toString(16),
            t: Date.now() - t0,
            bt: bt.map(a => {
              const rel = a.sub(base);
              return '0x' + rel.toString(16);
            }),
          });
        }
      } catch (e) {}
      inCb = false;
    }
  });
  send(JSON.stringify({type: 'ready', hooked: true}));
}

rpc.exports = {
  dump() {
    const out = JSON.stringify({type: 'dump', count: recs.length, recs: recs});
    recs = [];
    return out;
  },
};
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vtables", required=True, help="comma list of vtable offsets, e.g. 0x502fb8,0x5101c4")
    ap.add_argument("--seconds", type=float, default=12.0)
    ap.add_argument("--max", type=int, default=1500)
    args = ap.parse_args()

    vts = [s.strip() for s in args.vtables.split(",") if s.strip()]
    dev = frida.get_device_manager().add_remote_device("127.0.0.1:27042")
    session = dev.attach("Gadget")
    script = session.create_script(SCRIPT_TMPL % (json.dumps(vts), args.max))

    def on_msg(m, d):
        if m["type"] == "send":
            print(m["payload"], flush=True)
        elif m["type"] == "error":
            print("ERR:", m.get("description"), flush=True)

    script.on("message", on_msg)
    script.load()
    time.sleep(args.seconds)
    try:
        print(script.exports_sync.dump(), flush=True)
    except Exception as e:
        print("dump failed:", e, flush=True)
    session.detach()


if __name__ == "__main__":
    main()
