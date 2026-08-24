from __future__ import annotations

import base64
import os
import subprocess
import sys

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel

console = Console()


def copy_to_clipboard(text: str) -> bool:
    """Copy text to OS clipboard using local clipboard tools first, falling back to OSC 52 ANSI escape sequence."""
    text_bytes = text.encode("utf-8")

    # 1. Try local display tools first if available (avoids OSC 52 length truncation limits in terminal emulators)
    has_display = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY") or sys.platform == "darwin")
    if has_display:
        tools = [
            ["wl-copy"],
            ["xclip", "-selection", "clipboard"],
            ["xsel", "--clipboard", "--input"],
            ["pbcopy"],
        ]
        for cmd in tools:
            try:
                p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
                p.communicate(input=text_bytes)
                if p.returncode == 0:
                    return True
            except OSError:
                continue

    # 2. Fallback to OSC 52 escape sequence (works over SSH, VSCode Terminal, iTerm2, Kitty, tmux, etc.)
    b64_text = base64.b64encode(text_bytes).decode("ascii")
    if "TMUX" in os.environ:
        osc52_seq = f"\x1bPtmux;\x1b\x1b]52;c;{b64_text}\x07\x1b\\"
    else:
        osc52_seq = f"\x1b]52;c;{b64_text}\x07"

    try:
        sys.stdout.write(osc52_seq)
        sys.stdout.flush()
        return True
    except Exception:  # noqa: BLE001, S110
        return False


def pretty_command(cmd, cwd=None, check=True, capture_output=True):
    """
    Execute a command and stream its output in real-time inside a Rich Panel with the command as title.
    """
    if isinstance(cmd, list):
        cmd_str = " ".join(cmd)
        cmd_args = cmd
    else:
        cmd_str = cmd
        cmd_args = cmd.split()

    if not capture_output:
        return subprocess.run(cmd_args, cwd=cwd, check=check)

    title_running = f"[bold cyan]$ {cmd_str}[/bold cyan]"

    proc = subprocess.Popen(
        cmd_args,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    accumulated_lines = []

    with Live(Panel("[dim]Running...[/dim]", title=title_running, border_style="cyan"), console=console, refresh_per_second=10) as live:
        if proc.stdout:
            for line in iter(proc.stdout.readline, ""):
                accumulated_lines.append(line)
                current_text = "".join(accumulated_lines).strip()
                live.update(Panel(current_text or "[dim]Running...[/dim]", title=title_running, border_style="cyan"))

        proc.wait()
        output_text = "".join(accumulated_lines).strip()

        if proc.returncode != 0:
            title_failed = f"[bold red]$ {cmd_str} (failed)[/bold red]"
            live.update(Panel(output_text or f"Process exited with code {proc.returncode}", title=title_failed, border_style="red"))
        else:
            panel_content = output_text if output_text else "[dim](no output)[/dim]"
            live.update(Panel(panel_content, title=title_running, border_style="cyan"))

    if proc.returncode != 0 and check:
        raise subprocess.CalledProcessError(proc.returncode, cmd_args, output=output_text)

    return subprocess.CompletedProcess(cmd_args, proc.returncode, stdout=output_text, stderr="")


def parse_tmpl_sections(template_str: str) -> dict[str, str]:
    """Parse section blocks delimited by [section_name] from template content."""
    sections = {}
    current_section = None
    lines = []

    for line in template_str.splitlines():
        line_stripped = line.strip()
        if line_stripped.startswith("[") and line_stripped.endswith("]") and len(line_stripped) > 2:
            if current_section is not None:
                sections[current_section] = "\n".join(lines).strip()
            current_section = line_stripped[1:-1]
            lines = []
        else:
            lines.append(line)

    if current_section is not None:
        sections[current_section] = "\n".join(lines).strip()

    return sections


def display_and_interactive_copy(
    sections: list[dict[str, str]],
    header_info: str | None = None,
    header_title: str = "Instructions / Target Category",
    interactive: bool = True,
):
    """
    Display sections using Rich panels and provide an interactive copy menu.

    Each item in `sections` should be a dict:
      {
        "key": "1",
        "label": "Discourse Title",
        "content": "...",
        "render_as": "text" | "markdown"
      }
    """
    if header_info:
        console.print(Panel(header_info, title=f"[bold blue]{header_title}[/bold blue]", border_style="blue"))

    for sec in sections:
        label = sec["label"]
        content = sec["content"]
        render_as = sec.get("render_as", "text")
        key = sec["key"]

        title_str = f"[bold green]\\[{key}] {label}[/bold green]"
        if render_as == "markdown":
            body = Markdown(content)
        else:
            body = content

        console.print(Panel(body, title=title_str, border_style="green", expand=False))

    if not interactive or not sys.stdin.isatty():
        return

    while True:
        console.print("\n[bold cyan]Copy section to clipboard:[/bold cyan]")
        for sec in sections:
            console.print(f"  [[bold yellow]{sec['key']}[/bold yellow]] {sec['label']}")
        console.print("  [[bold yellow]q[/bold yellow]] Quit / Done\n")

        try:
            key_range = f"{sections[0]['key']}-{sections[-1]['key']}" if sections else "1"
            choice = input(f"Selection [{key_range}, q]: ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            console.print("\nExiting.")
            break

        if choice in ("q", "quit", "exit", ""):
            break

        matched_sec = next((s for s in sections if s["key"].lower() == choice), None)
        if matched_sec:
            success = copy_to_clipboard(matched_sec["content"])
            if success:
                console.print(f"[bold green]✔ Copied '{matched_sec['label']}' to clipboard![/bold green]")
            else:
                console.print("[bold yellow]⚠ Could not access system clipboard (xclip/xsel/wl-copy missing or display disconnected).[/bold yellow]")
                console.print(f"[dim]Content:\n{matched_sec['content']}[/dim]")
        else:
            console.print("[bold red]Invalid option, please try again.[/bold red]")
