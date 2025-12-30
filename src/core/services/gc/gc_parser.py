import steam.ext.csgo.protobufs
from steam import Message
from steam._gc import (
  CLEAR_PROTO_BIT,
  IS_PROTO,
  AppID,
  GCMessage,
  GCProtobufMessage,
)
from steam.protobufs import ProtobufMessage
from steam.protobufs.headers import READ_U32


def decode_bytes(data: bytes):
  """
  Декодирует бинарные данные Steam протокола в объект сообщения.

  Args:
      data: Байты сообщения (с EMsg в первых 4 байтах)

  Returns:
      ProtobufMessage или Message объект
  """
  # Читаем первые 4 байта - это EMsg (тип сообщения)
  emsg_value = READ_U32(data)

  # Проверяем флаг protobuf (бит 0x80000000)
  if IS_PROTO(emsg_value):
    # Это protobuf сообщение
    msg = ProtobufMessage().parse(data[4:], CLEAR_PROTO_BIT(emsg_value))
  else:
    # Это структурированное сообщение
    msg = Message().parse(data[4:], emsg_value)

  return msg


def decode_gc_bytes(data: bytes, app_id: int = 730):
  """
  Декодирует GC (Game Coordinator) сообщение.

  Args:
      data: Байты сообщения (с EMsg в первых 4 байтах)
      app_id: ID приложения (730 для CS:GO, 440 для TF2, и т.д.)
  """
  emsg_value = READ_U32(data)

  if IS_PROTO(emsg_value):
    msg = GCProtobufMessage().parse(data[4:], CLEAR_PROTO_BIT(emsg_value), AppID(app_id))
  else:
    msg = GCMessage().parse(data[4:], emsg_value, AppID(app_id))

  return msg
