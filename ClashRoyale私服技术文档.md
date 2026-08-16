# 皇室战争 1.9.2 私服完整技术文档

> 本文档完整记录从零搭建 Clash Royale 1.9.2 私服、编写匹配 Bot、以及制作自定义卡牌
> （觉醒冰人）的整个过程：架构、协议、数据格式、踩坑与最终方案。仅供个人学习研究。

---

## 1. 项目总览

### 1.1 组件与角色

| 组件 | 说明 |
|---|---|
| 客户端 | RetroRoyale 补丁版 Clash Royale **1.9.2**（包名 `com.retrocell.clashroyale`） |
| 主服务端 | HashRoyale（C# / .NET，RetroRoyale / ZrdRoyale 系 fork） |
| 战斗服务端 | `ClashRoyale.Battles`（UDP 中继 + 录像，**不模拟战斗**） |
| 数据库 | MySQL（库名 `rrdb2`，root 无密码） |
| 匹配 Bot | `tools/cr_bot.py`（协议级 bot，常驻 1v1 队列） |
| 真机 | 红米 K60（MIUI），通过 adb 调试 |

### 1.2 关键结论（先记住这三条）

1. **战斗由客户端本地模拟**：战斗服只负责把双方命令互相转发并记录录像，不做血量/伤害计算。
   因此改战斗玩法要改**客户端 APK 里的资源/逻辑**，服务端 CSV 只用于登录校验与主界面数据。
2. **必须用 RetroRoyale 补丁版客户端**：官方 1.9.2 会先发 `ClientHello(10100)` 等 `ServerHello`，
   而 HashRoyale 不实现该握手；补丁版直接发 `LoginMessage(10101)`（RC4 加密）。
3. **数据修改要"服务端 + 客户端"双端同步**：主服用 `HashRoyale/app/GameAssets` 下的 CSV，
   手机端用 APK `assets/csv_logic` 下的同名 CSV（SC 压缩格式）。

### 1.3 网络拓扑

```text
手机/客户端 ──TCP 9339──> 主服(HashRoyale) ──cluster 9876──> 战斗服(9449 UDP)
   │                          │                                    │
   │<──────TCP 9339───────────┘                                    │
   └──────────────UDP 9449（战斗命令直连战斗服）<────────────────────┘

Bot ──TCP 9339 + UDP 9449──> 主服/战斗服（与真机同协议，登录为独立账号）
MySQL 3306 <── 主服读写（player / clan 表）
```

### 1.4 目录结构

```text
ClashRoyal/
├── one-click-start.ps1        # 一键启动：MySQL→主服→战斗服→Bot→防火墙→装APK
├── start-server.ps1 / stop-server.ps1
├── 学习路线.md                 # 学习笔记（早期）
├── ClashRoyale私服技术文档.md  # 本文档
├── HashRoyale/                # 服务端源码 + 发布产物
│   ├── app/                   # 主服（ClashRoyale.exe + GameAssets + config.json）
│   ├── app_battles/           # 战斗服（ClashRoyale.Battles.exe）
│   └── src/                   # C# 源码
├── clients/                   # 各版本 APK（原版/补丁版/历次 mod）
└── tools/                     # 脚本与工具（见第 10 章）
```

---

## 2. 环境准备

### 2.1 PC 端

- Windows + PowerShell
- MySQL 8（本机放到 `%USERPROFILE%\cr-tools\mysql`，数据目录 `cr-tools\mysql-data`）
- .NET 8 runtime（跑编译好的 `ClashRoyale.exe`；源码编译需要 .NET SDK）
- Python 3（跑 Bot 与打包/分析脚本）
- Android SDK build-tools（`zipalign`、`apksigner`）与 platform-tools（`adb`）
- Java（apksigner 运行需要）

### 2.2 手机端

- 与 PC 同一局域网（本项目固定 `192.168.3.65`）
- 开启"开发者选项 → USB 调试"
- MIUI/HyperOS 安装 APK 时会弹"USB 安装提示"，需要点"继续安装"

---

## 3. 服务端部署与配置

### 3.1 源码与编译

参考 `HashRoyale/README.md`：

```bash
git clone https://github.com/Hashmane/HashRoyale.git
cd HashRoyale/src/ClashRoyale
dotnet publish -c Release -o ../../app
cd ../ClashRoyale.Battles
dotnet publish -c Release -o ../../app_battles
```

首次运行生成 `config.json`，编辑后再次运行才真正启动。

### 3.2 主服配置（`app/config.json`）

| 字段 | 本项目取值 | 说明 |
|---|---|---|
| `server_port` | 9339 | 客户端 TCP 端口 |
| `cluster_server_port` | 9876 | 主服↔战斗服内部端口 |
| `encryption_key` | `fhsd6f86f67rt8fw78fw789we78r9789wer6re` | RC4 静态密钥 |
| `mysql_server/database/user/password` | `127.0.0.1` / `rrdb2` / `root` / 空 | 数据库 |
| `udp_host` | `192.168.3.65` | **补丁新增**：下发战斗 UDP 地址用本机局域网 IP（否则手机连 127.0.0.1） |
| `use_udp` | true | 启用 UDP 战斗 |
| `DefaultGold/DefaultGems/DefaultLevel` | 100000 / 10000 / 13 | 新号初始资源 |
| `use_content_patch` | false | 不做网络内容补丁，资源全在 APK 里 |

### 3.3 战斗服配置（`app_battles/config.json`）

- `server_port = 9449`：UDP 战斗端口
- `battle_nonce = "nonce"`：与主服 cluster 加密 nonce 一致

### 3.4 数据库

库 `rrdb2` 只有两张表：

```sql
player(Id BIGINT PK, Trophies, Language, FacebookId, Home TEXT, Sessions TEXT)
clan(...)
```

玩家所有数据（卡组、宝箱、金币、宝石）都序列化在 `Home` 的 JSON 里。
卡牌条目示例（`BattleSpell.d` = ClassId×1,000,000 + InstanceId）：

```json
{"Count":1000,"InstanceId":58,"ClassId":26,"BattleSpell":{"d":26000058,"l":-1}}
```

### 3.5 启动/停止

```powershell
.\start-server.ps1    # MySQL → 主服 → 战斗服
.\stop-server.ps1     # 停主服/战斗服（保留 MySQL）
.\one-click-start.ps1 # 一键：全部服务 + Bot + 防火墙 + adb 安装/启动游戏
```

`one-click-start.ps1` 还做了：

- 检测端口 9339/9449/9876 是否已在监听，避免重复拉起；
- 自动给 Windows 防火墙添加 TCP 9339 / UDP 9449 规则；
- 用 `adb install -r --bypass-low-target-sdk-block` 安装 APK；
- 轮询 `uiautomator dump`，发现"继续安装"按钮就自动点击；
- 安装成功后用 `adb shell monkey` 启动游戏。

---

## 4. 客户端准备

### 4.1 为什么必须用补丁版客户端

官方客户端登录流程：`ClientHello(10100)` → 等 `ServerHello(20100)` 交换会话密钥。
HashRoyale 没有实现这套握手，所以官方 APK 改地址后登录直接失败（或提示
"you are using an unpatched client" / "请卸载并通过 Play Store 重新安装"）。

RetroRoyale 补丁版客户端：

- 跳过 ClientHello，直接发 RC4 加密的 `LoginMessage(10101)`；
- RC4 密钥 = `encryption_key + "nonce"`，**每条流先丢弃前 45 字节密钥流**；
- 内置服务器地址是已关闭的 `cluster.retroroyale.xyz`，需要改成本机 IP。

### 4.2 服务器地址补丁（`tools/patch_apk_lib.py`）

把 `lib/armeabi-v7a/libg.so`、`lib/x86/libg.so` 里的字节串
`cluster.retroroyale.xyz` **等长替换**为 `192.168.3.65 + \x00`（补零到原长度），
避免改动 ELF 节表。产物：`clients/retroroyale-1.9.2-phone-unsigned.apk`。

### 4.3 SC 资源容器格式

APK 里 `assets/sc/*.sc`（角色/建筑动画脚本）与 `assets/csv_*/*.csv`（数据表）
都是 Supercell 自定义压缩容器，解压后才能看到内容。

**`assets/sc/*.sc` 容器（版本 1）**：

```text
"SC" (2B) | version(4B BE=1) | hashLen(4B BE=16) | hash(16B)
        | uncompressedSize(4B LE) | LZMA props(5B) | LZMA 原始流
```

解压示例（Python）：

```python
import lzma
payload = data[10 + int.from_bytes(data[6:10], "big"):]   # 跳过 hash
props = payload[5:10]                                     # size(4)+props(5)
lc, lp, pb = props[0] % 9, (props[0] // 9) % 5, props[0] // 45
filters = [{"id": lzma.FILTER_LZMA1,
            "dict_size": int.from_bytes(props[1:5], "little"),
            "lc": lc, "lp": lp, "pb": pb}]
out = lzma.LZMADecompressor(format=lzma.FORMAT_RAW, filters=filters).decompress(payload[9:])
```

**`assets/csv_logic/*.csv`（以及 csv_client）**：

```text
LZMA props(5B) | dictSize(4B LE) | 原始大小(4B LE) | LZMA 原始流
```

脚本里常用 EOS 技巧直接解：

```python
def sc_decompress(data):
    return lzma.LZMADecompressor().decompress(data[:5] + b"\xff" * 8 + data[9:])

def sc_compress(text):
    raw = lzma.compress(text, format=lzma.FORMAT_RAW,
                        filters=[{"id": lzma.FILTER_LZMA1, "dict_size": 262144,
                                  "lc": 3, "lp": 0, "pb": 2}])
    return bytes([0x5D]) + (262144).to_bytes(4, "little") + len(text).to_bytes(4, "little") + raw
```

### 4.4 CSV 修改的坑

- `texts.csv` 是 **LF** 换行，其余 csv_logic 是 **CRLF**：追加行必须跟随原文件换行，
  否则客户端加载卡在 0%；
- 追加的行采用全字段带引号的写法（`"a","b","c"`）最稳；
- 修改脚本要**幂等**（已存在则跳过或原地更新），方便反复迭代。

### 4.5 重打包、签名、安装

```powershell
$bt = "$env:LOCALAPPDATA\Android\Sdk\build-tools\36.1.0"
& "$bt\zipalign.exe" -f 4 input-unsigned.apk aligned.apk
& "$bt\apksigner.bat" sign --ks tools\debug.keystore `
    --ks-pass pass:android --key-pass pass:android --out final.apk aligned.apk
adb install -r final.apk
```

`tools/debug.keystore` 是标准 Android debug 证书（密码 `android`），
重装同包名应用不需要卸载（`-r` 覆盖安装）。

---

## 5. 通信协议速览

### 5.1 TCP 帧（PiranhaMessage）

```text
消息ID(2B BE) | payload长度(3B BE) | 版本(2B BE) | payload(RC4 加密)
```

### 5.2 RC4

- 密钥：`fhsd6f86f67rt8fw78fw789we78r9789wer6re` + `"nonce"`
- 初始化后先丢弃 `len(key)`（45）字节密钥流
- **收发各一条独立流**；战斗 UDP 的每条 chunk payload 也是独立 RC4 流

### 5.3 基础编码

- `VInt`：Supercell 变长有符号整数（7 位一组，最高位续传，第 6 位为符号）；
- `ScString`：`长度(4B BE) + UTF-8 字节`。

### 5.4 消息 ID 速查

| ID | 名称 | 方向 | 说明 |
|---|---|---|---|
| 10100/20100 | ClientHello/ServerHello | C→S/S→C | 官方握手（本服不实现） |
| 10101 / 20104 / 20103 | Login / LoginOk / LoginFailed | C→S / S→C | 登录 |
| 24101 | OwnHomeData | S→C | 主城数据（卡组/宝箱/商店） |
| 24112 | UdpConnectionInfo | S→C | 战斗开始：UDP 地址/会话/队伍 |
| 14102 | EndClientTurn | C→S | 客户端回合（内含命令） |
| 12904 | SectorCommandMessage | UDP | 战斗命令块 |
| 21903 | SectorStateMessage | UDP | 战斗初始状态（卡组声明） |
| 20225 | BattleResult | S→C | 结算 |
| 10108 | KeepAlive | 双向 | 保活 |
| 25892 | Disconnected | S→C | 断开 |
| 14104 / 14107 | CollectFreeChest / CollectCrownChest | C→S | 领宝箱 |
| 509/511/516 | CollectFreeChest / CollectCrownChest / BuyChest | C→S | 命令 ID |

### 5.5 登录流程（补丁版客户端）

1. 客户端直接发 `LoginMessage(10101)`（账号 ID、token、版本、fingerprint 等）；
2. 服务端查库 → 回 `LoginOk(20104)` 或 `LoginFailed(20103)`；
3. 随后下发 `OwnHomeData(24101)` 等主界面数据。

### 5.6 匹配流程

1. 客户端发 `EndClientTurn(14102)`，里面带 `StartMatchmakeCommand(525)`；
2. 主服把队列里的双方配成 `LogicBattle`，各自收到 `UdpConnectionInfo(24112)`；
3. 双方用 UDP 向战斗服发 1400 字节注册包：

```text
[sessionId:8B BE][gameMode:1B][team/index:1B][0x00 填充到 1400B]
```

### 5.7 战斗 UDP 命令包

```text
[sessionId:8B BE][gameMode:1B][team:1B][ackCount:1B]
[chunkCount:vint]
每个 chunk：[seq:1B][消息ID:vint][payload长度:vint][RC4(payload)]
```

命令块 `SectorCommandMessage(12904)` 内部：

```text
[checksum:vint][sectorTick:vint][命令数:vint]
命令：[type:vint][clientTick:vint][checksum:vint][senderHi][senderLo] + 命令参数
```

部署卡牌是 `DoSpellCommand(type=1)`：

```text
[deckIndex:vint][cardClassId:vint][cardInstanceId:vint][spellIndex:vint]
[troopLevel:vint][x:vint][y:vint]
```

**关键约束**：`deckIndex` 必须指向对方客户端已声明的卡组槽位，且该卡必须在
"当前手牌"（卡组前 4 张的循环）里，否则命令被客户端**静默丢弃**。

---

## 6. 战斗相关修复（三冠结算等）

战斗服源码只有寥寥几个文件（`LogicBattle.cs`、`UdpMessageProcessor.cs`、
`Session*.cs`），全部改动都在这里。踩过的坑：

### 6.1 下兵无效 / 开局秒胜（UDP 块 RC4 失步）

- **现象**：客户端重传 UDP 包（同一 seq 发两遍），服务端把重传当新块又解了一次，
  RC4 流从此错位，后续命令全部乱码，`SectorCommandMessage` 解析抛异常；
- **修复**：`SessionContext.Process` 记录 `LastIncomingSeq`，重复 seq 跳过（不消耗 RC4）。

### 6.2 保活包误刷"战斗活跃" → 战斗永不结束

- 客户端每 ~2 秒发一个 count=0 的命令块才是活跃信号，10 字节保活包不算；
- 修复：只有真正处理命令块才刷新 `BattleActive`。

### 6.3 胜负判定

该 fork 战斗服不模拟战斗（塔血由客户端算），三冠后客户端停发命令块：

- 任一玩家超过 5 秒无命令块（且开战 >10 秒）→ 给**双方**发 `BattleFinishedMessage` 结算；
- 整场 240 秒兜底（3 分钟常规 + 1 分钟加时，原 180 秒会在加时前截断）。

---

## 7. 匹配 Bot（`tools/cr_bot.py`）

### 7.1 架构

```text
TCP 登录(id=2, token 存 bot_state.json) → 收到 OwnHomeData 后发
EndClientTurn+StartMatchmakeCommand(525) 常驻 1v1 队列
  → 收到 UdpConnectionInfo → 启动 UDP 对局线程
  → 对局结束(BattleResult 20225) → 立即重新排队
```

- 登录失败且已有 token 时：删除 state 文件重新注册新账号；
- TCP 断线自动重连；
- 对局线程：注册 UDP → 每 0.5 秒发一个命令块 → 240 秒后停止发命令让战斗自然结束。

### 7.2 Bot 出牌逻辑的迭代

1. **最初**：只发空命令块保活，bot 不下牌（方便先打通匹配/结算流程）；
2. **随机下牌**：随机卡牌/位置/等级，不看圣水不看卡组 —— 客户端不接受，被静默丢弃；
3. **按卡组槽位**：必须发**当前手牌**（卡组前 4 张循环）里的卡，出过的牌挪到队尾；
4. **圣水采集器优先**：卡组 8 张全建筑 `(27,1)..(27,8)`，采集器在槽位 7；
   出牌前检查采集器是否在手牌，在就优先放，否则随机；
5. **动态规划式修正**：避免"一直憋着只发采集器"导致整局不出牌 ——
   采集器在手牌才优先，否则立刻随机出牌。

### 7.3 关键常量

```python
BOT_DECK = [(27,1)..(27,8)]   # 8 张建筑，第 8 张是 ElixirCollector
COLLECTOR_SLOT = 7
BATTLE_DURATION = 240         # 秒
CMD_INTERVAL = 0.5            # UDP 命令块间隔
PLACE_INTERVAL = 0.5          # 出牌间隔
```

Bot 卡组必须与服务端为该账号保存的卡组一致（客户端只渲染已声明的卡槽）。

---

## 8. 数据修改与自定义内容

### 8.1 通用修改流程

```text
1) 改 HashRoyale/app/GameAssets/csv_logic/*.csv（服务端登录校验/主界面数据）
2) 同步改 APK assets/csv_logic/*.csv（客户端实际执行的数据）
3) 重新打包签名 → adb 安装 → 重启游戏
4) 服务端 CSV 改动需重启主服加载
```

### 8.2 圣水收集器（每 0.5 秒产 1 点圣水）

`buildings.csv` 的 `ElixirCollector` 行：

| 字段 | 原值 | 改后 |
|---|---|---|
| `ManaGenerateTimeMs` | 8500（8.5 秒/点） | **500**（0.5 秒/点） |
| `ManaCollectAmount` | 1 | 1（不变） |

### 8.3 商店礼包 → 宝箱解锁所有卡

先试过"商店里加一个解锁所有卡的礼包"，客户端点击购买无反应（商店购买链路未实现），
于是改走宝箱购买链路：`src/ClashRoyale/Logic/Home/Chests/Chests.cs` 的 `BuyChest()`：

```csharp
// 商店里任意 Giant 宝箱：10 金币 = 解锁全部卡
if (type == Chest.ChestType.Shop && mainchest.Name.StartsWith("Giant_"))
{
    if (!Home.UseGold(10)) return null;
    foreach (var card in Cards.GetAllCards())
    {
        var unlockCard = new Card(card.ClassId, card.InstanceId, true, 1000);
        unlockChest.Add(unlockCard);
        Home.Deck.Add(unlockCard);
    }
    return unlockChest;
}
```

### 8.4 给玩家加卡

直接改 MySQL：`UPDATE player SET Home = ... WHERE Id = 1;`，在 `Home.deck` 数组里加：

```json
{"Count":1000,"InstanceId":58,"ClassId":26,"BattleSpell":{"d":26000058,"l":-1}}
```

卡牌全局 ID = `ClassId × 1,000,000 + InstanceId`：

- ClassId 26 = 兵种卡（spells_characters.csv）
- ClassId 27 = 建筑卡（spells_buildings.csv）
- ClassId 28 = 法术卡（spells_other.csv）

---

## 9. 自定义卡牌：觉醒冰人（完整过程）

### 9.1 需求

以**戈仑冰人**（数据名 `IceGolemite`）为模板：

- 费用与数值一致（2 费、595 血、40 伤）；
- 新增特性：**每隔 1.5 秒在当前位置释放原戈仑冰人的亡语效果**
  （40 伤害 + 2 秒冰缓，半径 2000）。

### 9.2 第 1 版：纯数据字段 `SpawnAreaObject + SpawnInterval`（失败）

在 `characters.csv` 克隆出 `AwakenedIceGolem`，配置：

```text
SpawnStartTime = 0
SpawnInterval  = 1500
SpawnAreaObject = AwakenedFreeze      # FreezeIceGolemite 克隆 + Damage=40
```

**实测结果**：只在登场时触发一次。

原因：`SpawnAreaObject` 是"登场一次性"字段（冰法登场雷击同款机制），
引擎对区域效果**忽略 `SpawnInterval`**。

### 9.3 中间研究：Lua / SC 脚本到底管什么

怀疑周期性效果要改角色脚本 `assets/sc/chr_snowman.sc`，于是逆向该文件：

- 解压后是 Supercell 自定义字节码（魔数 `56 01 36 00`），不是标准 Lua 5.1；
- 文件 = 头(19B) + u16 元数据表 + 长度前缀字符串表（动画名如
  `snowman_red_attack1_1`）+ 代码段，字符串明文、代码里带 `action_frame` 等标识；
- 对比 `chr_archer.sc` / `spell_goblin_barrel.sc` 等，确认是**动画状态机脚本**；
- 在 `libg.so` 里 grep 到 `SpawnAreaObject` / `SpawnCharacter` / `SpawnInterval` /
  `DeathAreaEffect` 等字符串 → **战斗逻辑在原生 C++（libg.so），Lua/SC 只负责动画**。

结论：改 Lua 没用，必须在数据字段层面实现，或者改原生库（代价过高）。

### 9.4 第 2 版：隐形角色傀儡 + `SpawnAreaObject`（半失败）

改用夜巫（Witch）同款**周期召唤**机制：

```text
AwakenedIceGolem: SpawnCharacter=AwakenedIcePulse, SpawnInterval=1500,
                  SpawnNumber=1, SpawnPauseTime=1500, SpawnRadius=0
AwakenedIcePulse(角色): SpawnAreaObject=AwakenedFreeze, LifeTime=100, HP=1, Scale=1
```

**实测结果**：每 1.5 秒确实闪出一个血条然后消失，但**没有任何冰爆效果**。

原因：

1. `SpawnCharacter` 生成出来的单位**不会触发自己的 `SpawnAreaObject`**
   （登场区域效果只对玩家部署的单位生效）；
2. `LifeTime` 到期只是"移除"单位，不走死亡逻辑，自然也没有任何效果。

### 9.5 第 3 版：无血量建筑 + DeployTime 引信（成功）

研究原版数据发现现成机制：

- **巨骷髅炸弹** `GiantSkeletonBomb`：建筑、**无 Hitpoints**、`DeployTime=3000` 即引信，
  到点自动死亡并触发 `DeathDamage=720`；
- **狂暴瓶** `RageBarbarianBottle`：建筑、无血量、`DeployTime=500`，
  死亡时触发 `DeathAreaEffect=BarbarianRage`。

于是把脉冲单位改成**建筑**：

```text
AwakenedIcePulse(buildings.csv, 克隆 RageBarbarianBottle):
  DeployTime=100          # 100ms 引信，几乎瞬爆
  Hitpoints=(空)          # 无血量 → 到点自动死亡
  DeathDamage=40
  DeathDamageRadius=2000
  DeathAreaEffect=FreezeIceGolemite   # 原版冰人亡语的冰缓区域！
  DeathEffect=snowman_die             # 原版冰人死亡特效
  Scale=1                # 隐形
```

**实测结果**：冰爆效果出现了，每 1.5 秒一次 ✅ —— 但脉冲单位有碰撞体积，
把冰人本体挤开了。

### 9.6 第 4 版：消除碰撞（完成）

建筑是"不可推动"的，和冰人重叠时会把冰人挤走。把脉冲的
`CollisionRadius` 从 100 改成 **0**（无碰撞），重建安装后冰人不再被挤开。

### 9.7 最终字段一览

**`AwakenedIceGolem`（characters.csv，克隆 IceGolemite）**

| 字段 | 值 | 说明 |
|---|---|---|
| `Rarity/Cost` | Rare / 2 | 与样本一致 |
| `Hitpoints/Damage` | 595 / 40 | 与样本一致 |
| `SpawnStartTime` | 0 | 立即开始周期 |
| `SpawnInterval` | 1500 | 1.5 秒 |
| `SpawnNumber` | 1 | 每次 1 个 |
| `SpawnPauseTime` | 1500 | 周期间隔（勿设 0，行为不确定） |
| `SpawnCharacter` | AwakenedIcePulse | 召唤脉冲 |
| `SpawnCharacterLevelIndex` | 1 | |
| `SpawnRadius` | 0 | 生成在自身位置 |
| `DeathAreaEffect/DeathDamage` | FreezeIceGolemite / 40 | 保留原版死亡行为 |

**`AwakenedIcePulse`（buildings.csv，克隆 RageBarbarianBottle）**

| 字段 | 值 | 说明 |
|---|---|---|
| `DeployTime` | 100 | 引信，100ms 后死亡 |
| `Hitpoints` | （空） | 无血量 |
| `DeathDamage` | 40 | 原版亡语伤害 |
| `DeathDamageRadius` | 2000 | 原版亡语半径 |
| `DeathAreaEffect` | FreezeIceGolemite | 2 秒冰缓区域 |
| `DeathEffect` | snowman_die | 原版死亡特效 |
| `CollisionRadius` | 0 | 无碰撞，不推挤本体 |
| `Scale` | 1 | 隐形 |

**`AwakenedFreeze`（area_effect_objects.csv）**：第 1 版产物（FreezeIceGolemite 克隆
+ `Damage=40`），当前版本实际使用原版 `FreezeIceGolemite`，伤害由脉冲的
`DeathDamage` 提供。

### 9.8 配套脚本

- `tools/create_awakened_ice_golem.py`：v1（SpawnAreaObject 版），含服务端+客户端双端补丁；
- `tools/make_awakened_ice_pulse.py`：v2（角色傀儡版），幂等；
- `tools/make_awakened_ice_bomb.py`：v3/v4（建筑炸弹版，`CollisionRadius=0`），幂等。

### 9.9 相关 CSV 换行/压缩注意点

- 追加行必须用 `"全字段引号"` 并跟随原文件换行（CRLF）；
- 修改后重压 SC 再写回 APK；
- 客户端卡在 0% 大概率是 CSV 换行或 SC 压缩参数不对，可用 `bisect_apk.py`
  二分定位是 texts 还是 cards 变更导致加载失败。

## 10. 自定义卡牌：界炸弹兵（Boundary Bomber）

### 10.1 需求

以**炸弹兵**（数据名 `Bomber`）为模板，数值与费用一致（3 费、147 血、128 弹伤、
1900ms 攻速、4500 射程），新增特性：

> 锁定目标后，每次丢出炸弹时，同时生成一发"火箭"飞向目标点。

### 10.2 实现思路：多弹攻击机制

1.9.2 的角色攻击**每发投射物都从单位自身出生**（`ProjectileStartRadius` 只是
朝目标方向的偏移），没有数据字段能把投射物起点设到国王塔。真正"从国王塔发射"
需要改原生引擎（`libg.so`）。

退而求其次、且效果最接近的是**公主同款多弹攻击**：

```text
MultipleProjectiles = 2          # 每次攻击发射 2 发
CustomFirstProjectile = BoundaryRocket   # 第 1 发 = 火箭
Projectile = BombSkeletonProjectile      # 第 2 发 = 原版炸弹
```

这样每次攻击同时出现"炸弹抛物线 + 火箭尾迹（Rocket_Emitter）飞向目标"，火箭带
爆炸特效与大范围伤害，视觉上就是"丢炸弹时多了一发火箭"。

### 10.3 数据改动

**`BoundaryRocket`（projectiles.csv，克隆 `RocketSpell`）**

| 字段 | 值 | 说明 |
|---|---|---|
| `ExportName` | projectile_rocket | 原版火箭 3D 模型 |
| `HitEffect` | Rocket_explosion | 火箭爆炸特效 |
| `TrailEffect` | Rocket_Emitter | 火箭尾迹 |
| `Damage` | 128 | 与炸弹持平，保持卡牌平衡 |
| `Radius` | 2000 | 爆炸半径 |
| `Gravity` | 50 / `use360Frames`=true | 原版火箭弹道 |
| `CrownTowerDamagePercent` | -60 | 对塔伤害打折（保留火箭身份） |

**`BoundaryBomber`（characters.csv，克隆 Bomber）**

```text
Projectile = BombSkeletonProjectile   # 保留原版炸弹
CustomFirstProjectile = BoundaryRocket
MultipleProjectiles = 2
其余数值与 Bomber 完全一致
```

**卡牌（spells_characters.csv，克隆 Bomber）**：3 费，`SummonCharacter=BoundaryBomber`，
TID 指向新增文案（CN：界炸弹兵 / EN：Boundary Bomber）。

**玩家收藏**：`ClassId=26, InstanceId=59`（`d=26000059`）已在 Home JSON 中，
加卡后即可在卡组编辑器里使用。

### 10.4 配套脚本

- `tools/make_boundary_bomber.py`：一次性完成 服务端（spells_characters /
  characters / projectiles）+ 客户端（同上 + texts）双端补丁，幂等。

### 10.5 已知限制与后续

- 火箭从炸弹兵本体发射，不是国王塔；要做到"国王塔出生"需要逆向 `libg.so`
  修改投射物出生点逻辑（或 Hook 客户端）；
- 若希望火箭伤害/爆炸半径更像原版火箭（700 伤 / 2000 半径），改
  `BoundaryRocket.Damage` 即可，但要接受卡牌强度变化。

---

## 10. 调试工具箱

| 脚本 | 用途 |
|---|---|
| `tools/patch_apk_lib.py` | 把 libg.so 里的服务器域名等长替换成局域网 IP |
| `tools/bisect_apk.py` | 二分定位"哪类 CSV 改动导致客户端加载失败" |
| `tools/serverhello_probe.py` | 迷你 TCP 服务端，探测客户端首包（握手/登录） |
| `tools/rc4_analyze.py` / `rc4_scan.py` | 分析/猜测 RC4 密钥与密钥流 |
| `tools/capture_listener.py` | 监听 UDP 战斗流量 |
| `tools/cr_bot.py` | 匹配/对战 Bot |
| `tools/tap_text.py` | 按文本自动点击（配合 uiautomator dump） |

常用 adb 命令：

```powershell
adb devices
adb install -r app.apk
adb shell am force-stop com.retrocell.clashroyale
adb shell am start -n com.retrocell.clashroyale/com.supercell.clashroyale.GameApp
adb shell uiautomator dump /sdcard/ui.xml && adb shell cat /sdcard/ui.xml
adb exec-out screencap -p > screen.png
```

日志位置：

```text
HashRoyale/main-server.log        主服消息/命令日志（含 EncodeAttack、RAW-DUMP）
HashRoyale/battle-server.log      战斗服 UDP 命令日志
HashRoyale/main-server.err.log    主服错误
tools/cr_bot.log                  Bot 日志
```

---

## 11. 踩坑记录（按对话时间线）

| 问题 | 原因 | 解决 |
|---|---|---|
| 登录失败：you are using an unpatched client | 官方客户端无内容补丁 | 换 RetroRoyale 补丁版 APK |
| 检测到未成功安装，请从 Play Store 重装 | 包名/签名不符或资源不完整 | 用 `com.retrocell.clashroyale` 补丁包覆盖安装 |
| 登录失败，请稍后再次尝试 | 服务器/防火墙/RC4 配置问题 | 检查 9339 监听、防火墙规则、`encryption_key` 一致 |
| 弹"重试"太久 | 客户端失败后一直等待 | 等几秒无响应自动 force-stop 重启 |
| Bot 开局没多久直接获胜 | 战斗服把重传 UDP 块当新块解密（RC4 失步） | 按 seq 跳过重复块 |
| 手机端下兵没反应 | 命令未按客户端手牌/槽位规则 | deckIndex 必须指向已声明卡槽且在手牌中 |
| 三冠后不弹结算 | 战斗服不知道对局已结束 | 5 秒无命令块→双端结算 + 240 秒兜底 |
| Bot 不下牌/牌没到手机 | 乱发不在手牌的卡被静默丢弃 | 维护手牌循环，只发前 4 槽的卡 |
| 采集器不优先 | 只在"手牌有采集器"时才优先，否则随机 | 动态判断手牌后决策 |
| 邮件内容全是问号 | 中文经管道编码丢失 | 直接写 UTF-8 HTML 文件再 `--html-file` 发送 |
| 新卡效果只触发一次 | `SpawnAreaObject` 登场一次性，忽略 `SpawnInterval` | 改周期召唤 + 建筑引信死亡触发 |
| 脉冲单位把冰人挤开 | 建筑不可推动，重叠时推开本体 | `CollisionRadius=0` |
| 界炸弹兵火箭起点 | 1.9.2 无"投射物出生点"数据字段 | 用多弹攻击近似（火箭从本体发射），
  真"从国王塔发射"需改原生引擎 |

---

## 12. 文件清单

```text
one-click-start.ps1 / start-server.ps1 / stop-server.ps1   启动脚本
HashRoyale/app/config.json                                 主服配置
HashRoyale/app_battles/config.json                         战斗服配置
HashRoyale/app/GameAssets/csv_logic/*.csv                  服务端数据表
clients/retroroyale-1.9.2.apk                              下载的补丁版客户端
clients/retroroyale-1.9.2-phone.apk                        已改服务器地址的基础包
clients/retroroyale-1.9.2-phone-mod4.apk                   最新完整包（觉醒冰人+采集器）
tools/cr_bot.py                                            匹配/对战 Bot
tools/make_awakened_ice_bomb.py                            觉醒冰人 v3/v4 补丁
tools/make_boundary_bomber.py                              界炸弹兵补丁（多弹攻击）
tools/debug.keystore                                       APK 签名证书
```

## 13. 后续可做的事

- 若要让脉冲中心严格贴合冰人且完全无碰撞，可再研究 `SpawnProjectile`（无实体单位，
  但 1.9.2 中无角色使用先例，需实验）；
- 把自定义卡做成完整的多级数值（等级缩放、描述文案）；
- 深入逆向 `libg.so`，把 `SpawnAreaObject` 改成真正周期性触发；
- 给 Bot 加真正的"对战策略"（进攻路线、圣水管理、解卡）。

---

## 14. 界炸弹兵"火箭从国王塔发射"——Frida 逆向进展

> 时间：2026-08-16（手机端，Frida Gadget 注入）

### 14.1 为什么数据层做不到

1.9.2 的角色投射物出生点只有 `ProjectileStartRadius`（沿单位朝向偏移的静态值）、
`ProjectileYOffset`、`ProjectileStartZ`，没有"世界坐标出生点"字段；投射物出生点写死在
`libg.so` 的创建逻辑里，随发射者朝向变化。数据层只能做到"从炸弹兵身后偏移"。

### 14.2 Frida 注入方案（已完成）

- `GameApp.smali` 在 `loadLibrary("g")` 后追加 `loadLibrary("frida-gadget")`；
- Gadget 16.7.19（17.17.0 会 SIGSEGV），监听 `127.0.0.1:27042`，`adb forward` 转发；
- 配置必须是 `{"interaction":{"type":"listen","address":"127.0.0.1","port":27042,"on_load":"resume"}}`
  （放 `libfrida-gadget.config.so`），否则冷启动灰屏；
- 当前 APK：`clients/retroroyale-1.9.2-phone-mod7-gadget.apk`。

### 14.3 libg.so 静态分析结论

- **文件没有加密**：早期"反汇编全是乱码"是脚本把段基址加了两次；按 Thumb 偶数对齐后可直接反汇编；
- 游戏字符串（`LogicProjectile::init called twice?`、`ProjectileStartRadius` 等）**没有直接静态引用**
  （无 movw/movt、ADR、字面量池指针、重定位），运行时模块数据区也没有指向它们的指针——
  字符串通过"全局基址 + 偏移"的运行时表间接解析；
- 游戏不直接 BL 调 `operator new`（1.49M 条指令中无 `bl _Znwj`），分配走私有分配器/虚方法间址，
  所以只能动态定位。

### 14.4 动态定位结果：投射物对象 = 虚表 0x502fb8

战斗中每 12 秒释放约 712 次（≈31/秒）的虚表 `0x502fb8` 对象，分配大小 0x84/0x98，
销毁链直达战斗 tick。经 `.rel.dyn` 重定位解析其虚表方法：

- vtable[21] (0x927e0)：把起点/终点写入 `+0x68..0x74`；
- **vtable[28] (0x927f0)：逐帧插值 tick**——起点 `+0x68/+0x6c` → 终点 `+0x70/+0x74`，
  结果写回当前位置 `+0x58/+0x5c`，再调用 0x23d494 更新父对象；速度在 `+0x54`；
- vtable[29] (0x92978)：比较当前位置，写 `+4` 到达标志。

结论：**把投射物对象的 `+0x68/+0x6c`（起点）和 `+0x58/+0x5c`（当前）覆盖为己方国王塔坐标，
火箭就会从塔飞向目标。** 国王塔坐标可从"己方塔射出的投射物"的起点字段自动缓存
（塔会自动攻击 bot 单位）。

### 14.5 待办（手机回来后）

1. 重新扫描 `BoundaryRocket` 的 ProjectileData 地址（ASLR 每进程不同）；
2. 挂 vtable[28]，dump 存活投射物，确认对象中指向 ProjectileData 的字段偏移；
3. 用 `tools/frida_rocket_hook.py --calibrate` 校准 → `--apply` 正式覆盖；
4. 备选：限速回溯抓创建链，直接在创建时覆盖，效果更干净；
5. 微调速度/进度字段，避免火箭因路径变长而提前到位。

### 14.6 工具与脚本

- `tools/frida_alloc_hist.py`：分配尺寸直方图（轻量）；
- `tools/frida_bt_capture.py`：指定尺寸分配回溯（须限速，否则拖死游戏）；
- `tools/frida_vtable_collect.py` / `frida_free_bt.py` / `frida_obj_size.py`：虚表收集/释放回溯/分配释放配对；
- `tools/frida_find_data.py`：堆中字符串与数据对象定位；
- `tools/frida_rocket_hook.py`：火箭起点覆盖（校准/应用两模式）；
- `tools/projectile_research.md`：完整研究记录。

### 14.7 踩坑备忘（Frida）

- 高频 `Thread.backtrace` 会拖死游戏/设备（曾致灰屏与 adb 掉线），必须限速/采样；
- Python 会话被超时杀掉会留下僵尸会话卡死 Gadget，需重启游戏进程；
- adb 偶发卡死：`adb kill-server` 重连；Gadget 卡死只能重启游戏；
- 手机当前 Bot 卡组为 8×界炸弹兵（MySQL player id=2 已同步）。

---

## 15. 后续自定义卡牌（2026-08-16）

### 15.1 关键教训：客户端必须认识卡组里的所有卡

排查多次“进游戏 60~120 秒必闪退”后确认根因：**客户端在渲染玩家卡组时，遇到自己数据里
不存在的卡就会空指针闪退**（主界面更新链，libg+0x19ba64 一带）。因此：

- 每张加入玩家卡组的自定义卡，客户端 APK 里必须存在对应数据；
- 每次新增自定义卡，都要以**包含全部已有自定义卡的最新 APK**为基础重新构建
  （例如 mod18 = mod15 + 界电磁炮；mod31 = mod30 + 界地狱塔），不能从旧包往上加。

### 15.2 一条龙服务（OneStopService）最终实现

前几版用“角色桶”失败（缺动画剪辑闪退、死亡召唤不触发、除零崩溃）。最终按**原版哥布林飞桶逻辑**：

- `spells_other.csv` 法术卡：`Projectile=OneStopBarrelSpell`，`Effect=goblin_barrel_spawn`，`OnlyEnemies`；
- `projectiles.csv`：OneStopBarrelSpell = GoblinBarrelSpell 克隆（真桶模型 `spell_goblin_barrel.sc`），
  命中时 `SpawnCharacter=OneStopBarrelSpawner`；
- `buildings.csv`：隐形容器 → 落地瞬间 `SpawnCharacter=AngryBarbarian×2`，DeployTime=100 引信
  → 死亡 `DeathSpawnCharacter=FireSpirits×3` + `DeathAreaEffect=BarbarianRage`。

### 15.3 界电磁炮（BoundaryZapMachine）

- ZapMachine 克隆；攻击投射物 = BoundaryZapMachineProjectile（ZapMachineProjectile 克隆，
  `SpawnAreaEffectObject=Lightning`，Damage=0）——子弹落地直接释放 6 费大闪电；
- 电击走容器链：命中生成 BoundaryZapContainer（DeployTime=100 → `DeathAreaEffect=Zap`）；
- 蓄力减半：LoadTime 4500→2250，HitSpeed 5000→2500。

### 15.4 界气球兵（BoundaryBalloon）

- Balloon 克隆 + 复制 Assassin（幻影刺客）突刺字段：DashMinRange=4000、DashMaxRange=30000（全图）、
  SightRange=30000（全图视野）、DashDamage=320、DashCooldown=800、DashImmuneToDamageTime=100。

### 15.5 界地狱飞龙（BoundaryInfernoDragon）

- InfernoDragon 克隆；Damage=0/VariableDamage2=0；
- 每次攻击发射复仇滚木：`Projectile=BoundaryLogProjectileAir`（LogProjectile 克隆 +
  RandomAngle=360 + Homing=true + AoeToAir=true），滚动段 LogProjectileRollingAir 也 AoeToAir=true；
- 出生点偏移 `ProjectileStartRadius=-20000`（沿朝向，数据层无法随机出生方向——`RandomAngle` 只能随机飞行）。

### 15.6 界地狱塔（BoundaryInfernoTower）

- InfernoTower 建筑克隆（`spells_buildings.csv` 卡 + `buildings.csv` 建筑）；
- 攻击投射物 = BoundaryFireballProjectile（FireballSpell 克隆 + RandomAngle=360 + RandomDistance=4000），
  每次攻击向塔周围随机位置发射火球；塔自身 Damage=0。

### 15.7 新增卡牌补丁脚本

- `tools/make_onestop_service.py`（一条龙服务）
- `tools/make_boundary_zap_machine.py`（界电磁炮）
- `tools/make_boundary_balloon.py`（界气球兵）
- `tools/make_boundary_inferno_dragon.py`（界地狱飞龙）
- `tools/make_boundary_inferno_tower.py`（界地狱塔）

每个脚本幂等：改服务端 CSV + 客户端 APK（SC 压缩 CSV/文本），再 zipalign+apksigner 签名。
卡组条目写入 `player.Home.deck`（classId：26=角色、27=建筑、28=法术）。
