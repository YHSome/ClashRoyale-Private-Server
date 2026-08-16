using System;
using System.Linq;
using System.Net;
using ClashRoyale.Battles.Protocol;
using ClashRoyale.Utilities.Crypto;
using ClashRoyale.Utilities.Netty;
using DotNetty.Buffers;
using DotNetty.Transport.Channels;
using DotNetty.Transport.Channels.Sockets;
using SharpRaven.Data;

namespace ClashRoyale.Battles.Logic.Session
{
    public class SessionContext
    {
        public bool Active
        {
            get => DateTime.UtcNow.Subtract(_lastMessage).TotalSeconds < 10;
            set
            {
                if (value) _lastMessage = DateTime.UtcNow;
            }
        }

        public bool BattleActive
        {
            get => DateTime.UtcNow.Subtract(LastCommands).TotalSeconds < 10;
            set
            {
                if (value) LastCommands = DateTime.UtcNow;
            }
        }

        public async void Process(IByteBuffer reader, IChannel channel)
        {
            Channel = channel;

            var ackCount = reader.ReadByte();

            if (ackCount > 0)
            {
                var buffer = Unpooled.Buffer();
                buffer.WriteLong(Session.Id);
                buffer.WriteByte(GameMode);
                buffer.WriteByte(Index);

                buffer.WriteByte(ackCount);

                for (var i = 0; i < ackCount; i++) buffer.WriteByte(reader.ReadByte());

                await Channel.WriteAndFlushAsync(new DatagramPacket(buffer, EndPoint));
            }

            if (ackCount > 0)
                return;

            var chunkCount = reader.ReadVInt();

            for (var i = 0; i < chunkCount; i++)
            {
                var chunkSeq = reader.ReadByte();
                var chunkId = reader.ReadVInt();
                var chunkLength = reader.ReadVInt();

                // UDP retransmissions: the client may re-send a chunk with the same
                // sequence number. If we decrypt it again the RC4 stream drifts and
                // every later chunk turns into garbage. Skip duplicates without
                // touching the stream.
                if (LastIncomingSeq != 0 && (sbyte) (chunkSeq - LastIncomingSeq) <= 0)
                {
                    Logger.Log($"Duplicate chunk seq={chunkSeq} id={chunkId} len={chunkLength} skipped.", GetType(),
                        ErrorLevel.Info);
                    if (chunkLength > 0)
                        reader.SkipBytes(chunkLength);
                    continue;
                }
                LastIncomingSeq = chunkSeq;

                if (!LogicMessageFactory.Messages.ContainsKey(chunkId))
                {
                    Logger.Log($"Message ID: {chunkId}, S: {chunkSeq}, L: {chunkLength} is not known.", GetType(),
                        ErrorLevel.Info);

                    // Consume the chunk payload and advance the RC4 stream anyway, so
                    // subsequent chunks stay in sync with the client's stream.
                    if (chunkLength > 0)
                    {
                        var unknown = reader.ReadBytes(chunkLength);
                        Rc4.Decrypt(ref unknown);
                    }
                    continue;
                }

                if (!(Activator.CreateInstance(LogicMessageFactory.Messages[chunkId], this, reader) is PiranhaMessage
                    message)) continue;

                try
                {
                    message.Id = chunkId;
                    message.Length = chunkLength;

                    // Any chunk we receive means the player is still in the battle.
                    // Set it before Decode so a malformed command can't trigger the
                    // idle check and end the match early.
                    BattleActive = true;

                    message.Decrypt();
                    message.Decode();
                    message.Process();

                    Logger.Log($"[C] Message {chunkId} ({message.GetType().Name}) handled.", GetType(),
                        ErrorLevel.Debug);
                }
                catch (Exception exception)
                {
                    Logger.Log($"Failed to process {chunkId}: " + exception, GetType(), ErrorLevel.Error);
                }

                var buffer = Unpooled.Buffer();
                buffer.WriteLong(Session.Id);
                buffer.WriteByte(GameMode);
                buffer.WriteByte(Index);

                buffer.WriteByte(1);
                buffer.WriteByte(chunkSeq);
                await Channel.WriteAndFlushAsync(new DatagramPacket(buffer, EndPoint));
            }

            var readable = reader.ReadableBytes;
            if (readable > 0)
                Logger.Log(
                    $"{BitConverter.ToString(reader.ReadBytes(readable).Array.Take(readable).ToArray()).Replace("-", "")}",
                    null, ErrorLevel.Debug);
        }

        #region Objects

        public Rc4Core Rc4 = new Rc4Core("fhsd6f86f67rt8fw78fw789we78r9789wer6re", "nonce");

        public Session Session { get; set; }
        public EndPoint EndPoint { get; set; }
        public IChannel Channel { get; set; }
        public byte GameMode { get; set; }
        public byte Index { get; set; }

        private DateTime _lastMessage = DateTime.UtcNow;
        public DateTime LastCommands = DateTime.UtcNow;
        public byte Seq = 1;
        public byte LastIncomingSeq = 0;

        public enum GameModes
        {
            Pvp = 0,
            Duo = 1
        }

        #endregion Objects
    }
}
