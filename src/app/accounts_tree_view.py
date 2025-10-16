from __future__ import annotations

from typing import Iterable, Dict

from PyQt6.QtGui import QStandardItemModel, QStandardItem
from PyQt6.QtWidgets import QTreeView

from src.core.accounts.model import Account


class AccountsTreeView:
    """Представление аккаунтов на базе QTreeView + QStandardItemModel.

    Колонки: Login | Status
    """

    COL_LOGIN = 0
    COL_STATUS = 1

    def __init__(self, tree: QTreeView) -> None:
        self._tree = tree
        self._model = QStandardItemModel(0, 2)
        self._model.setHorizontalHeaderLabels(["Login", "Status"])
        self._tree.setModel(self._model)
        self._tree.setAlternatingRowColors(True)
        self._tree.setRootIsDecorated(False)
        self._tree.setUniformRowHeights(True)
        self._tree.setItemsExpandable(False)
        self._tree.setExpandsOnDoubleClick(False)
        self._tree.header().setStretchLastSection(True)

        # Отображаемые аккаунты по login
        self._login_to_row: Dict[str, int] = {}

    def set_accounts(self, accounts: Iterable[Account]) -> None:
        self._model.removeRows(0, self._model.rowCount())
        self._login_to_row.clear()
        for acc in accounts:
            self._append_account(acc)
        self._tree.expandAll()

    def _append_account(self, acc: Account) -> None:
        row = self._model.rowCount()
        item_login = QStandardItem(acc.login)
        item_status = QStandardItem(getattr(acc, "status", "OFF"))
        item_login.setEditable(False)
        item_status.setEditable(False)
        self._model.appendRow([item_login, item_status])
        self._login_to_row[acc.login] = row

    def update_status(self, login: str, status: str) -> None:
        row = self._login_to_row.get(login)
        if row is None:
            return
        self._model.setItem(row, self.COL_STATUS, QStandardItem(status))


