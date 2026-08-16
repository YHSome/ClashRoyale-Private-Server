using System;
using DotNetty.Buffers;
using DotNetty.Transport.Channels;
using SharpRaven.Data;

namespace ClashRoyale.Core.Network.Handlers
{
    public class RawDumpHandler : ChannelHandlerAdapter
    {
        public override void ChannelRead(IChannelHandlerContext context, object message)
        {
            if (message is IByteBuffer buffer)
            {
                try
                {
                    var show = Math.Min(64, buffer.ReadableBytes);
                    var bytes = new byte[show];
                    buffer.GetBytes(buffer.ReaderIndex, bytes);
                    Logger.Log($"[RAW-DUMP] {BitConverter.ToString(bytes)}", GetType(), ErrorLevel.Info);
                }
                catch (Exception)
                {
                }
            }

            base.ChannelRead(context, message);
        }
    }
}
