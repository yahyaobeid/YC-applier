"""Interactive CLI review step using Rich."""

import logging
import os
import subprocess
import tempfile

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from yc_applier.scraper.models import ApplicationDraft

logger = logging.getLogger(__name__)
console = Console()


def _render_draft_panel(draft: ApplicationDraft) -> None:
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_row("[bold]Job[/bold]", draft.job.title)
    table.add_row("[bold]Company[/bold]", draft.job.company.name)
    table.add_row("[bold]Batch[/bold]", draft.job.company.batch or "—")
    table.add_row("[bold]URL[/bold]", draft.job.url)
    table.add_row("[bold]Score[/bold]", f"[green]{draft.match_score}[/green]")
    table.add_row("[bold]Reasoning[/bold]", draft.match_reasoning)

    console.print(table)
    console.print(Panel(
        Text(draft.draft_paragraph, style="italic"),
        title="[bold cyan]Draft Paragraph[/bold cyan]",
        expand=False,
    ))


def _open_editor(draft_text: str) -> str:
    """Open $EDITOR with the draft text; return edited version."""
    editor = os.environ.get("EDITOR", "")
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write(draft_text)
        tmpfile = f.name

    if editor:
        try:
            subprocess.run([editor, tmpfile], check=True)
            with open(tmpfile) as f:
                return f.read().strip()
        except Exception as exc:
            logger.warning("Editor failed (%s), falling back to input().", exc)
    else:
        console.print("[yellow]No $EDITOR set. Paste your edited paragraph (end with a blank line):[/yellow]")

    # input() fallback
    lines = []
    while True:
        line = input()
        if line == "":
            break
        lines.append(line)
    return "\n".join(lines).strip() or draft_text


def review_drafts(
    drafts: list[ApplicationDraft],
    auto_apply_above_score: int,
) -> list[ApplicationDraft]:
    """Walk through drafts, auto-approving high-scorers and prompting for the rest.

    Returns only the drafts that should proceed to submission (approved / auto_approved).
    """
    approved: list[ApplicationDraft] = []

    for i, draft in enumerate(drafts, 1):
        console.rule(f"[bold]Application {i}/{len(drafts)}[/bold]")

        # Auto-approve high-confidence matches
        if draft.match_score >= auto_apply_above_score:
            draft.status = "auto_approved"
            approved.append(draft)
            console.print(
                f"[bold green]AUTO-APPROVED[/bold green] "
                f"{draft.job.title} @ {draft.job.company.name} "
                f"(score {draft.match_score} ≥ {auto_apply_above_score})"
            )
            continue

        _render_draft_panel(draft)
        console.print(
            "\n[bold]\\[A][/bold]pprove  "
            "[bold]\\[E][/bold]dit  "
            "[bold]\\[S][/bold]kip  "
            "[bold]\\[Q][/bold]uit\n"
        )

        while True:
            choice = input("Choice: ").strip().upper()
            if choice == "A":
                draft.status = "approved"
                approved.append(draft)
                console.print("[green]Approved.[/green]")
                break
            elif choice == "E":
                edited = _open_editor(draft.draft_paragraph)
                draft.draft_paragraph = edited
                console.print("[cyan]Updated paragraph:[/cyan]")
                console.print(Panel(Text(edited, style="italic"), expand=False))
                draft.status = "approved"
                approved.append(draft)
                break
            elif choice == "S":
                draft.status = "rejected"
                console.print("[yellow]Skipped.[/yellow]")
                break
            elif choice == "Q":
                console.print("[red]Quitting review. Remaining jobs will not be applied to.[/red]")
                return approved
            else:
                console.print("[red]Invalid choice. Enter A, E, S, or Q.[/red]")

    return approved
