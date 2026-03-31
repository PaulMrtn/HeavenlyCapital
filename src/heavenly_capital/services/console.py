from rich.console import Console, Group
from rich.live import Live
from rich.table import Table
from rich.progress import Progress, BarColumn, TextColumn
from rich.panel import Panel
from rich.text import Text
import threading
import time
import random

console = Console()

def console_loop(stop_event: threading.Event):

    print("Starting rich demo console loop")

    with Live(refresh_per_second=4, console=console) as live:
        while not stop_event.is_set():
            pass




