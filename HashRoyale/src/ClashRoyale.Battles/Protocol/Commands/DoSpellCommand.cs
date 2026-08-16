using System;
using ClashRoyale.Battles.Logic.Session;
using ClashRoyale.Utilities.Netty;
using ClashRoyale.Utilities.Utils;
using DotNetty.Buffers;
using SharpRaven.Data;

namespace ClashRoyale.Battles.Protocol.Commands
{
    public class DoSpellCommand : LogicCommand
    {
        public DoSpellCommand(SessionContext ctx, IByteBuffer buffer) : base(ctx, buffer)
        {
            Type = 1;
        }

        public int ClientTick { get; set; }
        public int Checksum { get; set; }
        public int SenderHighId { get; set; }
        public int SenderLowId { get; set; }
        public int SpellDeckIndex { get; set; }
        public int SpellIndex { get; set; }
        public int ClassId { get; set; }
        public int InstanceId { get; set; }
        public int TroopLevel { get; set; }
        public int X { get; set; }
        public int Y { get; set; }

        public override void Decode()
        {
            // Header
            {
                ClientTick = Buffer.ReadVInt();
                Checksum = Buffer.ReadVInt();

                SenderHighId = Buffer.ReadVInt();
                SenderLowId = Buffer.ReadVInt();
            }

            SpellDeckIndex = Buffer.ReadVInt();

            ClassId = Buffer.ReadVInt();
            InstanceId = Buffer.ReadVInt();

            SpellIndex = Buffer.ReadVInt();

            TroopLevel = Buffer.ReadVInt();

            X = Buffer.ReadVInt();
            Y = Buffer.ReadVInt();
        }

        public override void Encode()
        {
            // The underlying buffer may be pooled/reused; make sure we start
            // from a clean state so no stale bytes leak into the relayed command.
            Data.Clear();

            // Header
            {
                Data.WriteVInt(Type);

                Data.WriteVInt(ClientTick);
                Data.WriteVInt(Checksum);

                Data.WriteVInt(SenderHighId);
                Data.WriteVInt(SenderLowId);
            }

            Data.WriteVInt(SpellDeckIndex);

            Data.WriteVInt(ClassId);
            Data.WriteVInt(InstanceId);

            Data.WriteVInt(SpellIndex);
        }

        public override void Process()
        {
            var battle = SessionContext.Session.Battle;
            if (battle == null) return;

            Logger.Log(
                $"[DoSpell] sender={SenderHighId}:{SenderLowId} deck={SpellDeckIndex} card={ClassId}:{InstanceId} " +
                $"level={TroopLevel} x={X} y={Y} tick={ClientTick}",
                GetType(), ErrorLevel.Info);

            var data = new byte[Data.ReadableBytes];
            Data.ReadBytes(data);
            Logger.Log($"[DoSpell-raw] data={BitConverter.ToString(data).Replace("-", "")} len={data.Length}",
                GetType(), ErrorLevel.Info);

            // Own side: command + level + x + y.
            var ownBuffer = Unpooled.Buffer(12);
            ownBuffer.WriteBytes(data);
            ownBuffer.WriteVInt(TroopLevel);
            ownBuffer.WriteVInt(X);
            ownBuffer.WriteVInt(Y);
            var ownBytes = new byte[ownBuffer.WriterIndex];
            ownBuffer.GetBytes(0, ownBytes);

            // Enemy side: the client expects an extra IsAttack flag followed by
            // the card's global id (see ClashRoyale main server DoSpellCommand).
            // Without these fields the enemy client misreads level/x/y and the
            // card never shows up.
            var enemyBuffer = Unpooled.Buffer(14);
            enemyBuffer.WriteBytes(data);
            enemyBuffer.WriteVInt(1); // IsAttack
            enemyBuffer.WriteVInt(GameUtils.Id(ClassId, InstanceId));
            enemyBuffer.WriteVInt(TroopLevel);
            enemyBuffer.WriteVInt(X);
            enemyBuffer.WriteVInt(Y);
            var enemyBytes = new byte[enemyBuffer.WriterIndex];
            enemyBuffer.GetBytes(0, enemyBytes);

            Logger.Log(
                $"[DoSpell-relay] own={BitConverter.ToString(ownBytes).Replace("-", "")} " +
                $"enemy={BitConverter.ToString(enemyBytes).Replace("-", "")}",
                GetType(), ErrorLevel.Info);

            // The battle may not be fully ready yet (the other player has not
            // registered / the queues were not built). Drop the relay instead
            // of crashing so the client is not stuck mid-deploy.
            var ownQueue = battle.GetOwnQueue(SessionContext.EndPoint);
            var enemyQueue = battle.GetEnemyQueue(SessionContext.EndPoint);
            if (ownQueue == null || enemyQueue == null) return;

            ownQueue.Enqueue(ownBytes);
            enemyQueue.Enqueue(enemyBytes);

            //battle.Replay.AddCommand(Type, ClientTick - 20, ClientTick, SenderHighId, SenderLowId, ClassId * 1000000 + InstanceId, X, Y, SpellDeckIndex);
        }
    }
}
