from __future__ import annotations

from datetime import datetime
import time
from typing import Text

from rich import box
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel

from heavenly_capital.core.thread import get_thread_manager


class ConsoleService:

    def __init__(self, log_service, snapshot, name: str = "ConsoleUI"):
        self.name = name
        self.log_service = log_service
        self.snapshot = snapshot
        self.console = Console()

        tm = get_thread_manager()
        tm.register_thread(name=self.name, target=self._run, daemon=True)


    def start(self):
        tm = get_thread_manager()
        tm.start_thread(self.name)

    def stop(self, wait: bool = True):
        tm = get_thread_manager()
        tm.stop_thread(self.name, wait=wait)

    def _render_logs(self):
        max_logs = 10
        logs = list(self.log_service.log_buffer)[-max_logs:]
        text = "\n".join(logs)
        return Panel(
            Text(text),
            title="[bold]Logs[/bold]",
            width=100,
            height=(max_logs + 2),
            padding=(1, 2),
            border_style="blue",

        )

    def _render_header(self):
        market_status = "Market: OPEN"
        hedge_fund_title = "Heavenly Capital – Trading Monitor"
        current_date = datetime.now().strftime("%d/%m/%Y")

        bandeau_text = f"{market_status}    {hedge_fund_title}    {current_date}"
        return Panel(
            bandeau_text,
            style="bold",
            border_style="bold blue",
            expand=True,
            padding=(0, 1),
            box=box.HEAVY,
        )

    def _render_snapshot(self):
        if not self.snapshot:
            return Panel("Snapshot not available", border_style="red")

        snap = self.snapshot()

        s = snap.today_session
        if s:
            session_text = (
                f"ID: {s.session_id or 'N/A'}\n"
                f"Date: {s.date or 'N/A'}\n"
                f"Phase: {s.phase or 'N/A'}\n"
                f"Status: {s.status or 'N/A'}\n"
                f"State: {s.state or 'N/A'}\n"
                f"Error: {s.error if s.error is not None else 'N/A'}"
            )
        else:
            session_text = "No session data yet"

        text = (
            f"[bold]SYSTEM[/bold]\n"
            f"Status: {snap.system_status or 'N/A'}\n"
            f"DB: {snap.db_status or 'N/A'}\n"
            f"Threads: {snap.runtime_threads if snap.runtime_threads is not None else 'N/A'}\n"
            f"Active Sessions: {snap.active_sessions if snap.active_sessions is not None else 'N/A'}\n\n"

            f"[bold]MARKET[/bold]\n"
            f"Market State: {snap.market_state or 'N/A'}\n"
            f"Trading State: {snap.trading_state or 'N/A'}\n"
            f"System State: {snap.system_state or 'N/A'}\n"
            f"Market Streaming: {snap.market_streaming if snap.market_streaming is not None else 'N/A'}\n\n"

            f"[bold]TODAY SESSION[/bold]\n"
            f"{session_text}\n\n"

            f"[bold]TIMESTAMP[/bold]\n"
            f"{datetime.fromtimestamp(snap.timestamp).strftime('%Y-%m-%d %H:%M:%S') if snap.timestamp else 'N/A'}"
        )

        return Panel(text,
                     title="[bold]Kernel Snapshot[/bold]",
                     style="bold",
                     width=100,
                     border_style="bold blue")


    def _run(self, stop_event):

        with Live(console=self.console, refresh_per_second=4) as live:
            while not stop_event.is_set():
                layout = Layout()

                layout.split(
                    Layout(name="header", size=3),
                    Layout(name="logs"),
                    Layout(name="snapshot")
                )

                layout["header"].update(self._render_header())
                layout["logs"].update(self._render_logs())
                layout["snapshot"].update(self._render_snapshot())

                live.update(layout)

                time.sleep(0.25)