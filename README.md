# Clash Royale 1.9.2 私服 + 自定义卡牌

基于 **HashRoyale / RetroRoyale** 搭建的 Clash Royale 1.9.2 私服，并在此基础上
通过纯数据补丁制作了多张自定义卡牌。客户端为 RetroRoyale 修补版 APK（`com.retrocell.clashroyale`）。

> ⚠️ 本项目仅供学习与个人研究使用。客户端 APK 含 Supercell 版权资源，未包含在本仓库中；
> 请自行获取 RetroRoyale 客户端并按下方流程打补丁。服务端数据（`GameAssets`）来自公开的
> HashRoyale 开源项目。

## 功能特性

- 完整可跑的 1.9.2 私服：主服（TCP 9339/集群 9876）+ 战斗服（UDP 9449）+ MySQL 存档
- 匹配 Bot（`tools/cr_bot.py`）：自动排队、对局中持续下牌、可自定义卡组
- 一键启动脚本：`start-server.ps1` / `stop-server.ps1` / `one-click-start.ps1` / `一键启动.bat`
- 自定义卡牌制作工具链：改服务端 CSV + 客户端 APK（SC/LZMA 压缩 CSV）+ 文本，再签名安装

## 已制作的自定义卡牌

| 卡牌 | 数据名 | 机制 |
|---|---|---|
| 觉醒冰人 | AwakenedIceGolem | 每 1.5s 在自身位置释放冰人亡语效果 |
| 界炸弹兵 | BoundaryBomber | 每次攻击丢炸弹并额外发射火箭（多弹攻击） |
| 一条龙服务 | OneStopService | 原版哥布林飞桶逻辑：法术→飞桶投射物→落地爆出 2 精英野蛮人 + 3 烈焰精灵 + 狂暴 |
| 界电磁炮 | BoundaryZapMachine | 电磁炮克隆；每次攻击在目标点释放雷电 + 电击（子弹伤害 0） |
| 界气球兵 | BoundaryBalloon | 气球兵 + 幻影刺客突刺特性（全图视野/突袭） |
| 界地狱飞龙 | BoundaryInfernoDragon | 攻击无伤害；每次攻击从远处以随机角度发射复仇滚木（可对空） |
| 界地狱塔 | BoundaryInfernoTower | 地狱塔克隆；每次攻击向随机位置发射火球 |
| 界迫击炮 | BoundaryMortar | 0.3 秒快速攻击；炮弹向随机方向偏移 3 格落地，落点生成一只小骷髅 |

## 环境要求

- Windows（本项目在 Windows + PowerShell 下开发）
- MySQL 5.7+（本地 3306）
- .NET 8（运行编译好的服务端，或从 `HashRoyale/src` 重新编译）
- Python 3（运行 Bot 与补丁脚本）
- Android SDK build-tools（`zipalign`/`apksigner`，签名 APK）
- 一台 Android 手机（真机测试；`adb` 安装 APK）

## 快速开始

### 1. 准备 MySQL

```powershell
# 启动本地 MySQL（或使用现有实例）
# 建库
mysql -u root -e "CREATE DATABASE rrdb2;"
```

### 2. 启动服务端

```powershell
.\start-server.ps1
# 主服 9339 / 集群 9876 / 战斗服 UDP 9449
```

首次启动会自动建表。玩家/账号数据存在 `rrdb2` 库的 `player` 表。

### 3. 启动匹配 Bot

```powershell
cd tools
python cr_bot.py bot_state.json
```

Bot 会登录账号（`bot_state.json`，格式见 `bot_state.example.json`）并进入 1v1 匹配队列，
对局中每 0.5s 下一张牌（卡组在 `cr_bot.py` 的 `BOT_DECK`，需与服务端玩家 2 的卡组一致）。

### 4. 客户端

客户端 APK 不包含在本仓库。获取 RetroRoyale 1.9.2 客户端后：

1. 用 `tools/make_*.py` 补丁脚本生成带自定义卡的 APK（脚本会同时改服务端 CSV 与客户端 APK）；
2. `zipalign` + `apksigner` 签名（使用 `tools/debug.keystore`，密码 `android`）；
3. `adb install -r clients\retroroyale-1.9.2-phone-modXX.apk` 安装；
4. 游戏内服务器地址需指向本机（192.168.x.x:9339）。

> **重要**：客户端必须包含玩家卡组中的**所有**卡，否则主界面渲染未知卡会闪退。
> 因此每次新增自定义卡后，都要从**包含全部已有自定义卡的最新 APK** 为基础重新构建。

## 自定义卡制作流程

1. 在服务端 `HashRoyale/app/GameAssets/csv_logic/*.csv` 加数据行（卡/角色/建筑/投射物/区域效果）；
2. 写补丁脚本（参考 `tools/make_boundary_zap_machine.py`）同步改客户端 APK 中 SC 压缩的 CSV 与文本；
3. 签名并安装，重启主服/战斗服/bot；
4. 把卡加进玩家卡组（`player` 表的 `Home.deck` JSON，classId：26=角色、27=建筑、28=法术）；
5. 训练营/1v1 实测。

## 目录结构

```text
HashRoyale/                服务端（源码 src/，编译产物 app/、app_battles/）
  app/                     主服：ClashRoyale.exe + GameAssets/csv_logic（数据表）
  app_battles/             战斗服（UDP 中继）
  src/                     C# 源码
tools/                     脚本与工具
  cr_bot.py                匹配/对战 Bot
  make_*.py                自定义卡补丁脚本
  frida_*.py               Frida 逆向研究脚本
  projectile_research.md   libg.so 投射物逆向研究记录
  debug.keystore           APK 签名证书（密码 android）
*.ps1 / *.bat              一键启动/停止脚本
ClashRoyale私服技术文档.md  完整开发/踩坑文档
学习路线.md                 学习笔记
```

## 自定义卡实现要点

- 1.9.2 的角色投射物只有 `ProjectileStartRadius`（沿朝向偏移），没有“世界坐标出生点”，
  数据层无法把投射物出生点定位到国王塔等任意位置（见 `projectile_research.md`）。
- “飞桶”类卡正确做法是 `spells_other` 法术卡 + 投射物（`spell_goblin_barrel.sc`），
  命中时 `SpawnCharacter` 生成容器；不要用“角色桶”（缺动画剪辑且会闪退）。
- 多单位/双效果可以用“容器链”：投射物 → 容器（DeployTime 引信）→ 死亡时 `DeathAreaEffect`/`DeathSpawnCharacter`。
- 客户端数据加载器会递归展开引用字段（实测确认：`Projectile`、`CustomFirstProjectile`、
  `SpawnCharacter`、`SpawnProjectile`），**任何“建筑→炮弹→建筑→炮弹…”的循环都会在加载期
  栈溢出闪退**（崩溃特征：libg.so 里 0x18130b / 0x1963ff 互相递归数百帧），所以 A↔B 互相
  召唤在纯数据里做不到；改造时要保证引用图是无环的（终点是角色/无引用的叶子节点）。
- `DeathSpawnCharacter=建筑` 加载期安全但运行时被静默忽略（两轮实测不生效）；
  `DeathAreaEffect` 触发自定义区域效果在进训练营时仍会被更深层加载展开，同样会崩。
- 随机方向落点用 `RandomAngle=360 + MinDistance=3000 + Homing=true`（界地狱龙滚木同款）；
  “落点生成单位”用投射物 `SpawnCharacter=角色`（哥布林飞桶同款，稳定可用）。
- `RandomAngle`/`RandomDistance` 只能随机投射物飞行/落点，不能随机出生点方向。
- 版本较老：精英野蛮人 = `AngryBarbarian`，幻影刺客 = `Assassin`，狂暴 = `BarbarianRage`。

## 版权声明

本仓库代码基于 MIT 许可的 HashRoyale/RetroRoyale 开源项目修改。游戏客户端与美术资源版权归
Supercell 所有；本仓库不包含客户端 APK 及其版权资源。请仅用于学习研究。
