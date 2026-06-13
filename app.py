"""WitGym Gradio demo for Hugging Face Spaces."""
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

LOGO_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" fill="none" width="52" height="52">
  <circle cx="32" cy="32" r="30" fill="#f5f0e6" stroke="#c4b8a8" stroke-width="2"/>
  <path d="M18 28c0-6 4-10 14-10s14 4 14 10" stroke="#5c4a3a" stroke-width="2.5" stroke-linecap="round"/>
  <ellipse cx="24" cy="30" rx="5" ry="6" fill="#2d6a4f"/>
  <ellipse cx="40" cy="30" rx="5" ry="6" fill="#2d6a4f"/>
  <path d="M26 42c2 3 10 3 12 0" stroke="#5c4a3a" stroke-width="2" stroke-linecap="round"/>
  <path d="M32 14v4M22 18l3 2M42 18l-3 2" stroke="#b08968" stroke-width="1.5" stroke-linecap="round"/>
</svg>"""

STARTERS = [
    ("Status", "I just got promoted to manager and I have no idea what I'm doing."),
    ("Social", "My coworker keeps stealing my lunch from the fridge."),
    ("Awkward", "I've been cc'd on an email chain I definitely should not be reading."),
    ("Delusion", "I'm pretending to understand cryptocurrency at dinner parties."),
    ("Confidence", "I give excellent feedback. People just don't know how to receive it."),
    ("Anxiety", "I've been ignoring a voicemail for so long it feels like a legal risk now."),
    ("Procrastination", "I went to bed early last night."),
    ("Self-awareness", "I sent a complaint about my manager to my manager."),
]

TRANSCRIPT_MIN_HEIGHT = 440
TRANSCRIPT_MAX_HEIGHT = 580

APP_CSS = """
:root {
  --wg-bg:          #fffff8;
  --wg-surface:     #faf9f6;
  --wg-surface-alt: #f5f2eb;
  --wg-border:      #e0d8cc;
  --wg-border-soft: rgba(200,190,175,0.5);
  --wg-ink:         #2a2118;
  --wg-ink-muted:   #6b6258;
  --wg-ink-faint:   #9e9288;
  --wg-green:       #2d6a4f;
  --wg-green-light: #f0fdf4;
  --wg-green-border:#4ade80;
  --wg-amber:       #b45309;
  --wg-amber-light: #fffbeb;
  --wg-amber-border:#fbbf24;
  --wg-blue:        #2563eb;
  --wg-blue-light:  #eff6ff;
  --wg-blue-border: #60a5fa;
  --wg-accent:      #3d3429;
  --wg-radius:      12px;
  --wg-radius-sm:   8px;
  --wg-shadow:      0 1px 4px rgba(61,52,41,0.07), 0 0 0 1px rgba(200,190,175,0.35);
  --wg-shadow-card: 0 2px 8px rgba(61,52,41,0.08), 0 0 0 1px rgba(200,190,175,0.4);
}

/* ── Layout ───────────────────────────────────────────────── */
#witgym-main { max-width: 1200px; margin: 0 auto; width: 100%; }

/* ── Header ──────────────────────────────────────────────── */
.wg-header {
  display: flex; flex-direction: column; align-items: center;
  text-align: center; gap: 0.3rem; padding: 1.25rem 1rem 0.5rem;
}
.wg-logo { flex-shrink: 0; }
.wg-title {
  font-size: 2rem; font-weight: 700; margin: 0;
  color: var(--wg-accent); letter-spacing: -0.02em;
}
.wg-tagline { color: var(--wg-ink-muted); margin: 0; font-size: 1rem; font-style: italic; }
.wg-desc {
  font-size: 0.82rem; color: var(--wg-ink-faint); margin: 0.15rem 0 0;
  max-width: 480px; line-height: 1.5;
}

/* ── Shell panels ────────────────────────────────────────── */
#wg-chat-shell {
  border: 1px solid var(--wg-border);
  background: var(--wg-surface);
  border-radius: var(--wg-radius);
  overflow: hidden;
  box-shadow: var(--wg-shadow);
}
#wg-sidebar {
  border: 1px solid var(--wg-border);
  background: var(--wg-surface);
  border-radius: var(--wg-radius);
  overflow: hidden;
  box-shadow: var(--wg-shadow);
  padding: 0.85rem;
  display: flex; flex-direction: column; gap: 0.5rem;
}
.wg-sidebar-heading {
  font-size: 0.68rem; font-weight: 700; letter-spacing: 0.1em;
  text-transform: uppercase; color: var(--wg-ink-faint); margin-bottom: 0.1rem;
}

/* ── Starter buttons ─────────────────────────────────────── */
.wg-starter-btn button {
  width: 100%; text-align: left; white-space: normal;
  height: auto !important; min-height: 2.4rem;
  line-height: 1.35; padding: 0.45rem 0.65rem !important;
  font-size: 0.88rem !important;
  border-radius: var(--wg-radius-sm) !important;
  background: var(--wg-bg) !important;
  border: 1px solid var(--wg-border) !important;
  color: var(--wg-ink) !important;
  transition: background 0.15s, border-color 0.15s, box-shadow 0.15s;
}
.wg-starter-btn button:hover {
  background: var(--wg-surface-alt) !important;
  border-color: var(--wg-green) !important;
  box-shadow: 0 1px 3px rgba(45,106,79,0.1) !important;
}
.wg-starter-tag {
  display: inline-block; font-size: 0.65rem; font-weight: 700;
  text-transform: uppercase; letter-spacing: 0.06em;
  color: var(--wg-green); margin-right: 0.35rem; opacity: 0.8;
}

/* ── Transcript ──────────────────────────────────────────── */
.wg-transcript { font-size: 16px; line-height: 1.65; color: var(--wg-ink); }
.wg-empty {
  color: var(--wg-ink-faint); font-style: italic;
  padding: 2.5rem 1.5rem; text-align: center;
  display: flex; flex-direction: column; align-items: center; gap: 0.6rem;
}
.wg-empty-icon { font-size: 2rem; opacity: 0.5; }
.wg-empty-text { max-width: 300px; line-height: 1.55; }

.wg-turn { margin-bottom: 1.75rem; }
.wg-user {
  color: var(--wg-green); font-weight: 700;
  margin-bottom: 0.65rem; font-size: 17px;
}
.wg-label { font-weight: 700; margin-right: 0.3rem; }

/* Thinking indicator */
.wg-thinking {
  display: flex; align-items: center; gap: 0.5rem;
  color: var(--wg-ink-muted); font-style: italic; font-size: 1rem;
  padding: 0.6rem 0.85rem; margin-top: 0.25rem;
  background: var(--wg-surface-alt); border-radius: var(--wg-radius-sm);
  border: 1px solid var(--wg-border-soft);
}
.wg-thinking-icon { flex-shrink: 0; animation: wg-spin 0.9s linear infinite; }
@keyframes wg-spin { to { transform: rotate(360deg); } }
@media (prefers-reduced-motion: reduce) { .wg-thinking-icon { animation: none; } }

/* Coach reply */
.wg-coach-reply {
  margin-top: 0.9rem; padding: 0.9rem 1.1rem;
  background: var(--wg-green-light);
  border: 1px solid var(--wg-green-border);
  border-left: 3px solid var(--wg-green);
  border-radius: var(--wg-radius);
  box-shadow: var(--wg-shadow-card);
}
.wg-coach-reply-header {
  font-size: 0.68rem; font-weight: 700; letter-spacing: 0.1em;
  text-transform: uppercase; color: var(--wg-green); margin-bottom: 0.45rem;
}
.wg-coach-reply-body {
  font-size: 1.18rem; line-height: 1.6; color: #1a2e22; font-weight: 500;
}
.wg-coach-reply--compact { margin-top: 0.5rem; }

/* Debug divider */
.wg-debug-toggle {
  display: flex; align-items: center; gap: 0.65rem;
  margin: 0.85rem 0 0.5rem; cursor: pointer; user-select: none;
}
.wg-debug-toggle-line { flex: 1; height: 1px; background: var(--wg-border); }
.wg-debug-toggle-label {
  font-size: 0.75rem; font-style: italic; color: var(--wg-ink-faint);
  white-space: nowrap; font-weight: 500;
  padding: 0.15rem 0.5rem;
  border: 1px solid var(--wg-border); border-radius: 20px;
  background: var(--wg-surface-alt);
  transition: color 0.15s, border-color 0.15s;
}
.wg-debug-toggle-label:hover { color: var(--wg-ink-muted); border-color: #c0b8aa; }
.wg-debug-chevron {
  font-size: 0.65rem; color: var(--wg-ink-faint); transition: transform 0.2s;
  display: inline-block; margin-left: 0.25rem;
}
.wg-debug-body { overflow: hidden; transition: opacity 0.2s; }
.wg-debug-body.wg-collapsed { display: none; }

/* Debug panels */
.wg-panel {
  border-radius: var(--wg-radius-sm); padding: 0.65rem 0.85rem;
  margin: 0.45rem 0; border: 1px solid; font-size: 14px;
  box-shadow: 0 1px 2px rgba(0,0,0,0.04);
}
.wg-panel-title {
  font-weight: 700; margin-bottom: 0.35rem; font-size: 12px;
  text-transform: uppercase; letter-spacing: 0.05em;
}
.wg-panel-yellow { background: var(--wg-amber-light); border-color: var(--wg-amber-border); color: #78350f; }
.wg-panel-yellow .wg-panel-title { color: var(--wg-amber); }
.wg-panel-blue { background: var(--wg-blue-light); border-color: var(--wg-blue-border); color: #1e3a5f; }
.wg-panel-blue .wg-panel-title { color: var(--wg-blue); }
.wg-panel-green { background: var(--wg-green-light); border-color: var(--wg-green-border); color: #14532d; }
.wg-panel-green .wg-panel-title { color: var(--wg-green); }
.wg-panel-dim { background: #f5f5f4; border-color: #d6d3d1; color: #78716c; opacity: 0.8; }
.wg-meta { border-collapse: collapse; width: 100%; }
.wg-meta td { padding: 0.12rem 0.5rem 0.12rem 0; vertical-align: top; }
.wg-rule { border-top: 1px solid var(--wg-border); margin: 0.75rem 0; }
.wg-dim { color: var(--wg-ink-faint); }
.wg-dim-italic { color: var(--wg-ink-faint); font-style: italic; }
.wg-cyan { color: #0891b2; font-weight: 500; }
.wg-bold { font-weight: 600; }

/* Bottom toolbar */
.wg-toolbar {
  display: flex; gap: 0.5rem; align-items: center;
  padding: 0.5rem 0.75rem; background: var(--wg-surface-alt);
  border-top: 1px solid var(--wg-border);
}
"""

# JS injected into transcript HTML to handle collapsible debug sections
_TOGGLE_JS = """
<script>
(function(){
  document.querySelectorAll('.wg-debug-toggle').forEach(function(toggle){
    toggle.addEventListener('click', function(){
      var body = toggle.nextElementSibling;
      var chevron = toggle.querySelector('.wg-debug-chevron');
      var isCollapsed = body.classList.toggle('wg-collapsed');
      if(chevron) chevron.textContent = isCollapsed ? '▶' : '▼';
    });
  });
})();
</script>
"""

_shared = None
_warmup_done = threading.Event()
_warmup_error: str | None = None


def _ensure_index():
    from witgym.retriever import load_index
    load_index(INDEX_PATH)


def _get_shared():
    global _shared
    if _shared is None:
        _ensure_index()
        _shared = get_shared_resources(index_path=INDEX_PATH)
    return _shared


def _loading_html(message: str) -> str:
    return f'<div class="wg-transcript"><div class="wg-empty"><div class="wg-empty-icon">⏳</div><div class="wg-empty-text">{html.escape(message)}</div></div></div>'


def _format_warmup_error(exc: Exception) -> str:
    from witgym.hub_data import get_startup_status
    lines = [str(exc)]
    status = get_startup_status()
    if status:
        lines.append("")
        lines.append("Diagnostics:")
        lines.extend(f"• {entry}" for entry in status)
    return "\n".join(lines)


def _bg_warmup():
    global _warmup_error
    try:
        if config.LLM_BACKEND == "hf_api":
            logger.info("Background warmup: HF API mode — embedder + index only")
        else:
            logger.info("Background warmup: loading local model + embedder + index")
        _get_shared()
    except Exception as e:
        logger.exception("Background warmup failed")
        _warmup_error = _format_warmup_error(e)
    finally:
        _warmup_done.set()


def _on_page_load():
    if _warmup_error:
        return _loading_html(f"Startup error: {_warmup_error}")
    return format_transcript_html([])


threading.Thread(target=_bg_warmup, daemon=True).start()


def _new_session():
    return {"conversation": ConversationManager(), "traces": []}


def _header_html() -> str:
    return f"""
    <div class="wg-header">
      <div class="wg-logo">{LOGO_SVG}</div>
      <p class="wg-title">WitGym</p>
      <p class="wg-tagline">Coach your comedy instincts — one situation at a time.</p>
      <p class="wg-desc">Grounded in iconic <em>The Office</em> scenes via CBR-RAG. Drop a situation, get the wittiest angle back.</p>
    </div>
    """


def _clear_input():
    return gr.update(value="", interactive=True)


def _disable_input():
    return gr.update(value="", interactive=False)


def fill_starter(text: str) -> str:
    return text


def practice(user_input: str, session, show_debug: bool, progress=gr.Progress()):
    if not isinstance(session, dict):
        session = _new_session()

    user_input = (user_input or "").strip()
    if not user_input:
        yield format_transcript_html(session["traces"], show_debug=show_debug), _clear_input(), session
        return

    logger.info(f"Practice: {user_input[:80]!r}")
    yield (
        format_transcript_html(session["traces"], append_html=thinking_turn_html(user_input), show_debug=show_debug),
        _disable_input(),
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
        err_turn = (
            f'<div class="wg-turn"><div class="wg-user"><span class="wg-label">You</span> '
            f'{html.escape(user_input)}</div>'
            f'<div style="color:#dc2626;padding:0.5rem 0">Error: {html.escape(str(e))}</div></div>'
        )
        yield format_transcript_html(session["traces"], append_html=err_turn, show_debug=show_debug), _clear_input(), session
        return

    session["traces"].append((user_input, result))
    session["traces"] = session["traces"][-5:]

    yield format_transcript_html(session["traces"], show_debug=show_debug), _clear_input(), session


def clear_session(show_debug: bool):
    return (
        format_transcript_html([], show_debug=show_debug),
        _clear_input(),
        _new_session(),
    )


def toggle_debug(show_debug: bool, session):
    traces = session.get("traces", []) if isinstance(session, dict) else []
    return format_transcript_html(traces, show_debug=show_debug)


def _theme():
    return (
        gr.themes.Soft(
            primary_hue=gr.themes.colors.stone,
            secondary_hue=gr.themes.colors.amber,
            neutral_hue=gr.themes.colors.stone,
            text_size=gr.themes.sizes.text_lg,
            radius_size=gr.themes.sizes.radius_lg,
            font=(
                "Aptos",
                gr.themes.GoogleFont("EB Garamond"),
                "Garamond",
                "Georgia",
                "Times New Roman",
                "serif",
            ),
        )
        .set(
            body_background_fill="#fffff8",
            block_background_fill="#faf9f6",
            button_primary_background_fill="#3d3429",
            button_primary_background_fill_hover="#4a4034",
            button_primary_text_color="#faf9f6",
        )
    )


def build_ui():
    with gr.Blocks(title="WitGym", fill_height=True, css=APP_CSS, theme=_theme()) as demo:
        gr.HTML(_header_html())

        session_state = gr.State(_new_session())
        show_debug_state = gr.State(False)

        with gr.Column(elem_id="witgym-main"):
            with gr.Row(equal_height=True):
                # ── Main chat column ──────────────────────────────────
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
                            )
                            clear_btn = gr.Button(
                                "New session",
                                size="sm",
                                variant="secondary",
                                scale=1,
                            )

                    # Debug toggle below the shell
                    with gr.Row():
                        debug_toggle = gr.Checkbox(
                            label="Show coaching notes (CBR-RAG debug panels)",
                            value=False,
                            scale=1,
                        )

                # ── Sidebar column ────────────────────────────────────
                with gr.Column(scale=1, elem_id="wg-sidebar"):
                    gr.Markdown("**Try a situation**", elem_classes=["wg-sidebar-heading"])
                    for tag, text in STARTERS:
                        btn_label = f"[{tag}]  {text}"
                        starter_btn = gr.Button(
                            btn_label,
                            size="sm",
                            variant="secondary",
                            elem_classes=["wg-starter-btn"],
                        )
                        starter_btn.click(
                            fn=fill_starter,
                            inputs=[gr.State(text)],
                            outputs=user_input,
                            queue=False,
                        )

        # ── Event wiring ──────────────────────────────────────────────
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
    launch_kwargs = dict(favicon_path=_FAVICON)
    if os.getenv("SPACE_ID"):
        launch_kwargs["server_name"] = "0.0.0.0"
    demo.launch(**launch_kwargs)
