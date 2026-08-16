#!/usr/bin/env python3
"""界炸弹兵：把 BoundaryRocket 投射物的起点覆盖为己方国王塔。

用法（手机在线、游戏在对局中）：
  python frida_rocket_hook.py --calibrate   # 校准：dump 存活投射物字段，找数据指针偏移
  python frida_rocket_hook.py --apply       # 正式覆盖（需要先确认 --data-off）

原理：
  vtable 0x502fb8 是投射物/移动对象；vtable[28] (0x927f0) 是逐帧插值 tick：
    起点 +0x68/+0x6c，终点 +0x70/+0x74，当前位置 +0x58/+0x5c，速度 +0x54。
  在首个 tick 把起点与当前位置覆盖为国王塔坐标，火箭即从塔飞向目标。
  国王塔坐标从"己方塔自己射出的投射物"的起点字段缓存（塔会自动打 bot 单位）。
"""

import argparse
import time

import frida

VTABLE = 0x502fb8
TICK_SLOT = 28


def build_script(calibrate, data_off, data_addr):
    js = r"""
'use strict';
const g = Process.findModuleByName('libg.so');
const base = g.base;
const vtable = base.add(0x%x);
const tickAddr = vtable.add(%d * 4).readPointer().and(ptr('~1'));

let towerX = null, towerY = null;
let applied = 0, ticks = 0;
const seen = new Set();

function hex(x) { return '0x' + x.toString(16); }

Interceptor.attach(tickAddr, {
  onEnter(args) {
    ticks++;
    const obj = args[0];
    if (towerX === null) {
      const sx = obj.add(0x68).readFloat();
      const sy = obj.add(0x6c).readFloat();
      if (sy > 0 && sy < 9000) {
        towerX = sx; towerY = sy;
        send('Tower pos cached: ' + sx + ',' + sy);
      }
    }
    const key = obj.toString();
    if (seen.has(key)) return;
    seen.add(key);
    if (seen.size > 200) seen.clear();
    if (%s) {
      if (applied < 6) {
        const words = [];
        for (let i = 0; i < 0x28; i++) words.push(obj.add(i*4).readU32());
        send('CAL obj=' + key + ' words=' + words.map(w => '0x' + (w>>>0).toString(16)).join(','));
      }
      applied++;
      return;
    }
    if (%d >= 0) {
      const d = obj.add(%d).readPointer();
      if (!d.equals(ptr(%s))) return;
    }
    if (towerX === null) return;
    obj.add(0x68).writeFloat(towerX);
    obj.add(0x6c).writeFloat(towerY);
    obj.add(0x58).writeFloat(towerX);
    obj.add(0x5c).writeFloat(towerY);
    applied++;
    if (applied <= 5) send('OVERRIDE #' + applied + ' -> ' + towerX + ',' + towerY);
  }
});
send('hooked tick at ' + hex(tickAddr.sub(base).toUInt32()));
setInterval(() => send('STAT ticks=' + ticks + ' applied=' + applied + ' tower=' + (towerX === null ? '?' : towerX+','+towerY)), 5000);
"""
    return js % (VTABLE, TICK_SLOT, "true" if calibrate else "false", data_off, data_off,
                 json_dumps(data_addr))


def json_dumps(s):
    import json
    return json.dumps(s or "0")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--calibrate", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--data-off", type=lambda s: int(s, 0), default=-1)
    ap.add_argument("--data-addr", default="")
    ap.add_argument("--seconds", type=float, default=20.0)
    args = ap.parse_args()

    if not (args.calibrate or args.apply):
        ap.error("need --calibrate or --apply")

    dev = frida.get_device_manager().add_remote_device("127.0.0.1:27042")
    session = None
    try:
        session = dev.attach("Gadget")
        script = session.create_script(build_script(args.calibrate, args.data_off, args.data_addr))
        script.on("message", lambda m, d: print(m.get("payload") if m["type"] == "send" else m, flush=True))
        script.load()
        time.sleep(args.seconds)
    finally:
        if session:
            try:
                session.detach()
            except Exception:
                pass


if __name__ == "__main__":
    main()
