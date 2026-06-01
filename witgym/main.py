"""CLI entry points: `witgym-chat` and `witgym-index`."""
import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from loguru import logger
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.rule import Rule
from rich.table import Table
from rich import box

console = Console()


def _setup_logging(debug: bool):
    logger.remove()
    level = "DEBUG" if debug else "INFO"
    logger.add(sys.stderr, level=level, format="<green>{time:HH:mm:ss}</green> | <level>{level}</level> | {message}")


def _show_debug_panel(result):
    """Render a detailed debug panel showing all intermediate data."""
    console.print(Rule("[dim]DEBUG[/dim]", style="dim"))

    # Metadata table
    meta = result.metadata
    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    table.add_column("Field", style="dim")
    table.add_column("Value", style="cyan")
    table.add_row("Archetype", meta.archetype.value)
    table.add_row("Tension", meta.tension_type.value)
    table.add_row("Distance", meta.violation_distance.value)
    table.add_row("Surface", meta.surface)
    table.add_row("Subtext", meta.subtext)
    table.add_row("Power dynamic", meta.power_dynamic)
    table.add_row("Boring response (suppressed)", f"[dim italic]{meta.obvious_response}[/dim italic]")
    console.print(Panel(table, title="[yellow]Pass 1 — Extracted Metadata[/yellow]", border_style="yellow"))

    # Retrieved scenes
    for i, scene in enumerate(result.retrieved_scenes):
        console.print(Panel(
            f"[bold]{scene.show}[/bold] — {scene.character}\n"
            f"[dim]Setup:[/dim] {scene.setup}\n"
            f"[dim]Response:[/dim] {scene.response}\n"
            f"[dim]Why it works:[/dim] {scene.why_it_works}\n"
            f"[dim]Archetype:[/dim] {scene.archetype.value}",
            title=f"[blue]Retrieved Scene {i + 1}[/blue]",
            border_style="blue",
        ))

    # All 3 candidates
    for c in result.candidates:
        style = "green" if c.text == result.selected else "dim"
        prefix = "✓ SELECTED" if c.text == result.selected else c.persona.upper()
        console.print(Panel(
            c.text,
            title=f"[{style}]{prefix}[/{style}]",
            border_style=style,
        ))

    console.print(Rule(style="dim"))


def chat_cmd():
    parser = argparse.ArgumentParser(description="WitGym — conversational comedy engine")
    parser.add_argument("--debug", action="store_true", help="Show metadata, retrieved scenes, and all candidates")
    parser.add_argument("--index", default="data/index.json", help="Path to the index file")
    args = parser.parse_args()

    _setup_logging(args.debug)

    if not Path(args.index).exists():
        console.print(f"[red]Index not found at {args.index}. Run `witgym-index` first.[/red]")
        sys.exit(1)

    console.print(Panel(
        "[bold cyan]WitGym[/bold cyan] — Comedy engine grounded in human precedent\n"
        "[dim]Type your message. /quit to exit. --debug for internals.[/dim]",
        border_style="cyan",
    ))

    from witgym.engine import WitGymEngine
    engine = WitGymEngine(index_path=args.index)

    while True:
        try:
            user_input = Prompt.ask("\n[bold green]You[/bold green]").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Goodbye.[/dim]")
            break

        if not user_input:
            continue
        if user_input.lower() in {"/quit", "/exit", "quit", "exit"}:
            console.print("[dim]Goodbye.[/dim]")
            break

        with console.status("[dim]Thinking...[/dim]", spinner="dots"):
            try:
                result = engine.respond(user_input)
            except Exception as e:
                logger.exception("Engine error")
                console.print(f"[red]Error: {e}[/red]")
                continue

        # Main response
        console.print(Panel(
            f"[bold white]{result.selected}[/bold white]",
            title=f"[cyan]WitGym[/cyan] [dim]({result.metadata.archetype.value})[/dim]",
            border_style="cyan",
        ))

        if args.debug:
            _show_debug_panel(result)


def index_cmd():
    parser = argparse.ArgumentParser(description="WitGym — build RAG index from transcript files")
    parser.add_argument("--transcripts", default="data/transcripts", help="Directory containing .txt transcript files")
    parser.add_argument("--output", default="data/index.json", help="Output index path")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    _setup_logging(args.debug)
    load_dotenv()

    from witgym.indexer import build_index
    scenes = build_index(transcript_dir=args.transcripts, index_path=args.output)
    console.print(f"[green]✓ Index built: {len(scenes)} scenes → {args.output}[/green]")


if __name__ == "__main__":
    # Allow: python -m witgym.main chat / python -m witgym.main index
    if len(sys.argv) > 1 and sys.argv[1] == "index":
        sys.argv.pop(1)
        index_cmd()
    else:
        chat_cmd()
