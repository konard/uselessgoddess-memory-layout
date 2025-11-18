import asyncio
import functools


def name_of(value):
  return value.__class__.__name__


def type_of(value):
  return type(value).__name__


async def run_blocking(func, *args, **kwargs):
  loop = asyncio.get_running_loop()

  if kwargs:
    func = functools.partial(func, **kwargs)

  # TODO: potential custom executor
  return await loop.run_in_executor(None, func, *args)


def block_on(func):
  async def inner(*args, **kwargs):
    return await run_blocking(func, *args, **kwargs)

  return inner
