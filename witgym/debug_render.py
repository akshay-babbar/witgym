"""Format WitGymResponse traces for Gradio — styled HTML transcript."""
import html
import json
from typing import List, Tuple, Any, Optional
from witgym.schemas import WitGymResponse
from witgym.avatars import char_avatar_url

# Maps character first-name or full-name → title string
_CHAR_TITLES: dict[str, str] = {
    "michael":        "Regional Manager",
    "dwight":         "Assistant (to the) Reg. Manager",
    "jim":            "Sales Representative",
    "pam":            "Receptionist",
    "kevin":          "Accountant",
    "andy":           "Sales Representative",
    "stanley":        "Sales Representative",
    "angela":         "Head of Accounting",
    "ryan":           "Temp → VP → Temp",
    "kelly":          "Customer Service Rep",
    "michael scott":  "Regional Manager",
    "dwight schrute": "Asst. (to the) Reg. Manager",
    "jim halpert":    "Sales Representative",
    "pam beesly":     "Receptionist",
    "kevin malone":   "Accountant",
    "andy bernard":   "Sales Representative",
    "stanley hudson": "Sales Representative",
    "angela martin":  "Head of Accounting",
    "ryan howard":    "Temp → VP → Temp",
    "kelly kapoor":   "Customer Service Rep",
}


def _avatar_url(character: str) -> str:
    return char_avatar_url(character)


def _char_title(character: str) -> str:
    key = character.lower().strip()
    return _CHAR_TITLES.get(key, "The Office")


def _esc(text: str) -> str:
    return html.escape(text or "")


def _jstr(text: str) -> str:
    """JSON-encode a string for safe embedding in an HTML onclick attribute."""
    return json.dumps(text)


_THINKING_ICON = (
    '<svg class="wg-thinking-icon" viewBox="0 0 24 24" width="18" height="18" '
    'aria-hidden="true" fill="none" xmlns="http://www.w3.org/2000/svg">'
    '<circle cx="12" cy="12" r="9" stroke="#2d6a4f" stroke-width="2" opacity="0.3"/>'
    '<path d="M12 3a9 9 0 0 1 9 9" stroke="#2d6a4f" stroke-width="2.5" stroke-linecap="round"/>'
    '</svg>'
)


def thinking_turn_html(user_input: str) -> str:
    return (
        '<div class="wg-turn wg-turn--thinking">'
        f'<div class="wg-user"><span class="wg-label">You</span> {_esc(user_input)}</div>'
        f'<div class="wg-thinking">{_THINKING_ICON}'
        '<span class="wg-step-cycle">'
        '<span>reading the room…</span>'
        '<span>finding precedent…</span>'
        '<span>drafting candidates…</span>'
        '</span></div>'
        '</div>'
    )


def _debug_panels_html(result: WitGymResponse) -> str:
    meta = result.metadata
    parts = [
        '<div class="wg-panel wg-panel-yellow">',
        '<div class="wg-panel-title">Pass 1 — Extracted Metadata</div>',
        '<table class="wg-meta">',
        f'<tr><td class="wg-dim">Archetype</td><td class="wg-cyan">{_esc(meta.archetype.value)}</td></tr>',
        f'<tr><td class="wg-dim">Tension</td><td class="wg-cyan">{_esc(meta.tension_type.value)}</td></tr>',
        f'<tr><td class="wg-dim">Distance</td><td class="wg-cyan">{_esc(meta.violation_distance.value)}</td></tr>',
        f'<tr><td class="wg-dim">Twist potential</td><td class="wg-cyan">{meta.twist_potential}/10</td></tr>',
        f'<tr><td class="wg-dim">Surface</td><td class="wg-cyan">{_esc(meta.surface)}</td></tr>',
        f'<tr><td class="wg-dim">Subtext</td><td class="wg-cyan">{_esc(meta.subtext)}</td></tr>',
        f'<tr><td class="wg-dim">Power dynamic</td><td class="wg-cyan">{_esc(meta.power_dynamic)}</td></tr>',
        f'<tr><td class="wg-dim">Connector</td><td class="wg-cyan">{_esc(meta.connector or "none")}</td></tr>',
        f'<tr><td class="wg-dim">Suppressed cliché</td><td class="wg-dim-italic">{_esc(meta.obvious_response)}</td></tr>',
        '</table></div>',
    ]

    for i, scene in enumerate(result.retrieved_scenes, 1):
        char    = scene.character
        av_url  = _avatar_url(char)
        title   = _char_title(char)
        show    = scene.show or "The Office"
        # Build onclick that calls the global wgOpenScene function
        onclick = (
            f"wgOpenScene({_jstr(char)},{_jstr(show)},{_jstr(scene.setup)},"
            f"{_jstr(scene.response)},{_jstr(scene.why_it_works)},{_jstr(av_url)},{_jstr(title)})"
        )
        parts += [
            f'<div class="wg-panel wg-panel-blue wg-clickable" onclick="{_esc(onclick)}" '
            f'title="Click to see {_esc(char)}\'s full scene">',
            f'<div class="wg-panel-title">Retrieved Scene {i} — {_esc(show)} · click to expand <span class="wg-scene-arrow">↗</span></div>',
            f'<div><span class="wg-bold">{_esc(char)}</span> <span class="wg-dim">· {_esc(title)}</span></div>',
            f'<div><span class="wg-dim">Setup:</span> {_esc(scene.setup)}</div>',
            f'<div><span class="wg-dim">Response:</span> {_esc(scene.response)}</div>',
            '</div>',
        ]

    for c in result.candidates:
        selected = c.text == result.selected
        cls   = "wg-panel-green" if selected else "wg-panel-dim"
        title = "✓ Selected candidate" if selected else f"Candidate — {c.persona}"
        parts += [
            f'<div class="wg-panel {cls}">',
            f'<div class="wg-panel-title">{_esc(title)}</div>',
            f'<div>{_esc(c.text)}</div>',
            '</div>',
        ]

    return "".join(parts)


def _twist_meter_html(twist_potential: int) -> str:
    pct = twist_potential * 10
    return (
        f'<div class="wg-twist-meter">'
        f'<span class="wg-twist-label">COMEDY COMPLEXITY</span>'
        f'<div class="wg-twist-bar"><div class="wg-twist-fill" style="width:{pct}%"></div></div>'
        f'<span class="wg-twist-score">{twist_potential}/10</span>'
        f'</div>'
    )


def format_trace_html(result: WitGymResponse, user_input: str, show_debug: bool = True, is_last: bool = False) -> str:
    parts = [
        '<div class="wg-turn">',
        f'<div class="wg-user"><span class="wg-label">You</span> {_esc(user_input)}</div>',
    ]

    if result.route == "smalltalk":
        parts += [
            '<div class="wg-coach-reply wg-coach-reply--compact">',
            '<div class="wg-coach-reply-header">Your humor coach</div>',
            f'<div class="wg-coach-reply-body">{_esc(result.selected)}</div>',
            '</div></div>',
        ]
        return "".join(parts)

    collapsed_cls = "" if show_debug else " wg-collapsed"
    chevron       = "▼" if show_debug else "▶"

    # Alternate candidates (non-selected) for client-side "another take"
    alts = [{"persona": c.persona, "text": c.text} for c in result.candidates if c.text != result.selected]
    alts_json = html.escape(json.dumps(alts))

    # Winning persona label — use pre-compression value stored in response
    winning_persona = result.winning_persona
    persona_label = f' · <em class="wg-persona-label">{_esc(winning_persona)}</em>' if winning_persona else ""

    # Another take button (only if alternatives exist)
    another_take_btn = (
        '<span class="wg-another-take" onclick="wgAnotherTake(this)" title="Try another candidate">↻ another take</span>'
        if alts else ""
    )

    # New-turn reveal class for animation
    new_cls = " wg-coach-reply--new" if is_last else ""

    parts += [
        _twist_meter_html(result.metadata.twist_potential),
        '<div class="wg-debug-toggle">',
        '<span class="wg-debug-toggle-line"></span>',
        f'<span class="wg-debug-toggle-label">Coaching notes <span class="wg-debug-chevron">{chevron}</span></span>',
        '<span class="wg-debug-toggle-line"></span>',
        '</div>',
        f'<div class="wg-debug-body{collapsed_cls}">',
        _debug_panels_html(result),
        '</div>',
        f'<div class="wg-coach-reply{new_cls}" data-alts="{alts_json}" data-alt-idx="0">',
        f'<div class="wg-coach-reply-header">Your humor coach{persona_label}{another_take_btn}</div>',
        f'<div class="wg-coach-reply-body">{_esc(result.selected)}</div>',
        '</div>',
        '<div class="wg-rule"></div></div>',
    ]
    return "".join(parts)


# All JS is in _GLOBAL_JS (app.py, injected via head=) — scripts in gr.HTML value
# are not executed by Gradio 6.x (set via innerHTML). See app.py _GLOBAL_JS.
_PAGE_JS = ""


def format_transcript_html(
    traces: List[Tuple[str, Any]],
    max_turns: int = 5,
    append_html: str = "",
    show_debug: bool = True,
) -> str:
    if not traces and not append_html:
        body = (
            '<div class="wg-empty">'
            '<div class="wg-empty-icon">🎭</div>'
            '<div class="wg-empty-text">Drop a situation — awkward, delusional, or painfully relatable — '
            'and your coach will find the wit in it.</div>'
            '</div>'
        )
    else:
        recent = traces[-max_turns:]
        body = "".join(
            format_trace_html(
                r if isinstance(r, WitGymResponse) else WitGymResponse.model_validate(r),
                user_input,
                show_debug=show_debug,
                is_last=(i == len(recent) - 1),
            )
            for i, (user_input, r) in enumerate(recent)
        ) + append_html

    return f'<div class="wg-transcript">{body}</div>{_PAGE_JS}'


# Legacy helpers
def format_trace(result: WitGymResponse, user_input: str) -> str:
    lines = [f"**You:** {user_input}", f"**WitGym:** {result.selected}", ""]
    if result.route != "smalltalk":
        meta = result.metadata
        lines.append(f"_archetype={meta.archetype.value}, tension={meta.tension_type.value}_")
    return "\n".join(lines)


def format_logs(traces: List[Tuple[str, Any]], max_turns: int = 5) -> str:
    return format_transcript_html(traces, max_turns)
