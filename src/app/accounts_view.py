from __future__ import annotations

from typing import Iterable

from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem

from src.core.accounts.model import Account


class AccountsView:
    """Отображение списка аккаунтов."""

    def __init__(self, table: QTableWidget) -> None:
        self._table = table
        self._table.setColumnCount(2)
        self._table.setHorizontalHeaderLabels(["Login", "Status"])
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

    def set_accounts(self, accounts: Iterable[Account]) -> None:
        rows = list(accounts)
        self._table.setRowCount(len(rows))
        for row, acc in enumerate(rows):
            self._table.setItem(row, 0, QTableWidgetItem(acc.login))
            self._table.setItem(row, 1, QTableWidgetItem(getattr(acc, "status", "OFF")))

    # Дополнительные методы для выборки можно добавить позже


