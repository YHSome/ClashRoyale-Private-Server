#!/usr/bin/env python3
"""Collect vtable pointers from freed objects (operator delete) to identify
LogicProjectile's vtable. Safe: only reads the first word of freed pointers."""

import argparse
import json
import time

import frida

SCRIPT = r"""
'use strict';
const g = Process.findModuleByName('libg.so');
const base = g.base;
const relroStart = base.add(0x4f5690);
const relroEnd = base.add(0x5132a0);
const dataStart = base.add(0x515000);
const dataEnd = base.add(0x59b940);
let inCb = false;
const vtables = {};
const samples = {};

const delAddr = Module.findExportByName('libg.so', '_ZdlPv');
if (delAddr) {
  Interceptor.attach(delAddr, {
    onEnter(args) {
      if (inCb) return;
      const p = args[0];
      if (p.isNull()) return;
      inCb = true;
      try {
        const v = p.readPointer();
        const rel = v.sub(base);
        const off = rel.toUInt32();
        const inRelro = v.compare(relroStart) >= 0 && v.compare(relroEnd) < 0;
        const inData = v.compare(dataStart) >= 0 && v.compare(dataEnd) < 0;
        const inText = off >= 0x5e6f8 && off < 0x40470c;
        if (inRelro || inData || inText) {
          const key = '0x' + off.toString(16);
          vtables[key] = (vtables[key] || 0) + 1;
          if (!samples[key]) {
            samples[key] = {
              ptr: p.toString(),
              words: Array.from(new Uint8Array(p.readByteArray(0x40))).map(x => x.toString(16).padStart(2, '0')).join(' ')
            };
          }
        }
      } catch (e) {}
      inCb = false;
    }
  });
  send(JSON.stringify({type: 'ready', hooked: true}));
} else {
  send(JSON.stringify({type: 'ready', hooked: false}));
}

rpc.exports = {
  dump() {
    return JSON.stringify({type: 'dump', vtables: vtables, samples: samples});
  },
};
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=10.0)
    args = ap.parse_args()

    dev = frida.get_device_manager().add_remote_device("127.0.0.1:27042")
    session = dev.attach("Gadget")
    script = session.create_script(SCRIPT)

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
