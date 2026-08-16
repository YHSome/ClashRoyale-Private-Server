#!/usr/bin/env python3
"""一个火枪手 (OneMusketeer) —— 前 3 发火箭、之后变普通 的 Frida 实现。

原理（已在模拟器 ARM 版实测标定）：
  * 投射物对象由 operator new(_Znwj) 分配，大小 272 字节，
    创建调用点返回地址 = libg+0x7c117（战斗 tick 链 0xbc3a7/0x6b7f3 之下）；
  * OneMusketeer 角色数据表：射程字段 = 40000（Range/SightRange 两个值相邻，
    偏移 +0 与 +0x14）；攻速 1100 @ -8、装弹 600 @ +104（校验签名）；
  * 火箭行对象：通过字符串 "BoundaryOneMusketeerRocket" → 表槽 → 行对象 两跳定位；
  * 角色表里指向火箭行对象的字 = Projectile 字段；
  * "MusketeerProjectile" 行对象 = 恢复值。

流程：脚本加载后自标定 → 挂 _Znwj 计数（272 字节 + 调用点 0x7c117）→
第 3 发火箭后把 Range/SightRange 改成 6000、Projectile 改回 MusketeerProjectile。
若战斗环境稳定即可自动生效；不稳定时可手动进入战斗后运行本脚本。
"""

import frida
import json
import sys
import time

JS = r"""
'use strict';
const g = Process.findModuleByName('libg.so');
const base = g.base;

// ---------- 工具 ----------
function scanPattern(pat) {
  const out = [];
  const ranges = Process.enumerateRanges('rw-');
  for (const r of ranges) {
    if (r.size > 0x20000000) continue;
    if (r.file && r.file.path) continue;
    try { for (const h of Memory.scanSync(r.base, r.size, pat)) out.push(h.address); } catch (e) {}
  }
  return out;
}

function u32hex(v) { return (v >>> 0).toString(16); }

// ---------- 1. 定位 OneMusketeer 角色数据表 ----------
// 特征：Range=40000 与 SightRange=40000 相邻（0x14 内成对）
let muskTable = null;
let rangeOff = -1;
let sightOff = -1;
{
  const hits = scanPattern("40 9c 00 00");
  outer:
  for (const h of hits) {
    const hh = h.toUInt32();
    for (const j of hits) {
      const jj = j.toUInt32();
      if (jj > hh && jj - hh <= 0x20) {
        // 校验：往回的 -8 是 1100(攻速)，+104 是 600(装弹)
        try {
          const hs = h.sub(8).readU32();
          const lt = h.add(104).readU32();
          if (hs === 1100 && lt === 600) {
            muskTable = h;
            rangeOff = 0;
            sightOff = jj - hh;
            break outer;
          }
        } catch (e) {}
      }
    }
  }
}
send('ONE_MUSK_TABLE=' + (muskTable ? muskTable.toString() : 'NOT FOUND'));

// ---------- 2. 两跳定位火箭行对象 / 普通子弹行对象 ----------
function findRowByString(str) {
  const pat = Array.from(str).map(c => c.charCodeAt(0).toString(16).padStart(2, '0')).join(' ');
  const strs = scanPattern(pat);
  if (!strs.length) return null;
  // hop1: 指向字符串的槽
  const hop1 = [];
  for (const s of strs) {
    const p = (s.toUInt32()).toString(16).padStart(8, '0').match(/.{2}/g).reverse().join(' ');
    for (const h of scanPattern(p)) hop1.push(h);
  }
  if (!hop1.length) return null;
  // hop2: 指向这些槽(±8)的位置 = 行对象的 Name 字段
  for (const h of hop1) {
    for (let d = -8; d <= 8; d += 4) {
      const t = h.add(d).toUInt32();
      const p = (t).toString(16).padStart(8, '0').match(/.{2}/g).reverse().join(' ');
      for (const x of scanPattern(p)) {
        return x.sub(0x100); // 行对象基址（Name 字段前约 0x100 处，宽松取）
      }
    }
  }
  return null;
}

// ---------- 3. 计数并打补丁 ----------
const newAddr = Module.findExportByName('libg.so', '_Znwj');
let rocketCount = 0;
let patched = false;

function patchToNormal() {
  if (!muskTable || patched) return;
  try {
    muskTable.add(rangeOff).writeU32(6000);
    muskTable.add(sightOff).writeU32(6000);
    send('PATCHED range -> 6000');
    // Projectile 换回普通子弹（若行对象已定位）
    const bullet = findRowByString('MusketeerProjectile');
    if (bullet) {
      // 在角色表里找指向火箭行对象的字 = Projectile 字段
      const rocket = findRowByString('BoundaryOneMusketeerRocket');
      if (rocket) {
        const rp = rocket.toUInt32();
        for (let i = -0x300; i < 0x2000; i += 4) {
          try {
            if (muskTable.add(i).readU32() === rp) {
              muskTable.add(i).writeU32(bullet.toUInt32());
              send('PATCHED projectile @ +' + i.toString(16));
              break;
            }
          } catch (e) {}
        }
      }
    }
    patched = true;
  } catch (e) {
    send('PATCH ERR ' + e.message);
  }
}

if (newAddr) {
  Interceptor.attach(newAddr, {
    onEnter(args) { this.sz = args[0].toInt32(); },
    onLeave(retval) {
      if (this.sz !== 272) return;
      const rel = this.returnAddress.sub(base).toUInt32() & ~1;
      if (rel !== 0x7c117) return;
      rocketCount++;
      send('ROCKET #' + rocketCount);
      if (rocketCount >= 3) patchToNormal();
    }
  });
  send('HOOKED creator');
} else {
  send('NO _Znwj');
}
"""


def main():
    dev = frida.get_device_manager().add_remote_device("127.0.0.1:27042")
    session = dev.attach("Gadget")
    script = session.create_script(JS)

    def on_msg(m, d):
        if m["type"] == "send":
            print(m["payload"], flush=True)
        elif m["type"] == "error":
            print("SCRIPT ERROR:", m.get("description"), flush=True)

    script.on("message", on_msg)
    script.load()
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass
    session.detach()


if __name__ == "__main__":
    main()
