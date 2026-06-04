from __future__ import annotations

import readchar
import sys
import io
import threading
from datetime import datetime
import time
from decimal import Decimal
from typing import Text

from rich import box
from rich.console import Console, Group, RenderableType
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.text import Text
from rich.table import Table

from heavenly_capital.core.thread import get_thread_manager


class _ErrorCapture(io.TextIOBase):
    def __init__(self, buffer: list):
        self._buffer = buffer

    def write(self, text: str) -> int:
        if text.strip():
            self._buffer.append(text.strip())
            if len(self._buffer) > 20:
                self._buffer.pop(0)
        return len(text)


class ConsoleService:

    def __init__(self, log_service, snapshot, name: str = "ConsoleUI"):
        self.name = name
        self.log_service = log_service
        self.snapshot = snapshot
        self.console = Console()

        self._portfolio_index: int = 0
        self._index_lock = threading.Lock()

        self._output_buffer = []
        self._original_stderr = sys.stderr

        tm = get_thread_manager()
        tm.register_thread(name=self.name, target=self._run, daemon=True)


    def start(self):
        tm = get_thread_manager()
        tm.start_thread(self.name)

    def stop(self, wait: bool = True):
        sys.stderr = self._original_stderr
        tm = get_thread_manager()
        tm.stop_thread(self.name, wait=wait)


    # ── Navigation ──────────────────────────────────────────────────────────

    def next_portfolio(self):
        with self._index_lock:
            self._portfolio_index += 1

    def prev_portfolio(self):
        with self._index_lock:
            self._portfolio_index = max(0, self._portfolio_index - 1)

    def _get_portfolio_index(self, total: int) -> int:
        with self._index_lock:
            if total == 0:
                return 0
            self._portfolio_index %= total
            return self._portfolio_index


    # ── Panel ────────────────────────────────────────────────────────────

    @staticmethod
    def _render_header(snap=None) -> Panel:

        if snap and snap.market.market_state:
            state = snap.market.market_state.upper()
            if "CLOSE" in state:
                market_status = f"[bold red]{snap.market.market_state}[/bold red]"
            else:
                market_status = f"[bold green]{snap.market.market_state}[/bold green]"
        else:
            market_status = "[dim]N/A[/dim]"

        current_time = datetime.now().strftime("%d/%m/%Y ─ %H:%M:%S")

        grid = Table.grid(expand=True)
        grid.add_column(justify="left", ratio=1)
        grid.add_column(justify="center", ratio=1)
        grid.add_column(justify="right", ratio=1)

        pad = "  "
        grid.add_row(
            f"{pad}[bold]{current_time}[/bold]  │  [bold]Market Status:[/bold] {market_status}",
            "[bold blue]HEAVENLY CAPITAL[/bold blue] │ TRADING STATION",
            f"[bold]Author:[/bold] PAUL MARTIN {pad}"
        )

        return Panel(
            grid,
            border_style="bold blue",
            expand=True,
            padding=(0, 1),
            box=box.HEAVY,
        )

    def _render_logs(self):
        max_logs = 17
        logs = list(self.log_service.log_buffer)[-max_logs:]
        text = "\n".join(logs)
        return Panel(
            Text(text),
            title="[bold]Logs[/bold]",
            padding=(1, 2),
            border_style="blue",

        )


    @staticmethod
    def _render_system_monitor(snap) -> Panel:
        if not snap:
            return Panel(
                Text("Awaiting system snapshot...", style="dim"),
                title="[bold]System Monitor[/bold]",
                border_style="bold blue"
            )

        ind = "  "

        s = snap.today_session
        if s:
            session_text = (
                f"{ind}Date:     {s.date or 'N/A'}\n"
                f"{ind}Phase:    {s.phase or 'N/A'}\n"
                f"{ind}Status:   {s.status or 'N/A'}\n"
                f"{ind}State:    {s.state or 'N/A'}\n"
                f"{ind}Error:    {s.error if s.error is not None else 'N/A'}"
            )
        else:
            session_text = f"{ind}[dim]No session data yet[/dim]"

        system_text = (
            f"{ind}Status:            {snap.system.status or 'N/A'}\n"
            f"{ind}Database:          {snap.system.db_status or 'N/A'}\n"
            f"{ind}Threads:           {snap.system.runtime_threads if snap.system.runtime_threads is not None else 'N/A'}\n"
            f"{ind}Active Portfolios: {snap.system.active_sessions if snap.system.active_sessions is not None else 'N/A'}"
        )

        market_text = (
            f"{ind}Market State:      {snap.market.market_state or 'N/A'}\n"
            f"{ind}Trading State:     {snap.market.trading_state or 'N/A'}\n"
            f"{ind}Market Streaming:  {snap.market.streaming if snap.market.streaming is not None else 'N/A'}"
        )

        tick_rate = snap.market.tick_rate
        tick_rate_fmt = f"{tick_rate:.0f}" if isinstance(tick_rate, (int, float)) else (
            str(tick_rate) if tick_rate else "N/A")

        tick_gap = snap.market.last_tick_gap
        tick_gap_fmt = f"{tick_gap:.2f}" if isinstance(tick_gap, (int, float)) else (
            str(tick_gap) if tick_gap else "N/A")

        ibkr_text = (
            f"{ind}Clients:           {snap.market.clients_connected if snap.market.clients_connected is not None else 'N/A'}\n"
            f"{ind}Contracts:         {snap.market.subscribed_contracts if snap.market.subscribed_contracts is not None else 'N/A'}\n"
            f"{ind}Tick Rate:         {tick_rate_fmt}\n"
            f"{ind}Last Tick Gap:     {tick_gap_fmt}\n"
            f"{ind}Orders Tracked:    {snap.market.orders_tracked if snap.market.orders_tracked is not None else 'N/A'}"
        )

        grid = Table.grid(expand=True)
        grid.add_column(ratio=1)
        grid.add_column(ratio=1)

        grid.add_row(
            Group("[bold]SYSTEM[/bold]\n", system_text),
            Group("[bold]MARKET[/bold]\n", market_text)
        )

        grid.add_row("", "")

        grid.add_row(
            Group("\n[bold]BROKER[/bold]\n", ibkr_text),
            Group("\n[bold]SESSION[/bold]\n", session_text)
        )

        return Panel(
            grid,
            title="[bold]System Monitor[/bold]",
            padding=(1, 2),
            border_style="bold blue"
        )


    @staticmethod
    def _render_orders_table(orders) -> Table:
        table = Table(
            box=box.SIMPLE,
            show_header=True,
            header_style="bold",
            pad_edge=False,
            expand=True,
        )

        table.add_column("Con ID", width=12)
        table.add_column("Side", width=6)
        table.add_column("Type", width=8)
        table.add_column("Qty", justify="right", width=8)
        table.add_column("Filled", justify="right", width=8)
        table.add_column("Remaining", justify="right", width=10)
        table.add_column("Status", width=16)

        for o in orders:
            side_color = "green" if o.side == "BUY" else "red"
            table.add_row(
                str(o.con_id),
                Text(o.side, style=side_color),
                o.order_type,
                f"{o.quantity:.0f}",
                f"{o.filled_quantity:.0f}",
                f"{o.remaining_quantity:.0f}",
                o.status,
            )

        return table


    @staticmethod
    def _render_positions_table(positions) -> Table:
        table = Table(
            box=box.SIMPLE,
            show_header=True,
            header_style="bold",
            pad_edge=False,
            expand=True,
        )

        table.add_column("Symbol")
        table.add_column("Qty", justify="right")
        table.add_column("Avg Price", justify="right")
        table.add_column("Last Price", justify="right")
        table.add_column("Market Val", justify="right")
        table.add_column("Unreal P&L", justify="right")
        table.add_column("Perf", justify="right")

        def fmt(value, decimals=2):
            if value is None:
                return "N/A"
            if isinstance(value, (Decimal, float, int)):
                return f"{float(value):,.{decimals}f}"
            return str(value)

        def fmt_pct(value):
            if value is None:
                return "N/A"
            return f"{float(value) * 100:+.2f}%"

        for pos in positions:
            table.add_row(
                pos.symbol,
                fmt(pos.quantity, decimals=0),
                fmt(pos.avg_price),
                fmt(pos.market_price),
                fmt(pos.market_value),
                fmt(pos.unrealized_pnl),
                fmt_pct(pos.performance),
            )

        total_value = sum(float(p.market_value) for p in positions if p.market_value is not None)
        total_pnl = sum(float(p.unrealized_pnl) for p in positions if p.unrealized_pnl is not None)
        table.add_row(
            Text("TOTAL", style="bold"),
            "", "", "",
            Text(f"${total_value:,.2f}", style="bold"),
            Text(f"${total_pnl:,.2f}", style="bold"),
            "",
        )

        return table

    @staticmethod
    def _format_header_line(left: str, right: str, panel_width: int = 110) -> str:
        visible_len = len(left) + len(right)
        padding = max(2, panel_width - visible_len)
        return f"{left}{' ' * padding}[dim]{right}[/dim]"

    def _render_portfolio(self, snap) -> Panel:
        portfolios = snap.portfolios if snap else []
        total = len(portfolios)

        if total == 0:
            return Panel(
                Text("No portfolio data yet", style="dim"),
                title="[bold]Portfolio Manager[/bold]",
                border_style="bold blue",
            )

        idx = self._get_portfolio_index(total)
        ptf = portfolios[idx]

        def fmt(value, prefix="", decimals=2) -> str:
            if value is None:
                return "N/A"
            if isinstance(value, (Decimal, float, int)):
                return f"{prefix} {float(value):,.{decimals}f}"
            return str(value)

        def fmt_pct(value) -> str:
            if value is None:
                return "N/A"
            return f"{float(value) * 100:+.2f}%"


        # ── Header ───────────────────────────
        nav_hint = f"[{idx + 1}/{total}]  ← → to switch"

        header_lines = []
        header_lines.append(
            self._format_header_line(
                left=f"[bold]Portfolio Name:[/bold] {ptf.portfolio_id} │ [bold]Trading Mode:[/bold] {ptf.mode} │ [bold]IBKR Account:[/bold] {ptf.account_id}",
                right=nav_hint,
            )
        )

        header_lines.append("")
        header_lines.append("")


        # ── Balance ───────────────────────────
        header_lines.append("[bold]BALANCE[/bold]")
        header_lines.append("")
        header_lines.append(f"  {'Cash':<18} {fmt(ptf.cash, prefix='$'):>14}")
        header_lines.append(f"  {'Stock Value':<18} {fmt(ptf.stock_value, prefix='$'):>14}")
        header_lines.append(f"  {'Total Value':<18} {fmt(ptf.total_value, prefix='$'):>14}")
        header_lines.append(f"  {'Unrealized P&L':<18} {fmt(ptf.unrealized_pnl, prefix='$'):>14}")
        header_lines.append(f"  {'Performance':<18} {fmt_pct(ptf.performance):>14}")
        header_lines.append("")
        header_lines.append("")


        # ── Positions ───────────────────────────
        header_lines.append(
            f"[bold]POSITIONS ({len(ptf.positions)})[/bold]" if ptf.positions else "[bold]POSITIONS[/bold]"
        )
        if not ptf.positions:
            header_lines.append("")
            header_lines.append("  [dim]No open positions[/dim]")
            header_lines.append("")

        # ── Order Activity ────────────────────────────────────────────────
        activity_lines = []
        activity_lines.append("")
        activity_lines.append("[bold]ACTIVITY[/bold]")

        if not ptf.orders:
            activity_lines.append("")
            activity_lines.append("  [dim]No orders[/dim]")


        # ── Render ─────────────────────────────────────────────────────────────────
        elements: list[RenderableType] = ["\n".join(header_lines)]

        if ptf.positions:
            elements.append(self._render_positions_table(ptf.positions))

        elements.append("\n".join(activity_lines))

        if ptf.orders:
            elements.append(self._render_orders_table(ptf.orders))

        return Panel(
            Group(*elements),
            title="[bold]Portfolio Manager[/bold]",
            border_style="bold blue",
            padding=(1, 2),
        )

    def _render_terminal_output(self):
        max_outputs = 5
        outputs = self._output_buffer[-max_outputs:]

        if not outputs:
            text = ""
        else:
            text = "\n".join(outputs)

        return Panel(
            text,
            title="[bold blue]Terminal[/bold blue]",
            border_style="blue"
        )


    # ── Main loop ─────────────────────────────────────────────────────────────

    @staticmethod
    def _build_layout() -> Layout:
        layout = Layout()
        layout.split(
            Layout(name="header", size=3),
            Layout(name="body"),
        )
        layout["body"].split_row(
            Layout(name="left", ratio=1),
            Layout(name="separator", size=2),
            Layout(name="portfolio", ratio=1),
        )
        layout["left"].split(
            Layout(name="logs", ratio=16),
            Layout(name="system", ratio=14),
            Layout(name="errors", size=10),
        )
        return layout

    def _run(self, stop_event: threading.Event):
        def read_keys():
            while not stop_event.is_set():
                try:
                    key = readchar.readkey()
                    if key == readchar.key.RIGHT:
                        self.next_portfolio()
                    elif key == readchar.key.LEFT:
                        self.prev_portfolio()
                except Exception:
                    pass

        key_thread = threading.Thread(target=read_keys, daemon=True)
        key_thread.start()

        layout = self._build_layout()

        with Live(
            console=self.console,
            refresh_per_second=4,
            screen=True,
        ) as live:
            while not stop_event.is_set():
                snap = self.snapshot() if self.snapshot else None

                layout["header"].update(self._render_header(snap))
                layout["logs"].update(self._render_logs())
                layout["system"].update(self._render_system_monitor(snap))
                layout["errors"].update(self._render_terminal_output())
                layout["separator"].update(Text(""))
                layout["portfolio"].update(self._render_portfolio(snap))

                live.update(layout)
                time.sleep(0.25)