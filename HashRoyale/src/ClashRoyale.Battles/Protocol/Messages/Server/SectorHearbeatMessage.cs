using System.Collections.Generic;
using System;
using ClashRoyale.Battles.Logic.Session;
using ClashRoyale.Utilities.Netty;

namespace ClashRoyale.Battles.Protocol.Messages.Server
{
    public class SectorHearbeatMessage : PiranhaMessage
    {
        public SectorHearbeatMessage(SessionContext ctx) : base(ctx)
        {
            Id = 21902;
        }

        public int Turn { get; set; }
        public Queue<byte[]> Commands { get; set; }

        public override void Encode()
        {
            Writer.WriteVInt(Turn);
            Writer.WriteVInt(0);

            Writer.WriteVInt(Commands.Count);

            var index = 0;
            while (Commands.Count > 0)
            {
                var command = Commands.Dequeue();
                Logger.Log($"[Heartbeat] cmd#{index++} bytes={command.Length} hex={BitConverter.ToString(command).Replace("-", "")}",
                    GetType(), SharpRaven.Data.ErrorLevel.Info);
                Writer.WriteBytes(command);
            }
        }
    }
}
