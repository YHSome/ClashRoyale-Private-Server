#!/usr/bin/env python3
"""HashRoyale (Clash Royale 1.9.2) matchmaking bot.

Logs in as a dedicated bot account, stays in the 1v1 matchmaking queue, and
when matched keeps the battle alive by sending empty sector commands over UDP
for a fixed duration, then re-enters matchmaking.

Protocol notes (from HashRoyale source):
  * TCP frame : [id:2][len:3][ver:2][payload], len = payload length
  * RC4 key   : "fhsd6f86f67rt8fw78fw789we78r9789wer6re" + "nonce",
                discard the first key-length PRGA bytes once per stream
  * Login     : id 10101, version 3
  * Matchmake : EndClientTurn(14102) containing StartMatchmakeCommand(525)
  * UDP reg   : 1400-byte packet [sessionId:8][gameMode:1][team:1][padding]
  * UDP cmd   : [sessionId:8][gameMode:1][team:1][ack:1][chunkCount:vint]
                then per chunk [seq:1][id:vint][len:vint][RC4(payload)]
"""

import json
import os
import random
import socket
import struct
import sys
import threading
import time

MAIN_HOST = "192.168.3.65"
MAIN_PORT = 9339

RC4_KEY = b"fhsd6f86f67rt8fw78fw789we78r9789wer6re" + b"nonce"

STATE_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    sys.argv[1] if len(sys.argv) > 1 else "bot_state.json",
)

BATTLE_DURATION = 240  # seconds the bot stays in a battle (3 min + 1 min overtime)
CMD_INTERVAL = 0.5  # seconds between UDP sector commands
PLACE_INTERVAL = 0.5  # seconds between card-drop attempts (client has no elixir check)

# The bot's 8-card deck. MUST match the deck stored for player id=2 on the
# server (the client only renders cards that match a declared deck slot).
# The client only accepts commands for cards that are in the current hand
# (the first 4 cards of the deck cycle), so we always play from the hand and
# move the played card to the back. The ElixirCollector stays in its natural
# slot and gets prioritized whenever it cycles into the hand.
# 8 buildings (classId 27): Cannon, GoblinHut, Mortar, InfernoTower,
# BombTower, BarbarianHut, Tesla, ElixirCollector.
BOT_DECK = [
    (27, 1), (27, 2), (27, 3), (27, 4),
    (27, 5), (27, 6), (27, 7), (27, 8),
]

COLLECTOR_SLOT = 7  # ElixirCollector (27:8) sits in the last deck slot


# ---------------------------------------------------------------- RC4
class Rc4:
    def __init__(self, key: bytes, discard: int):
        s = list(range(256))
        j = 0
        for i in range(256):
            j = (j + s[i] + key[i % len(key)]) & 0xFF
            s[i], s[j] = s[j], s[i]
        self.s = s
        self.i = 0
        self.j = 0
        for _ in range(discard):
            self.prga()

    def prga(self) -> int:
        self.i = (self.i + 1) & 0xFF
        self.j = (self.j + self.s[self.i]) & 0xFF
        self.s[self.i], self.s[self.j] = self.s[self.j], self.s[self.i]
        return self.s[(self.s[self.i] + self.s[self.j]) & 0xFF]

    def crypt(self, data: bytes) -> bytes:
        return bytes(b ^ self.prga() for b in data)


# ---------------------------------------------------------------- VInt / ScString
def write_vint(value: int) -> bytes:
    value &= 0xFFFFFFFF
    if value >= 0x80000000:
        value -= 0x100000000
    temp = (value >> 25) & 0x40
    flipped = value ^ (value >> 31)
    temp |= value & 0x3F
    value >>= 6
    flipped >>= 6
    if flipped == 0:
        return bytes([temp & 0xFF])
    out = bytearray([(temp | 0x80) & 0xFF])
    while True:
        flipped >>= 7
        out.append((value & 0x7F) | (0x80 if flipped else 0))
        value >>= 7
        if flipped == 0:
            break
    return bytes(out)


def read_vint(buf: bytes, pos: int):
    b = buf[pos]
    pos += 1
    sign = (b >> 6) & 1
    i = b & 0x3F
    offset = 6
    for _ in range(4):
        if not (b & 0x80):
            break
        b = buf[pos]
        pos += 1
        i |= (b & 0x7F) << offset
        offset += 7
    if b & 0x80:
        return -1, pos
    if sign == 1 and offset < 32:
        i |= 0xFFFFFFFF << offset
    return i, pos


def scstring(value: str) -> bytes:
    data = value.encode("utf-8")
    return struct.pack(">i", len(data)) + data


def read_scstring(buf: bytes, pos: int):
    (length,) = struct.unpack_from(">i", buf, pos)
    pos += 4
    if length <= 0 or length > 900000:
        return "", pos
    return buf[pos : pos + length].decode("utf-8", errors="replace"), pos + length


# ---------------------------------------------------------------- TCP framing
class Client:
    def __init__(self):
        self.sock = None
        self.out_rc4 = None  # client -> server stream
        self.in_rc4 = None   # server -> client stream
        self.home_t0 = None  # when OwnHomeData received (for tick tracking)

    def connect(self):
        self.sock = socket.create_connection((MAIN_HOST, MAIN_PORT), timeout=10)
        self.sock.settimeout(10)
        self.out_rc4 = Rc4(RC4_KEY, len(RC4_KEY))
        self.in_rc4 = Rc4(RC4_KEY, len(RC4_KEY))
        self.home_t0 = None
        self._last_ka = 0.0

    def send_message(self, mid: int, payload: bytes, version: int = 0):
        enc = self.out_rc4.crypt(payload)
        frame = struct.pack(">H", mid) + len(enc).to_bytes(3, "big") + struct.pack(">H", version) + enc
        self.sock.sendall(frame)

    def recv_message(self):
        """Returns (mid, version, payload) or None on socket timeout."""
        head = b""
        try:
            while len(head) < 7:
                chunk = self.sock.recv(7 - len(head))
                if not chunk:
                    raise ConnectionError("closed")
                head += chunk
        except socket.timeout:
            return None
        mid = struct.unpack(">H", head[0:2])[0]
        length = int.from_bytes(head[2:5], "big")
        version = struct.unpack(">H", head[5:7])[0]
        payload = b""
        try:
            while len(payload) < length:
                chunk = self.sock.recv(length - len(payload))
                if not chunk:
                    raise ConnectionError("closed")
                payload += chunk
        except socket.timeout:
            raise ConnectionError("partial frame timeout")
        return mid, version, self.in_rc4.crypt(payload)

    def close(self):
        try:
            self.sock.close()
        except Exception:
            pass


# ---------------------------------------------------------------- message builders
def build_login(user_id: int, token: str) -> bytes:
    p = struct.pack(">q", user_id)
    p += scstring(token)
    p += write_vint(3)   # major
    p += write_vint(0)   # minor
    p += write_vint(377)  # build
    p += scstring("62e9d186487cc657aad6466c05d081e6b49e4023")
    p += struct.pack(">i", 0)  # ignored int
    p += scstring("bot-udid-0001")
    p += scstring("00:11:22:33:44:55")
    p += scstring("BotPhone")
    p += scstring("")
    p += scstring("13")
    p += b"\x01"  # isAndroid
    p += scstring("")  # ignored
    p += scstring("crbot0001")
    p += scstring("zh-CN")
    return p


def build_end_turn(tick: int) -> bytes:
    # EndClientTurn: [tick][ignore][count=1] + command 525 (StartMatchmake)
    p = write_vint(tick)
    p += write_vint(0)
    p += write_vint(1)
    p += write_vint(525)
    p += write_vint(0)  # command tick
    p += write_vint(0)  # command ignore
    p += write_vint(0)
    p += write_vint(0)
    p += b"\x00"  # Is2V2 = false
    return p


def build_dospell(tick: int, player_low_id: int, deck_slot: int) -> bytes:
    """Build a SectorCommandMessage chunk with one DoSpellCommand (type 1)."""
    # The enemy client only renders cards that were declared in the battle's
    # SectorState deck, so the card must match the deck slot. Level and
    # position stay fully random; elixir is ignored.
    card_class, card_instance = BOT_DECK[deck_slot]
    troop_level = random.randrange(1, 14)
    # Keep placements inside the arena (x ~ 0..14000, y ~ 0..18000);
    # the client silently drops enemy placements that are off the map.
    x = random.randrange(2500, 12000)
    y = random.randrange(2500, 12500)
    p = write_vint(0)  # sector checksum
    p += write_vint(tick)  # sector tick
    p += write_vint(1)  # command count
    p += write_vint(1)  # command type: DoSpell
    p += write_vint(tick)  # client tick
    p += write_vint(-1)  # command checksum
    p += write_vint(0)  # sender high id
    p += write_vint(player_low_id)  # sender low id
    # Deck index must point at the card's actual slot in the enemy deck
    # (0-based). The client drops commands whose card does not match the
    # declared deck slot.
    p += write_vint(deck_slot)  # deck index = card slot
    p += write_vint(card_class)  # card class id
    p += write_vint(card_instance)  # card instance id
    p += write_vint(-1)  # spell index
    p += write_vint(troop_level)  # troop level
    p += write_vint(x)  # x
    p += write_vint(y)  # y
    return p


# ---------------------------------------------------------------- UDP battle
class UdpBattle(threading.Thread):
    def __init__(self, host: str, port: int, session_id: int, gamemode: int, index: int, player_low_id: int):
        super().__init__(daemon=True)
        self.host = host
        self.port = port
        self.session_id = session_id
        self.gamemode = gamemode
        self.index = index
        self.player_low_id = player_low_id
        self.battle_start = time.time()
        self.next_place = time.time() + PLACE_INTERVAL
        self.stop_at = time.time() + BATTLE_DURATION
        # Deck cycle: the "hand" is the first 4 slots; played cards go to the
        # back, just like a real deck cycle. Never play a card that is not in
        # the hand, otherwise the client treats the command as invalid.
        self.deck_cycle = list(range(len(BOT_DECK)))

    def pick_slot(self) -> int:
        """Choose the next card: ElixirCollector whenever it is in the hand;
        only fall back to a random card when the collector is not an option."""
        hand = self.deck_cycle[:4]
        if COLLECTOR_SLOT in hand:
            return COLLECTOR_SLOT
        return random.choice(hand)

    def play_slot(self, slot: int) -> None:
        self.deck_cycle.remove(slot)
        self.deck_cycle.append(slot)

    def run(self):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(5)
            # registration packet: exactly 1400 bytes
            reg = struct.pack(">q", self.session_id) + bytes([self.gamemode, self.index])
            reg += b"\x00" * (1400 - len(reg))
            sock.sendto(reg, (self.host, self.port))
            log("UDP registered session=%d index=%d on %s:%d" % (self.session_id, self.index, self.host, self.port))

            rc4 = Rc4(RC4_KEY, len(RC4_KEY))
            seq = 1
            while time.time() < self.stop_at:
                tick = int((time.time() - self.battle_start) * 20)
                if time.time() >= self.next_place:
                    slot = self.pick_slot()
                    self.play_slot(slot)
                    chunk_payload = build_dospell(tick, self.player_low_id, slot)
                    self.next_place = time.time() + PLACE_INTERVAL
                else:
                    # SectorCommandMessage(12904) with 0 commands keeps BattleActive fresh
                    chunk_payload = b"\x00\x00\x00"
                enc = rc4.crypt(chunk_payload)
                packet = struct.pack(">q", self.session_id)
                packet += bytes([self.gamemode, self.index, 0])  # team, ackCount=0
                packet += write_vint(1)  # chunkCount
                packet += bytes([seq & 0xFF])
                packet += write_vint(12904)
                packet += write_vint(len(enc))
                packet += enc
                sock.sendto(packet, (self.host, self.port))
                seq += 1
                # drain any responses (acks) so the socket buffer stays clean
                try:
                    sock.recvfrom(2048)
                except socket.timeout:
                    pass
                time.sleep(CMD_INTERVAL)
            log("battle duration reached, letting battle end")
        except Exception as exc:
            log("UDP battle error: %r" % exc)


# ---------------------------------------------------------------- main loop
def load_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data.get("id", 0), data.get("token", "")
    except Exception:
        return 0, ""


def save_state(user_id, token):
    with open(STATE_FILE, "w", encoding="utf-8") as fh:
        json.dump({"id": user_id, "token": token}, fh)


def log(msg: str):
    print("[%s] %s" % (time.strftime("%H:%M:%S"), msg), flush=True)


def run_once(user_id, token, udp_battle_ref):
    client = Client()
    client.connect()
    log("TCP connected, logging in (id=%s)..." % user_id)
    client.send_message(10101, build_login(user_id, token), version=3)

    logged_in = False
    queued = False
    udp = udp_battle_ref

    while True:
        msg = client.recv_message()

        # keep the TCP connection alive even while the battle is UDP-only
        if client.home_t0 is not None and (time.time() - client._last_ka) > 20:
            client._last_ka = time.time()
            client.send_message(10108, b"")

        if msg is None:
            continue
        mid, ver, payload = msg

        if mid == 20104:  # LoginOk
            pos = 0
            (user_id,) = struct.unpack_from(">q", payload, pos)
            pos += 8
            pos += 8  # second copy of the id
            token, pos = read_scstring(payload, pos)
            save_state(user_id, token)
            logged_in = True
            log("LoginOk: id=%d token=%s" % (user_id, token))

        elif mid == 20103:  # LoginFailed
            reason = payload[1:].split(b"\x00")[0] if len(payload) > 1 else b""
            log("LoginFailed: %r" % reason)
            return "login_failed", user_id, token, udp

        elif mid == 24101:  # OwnHomeData
            client.home_t0 = time.time()
            if not queued and logged_in:
                client.send_message(14102, build_end_turn(0))
                queued = True
                log("queued for 1v1 matchmaking")

        elif mid == 24112:  # UdpConnectionInfo
            pos = 0
            port, pos = read_vint(payload, pos)
            host, pos = read_scstring(payload, pos)
            pos += 4  # int 10
            (session_id,) = struct.unpack_from(">q", payload, pos)
            pos += 8
            gamemode = payload[pos]
            index = payload[pos + 1]
            pos += 2
            nonce, pos = read_scstring(payload, pos)
            log("Battle started! UDP %s:%d session=%d index=%d nonce=%s" % (host, port, session_id, index, nonce))
            udp = UdpBattle(host, port, session_id, gamemode, index, user_id)
            udp.start()
            queued = False

        elif mid == 20225:  # BattleResult
            log("battle result received, re-queuing")
            tick = int((time.time() - (client.home_t0 or time.time())) * 20)
            client.send_message(14102, build_end_turn(tick))
            queued = True

        elif mid == 25892:  # Disconnected
            log("server sent Disconnected")
            return "disconnected", user_id, token, udp

        elif mid in (10108, 24135, 20108, 22957, 24107, 24124, 24125, 24445):
            pass  # ignore heartbeats/ack/matchmake info
        else:
            log("msg id=%d ver=%d len=%d (ignored)" % (mid, ver, len(payload)))



def main():
    user_id, token = load_state()
    while True:
        try:
            udp_ref = [None]
            result = run_once(user_id, token, udp_ref)
            if result and result[0] == "login_failed" and user_id > 0:
                log("account rejected, recreating as a fresh account")
                os.remove(STATE_FILE) if os.path.exists(STATE_FILE) else None
                user_id, token = 0, ""
        except (ConnectionError, OSError, socket.timeout) as exc:
            log("connection lost: %r" % exc)
        except KeyboardInterrupt:
            break
        except Exception as exc:
            log("unexpected error: %r" % exc)
        time.sleep(3)


if __name__ == "__main__":
    main()
