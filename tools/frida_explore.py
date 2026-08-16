#!/usr/bin/env python3
"""Frida exploration: minimal diagnostics for libg.so runtime layout."""

import frida
import time

SCRIPT = r"""
'use strict';

const g = Process.findModuleByName('libg.so');
send('libg base=' + g.base + ' size=' + g.size);

function findString(mod, text) {
  const pat = Array.from(text).map(c => c.charCodeAt(0).toString(16).padStart(2, '0')).join(' ');
  for (const r of mod.enumerateRanges('r-x').concat(mod.enumerateRanges('r--')).concat(mod.enumerateRanges('rw-'))) {
    const hits = Memory.scanSync(r.base, r.size, pat);
    if (hits.length) return hits[0].address;
  }
  return null;
}

function scanRefsSync(mod, strAddr) {
  const results = [];
  for (const r of mod.enumerateRanges('r-x').concat(mod.enumerateRanges('r--')).concat(mod.enumerateRanges('rw-'))) {
    const hits = Memory.scanSync(r.base, r.size, ptr(strAddr).toMatchPattern());
    for (const h of hits) results.push('0x' + h.address.sub(mod.base).toString(16));
  }
  return results;
}

function scanMovwMovtSync(mod, strAddr) {
  const results = [];
  const lo = strAddr & 0xffff;
  const hi = (strAddr >>> 16) & 0xffff;
  for (const r of mod.enumerateRanges('r-x')) {
    const u8 = new Uint8Array(Memory.readByteArray(r.base, r.size));
    function decode(h1, h2) {
      if ((h1 & 0xF800) !== 0xF200) return null;
      const op = (h1 >> 5) & 0x1F;
      let isMovw;
      if (op === 0x12) isMovw = true;
      else if (op === 0x16) isMovw = false;
      else return null;
      const iBit = (h1 >> 10) & 1;
      const imm4 = h1 & 0xF;
      const imm3 = (h2 >> 12) & 0x7;
      const rd = (h2 >> 8) & 0xF;
      const imm8 = h2 & 0xFF;
      return { isMovw, imm16: (imm4 << 12) | (iBit << 11) | (imm3 << 8) | imm8, rd };
    }
    for (let i = 0; i + 4 <= u8.length; i += 2) {
      const d1 = decode(u8[i] | (u8[i + 1] << 8), u8[i + 2] | (u8[i + 3] << 8));
      if (!d1) continue;
      for (let j = 2; j <= 6; j += 2) {
        if (i + j + 4 > u8.length) break;
        const d2 = decode(u8[i + j] | (u8[i + j + 1] << 8), u8[i + j + 2] | (u8[i + j + 3] << 8));
        if (!d2 || d2.rd !== d1.rd) continue;
        const val = d1.isMovw ? (d1.imm16 | (d2.imm16 << 16)) : (d2.imm16 | (d1.imm16 << 16));
        if (val === strAddr) results.push('0x' + i.toString(16));
      }
    }
  }
  return results;
}

const anchors = {
  'ProjectileStartRadius': 'ProjectileStartRadius',
  'LogicGameObjectManager::addGameObject(null)': 'LogicGameObjectManager::addGameObject(null)',
  'LogicProjectile::init called twice': 'LogicProjectile::init called twice',
  'createGameObjectByData invalid type': 'createGameObjectByData invalid type',
  'LogicMovementComponent::tickToTarget: Speed is zero': 'LogicMovementComponent::tickToTarget: Speed is zero',
};
for (const [name, text] of Object.entries(anchors)) {
  const addr = findString(g, text);
  if (!addr) { send(name + ': STRING NOT FOUND'); continue; }
  send(name + ' runtime @ 0x' + addr.sub(g.base).toString(16));
  send(name + ' refs: ' + JSON.stringify(scanRefsSync(g, addr.toUInt32()).slice(0, 40)));
  send(name + ' movw/movt: ' + JSON.stringify(scanMovwMovtSync(g, addr.toUInt32()).slice(0, 40)));
}
"""


def main():
    dev = frida.get_device_manager().add_remote_device("127.0.0.1:27042")
    session = dev.attach("Gadget")
    script = session.create_script(SCRIPT)
    script.on("message", lambda m, d: print(m.get("payload") if m["type"] == "send" else m))
    script.load()
    time.sleep(8)
    session.detach()


if __name__ == "__main__":
    main()
