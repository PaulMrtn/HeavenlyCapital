from rich.console import Console
from rich.live import Live
import time

console = Console()

renderer = KernelSnapshotRenderer()

with Live(refresh_per_second=2, console=console) as live:

    while True:

        snapshot = kernel.build_snapshot()

        live.update(renderer.render(snapshot))

        time.sleep(0.5)