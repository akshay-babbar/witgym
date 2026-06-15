"""Format WitGymResponse traces for Gradio — styled HTML transcript."""
import html
import json
import re
from dataclasses import dataclass, field
from typing import List, Tuple, Any, Optional
from witgym.schemas import WitGymResponse, PipelineEvent, ComedyMetadata, CandidateResponse, TranscriptScene
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


def _fmt_chip(value: str) -> str:
    return value.replace("_", " ").upper()


# Succinct definitions for each comedy structural property — shown on chip click
_CHIP_DEFS: dict[str, tuple[str, str]] = {
    # Archetypes
    "status_assertion":   ("ARCHETYPE · STATUS ASSERTION", "What it is: someone is trying to claim authority, status, or competence. Why it matters: the joke works by exposing the gap between the claim and the reality."),
    "self_delusion":      ("ARCHETYPE · SELF-DELUSION", "What it is: someone believes a flattering story about themselves that reality cannot support. Why it matters: comedy lands when the fantasy finally runs into the facts."),
    "power_inversion":    ("ARCHETYPE · POWER INVERSION", "What it is: the expected pecking order flips. Why it matters: surprise grows when the person who should control the room suddenly loses it."),
    "anxiety_escalation": ("ARCHETYPE · ANXIETY ESCALATION", "What it is: a small worry spirals into a full disaster movie. Why it matters: the joke gets sharper as the reaction becomes bigger than the actual problem."),
    "social_fail":        ("ARCHETYPE · SOCIAL PERFORMANCE FAIL", "What it is: someone tries to look normal, smooth, or impressive and fumbles it. Why it matters: comedy comes from watching the performance collapse in public."),
    "misplaced_conf":     ("ARCHETYPE · MISPLACED CONFIDENCE", "What it is: someone sounds certain without having the facts. Why it matters: the joke exposes confidence that has outrun competence."),
    # Tensions
    "social_embarrass":   ("TENSION · SOCIAL EMBARRASSMENT", "What it is: the fear of looking foolish in front of other people. Why it matters: embarrassment raises the emotional stakes, so even a short line can hit hard."),
    "existential":        ("TENSION · EXISTENTIAL ANXIETY", "What it is: the moment quietly touches identity, meaning, or dread. Why it matters: deeper fear gives the joke weight instead of making it feel throwaway."),
    "status_threat":      ("TENSION · STATUS THREAT", "What it is: someone's rank, credibility, or belonging feels under pressure. Why it matters: status danger creates friction, and friction gives the line bite."),
    "identity_expose":    ("TENSION · IDENTITY EXPOSURE", "What it is: the person's mask is slipping. Why it matters: jokes get stronger when they reveal the truth the speaker was trying to hide."),
    "logic_collapse":     ("TENSION · LOGIC COLLAPSE", "What it is: the person's explanation breaks under its own rules. Why it matters: once the logic collapses, the line can simply point at the wreckage."),
    # Distances
    "mild":               ("SHARPNESS · MILD VIOLATION", "What it is: a safe, lightly subversive joke. Why it matters: this keeps the line playful instead of confrontational."),
    "moderate":           ("SHARPNESS · MODERATE VIOLATION", "What it is: a joke with some edge, but still recoverable. Why it matters: this is often the sweet spot for sounding bold without losing the room."),
    "sharp":              ("SHARPNESS · SHARP VIOLATION", "What it is: a line that cuts close to the bone. Why it matters: sharper jokes can win bigger laughs, but they also raise the risk of silence."),
}

_PERSONA_DEFS: dict[str, tuple[str, str]] = {
    "cynic": ("PERSONA · CYNIC", "This lens says the quiet part out loud. It spots the real motive, the hidden cost, or the ugly truth underneath the situation."),
    "conviction": ("PERSONA · CONVICTION", "This lens commits completely to a wrong belief. It is funny because the certainty exposes something true about the speaker."),
    "absurdist": ("PERSONA · ABSURDIST", "This lens follows the situation's logic farther than a normal person would. It makes the joke by treating the spiral as perfectly reasonable."),
    "bisociate": ("PERSONA · BISOCIATE", "This lens jumps to a different but structurally matching world. It works when the same comic pattern suddenly shows up somewhere unexpected."),
}


def _jstr(text: str) -> str:
    """JSON-encode a string for safe embedding in an HTML onclick attribute."""
    return json.dumps(text)


_MODE_BADGES = {
    "banter": '<span class="wg-mode-badge wg-mode-banter">⚡ BANTER</span>',
    "quick_wit": '<span class="wg-mode-badge wg-mode-wit">🎯 QUICK WIT</span>',
    "coaching": '<span class="wg-mode-badge wg-mode-coach">🎓 COACHING</span>',
    "humour": '<span class="wg-mode-badge wg-mode-wit">🎯 QUICK WIT</span>',
    "smalltalk": '<span class="wg-mode-badge wg-mode-banter">⚡ BANTER</span>',
}


def _mode_badge_html(route: str) -> str:
    return _MODE_BADGES.get(route, _MODE_BADGES["quick_wit"])


def _coach_header_html(selected_char: str) -> str:
    """Render 'JIM SAYS:' header with tiny avatar when a character is selected."""
    if not selected_char or selected_char == "AI":
        return '<div class="wg-coach-reply-header">Your humor coach</div>'
    av = _avatar_url(selected_char)
    name = selected_char.upper()
    return (
        f'<div class="wg-coach-reply-header wg-coach-reply-header--char">'
        f'<img src="{_esc(av)}" alt="{_esc(selected_char)}" class="wg-coach-reply-avatar" '
        f'onerror="this.style.display=\'none\'"/>'
        f'{_esc(name)} SAYS:'
        f'</div>'
    )


def _reply_actions_html() -> str:
    return (
        '<div class="wg-reply-actions">'
        '<button class="wg-action-btn wg-copy-btn" onclick="wgCopy(this)" title="Copy to clipboard" '
        'aria-label="Copy line to clipboard" data-icon="copy">'
        '<svg viewBox="0 0 20 20" class="wg-action-icon" aria-hidden="true">'
        '<rect x="7" y="4" width="8" height="10" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.8"/>'
        '<path d="M5 7H4.5A1.5 1.5 0 0 0 3 8.5v7A1.5 1.5 0 0 0 4.5 17h5A1.5 1.5 0 0 0 11 15.5V15" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>'
        '</svg></button>'
        '</div>'
    )


def _trace_payload_from_result(result: WitGymResponse) -> dict[str, Any]:
    metadata = result.metadata.model_dump(mode="json")
    scenes = [scene.model_dump(mode="json") for scene in result.retrieved_scenes]
    candidates = [candidate.model_dump(mode="json") for candidate in result.candidates]
    logs = [
        {"step": "metadata", "status": "ok", "detail": f"twist={metadata.get('twist_potential')} archetype={metadata.get('archetype')}"},
        {"step": "retrieval", "status": "ok", "detail": ", ".join(f"{s['character']}:{s['archetype']}" for s in scenes) or "no precedent scenes"},
        {"step": "candidate_generation", "status": "ok", "detail": ", ".join(f"{c['persona']}:{len(c['text'].split())}w" for c in candidates) or "no candidates"},
        {"step": "ranking", "status": "ok", "detail": result.winning_persona or "none"},
        {"step": "compression", "status": "ok", "detail": "selected line finalized"},
    ]
    return {
        "route": result.route,
        "winning_persona": result.winning_persona,
        "selected": result.selected,
        "metadata": metadata,
        "retrieved_scenes": scenes,
        "candidates": candidates,
        "explanation": result.explanation,
        "logs": logs,
    }


def _trace_payload_from_stream(state: "StreamingTurnState", selected_text: str) -> dict[str, Any]:
    metadata = state.metadata.model_dump(mode="json") if state.metadata else None
    scenes = [scene.model_dump(mode="json") for scene in state.scenes]
    candidates = [candidate.model_dump(mode="json") for candidate in state.candidates]
    logs = []
    if metadata:
        logs.append({"step": "metadata", "status": "ok", "detail": f"twist={metadata.get('twist_potential')} archetype={metadata.get('archetype')}"})
    if scenes:
        logs.append({"step": "retrieval", "status": "ok", "detail": ", ".join(f"{s['character']}:{s['archetype']}" for s in scenes)})
    if candidates:
        logs.append({"step": "candidate_generation", "status": "ok", "detail": ", ".join(f"{c['persona']}:{len(c['text'].split())}w" for c in candidates)})
    if state.winning_persona:
        logs.append({"step": "ranking", "status": "ok", "detail": state.winning_persona})
    if state.streaming_final or state.final_text:
        logs.append({"step": "compression", "status": "running" if state.streaming_final else "ok", "detail": "polishing final line" if state.streaming_final else "selected line finalized"})
    return {
        "route": state.route,
        "winning_persona": state.winning_persona,
        "selected": selected_text or state.selected,
        "final_text": state.final_text or None,
        "metadata": metadata,
        "retrieved_scenes": scenes,
        "candidates": candidates,
        "active_candidate": (
            {"persona": state.active_persona, "partial_text": state.active_candidate_text}
            if state.active_persona and state.active_candidate_text else None
        ),
        "streaming_final": state.streaming_final,
        "logs": logs,
    }


def _compact_reply_html(route: str, selected: str, *, coaching_hint: str = "", selected_char: str = "AI") -> str:
    hint = f'<div class="wg-dim-italic" style="margin-top:.35rem;font-size:.85rem">{_esc(coaching_hint)}</div>' if coaching_hint else ""
    return (
        f'{_mode_badge_html(route)}'
        f'<div class="wg-coach-reply wg-coach-reply--compact" '
        f'data-char="{_esc(selected_char or "AI")}">'
        f'{_reply_actions_html()}'
        f'{_coach_header_html(selected_char)}'
        f'<div class="wg-coach-reply-body">{_esc(selected)}</div>'
        f'{hint}'
        '</div>'
    )

def _explanation_panel_html(explanation: str) -> str:
    return (
        '<div class="wg-panel wg-panel-blue" style="margin-top:.5rem">'
        '<div class="wg-panel-title">WHY IT WORKS</div>'
        f'<div>{_esc(explanation)}</div>'
        '</div>'
    )


_THINKING_ICON = (
    '<svg class="wg-thinking-icon" viewBox="0 0 24 24" width="18" height="18" '
    'aria-hidden="true" fill="none" xmlns="http://www.w3.org/2000/svg">'
    '<circle cx="12" cy="12" r="9" stroke="#2d6a4f" stroke-width="2" opacity="0.3"/>'
    '<path d="M12 3a9 9 0 0 1 9 9" stroke="#2d6a4f" stroke-width="2.5" stroke-linecap="round"/>'
    '</svg>'
)

_STABLE_LOADING_LINE = "Checking Dunder Mifflin playbook…"


def _sanitize_streaming_reply_text(text: str) -> str:
    raw = (text or "").strip()
    if not raw:
        return ""
    json_match = re.search(r'"compressed_line"\s*:\s*"((?:[^"\\]|\\.)*)"', raw)
    if json_match:
        try:
            return json.loads(f'"{json_match.group(1)}"').strip()
        except Exception:
            return json_match.group(1).strip()
    if raw.startswith("{"):
        try:
            obj = json.loads(raw)
            value = next(iter(obj.values())) if obj else ""
            return str(value).strip()
        except Exception:
            return ""
    return raw


def thinking_turn_html(user_input: str) -> str:
    return (
        '<div class="wg-turn wg-turn--thinking">'
        f'<div class="wg-user"><span class="wg-label">You</span> {_esc(user_input)}</div>'
        f'<div class="wg-thinking">{_THINKING_ICON}'
        f'<span>{_esc(_STABLE_LOADING_LINE)}</span></div>'
        '</div>'
    )


def _chip_onclick(value: str) -> str:
    title, defn = _CHIP_DEFS.get(value, (_fmt_chip(value), "A comedy structural property."))
    return f"wgOpenChip({_jstr(title)},{_jstr(defn)})"


def _persona_onclick(value: str) -> str:
    title, defn = _PERSONA_DEFS.get(value, (f"PERSONA · {_fmt_chip(value)}", "This is the comic lens the coach used to write the line."))
    return f"wgOpenChip({_jstr(title)},{_jstr(defn)})"


def _insight_button(label: str, onclick: str) -> str:
    return (
        f'<button class="wg-insight-btn" type="button" onclick="{_esc(onclick)}">'
        f'{_esc(label)}'
        '</button>'
    )


def _coach_notes_html(result: WitGymResponse) -> str:
    meta = result.metadata
    buttons = [
        _insight_button("situation pattern", _chip_onclick(meta.archetype.value)),
        _insight_button("social pressure", _chip_onclick(meta.tension_type.value)),
        _insight_button(
            f"complexity {meta.twist_potential}/10",
            f"wgOpenChip({_jstr('COMEDY COMPLEXITY')},{_jstr('What it is: how many moving parts this moment has. Why it matters: lower scores usually want one clean observation, while higher scores can support a twistier line.')})",
        ),
        _insight_button(
            f"retrieved context · {len(result.retrieved_scenes)}",
            f"wgOpenChip({_jstr('RETRIEVED CONTEXT')},{_jstr('These are Office scenes with a similar comedy pattern. They are reference cases for how the joke works, not lines the coach is copying.')})",
        ),
    ]
    if result.winning_persona:
        buttons.append(_insight_button("persona lens", _persona_onclick(result.winning_persona)))
    return (
        '<div class="wg-insight-strip">'
        '<div class="wg-insight-title">How WitGym built this line</div>'
        '<div class="wg-insight-sub">Tap any note for a quick explanation.</div>'
        '<div class="wg-insight-buttons">'
        + "".join(buttons) +
        '</div>'
        '</div>'
    )


def _meta_pass1_html(meta) -> str:
    arc_click = _chip_onclick(meta.archetype.value)
    ten_click  = _chip_onclick(meta.tension_type.value)
    vio_click  = _chip_onclick(meta.violation_distance.value)
    _connector_onclick = "wgOpenChip(" + _jstr("CONNECTOR") + "," + _jstr("A word or phrase with two simultaneous readings. When it lands, both meanings hit at once — that’s the mechanism.") + ")"
    connector_chip = (
        f'<div class="wg-chip-row">'
        f'<span class="wg-chip-label">connector</span>'
        f'<span class="wg-chip wg-chip-green wg-chip-clickable"'
        f' onclick="{_esc(_connector_onclick)}"'
        f' title="what is a connector?">{_esc(meta.connector)}</span>'
        f'</div>'
    ) if meta.connector else ""
    return (
        '<div class="wg-panel wg-panel-yellow">'
        '<div class="wg-panel-title">Neurology of Comedy</div>'
        '<div class="wg-chip-row">'
        f'<span class="wg-chip wg-chip-cyan wg-chip-clickable" onclick="{_esc(arc_click)}" title="what is this archetype?">{_esc(_fmt_chip(meta.archetype.value))}</span>'
        f'<span class="wg-chip wg-chip-purple wg-chip-clickable" onclick="{_esc(ten_click)}" title="what is this tension?">{_esc(_fmt_chip(meta.tension_type.value))}</span>'
        f'<span class="wg-chip wg-chip-orange wg-chip-clickable" onclick="{_esc(vio_click)}" title="what is this distance?">{_esc(_fmt_chip(meta.violation_distance.value))}</span>'
        '</div>'
        f'{connector_chip}'
        f'<div class="wg-avoided"><span class="wg-dim">avoided →</span> '
        f'<span class="wg-dim-italic">{_esc(meta.obvious_response)}</span></div>'
        '<div class="wg-capsule wg-capsule--new">'
        '<div class="wg-capsule-head">SUBTEXT <span class="wg-cap-chev">▶</span></div>'
        f'<div class="wg-capsule-body wg-collapsed">{_esc(meta.subtext)}</div>'
        '</div>'
        '<div class="wg-capsule wg-capsule--new">'
        '<div class="wg-capsule-head">POWER DYNAMIC <span class="wg-cap-chev">▶</span></div>'
        f'<div class="wg-capsule-body wg-collapsed">{_esc(meta.power_dynamic)}</div>'
        '</div>'
        '</div>'
    )


def _debug_panels_html(result: WitGymResponse) -> str:
    trace = _trace_payload_from_result(result)
    trace_json = json.dumps(trace, indent=2, ensure_ascii=True)
    return (
        '<div class="wg-trace-block">'
        '<div class="wg-trace-title">TRACE JSON</div>'
        f'<pre class="wg-trace-json">{_esc(trace_json)}</pre>'
        '</div>'
    )


@dataclass
class StreamingTurnState:
    user_input: str
    metadata: Optional[ComedyMetadata] = None
    scenes: List[TranscriptScene] = field(default_factory=list)
    candidates: List[CandidateResponse] = field(default_factory=list)
    selected: str = ""
    winning_persona: Optional[str] = None
    route: str = "humour"
    active_persona: Optional[str] = None
    active_candidate_text: str = ""
    streaming_final: bool = False
    final_text: str = ""


def apply_stream_event(state: StreamingTurnState, event: PipelineEvent) -> None:
    if event.phase == "banter" and event.response:
        state.route = "banter"
        state.selected = event.response.selected
        return
    if event.phase == "coaching_ask" and event.response:
        state.route = "coaching"
        state.selected = event.response.selected
        return
    if event.phase == "smalltalk" and event.response:
        state.route = "banter"
        state.selected = event.response.selected
        return
    if event.metadata is not None:
        state.metadata = event.metadata
    if event.scenes is not None:
        state.scenes = event.scenes
    if event.candidates is not None:
        state.candidates = event.candidates
    if event.phase == "candidate_start":
        state.active_persona = event.persona
        state.active_candidate_text = ""
    elif event.phase == "candidate_token":
        state.active_persona = event.persona
        state.active_candidate_text = event.partial_text
    elif event.phase == "candidate_done":
        state.active_persona = None
        state.active_candidate_text = ""
    elif event.phase == "ranked":
        state.selected = event.selected or ""
        state.winning_persona = event.winning_persona
        state.streaming_final = False
        state.final_text = state.selected
    elif event.phase == "final_start":
        state.streaming_final = True
        state.final_text = event.partial_text or state.selected
    elif event.phase == "final_token":
        state.streaming_final = True
        state.final_text = event.partial_text
    elif event.phase == "done" and event.response:
        state.final_text = event.response.selected
        state.selected = event.response.selected
        state.candidates = event.response.candidates
        state.route = event.response.route
        state.streaming_final = False


def _streaming_debug_panels_html(state: StreamingTurnState, selected_text: str) -> str:
    if state.metadata is None:
        return ""
    trace = _trace_payload_from_stream(state, selected_text)
    trace_json = json.dumps(trace, indent=2, ensure_ascii=True)
    return (
        '<div class="wg-trace-block">'
        '<div class="wg-trace-title">TRACE JSON</div>'
        f'<pre class="wg-trace-json">{_esc(trace_json)}</pre>'
        '</div>'
    )


def format_streaming_turn_html(state: StreamingTurnState, show_debug: bool = True) -> str:
    parts = [
        '<div class="wg-turn wg-turn--thinking">',
        f'<div class="wg-user"><span class="wg-label">You</span> {_esc(state.user_input)}</div>',
    ]

    if state.route in ("banter", "smalltalk") and state.selected:
        parts += [
            _compact_reply_html("banter", state.selected),
            '</div>',
        ]
        return "".join(parts)

    if state.route == "coaching" and state.selected and state.metadata is None:
        parts += [
            _compact_reply_html(
                "coaching",
                state.selected,
                coaching_hint="coaching mode — waiting for your answer",
            ),
            '</div>',
        ]
        return "".join(parts)

    if state.metadata is None:
        parts += [
            f'<div class="wg-thinking">{_THINKING_ICON}<span>{_esc(_STABLE_LOADING_LINE)}</span></div></div>',
        ]
        return "".join(parts)

    collapsed_cls = "" if show_debug else " wg-collapsed"
    chevron = "▼" if show_debug else "▶"
    display_text = _sanitize_streaming_reply_text(state.final_text or state.selected)
    persona_label = (
        f' · <em class="wg-persona-label">{_esc(state.winning_persona)}</em>'
        if state.winning_persona else ""
    )

    # Guard: don't display raw JSON tokens or mixed text+JSON tails from compression streaming
    raw_display_text = (state.final_text or state.selected or "").strip()
    has_json_tail = '"compressed_line"' in raw_display_text or (
        "{" in raw_display_text and not raw_display_text.lstrip().startswith("{")
    )
    is_raw_json = bool(raw_display_text and raw_display_text.lstrip().startswith("{"))

    # ── Hero reply FIRST (above fold) ──────────────────────────────────────
    parts.append(_mode_badge_html(state.route))
    if display_text and not is_raw_json and not has_json_tail:
        polish = ' · <span class="wg-dim-italic">polishing…</span>' if state.streaming_final else ""
        parts += [
            '<div class="wg-coach-reply wg-coach-reply--new">',
            f'<div class="wg-coach-reply-header">Your humor coach{persona_label}{polish}</div>',
            f'<div class="wg-coach-reply-body">{_esc(display_text)}</div>',
            '</div>',
        ]
    elif state.streaming_final or is_raw_json or has_json_tail:
        # Compression pass running — show stable placeholder
        parts += [
            '<div class="wg-coach-reply wg-coach-reply--new">',
            f'<div class="wg-coach-reply-header">Your humor coach{persona_label} · <span class="wg-dim-italic">polishing…</span></div>',
            f'<div class="wg-coach-reply-body wg-dim-italic">Finding the sharpest version…</div>',
            '</div>',
        ]
    elif not state.active_persona:
        parts += [
            f'<div class="wg-thinking">{_THINKING_ICON}'
            '<span>drafting candidates…</span></div>',
        ]

    parts.append('<div class="wg-rule"></div></div>')
    return "".join(parts)


def format_transcript_with_streaming(
    traces: List[Tuple[str, Any]],
    stream_state: Optional[StreamingTurnState],
    show_debug: bool = True,
    max_turns: int = 5,
    selected_char: str = "AI",
) -> str:
    if not traces and stream_state is None:
        return format_transcript_html([], show_debug=show_debug, selected_char=selected_char)
    recent = traces[-max_turns:]
    body = "".join(
        format_trace_html(
            r if isinstance(r, WitGymResponse) else WitGymResponse.model_validate(r),
            user_input,
            show_debug=show_debug,
            is_last=False,
            selected_char=selected_char,
        )
        for user_input, r in recent
    )
    if stream_state is not None:
        body += format_streaming_turn_html(stream_state, show_debug=show_debug)
    if stream_state is not None and stream_state.metadata is not None:
        trace_payload = _trace_payload_from_stream(stream_state, stream_state.selected)
    elif recent:
        last_result = recent[-1][1] if isinstance(recent[-1][1], WitGymResponse) else WitGymResponse.model_validate(recent[-1][1])
        trace_payload = _trace_payload_from_result(last_result)
    else:
        trace_payload = None
    trace_attr = _esc(json.dumps(trace_payload, ensure_ascii=True)) if trace_payload else ""
    return f'<div class="wg-transcript" data-latest-trace="{trace_attr}">{body}</div>{_PAGE_JS}'


def _twist_meter_html(twist_potential: int) -> str:
    pct = twist_potential * 10
    return (
        f'<div class="wg-twist-meter">'
        f'<span class="wg-twist-label">COMEDY COMPLEXITY</span>'
        f'<div class="wg-twist-bar"><div class="wg-twist-fill" style="width:{pct}%"></div></div>'
        f'<span class="wg-twist-score">{twist_potential}/10</span>'
        f'</div>'
    )


def format_trace_html(result: WitGymResponse, user_input: str, show_debug: bool = True, is_last: bool = False, selected_char: str = "AI") -> str:
    parts = [
        '<div class="wg-turn">',
        f'<div class="wg-user"><span class="wg-label">You</span> {_esc(user_input)}</div>',
    ]

    if result.route in ("banter", "smalltalk"):
        parts += [
            _compact_reply_html("banter", result.selected, selected_char=selected_char),
            '</div>',
        ]
        return "".join(parts)

    if result.route == "coaching" and result.coaching_question and not result.candidates:
        parts += [
            _compact_reply_html(
                "coaching",
                result.selected,
                coaching_hint="coaching mode — waiting for your answer",
                selected_char=selected_char,
            ),
            '</div>',
        ]
        return "".join(parts)

    collapsed_cls = "" if show_debug else " wg-collapsed"
    chevron       = "▼" if show_debug else "▶"

    # Alternate candidates (non-selected) for client-side "another take"
    alts = [{"persona": c.persona, "text": c.text} for c in result.candidates if c.text != result.selected]
    alts_json = html.escape(json.dumps(alts))

    # Winning persona label — use pre-compression value stored in response
    winning_persona = result.winning_persona
    persona_label = (
        f' · <button class="wg-persona-label" type="button" onclick="{_esc(_persona_onclick(winning_persona))}">{_esc(winning_persona)}</button>'
        if winning_persona else ""
    )

    # Another take button (only if alternatives exist)
    another_take_btn = (
        '<span class="wg-another-take" onclick="wgAnotherTake(this)" title="Try another candidate">↻ another take</span>'
        if alts else ""
    )

    # New-turn reveal class for animation
    new_cls = " wg-coach-reply--new" if is_last else ""

    beckon_cls = " wg-debug-toggle--new" if is_last else ""

    # ── Hero reply FIRST (above fold) ──────────────────────────────────────
    coach_hdr = (
        f'<div class="wg-coach-reply-header wg-coach-reply-header--char">'
        + (f'<img src="{_esc(_avatar_url(selected_char))}" alt="{_esc(selected_char)}" class="wg-coach-reply-avatar" onerror="this.style.display=\'none\'"/>'
           if selected_char and selected_char != "AI" else "")
        + (f'{_esc(selected_char.upper())} SAYS:' if selected_char and selected_char != "AI" else f'Your humor coach{persona_label}')
        + f'{another_take_btn}</div>'
    )
    parts += [
        _mode_badge_html(result.route),
        (
            f'<div class="wg-coach-reply{new_cls}" data-alts="{alts_json}" data-alt-idx="0" '
            f'data-char="{_esc(selected_char or "AI")}">'
        ),
        f'{_reply_actions_html()}',
        coach_hdr,
        f'<div class="wg-coach-reply-body">{_esc(result.selected)}</div>',
        '</div>',
    ]
    if result.explanation:
        parts.append(_explanation_panel_html(result.explanation))
    parts.append(_coach_notes_html(result))

    # ── Drill chips (coaching follow-ups) ──────────────────────────────────
    if is_last:
        parts.append(
            '<div class="wg-drill-chips">'
            '<span class="wg-drill-chip" onclick="wgDrill(\'Make that line sharper and more cutting\')">sharpen it →</span>'
            '<span class="wg-drill-chip" onclick="wgDrill(\'Give me a completely different angle on the same situation\')">different angle →</span>'
            '<span class="wg-drill-chip" onclick="wgDrill(\'Explain why that line works — what comedy principle does it use?\')">why it works →</span>'
            '</div>'
        )

    parts.append('<div class="wg-rule"></div></div>')
    return "".join(parts)


# All JS is in _GLOBAL_JS (app.py, injected via head=) — scripts in gr.HTML value
# are not executed by Gradio 6.x (set via innerHTML). See app.py _GLOBAL_JS.
_PAGE_JS = ""


def format_transcript_html(
    traces: List[Tuple[str, Any]],
    max_turns: int = 5,
    append_html: str = "",
    show_debug: bool = True,
    selected_char: str = "AI",
) -> str:
    if not traces and not append_html:
        body = (
            '<div class="wg-empty">'
            '<div class="wg-empty-icon">🎤</div>'
            '<div class="wg-empty-text" style="font-size:1.05rem;font-weight:600;font-style:normal;color:inherit">Drop the situation.</div>'
            '<div class="wg-empty-text" style="margin-top:0.15rem">Your coach will find the line that lands.</div>'
            '<div class="wg-empty-text" style="margin-top:0.6rem;font-size:0.8rem;opacity:0.55;font-style:italic">Awkward, delusional, or painfully relatable — all valid.</div>'
            '</div>'
        )
    else:
        recent = traces[-max_turns:]
        if recent:
            last_trace_payload = _trace_payload_from_result(
                recent[-1][1] if isinstance(recent[-1][1], WitGymResponse) else WitGymResponse.model_validate(recent[-1][1])
            )
            trace_attr = _esc(json.dumps(last_trace_payload, ensure_ascii=True))
        else:
            trace_attr = ""
        body = "".join(
            format_trace_html(
                r if isinstance(r, WitGymResponse) else WitGymResponse.model_validate(r),
                user_input,
                show_debug=show_debug,
                is_last=(i == len(recent) - 1),
                selected_char=selected_char,
            )
            for i, (user_input, r) in enumerate(recent)
        ) + append_html
        return f'<div class="wg-transcript" data-latest-trace="{trace_attr}">{body}</div>{_PAGE_JS}'

    return f'<div class="wg-transcript" data-latest-trace="">{body}</div>{_PAGE_JS}'


# Legacy helpers
def format_trace(result: WitGymResponse, user_input: str) -> str:
    lines = [f"**You:** {user_input}", f"**WitGym:** {result.selected}", ""]
    if result.route not in ("banter", "smalltalk"):
        meta = result.metadata
        lines.append(f"_archetype={meta.archetype.value}, tension={meta.tension_type.value}_")
    return "\n".join(lines)


def format_logs(traces: List[Tuple[str, Any]], max_turns: int = 5) -> str:
    return format_transcript_html(traces, max_turns)
