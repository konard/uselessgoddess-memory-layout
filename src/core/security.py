import json
import os

from cryptography.fernet import Fernet
from tinydb.storages import Storage

import logging
from logging.handlers import RotatingFileHandler

INTERNAL_KEY = b"1llKWQG0rSXJgyI5GLja7iAw_x215iyPEZFlw4qaTyI="


class EncryptedJSONStorage(Storage):
  def __init__(self, filename):
    self.filename = filename
    self.cipher = Fernet(INTERNAL_KEY)

  def read(self):
    if not os.path.exists(self.filename):
      return None

    with open(self.filename, "rb") as handle:
      encrypted_data = handle.read()

    if not encrypted_data:
      return None

    try:
      decrypted_data = self.cipher.decrypt(encrypted_data)
      return json.loads(decrypted_data.decode("utf-8"))
    except Exception:
      return None

  def write(self, data):
    json_dump = json.dumps(data)
    encrypted_data = self.cipher.encrypt(json_dump.encode("utf-8"))

    with open(self.filename, "wb") as handle:
      handle.write(encrypted_data)

  def close(self):
    pass


class EncryptedRotatingFileHandler(RotatingFileHandler):
  def __init__(
    self,
    filename,
    mode="a",
    maxBytes=0,
    backupCount=0,
    encoding=None,
    delay=False,
  ):
    super().__init__(filename, mode, maxBytes, backupCount, encoding, delay)
    self.cipher = Fernet(INTERNAL_KEY)

  def emit(self, record):
    try:
      if self.shouldRollover(record):
        self.doRollover()

      msg = self.format(record)

      encrypted_line = self.cipher.encrypt(msg.encode("utf-8"))

      if self.stream is None:
        self.stream = self._open()

      self.stream.write(encrypted_line.decode("ascii") + "\n")

      self.flush()

    except Exception:
      self.handleError(record)
