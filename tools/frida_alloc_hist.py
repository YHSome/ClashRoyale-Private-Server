#!/usr/bin/env python3
"""Lightweight allocation-size profiler for libg.so (counts only, no
backtraces, safe to run during battle)."""

import argparse
import json
import sys
import time

import frida

SCRIPT = r"""
'use strict';
const g = Process.findModuleByName('libg.so');
const base = g.base;
const hist = {};
const exact = {};
let total = 0;
let started = 0;
// Re-entry guard: the JS callback must not allocate through the hooked
// functions, so we skip while inside the callback.
let inCb = false;

function nowMs() { return Date.now(); }

const newAddr = Module.findExportByName('libg.so', '_Znwj');
const newArrAddr = Module.findExportByName('libg.so', '_Znaj');

function onAlloc(sz) {
  if (sz < 0x10) return;
  total++;
  const bucket = sz >= 0x1000 ? '>=0x1000' : '0x' + (sz & ~0x3f).toString(16);
  hist[bucket] = (hist[bucket] || 0) + 1;
  exact[sz] = (exact[sz] || 0) + 1;
}

function attach(addr, argIdx) {
  if (!addr) return false;
  try {
    Interceptor.attach(addr, {
      onEnter(args) {
        if (inCb) return;
        inCb = true;
        try {
          const sz = args[argIdx].toInt32();
          onAlloc(sz);
        } catch (e) {
          // never break the game from the profiler
        }
        inCb = false;
      }
    });
    return true;
  } catch (e) {
    return 'err:' + e.message;
  }
}

const hooked = {
  _Znwj: attach(newAddr, 0),
  _Znaj: attach(newArrAddr, 0),
};
started = nowMs();
send(JSON.stringify({type: 'ready', hooked: hooked, base: base.toString()}));

rpc.exports = {
  snapshot() {
    return JSON.stringify({
      type: 'snapshot',
      elapsed: (nowMs() - started) / 1000,
      total: total,
      hist: hist,
      exactTop: Object.entries(exact).sort((a, b) => b[1] - a[1]).slice(0, 40),
    });
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
            print("SCRIPT ERROR:", m.get("description"), m.get("stack"), flush=True)
        else:
            print("MSG:", m, flush=True)

    script.on("message", on_msg)
    script.load()
    time.sleep(args.seconds)
    try:
        print(script.exports_sync.snapshot(), flush=True)
    except Exception as e:
        print("snapshot failed:", e, flush=True)
    session.detach()


if __name__ == "__main__":
    main()
