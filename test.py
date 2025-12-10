from core.context import Context
from core.services.windows_service import WindowService

context = Context()

accounts = context.accounts()

running_accounts = WindowService.scan_cs2_windows(accounts)

x, y = WindowService.get_next_window_position(running_accounts)

print(x, y)
