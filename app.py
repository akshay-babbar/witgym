"""WitGym Gradio demo — dark gym aesthetic matching design spec."""
import html
import os
import threading
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

if os.getenv("SPACE_ID"):
    os.environ.setdefault("LLM_BACKEND", "hf_api")

import gradio as gr
from loguru import logger

from witgym.conversation import ConversationManager
from witgym.engine import WitGymEngine, get_shared_resources
from witgym.debug_render import format_transcript_html, thinking_turn_html
from witgym import config

INDEX_PATH = os.getenv("WITGYM_INDEX_PATH", config.INDEX_PATH)
_FAVICON = Path(__file__).parent / "assets" / "favicon.png"

# ── Character coaching panel data ────────────────────────────────────────────
# (name, role, card-bg, skin, hair-color, hair-top-y, mouth-path)
_CHARS = [
    ("Michael",  "comedian",    "#5a1a0a", "#e8b090", "#3d1a08", 21, "M24 41 Q32 48 40 41"),
    ("Dwight",   "contrarian",  "#2d3d1a", "#d4a574", "#2a1f0a", 19, "M24 41 L40 41"),
    ("Jim",      "wit",         "#1a2d4a", "#e8c5a0", "#2a1a0a", 21, "M26 40 Q33 44 39 39"),
    ("Pam",      "empath",      "#5a1a4a", "#e8b090", "#1a0a00", 17, "M24 41 Q32 48 40 41"),
    ("Kevin",    "literalist",  "#3d1a5a", "#c47a3a", "#1a0a00", 20, "M24 41 L40 41"),
    ("Andy",     "overclaimer", "#7a3010", "#e8c5a0", "#c8a020", 21, "M22 40 Q32 49 42 40"),
    ("Stanley",  "cynic",       "#0f2d1a", "#7a4a2a", "#0a0a0a", 20, "M24 42 Q32 37 40 42"),
    ("Angela",   "moralist",    "#2a2a0a", "#f0d0b0", "#c8c040", 21, "M25 42 L39 42"),
    ("Ryan",     "hustler",     "#1f0a2d", "#d0906a", "#0a0a0a", 20, "M26 40 Q33 44 39 39"),
    ("Kelly",    "enthusiast",  "#6a0a3a", "#c47a4a", "#0a0a0a", 20, "M22 40 Q32 49 42 40"),
]

# ── Mascot SVG (smiley with wide rectangular sunglasses) ─────────────────────
_MASCOT_SVG = """<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg" class="wg-mascot" width="110" height="110" aria-hidden="true">
  <circle cx="50" cy="50" r="44" fill="#f0ebe0" stroke="#d4cfc0" stroke-width="1.5"/>
  <rect x="7"  y="34" width="35" height="22" rx="6" fill="#1a3d2b"/>
  <rect x="58" y="34" width="35" height="22" rx="6" fill="#1a3d2b"/>
  <rect x="42" y="42" width="16" height="6"  rx="2" fill="#1a3d2b"/>
  <path d="M34 68 Q50 80 66 68" stroke="#5c4a3a" stroke-width="3" fill="none" stroke-linecap="round"/>
</svg>"""

STARTERS = [
    ("Status",         "I just got promoted to manager and I have no idea what I'm doing."),
    ("Social",         "My coworker keeps stealing my lunch from the fridge."),
    ("Awkward",        "I've been cc'd on an email chain I definitely should not be reading."),
    ("Delusion",       "I'm pretending to understand cryptocurrency at dinner parties."),
    ("Confidence",     "I give excellent feedback. People just don't know how to receive it."),
    ("Anxiety",        "I've been ignoring a voicemail so long it feels like a legal risk."),
    ("Procrastination","I went to bed early last night."),
    ("Self-awareness", "I sent a complaint about my manager to my manager."),
]

TRANSCRIPT_MIN_HEIGHT = 440
TRANSCRIPT_MAX_HEIGHT = 580

APP_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=EB+Garamond:ital,wght@0,400;0,600;1,400&display=swap');

/* ── Global dark base ──────────────────────────────────────────── */
body, .gradio-container, .main, footer { background: #141414 !important; }
.gradio-container { min-height: 100vh; }

:root {
  --wg-bg:     #141414;
  --wg-surf:   #1e1e1e;
  --wg-surf2:  #252525;
  --wg-border: #2e2e2e;
  --wg-yellow: #f5c518;
  --wg-green:  #2d6a4f;
  --wg-white:  #f0f0f0;
  --wg-muted:  #777;
  --wg-dim:    #444;
  --wg-r:      10px;
}

/* ── Landing / Hero ────────────────────────────────────────────── */
.wg-hero {
  position: relative; min-height: 100svh;
  display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  background: var(--wg-bg); overflow: hidden;
  padding: 2rem 1rem 3rem; text-align: center;
}
.wg-hero::before {
  content: ''; position: absolute; inset: 0;
  background-image: radial-gradient(rgba(255,255,255,0.045) 1px, transparent 1px);
  background-size: 24px 24px; pointer-events: none;
}

/* REC indicator */
.wg-rec {
  position: absolute; top: 1.5rem; right: 1.75rem;
  display: flex; align-items: center; gap: 0.4rem;
  font-family: 'Courier New', monospace;
  font-size: 0.72rem; font-weight: 700;
  color: #e53e3e; letter-spacing: 0.2em; z-index: 1;
}
.wg-rec-dot {
  width: 8px; height: 8px; border-radius: 50%;
  background: #e53e3e; animation: wg-pulse 1.5s ease-in-out infinite;
}
@keyframes wg-pulse { 0%,100%{opacity:1} 50%{opacity:.35} }

/* Kicker */
.wg-kicker {
  font-family: 'EB Garamond', Georgia, serif;
  font-style: italic; font-size: 0.8rem;
  letter-spacing: 0.22em; color: var(--wg-yellow);
  text-transform: uppercase; margin-bottom: 1.1rem; z-index: 1;
}

/* Mascot */
.wg-mascot { margin-bottom: 0.6rem; z-index: 1;
  filter: drop-shadow(0 4px 20px rgba(45,106,79,0.3)); }

/* WIT / GYM wordmark */
.wg-wordmark {
  display: flex; flex-direction: column;
  align-items: center; line-height: 0.88;
  margin-bottom: 1rem; z-index: 1;
}
.wg-wordmark-wit, .wg-wordmark-gym {
  font-family: 'Bebas Neue', Impact, 'Arial Black', sans-serif;
  font-size: clamp(5.5rem, 20vw, 10rem); letter-spacing: 0.03em;
}
.wg-wordmark-wit { color: var(--wg-white); }
.wg-wordmark-gym { color: var(--wg-yellow); }

.wg-hero-tagline {
  font-family: 'EB Garamond', Georgia, serif; font-style: italic;
  font-size: 1.05rem; color: rgba(240,240,240,0.7);
  margin-bottom: 2rem; z-index: 1;
}

/* START TRAINING button */
#wg-start-btn { z-index: 1; justify-content: center !important; }
#wg-start-btn button {
  font-family: 'Bebas Neue', Impact, sans-serif !important;
  font-size: 1.2rem !important; letter-spacing: 0.22em !important;
  background: var(--wg-green) !important; color: #fff !important;
  border: none !important; border-radius: 50px !important;
  padding: 0.8rem 3.5rem !important; min-width: 220px;
  transition: background .2s, transform .15s;
}
#wg-start-btn button:hover {
  background: #235a40 !important; transform: translateY(-2px);
}

.wg-start-hint {
  font-size: 0.75rem; color: var(--wg-muted);
  margin-top: 0.65rem; font-style: italic; z-index: 1;
}

/* ── Coaching panel ────────────────────────────────────────────── */
.wg-coach-panel {
  width: 100%; padding: 2rem 1rem 2.5rem;
  background: var(--wg-bg); border-top: 1px solid var(--wg-border);
}
.wg-coach-divider {
  display: flex; align-items: center; gap: 1rem; margin-bottom: 1.5rem;
}
.wg-coach-div-line { flex: 1; height: 1px; background: var(--wg-dim); }
.wg-coach-div-text {
  font-family: 'Bebas Neue', Impact, sans-serif;
  font-size: 0.85rem; letter-spacing: 0.3em;
  color: var(--wg-yellow); white-space: nowrap;
}
.wg-char-grid {
  display: flex; flex-wrap: wrap; justify-content: center;
  gap: 0.65rem; max-width: 880px; margin: 0 auto;
}
.wg-char-card {
  display: flex; flex-direction: column; align-items: center;
  gap: 0.35rem; background: var(--wg-surf2);
  border-radius: var(--wg-r); padding: 0.6rem 0.4rem; width: 76px;
  border: 1px solid var(--wg-border);
  transition: border-color .15s, transform .15s;
}
.wg-char-card:hover { border-color: var(--wg-yellow); transform: translateY(-3px); }
.wg-char-name {
  font-family: 'Bebas Neue', sans-serif; font-size: 0.75rem;
  letter-spacing: 0.05em; color: var(--wg-white); text-align: center;
}
.wg-char-role {
  font-family: 'EB Garamond', serif; font-style: italic;
  font-size: 0.58rem; color: var(--wg-muted); text-align: center;
}

/* ── Practice screen header (compact) ─────────────────────────── */
.wg-practice-bar {
  display: flex; align-items: center; gap: 0.75rem;
  padding: 0.75rem 1.25rem; border-bottom: 1px solid var(--wg-border);
  background: var(--wg-bg); position: sticky; top: 0; z-index: 10;
}
.wg-practice-logo {
  font-family: 'Bebas Neue', Impact, sans-serif;
  font-size: 1.6rem; letter-spacing: 0.08em; color: var(--wg-white); line-height: 1;
}
.wg-practice-logo span { color: var(--wg-yellow); }
.wg-practice-sub {
  font-family: 'EB Garamond', Georgia, serif; font-style: italic;
  font-size: 0.8rem; color: var(--wg-muted);
}

/* ── Main layout ───────────────────────────────────────────────── */
#witgym-main { max-width: 1200px; margin: 0 auto; padding: 0.75rem 0.5rem 1rem; }

/* Chat shell */
#wg-chat-shell {
  background: var(--wg-surf) !important;
  border: 1px solid var(--wg-border) !important;
  border-radius: var(--wg-r) !important; overflow: hidden;
}

/* Inputs */
.gradio-container textarea,
.gradio-container input[type="text"] {
  background: #1a1a1a !important; color: var(--wg-white) !important;
  border-color: var(--wg-border) !important;
}
.gradio-container textarea::placeholder,
.gradio-container input[type="text"]::placeholder { color: var(--wg-muted) !important; }

/* Secondary buttons */
.gradio-container button.secondary {
  background: var(--wg-surf2) !important; border-color: var(--wg-border) !important;
  color: rgba(240,240,240,.85) !important;
}
.gradio-container button.secondary:hover { border-color: var(--wg-yellow) !important; }

/* Submit button */
#wg-submit-btn button {
  background: var(--wg-green) !important;
  font-family: 'Bebas Neue', sans-serif !important;
  letter-spacing: 0.18em !important; font-size: 1rem !important;
  transition: background .2s;
}
#wg-submit-btn button:hover { background: #235a40 !important; }

/* Sidebar */
#wg-sidebar {
  background: var(--wg-surf) !important; border: 1px solid var(--wg-border) !important;
  border-radius: var(--wg-r) !important; padding: 0.85rem !important;
}
.wg-sidebar-label {
  font-family: 'Bebas Neue', sans-serif; font-size: 0.9rem;
  letter-spacing: 0.15em; color: var(--wg-muted); margin-bottom: 0.4rem;
}

/* Starter buttons */
.wg-starter-btn button {
  width: 100%; text-align: left; white-space: normal;
  height: auto !important; min-height: 2.1rem;
  line-height: 1.3; padding: 0.38rem 0.55rem !important;
  font-size: 0.82rem !important; font-family: 'EB Garamond', serif !important;
  border-radius: 7px !important;
  background: var(--wg-surf2) !important; border: 1px solid var(--wg-border) !important;
  color: rgba(240,240,240,.8) !important; transition: border-color .15s, background .15s;
}
.wg-starter-btn button:hover {
  border-color: var(--wg-yellow) !important; background: #1a1500 !important;
}

/* ── Transcript ────────────────────────────────────────────────── */
.wg-transcript { font-size: 16px; line-height: 1.65; color: var(--wg-white); }
.wg-empty {
  color: var(--wg-muted); font-style: italic; font-family: 'EB Garamond', serif;
  padding: 2.5rem 1.5rem; text-align: center;
  display: flex; flex-direction: column; align-items: center; gap: 0.6rem;
}
.wg-empty-icon { font-size: 2rem; opacity: 0.45; }
.wg-empty-text { max-width: 280px; line-height: 1.55; }

.wg-turn { margin-bottom: 1.75rem; }
.wg-user { color: #4ade80; font-weight: 700; margin-bottom: 0.65rem; font-size: 17px; }
.wg-label { font-weight: 700; margin-right: 0.3rem; }

.wg-thinking {
  display: flex; align-items: center; gap: 0.5rem;
  color: var(--wg-muted); font-style: italic; font-size: 0.95rem;
  padding: 0.6rem 0.85rem; margin-top: 0.25rem;
  background: var(--wg-surf2); border-radius: 8px; border: 1px solid var(--wg-border);
}
.wg-thinking-icon { flex-shrink: 0; animation: wg-spin .9s linear infinite; }
@keyframes wg-spin { to { transform: rotate(360deg); } }
@media (prefers-reduced-motion: reduce) { .wg-thinking-icon { animation: none; } }

.wg-coach-reply {
  margin-top: 0.85rem; padding: 0.9rem 1.1rem;
  background: #051a0a; border: 1px solid var(--wg-green);
  border-left: 3px solid var(--wg-yellow); border-radius: var(--wg-r);
}
.wg-coach-reply-header {
  font-family: 'Bebas Neue', sans-serif; font-size: 0.82rem;
  letter-spacing: 0.15em; color: var(--wg-yellow); margin-bottom: 0.4rem;
}
.wg-coach-reply-body {
  font-family: 'EB Garamond', Georgia, serif;
  font-size: 1.2rem; line-height: 1.6; color: #c6f6d5; font-weight: 500;
}
.wg-coach-reply--compact { margin-top: 0.5rem; }

/* Debug toggle */
.wg-debug-toggle {
  display: flex; align-items: center; gap: 0.6rem;
  margin: 0.8rem 0 0.4rem; cursor: pointer; user-select: none;
}
.wg-debug-toggle-line { flex: 1; height: 1px; background: var(--wg-border); }
.wg-debug-toggle-label {
  font-family: 'EB Garamond', serif; font-style: italic;
  font-size: 0.75rem; color: var(--wg-muted); white-space: nowrap;
  padding: 0.12rem 0.45rem; border: 1px solid var(--wg-border);
  border-radius: 20px; background: var(--wg-surf2); transition: color .15s;
}
.wg-debug-toggle-label:hover { color: var(--wg-yellow); }
.wg-debug-chevron { font-size: 0.6rem; margin-left: 0.2rem; }
.wg-debug-body.wg-collapsed { display: none; }

/* Debug panels */
.wg-panel {
  border-radius: 7px; padding: 0.6rem 0.8rem;
  margin: 0.35rem 0; border: 1px solid; font-size: 13px;
}
.wg-panel-title {
  font-family: 'Bebas Neue', sans-serif; font-size: 0.75rem;
  letter-spacing: 0.08em; margin-bottom: 0.3rem;
}
.wg-panel-yellow { background: #1a1000; border-color: #6b3a0a; color: #fcd34d; }
.wg-panel-yellow .wg-panel-title { color: #fbbf24; }
.wg-panel-blue   { background: #050e1e; border-color: #1e3558; color: #93c5fd; }
.wg-panel-blue   .wg-panel-title { color: #60a5fa; }
.wg-panel-green  { background: #041409; border-color: #145228; color: #86efac; }
.wg-panel-green  .wg-panel-title { color: #4ade80; }
.wg-panel-dim    { background: #111; border-color: var(--wg-border); color: var(--wg-muted); }
.wg-meta { border-collapse: collapse; width: 100%; }
.wg-meta td { padding: 0.1rem 0.5rem 0.1rem 0; vertical-align: top; }
.wg-rule { border-top: 1px solid var(--wg-border); margin: 0.75rem 0; }
.wg-dim { color: var(--wg-muted); }
.wg-dim-italic { color: var(--wg-muted); font-style: italic; }
.wg-cyan { color: #22d3ee; font-weight: 500; }
.wg-bold { font-weight: 600; }

/* Checkbox label */
.gradio-container label span { color: var(--wg-muted) !important; font-size: 0.82rem !important; }
"""

# ── HTML generators ───────────────────────────────────────────────────────────

def _coaching_panel_html() -> str:
    cards = []
    for name, role, bg, skin, hair, hair_y, mouth in _CHARS:
        ellipse_ry = max(3, 36 - hair_y + 3)
        face = (
            f'<circle cx="32" cy="36" r="16" fill="{skin}"/>'
            f'<ellipse cx="32" cy="{hair_y}" rx="14" ry="{ellipse_ry}" fill="{hair}"/>'
            '<circle cx="27" cy="33" r="2" fill="#111"/>'
            '<circle cx="37" cy="33" r="2" fill="#111"/>'
            f'<path d="{mouth}" stroke="#2a2a2a" stroke-width="1.8" fill="none" stroke-linecap="round"/>'
        )
        cards.append(
            f'<div class="wg-char-card">'
            f'<svg viewBox="0 0 64 58" xmlns="http://www.w3.org/2000/svg" width="58" height="52">'
            f'<rect width="64" height="58" rx="8" fill="{bg}"/>{face}'
            f'</svg>'
            f'<span class="wg-char-name">{name}</span>'
            f'<span class="wg-char-role">{role}</span>'
            f'</div>'
        )
    return (
        '<div class="wg-coach-panel">'
        '<div class="wg-coach-divider">'
        '<span class="wg-coach-div-line"></span>'
        '<span class="wg-coach-div-text">— COACHING PANEL —</span>'
        '<span class="wg-coach-div-line"></span>'
        '</div>'
        f'<div class="wg-char-grid">{"".join(cards)}</div>'
        '</div>'
    )


def _landing_html() -> str:
    return (
        '<div class="wg-hero">'
        '<div class="wg-rec"><span class="wg-rec-dot"></span>REC</div>'
        '<div class="wg-kicker">CBR-RAG Comedy Coaching Engine</div>'
        f'{_MASCOT_SVG}'
        '<div class="wg-wordmark">'
        '<div class="wg-wordmark-wit">WIT</div>'
        '<div class="wg-wordmark-gym">GYM</div>'
        '</div>'
        '<p class="wg-hero-tagline">Coach your comedy instincts — one situation at a time.</p>'
        '</div>'
    )


def _practice_header_html() -> str:
    return (
        '<div class="wg-practice-bar">'
        '<div class="wg-practice-logo">WIT<span>GYM</span></div>'
        '<div class="wg-practice-sub">CBR-RAG Comedy Engine</div>'
        '</div>'
    )


# ── App state & engine ────────────────────────────────────────────────────────

_shared = None
_warmup_error: str | None = None


def _get_shared():
    global _shared
    if _shared is None:
        from witgym.retriever import load_index
        load_index(INDEX_PATH)
        _shared = get_shared_resources(index_path=INDEX_PATH)
    return _shared


def _format_warmup_error(exc: Exception) -> str:
    from witgym.hub_data import get_startup_status
    lines = [str(exc)]
    status = get_startup_status()
    if status:
        lines += ["", "Diagnostics:"] + [f"• {e}" for e in status]
    return "\n".join(lines)


def _bg_warmup():
    global _warmup_error
    try:
        _get_shared()
    except Exception as e:
        logger.exception("Background warmup failed")
        _warmup_error = _format_warmup_error(e)


threading.Thread(target=_bg_warmup, daemon=True).start()


def _new_session():
    return {"conversation": ConversationManager(), "traces": []}


def _err_html(msg: str) -> str:
    return f'<div class="wg-transcript"><div class="wg-empty"><div class="wg-empty-icon">⚠️</div><div class="wg-empty-text">{html.escape(msg)}</div></div></div>'


def _on_page_load():
    if _warmup_error:
        return _err_html(f"Startup error: {_warmup_error}")
    return format_transcript_html([])


def fill_starter(text: str) -> str:
    return text


def practice(user_input: str, session, show_debug: bool, progress=gr.Progress()):
    if not isinstance(session, dict):
        session = _new_session()
    user_input = (user_input or "").strip()
    if not user_input:
        yield format_transcript_html(session["traces"], show_debug=show_debug), gr.update(value="", interactive=True), session
        return

    logger.info(f"Practice: {user_input[:80]!r}")
    yield (
        format_transcript_html(session["traces"], append_html=thinking_turn_html(user_input), show_debug=show_debug),
        gr.update(value="", interactive=False),
        session,
    )

    progress(0.05, desc="Warming up coach…")
    engine = WitGymEngine(resources=_get_shared(), conversation=session["conversation"])
    progress(0.25, desc="Reading the room…")
    try:
        result = engine.respond(user_input)
        progress(0.95, desc="Polishing the line…")
    except Exception as e:
        logger.exception("Engine error")
        err = (
            f'<div class="wg-turn"><div class="wg-user"><span class="wg-label">You</span> '
            f'{html.escape(user_input)}</div>'
            f'<div style="color:#f87171;padding:.5rem 0">Error: {html.escape(str(e))}</div></div>'
        )
        yield format_transcript_html(session["traces"], append_html=err, show_debug=show_debug), gr.update(value="", interactive=True), session
        return

    session["traces"].append((user_input, result))
    session["traces"] = session["traces"][-5:]
    yield format_transcript_html(session["traces"], show_debug=show_debug), gr.update(value="", interactive=True), session


def clear_session(show_debug: bool):
    return format_transcript_html([], show_debug=show_debug), gr.update(value="", interactive=True), _new_session()


def toggle_debug(show_debug: bool, session):
    traces = session.get("traces", []) if isinstance(session, dict) else []
    return format_transcript_html(traces, show_debug=show_debug)


# ── Theme ─────────────────────────────────────────────────────────────────────

def _theme():
    return (
        gr.themes.Base(
            primary_hue=gr.themes.colors.green,
            secondary_hue=gr.themes.colors.yellow,
            neutral_hue=gr.themes.colors.zinc,
        )
        .set(
            body_background_fill="#141414",
            block_background_fill="#1e1e1e",
            button_primary_background_fill="#2d6a4f",
            button_primary_background_fill_hover="#235a40",
            button_primary_text_color="#ffffff",
            input_background_fill="#1a1a1a",
            input_border_color="#2e2e2e",
            border_color_primary="#2e2e2e",
            color_accent_soft="#f5c518",
        )
    )


# ── UI ────────────────────────────────────────────────────────────────────────

def build_ui():
    with gr.Blocks(title="WitGym", css=APP_CSS, theme=_theme()) as demo:
        session_state = gr.State(_new_session())
        show_debug_state = gr.State(False)

        # ── Landing screen ────────────────────────────────────────
        with gr.Column(visible=True) as landing_col:
            gr.HTML(_landing_html())
            with gr.Row(elem_id="wg-start-btn"):
                start_btn = gr.Button("START TRAINING →", variant="primary", size="lg")
            gr.HTML('<p class="wg-start-hint">Paste any real-life awkward situation to begin</p>')
            gr.HTML(_coaching_panel_html())

        # ── Practice screen ───────────────────────────────────────
        with gr.Column(visible=False) as practice_col:
            gr.HTML(_practice_header_html())

            with gr.Column(elem_id="witgym-main"):
                with gr.Row(equal_height=True):
                    with gr.Column(scale=3):
                        with gr.Group(elem_id="wg-chat-shell"):
                            transcript = gr.HTML(
                                value=format_transcript_html([]),
                                min_height=TRANSCRIPT_MIN_HEIGHT,
                                max_height=TRANSCRIPT_MAX_HEIGHT,
                                autoscroll=True,
                                show_label=False,
                                padding=True,
                            )
                            user_input = gr.Textbox(
                                show_label=False,
                                placeholder="Describe a situation… (Enter to send)",
                                lines=1,
                                max_lines=3,
                            )
                            with gr.Row():
                                submit_btn = gr.Button(
                                    "Practice Wit →",
                                    variant="primary",
                                    scale=4,
                                    elem_id="wg-submit-btn",
                                )
                                clear_btn = gr.Button("New session", size="sm", variant="secondary", scale=1)

                        with gr.Row():
                            debug_toggle = gr.Checkbox(
                                label="Show coaching notes (CBR-RAG debug panels)",
                                value=False,
                            )

                    with gr.Column(scale=1, elem_id="wg-sidebar"):
                        gr.HTML('<div class="wg-sidebar-label">Try a situation</div>')
                        for tag, text in STARTERS:
                            sb = gr.Button(f"[{tag}] {text}", size="sm", variant="secondary", elem_classes=["wg-starter-btn"])
                            sb.click(fn=fill_starter, inputs=[gr.State(text)], outputs=user_input, queue=False)

        # ── Event wiring ──────────────────────────────────────────
        start_btn.click(
            fn=lambda: (gr.update(visible=False), gr.update(visible=True)),
            outputs=[landing_col, practice_col],
            queue=False,
        )
        submit_btn.click(
            fn=practice,
            inputs=[user_input, session_state, show_debug_state],
            outputs=[transcript, user_input, session_state],
            show_progress="full",
            show_progress_on=submit_btn,
        )
        user_input.submit(
            fn=practice,
            inputs=[user_input, session_state, show_debug_state],
            outputs=[transcript, user_input, session_state],
            show_progress="full",
            show_progress_on=submit_btn,
        )
        clear_btn.click(
            fn=clear_session,
            inputs=[show_debug_state],
            outputs=[transcript, user_input, session_state],
        )
        debug_toggle.change(
            fn=lambda v, s: (v, toggle_debug(v, s)),
            inputs=[debug_toggle, session_state],
            outputs=[show_debug_state, transcript],
            queue=False,
        )

        demo.load(fn=_on_page_load, outputs=transcript, show_progress="hidden")

    return demo


demo = build_ui()
demo.queue(default_concurrency_limit=1)
demo.favicon_path = _FAVICON

if __name__ == "__main__":
    kwargs = dict(favicon_path=_FAVICON)
    if os.getenv("SPACE_ID"):
        kwargs["server_name"] = "0.0.0.0"
    demo.launch(**kwargs)
