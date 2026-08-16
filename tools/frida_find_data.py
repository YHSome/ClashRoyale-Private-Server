#!/usr/bin/env python3
"""Find runtime copies of ASCII strings and 4-byte pointers to them, to
locate game-data objects (e.g. ProjectileData for BoundaryRocket)."""

import argparse
import json
import time

import frida

SCRIPT_TMPL = r"""
'use strict';
const TARGETS = %s;

function hexBytes(b) {
  return Array.from(new Uint8Array(b)).map(x => x.toString(16).padStart(2, '0')).join(' ');
}

function scanForStrings() {
  const out = {};
  for (const t of TARGETS) {
    out[t] = [];
    const pat = Array.from(t).map(c => c.charCodeAt(0).toString(16).padStart(2, '0')).join(' ');
    const ranges = Process.enumerateRanges('rw-').concat(Process.enumerateRanges('r--'));
    for (const r of ranges) {
      if (r.size > 0x40000000) continue; // skip huge
      if (r.file && r.file.path) continue; // skip file-backed
      try {
        const hits = Memory.scanSync(r.base, r.size, pat);
        for (const h of hits) {
          let ctx = '';
          try {
            ctx = hexBytes(Memory.readByteArray(h.address.sub(8), 32));
          } catch (e) {}
          out[t].push({addr: h.address.toString(), ctx: ctx});
        }
      } catch (e) {}
    }
  }
  return out;
}

function scanPointers(addrList) {
  const out = [];
  const ranges = Process.enumerateRanges('rw-').concat(Process.enumerateRanges('r--'));
  for (const a of addrList) {
    const pat = (a >>> 0).toString(16).padStart(8, '0').match(/.{2}/g).reverse().join(' ');
    for (const r of ranges) {
      if (r.size > 0x40000000) continue;
      if (r.file && r.file.path) continue;
      try {
        const hits = Memory.scanSync(r.base, r.size, pat);
        for (const h of hits) {
          out.push({ptr: a.toString(16), at: h.address.toString()});
        }
      } catch (e) {}
    }
  }
  return out;
}

rpc.exports = {
  run() {
    const strings = scanForStrings();
    const addrs = [];
    for (const t of TARGETS) {
      for (const h of strings[t]) addrs.push(h.addr);
    }
    const ptrs = scanPointers(addrs.map(a => parseInt(a, 16)));
    return JSON.stringify({strings: strings, ptrs: ptrs});
  },
};
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--strings", required=True, help="comma-separated ASCII strings")
    args = ap.parse_args()
    targets = [s for s in args.strings.split(",") if s]

    dev = frida.get_device_manager().add_remote_device("127.0.0.1:27042")
    session = dev.attach("Gadget")
    script = session.create_script(SCRIPT_TMPL % json.dumps(targets))
    script.load()
    print(script.exports_sync.run(), flush=True)
    session.detach()


if __name__ == "__main__":
    main()
