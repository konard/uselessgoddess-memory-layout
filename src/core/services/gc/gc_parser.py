from steam.protobufs import ProtobufMessage, EMsg
from steam.protobufs.base import CMsgMulti


def decode_protobuf(data: bytes, emsg: EMsg):
  """Декодирует protobuf сообщение известного типа"""
  msg = ProtobufMessage().parse(data, emsg)
  return msg


def decode_pure_protobuf(data: bytes):
  """Декодирует чистый protobuf (без Steam заголовка)"""
  msg = CMsgMulti()
  msg.parse(data)  # msg=MISSING означает прямой парсинг без определения типа
  return msg
