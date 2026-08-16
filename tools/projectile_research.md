# 界炸弹兵“火箭从国王塔发射”研究记录（Frida 路线）

## 目标

界炸弹兵（BoundaryBomber，炸弹兵克隆 + 自定义卡）每次攻击丢炸弹时，额外从**己方国王塔**
发射一发火箭到目标点。当前数据层实现（`MultipleProjectiles=2` + `CustomFirstProjectile=BoundaryRocket`
+ `ProjectileStartRadius=-20000`）只能让火箭从炸弹兵身后偏移出发，且随朝向变化，无法真正定位到国王塔。

## 已确认的关键事实

1. **libg.so 文件没有加密**。之前“静态反汇编全是乱码”是我脚本里把段基址加了两次导致的错位；
   正确按偶数（Thumb）对齐后，文件里的代码可以直接用 capstone 反汇编。
2. **游戏字符串没有直接静态引用**：对 `LogicProjectile::init called twice?`、`ProjectileStartRadius`、
   `LogicGameObjectManager::addGameObject(null)` 等锚点字符串，全文件扫描确认：
   - 无 4 字节直接指针（字面量池/数据段均无）
   - 无 movw/movt 指令对
   - 无 ADR.W / ADR
   - 无重定位（.rel.dyn/.rel.plt）指向
   运行时模块的 r--/rw- 数据区同样没有这些字符串的指针。字符串通过运行时构造的间接表解析，
   代码用“全局基址 + 偏移”访问（见 0x797c1 等函数里的 `ldr rN,[pc]; add rN,pc` 模式）。
3. **游戏不用直接 BL 调 `operator new`**：全代码 1.49M 条指令中没有任何 `bl _Znwj`。
   游戏私有分配器通过寄存器间址/虚方法调用，因此静态找“分配点”不可行，必须动态。
4. **战斗完全在手机端客户端模拟**，投射物创建发生在 `LogicBattle::tick` 链内
   （回溯链 `... <- 0xbc3a7 <- 0x6b7f3 <- Java_com_supercell_titan_GameApp_update`）。
5. Frida 16.7.19 gadget（resume 配置）工作正常；`Thread.backtrace(ACCURATE)` 可用；
   `Memory.scanSync` 可用（异步 `Memory.scan` 在本机 gadget 上静默失效）。

## 运行时定位结果（已实现）

### 投射物对象 = 虚表 0x502fb8

战斗中每 12 秒释放约 712 次的虚表 0x502fb8 对象（约 31 次/秒），分配大小 0x84 / 0x98，
销毁链直达战斗 tick。其虚表方法（经 .rel.dyn 重定位解析）：

- vtable[21] (0x927e0)：把两个点写入 `+0x68..0x74`（setStart+setTarget）
- vtable[28] (0x927f0)：**逐帧 tick**，起点 `+0x68/+0x6c` → 终点 `+0x70/+0x74` 插值，
  结果写回当前位置 `+0x58/+0x5c`，并调用 0x23d494 更新到父对象
- vtable[29] (0x92978)：读 `+0x58/+0x5c`，比较到达状态，写 `+4` 标志

对象布局（vtable 0x502fb8）：

| 偏移 | 类型 | 含义 |
|---|---|---|
| +0x00 | ptr | vtable |
| +0x04 | u8 | 到达/移动标志 |
| +0x48 | int | 计算值 |
| +0x4c | ptr | 目标对象引用 |
| +0x50 | int | 进度计数 |
| +0x54 | int | 速度 |
| +0x58/+0x5c | float | 当前位置 x/y |
| +0x60 | float | 累计偏移 |
| +0x64 | ptr | 数组/组件 |
| +0x68/+0x6c | float | **起点 x/y** |
| +0x70/+0x74 | float | 终点 x/y |
| +0x78/+0x79 | u8 | 标志 |

结论：vtable 0x502fb8 = 投射物/移动组件。**把 `+0x68/+0x6c`（起点）和 `+0x58/+0x5c`（当前）
覆盖为国王塔坐标，火箭就会从塔飞向目标。**

### 数据对象定位（可在运行时重复）

`tools/frida_find_data.py` 能在堆中扫描 ASCII 字符串及其 4 字节指针：
- `BoundaryRocket` 名字串 + 指向它的数据对象槽位（每次进程启动地址不同，需重新扫描）
- 同法可找 `RocketSpell`、`BombSkeletonProjectile` 和 `KingTower` 相关数据

## 待完成（手机回来后）

1. 重新扫描 `BoundaryRocket` 数据对象地址（每进程 ASLR 不同）。
2. 挂 vtable[28] tick（`base + vtable[0x502fb8][28]`），dump 前几个存活对象，
   确认投射物对象里哪个字段指向 `BoundaryRocket` 的 ProjectileData（用于区分火箭/炸弹）。
3. 从己方塔射出的投射物（塔自动攻击 bot 单位）的 `+0x68/+0x6c` 读取国王塔坐标并缓存。
4. 正式 hook：当投射物数据 == BoundaryRocket 时，在首个 tick 把起点/当前覆盖为国王塔坐标。
5. 微调：若速度/进度计算导致火箭提前到达，再覆盖 `+0x54`（速度）或每帧维持起点。
6. 备选：用限速回溯（每尺寸每秒 ≤5 次）抓创建链，找到创建函数后直接在创建时覆盖，
   效果更干净。

## 工具清单

- `frida_alloc_hist.py`：分配尺寸直方图（轻量，安全）
- `frida_bt_capture.py`：指定尺寸的分配回溯（限速使用，避免拖死游戏）
- `frida_vtable_collect.py` / `frida_free_bt.py` / `frida_obj_size.py`：
  释放对象虚表收集 / 释放回溯 / 分配-释放配对
- `frida_find_data.py`：堆中字符串与数据对象定位
- `frida_explore.py`：只读诊断

## 踩坑备忘

- 高频 `Thread.backtrace` 会拖死游戏/设备（全量 malloc 回溯曾导致灰屏与掉线），必须限速/只采样。
- 任何 hook 会话要短、异常要 detach；Python 被超时杀掉会留下僵尸会话卡死 gadget，需重启游戏。
- adb 与 gadget 都会偶发卡死：`adb kill-server` 重连；gadget 卡死只能重启游戏进程。
- 手机当前安装的是 mod7 gadget APK（`clients/retroroyale-1.9.2-phone-mod7-gadget.apk`，
  `on_load=resume`，冷启动不灰屏）。

## 当前服务器/bot 状态

- bot 卡组已改为 8×界炸弹兵（服务器 MySQL player id=2 的 Home.deck 已同步更新，
  `cr_bot.py` 的 `BOT_DECK = [(26,61)]*8`，收集器优先级已移除）。
- 主服 `ClashRoyale`、战斗服 `ClashRoyale.Battles`、bot `cr_bot.py` 正常运行。


## 2026-08-17 补充（模拟器 ARM 翻译版）

- 下载的安卓模拟器实际通过 **ARM 翻译**运行（`Process.findModuleByName('libg.so').path`
  指向 `lib/arm/libg.so`，运行时代码是 Thumb；APK 里的 lib/x86 未生效）。
- 本构建投射物对象大小 = **272 字节**（`_Znwj` 分配），创建调用点返回地址 =
  `libg+0x7c117`，创建链 `0x7c117 <- 0x7c3cf <- 0x79a79 <- 0x7a155 <- 0x86c01 <-
  0xa87cf <- 0xbaa2f <- 0xbc3a7 <- 0x6b7f3`（与早期记录的 ARM 战斗 tick 链一致）。
- OneMusketeer 角色数据表自标定特征：相邻双 40000（Range/SightRange，偏移 +0/+0x14），
  往回 -8 = 1100（攻速）、+104 = 600（装弹）；x86 静态反汇编不可用（.text 区域疑似加密/随机）。
- 挂钩方案：`_Znwj` onEnter 记录 size，onLeave 用 `this.returnAddress` 过滤调用点，
  即可在投射物创建时精确计数（`tools/frida_one_musketeer_hook.py`）。
