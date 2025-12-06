import sys
import asyncio
import functools
import inspect
from typing import get_type_hints
from pathlib import Path


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


def async_methods(cls):
  """Декоратор класса, который создает асинхронные версии всех методов с суффиксом _async"""
  # Сначала собираем все методы в список, чтобы не изменять словарь во время итерации
  methods_to_process = []
  for attr_name, attr in cls.__dict__.items():
    if attr_name.startswith("_") or attr_name.endswith("_async"):
      continue

    if callable(attr) and not asyncio.iscoroutinefunction(attr):
      methods_to_process.append((attr_name, attr))

  # Теперь добавляем асинхронные версии
  for attr_name, attr in methods_to_process:
    async_name = attr_name + "_async"
    # Всегда перезаписываем, даже если stub метод уже существует
    actual_func = attr.__func__ if isinstance(attr, staticmethod) else attr
    doc = (
      getattr(actual_func, "__doc__", None)
      or getattr(attr, "__doc__", None)
      or ""
    )

    # Сохраняем сигнатуру и аннотации типов для IDE
    try:
      sig = inspect.signature(actual_func)
      async_func = block_on(actual_func)
      # Копируем сигнатуру для IDE
      async_func.__signature__ = sig
      # Копируем аннотации типов
      if hasattr(actual_func, "__annotations__"):
        async_func.__annotations__ = actual_func.__annotations__.copy()
    except (ValueError, TypeError):
      # Если не удалось получить сигнатуру, просто создаем функцию
      async_func = block_on(actual_func)

    async_func.__name__ = async_name
    async_func.__doc__ = f"Асинхронная версия {attr_name}. {doc}"
    if isinstance(attr, staticmethod):
      async_func = staticmethod(async_func)
    setattr(cls, async_name, async_func)

  return cls
