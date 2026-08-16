#!/usr/bin/env python3
"""Targeted backtrace capture for specific allocation sizes (safe: only
records allocations whose exact size matches the filter)."""

import argparse
import json
import time

import frida

SCRIPT_TMPL = r"""
'use strict';
const g = Process.findModuleByName('libg.so');
const base = g.base;
const SIZES = new Set(%s.map(x => parseInt(x, 0)));
const MAX = %d;
let recs = [];
let inCb = false;
const t0 = Date.now();

const newAddr = Module.findExportByName('libg.so', '_Znwj');
if (newAddr) {
  Interceptor.attach(newAddr, {
    onEnter(args) {
      if (inCb) return;
      const sz = args[0].toInt32();
      if (!SIZES.has(sz) || recs.length >= MAX) return;
      inCb = true;
      try {
        const bt = Thread.backtrace(this.context, Backtracer.ACCURATE);
        recs.push({
          sz: sz,
          t: Date.now() - t0,
          bt: bt.map(a => {
            const rel = a.sub(base);
            return '0x' + rel.toString(16);
          }),
        });
      } catch (e) {
      }
      inCb = false;
    }
  });
  send(JSON.stringify({type: 'ready', hooked: true, base: base.toString()}));
} else {
  send(JSON.stringify({type: 'ready', hooked: false}));
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
    ap.add_argument("--sizes", required=True, help="comma list of sizes, e.g. 0x110,0x140")
    ap.add_argument("--seconds", type=float, default=10.0)
    ap.add_argument("--max", type=int, default=800)
    args = ap.parse_args()

    sizes = [s.strip() for s in args.sizes.split(",") if s.strip()]
    script_src = SCRIPT_TMPL % (json.dumps(sizes), args.max)

    dev = frida.get_device_manager().add_remote_device("127.0.0.1:27042")
    session = dev.attach("Gadget")
    script = session.create_script(script_src)

    def on_msg(m, d):
        if m["type"] == "send":
            print(m["payload"], flush=True)
        elif m["type"] == "error":
            print("SCRIPT ERROR:", m.get("description"), flush=True)

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
