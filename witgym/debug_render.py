"""Format WitGymResponse traces for Gradio — CLI-style HTML transcript."""
import html
from typing import List, Tuple, Any
from witgym.schemas import WitGymResponse


def _esc(text: str) -> str:
    return html.escape(text or "")


_THINKING_ICON = (
    '<svg class="wg-thinking-icon" viewBox="0 0 24 24" width="18" height="18" '
    'aria-hidden="true" fill="none" xmlns="http://www.w3.org/2000/svg">'
    '<circle cx="12" cy="12" r="9" stroke="#2d6a4f" stroke-width="2" opacity="0.2"/>'
    '<path d="M12 3a9 9 0 0 1 9 9" stroke="#2d6a4f" stroke-width="2.5" '
    'stroke-linecap="round"/></svg>'
)


def thinking_turn_html(user_input: str) -> str:
    """Immediate feedback while the engine runs — shown before final coaching notes."""
    return (
        '<div class="wg-turn wg-turn--thinking">'
        f'<div class="wg-user"><span class="wg-label">You</span> {_esc(user_input)}</div>'
        '<div class="wg-thinking">'
        f"{_THINKING_ICON}"
        "<span>Your humor coach is thinking…</span>"
        "</div>"
        "</div>"
    )


def format_trace_html(result: WitGymResponse, user_input: str) -> str:
    """Render one turn as styled HTML matching CLI debug panels."""
    parts = [
        '<div class="wg-turn">',
        f'<div class="wg-user"><span class="wg-label">You</span> {_esc(user_input)}</div>',
    ]

    if result.route == "smalltalk":
        parts.append(
            '<div class="wg-coach-reply wg-coach-reply--compact">'
            '<div class="wg-coach-reply-header">Your humor coach</div>'
            f'<div class="wg-coach-reply-body">{_esc(result.selected)}</div>'
            "</div>"
        )
        parts.append("</div>")
        return "\n".join(parts)

    meta = result.metadata
    parts.append(
        '<div class="wg-coach-divider">'
        '<span class="wg-coach-divider-line"></span>'
        '<span class="wg-coach-divider-label">Comedy Hall of Fame — coaching notes</span>'
        '<span class="wg-coach-divider-line"></span>'
        "</div>"
        '<div class="wg-panel wg-panel-yellow">'
        '<div class="wg-panel-title">Pass 1 — Extracted Metadata</div>'
        '<table class="wg-meta">'
        f'<tr><td class="wg-dim">Archetype</td><td class="wg-cyan">{_esc(meta.archetype.value)}</td></tr>'
        f'<tr><td class="wg-dim">Tension</td><td class="wg-cyan">{_esc(meta.tension_type.value)}</td></tr>'
        f'<tr><td class="wg-dim">Distance</td><td class="wg-cyan">{_esc(meta.violation_distance.value)}</td></tr>'
        f'<tr><td class="wg-dim">Twist potential</td><td class="wg-cyan">{meta.twist_potential}/10</td></tr>'
        f'<tr><td class="wg-dim">Surface</td><td class="wg-cyan">{_esc(meta.surface)}</td></tr>'
        f'<tr><td class="wg-dim">Subtext</td><td class="wg-cyan">{_esc(meta.subtext)}</td></tr>'
        f'<tr><td class="wg-dim">Power dynamic</td><td class="wg-cyan">{_esc(meta.power_dynamic)}</td></tr>'
        f'<tr><td class="wg-dim">Connector</td><td class="wg-cyan">{_esc(meta.connector or "none")}</td></tr>'
        f'<tr><td class="wg-dim">Boring response (suppressed)</td>'
        f'<td class="wg-dim-italic">{_esc(meta.obvious_response)}</td></tr>'
        "</table></div>"
    )

    for i, scene in enumerate(result.retrieved_scenes, 1):
        parts.append(
            f'<div class="wg-panel wg-panel-blue">'
            f'<div class="wg-panel-title">Retrieved Scene {i}</div>'
            f'<div><span class="wg-bold">{_esc(scene.show)}</span> — {_esc(scene.character)}</div>'
            f'<div><span class="wg-dim">Setup:</span> {_esc(scene.setup)}</div>'
            f'<div><span class="wg-dim">Response:</span> {_esc(scene.response)}</div>'
            f'<div><span class="wg-dim">Why it works:</span> {_esc(scene.why_it_works)}</div>'
            f'<div><span class="wg-dim">Archetype:</span> {_esc(scene.archetype.value)}</div>'
            f"</div>"
        )

    for c in result.candidates:
        selected = c.text == result.selected
        cls = "wg-panel-green" if selected else "wg-panel-dim"
        title = "✓ SELECTED" if selected else c.persona.upper()
        parts.append(
            f'<div class="wg-panel {cls}">'
            f'<div class="wg-panel-title">{_esc(title)}</div>'
            f"<div>{_esc(c.text)}</div></div>"
        )

    parts.append(
        '<div class="wg-coach-reply">'
        '<div class="wg-coach-reply-header">Your humor coach</div>'
        f'<div class="wg-coach-reply-body">{_esc(result.selected)}</div>'
        "</div>"
    )
    parts.append('<div class="wg-rule"></div></div>')
    return "\n".join(parts)


def format_transcript_html(
    traces: List[Tuple[str, Any]],
    max_turns: int = 5,
    append_html: str = "",
) -> str:
    """Full scrollable transcript — oldest first, newest at bottom."""
    if not traces and not append_html:
        inner = (
            '<div class="wg-empty">Type your situation in the box below, then press '
            '<strong>Start Practicing Humour</strong> (or Enter).</div>'
        )
        body = inner
    else:
        blocks = []
        if traces:
            recent = traces[-max_turns:]
            blocks = [
                format_trace_html(
                    r if isinstance(r, WitGymResponse) else WitGymResponse.model_validate(r),
                    user_input,
                )
                for user_input, r in recent
            ]
        body = f'{"".join(blocks)}{append_html}'

    return f'<div class="wg-transcript">{body}</div>'


# Legacy markdown helpers (CLI-adjacent tooling)
def format_trace(result: WitGymResponse, user_input: str) -> str:
    """Plain-markdown fallback."""
    lines = [f"**You:** {user_input}", f"**WitGym:** {result.selected}", ""]
    if result.route == "smalltalk":
        return "\n".join(lines)
    meta = result.metadata
    lines.append(f"_archetype={meta.archetype.value}, tension={meta.tension_type.value}_")
    return "\n".join(lines)


def format_logs(traces: List[Tuple[str, Any]], max_turns: int = 5) -> str:
    return format_transcript_html(traces, max_turns)
