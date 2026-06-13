"""WitGym Gradio demo for Hugging Face Spaces."""
import html
import os
import threading
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Spaces: default to HF API so we don't load 9B weights on the Space container
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

LOGO_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" fill="none" width="56" height="56">
  <circle cx="32" cy="32" r="30" fill="#f5f0e6" stroke="#c4b8a8" stroke-width="2"/>
  <path d="M18 28c0-6 4-10 14-10s14 4 14 10" stroke="#5c4a3a" stroke-width="2.5" stroke-linecap="round"/>
  <ellipse cx="24" cy="30" rx="5" ry="6" fill="#2d6a4f"/>
  <ellipse cx="40" cy="30" rx="5" ry="6" fill="#2d6a4f"/>
  <path d="M26 42c2 3 10 3 12 0" stroke="#5c4a3a" stroke-width="2" stroke-linecap="round"/>
  <path d="M32 14v4M22 18l3 2M42 18l-3 2" stroke="#b08968" stroke-width="1.5" stroke-linecap="round"/>
</svg>"""

STARTERS = [
    "I've been ignoring a voicemail for so long that opening it now feels like a legal risk.",
    "I'm very low-maintenance. I just have high standards.",
    "I don't micromanage. I just like to stay closely involved in outcomes.",
    "My intern corrected my presentation in front of the client.",
    "I sent a complaint about my manager to my manager.",
    "I've been so invested in this project I forgot to eat today.",
    "I give excellent feedback. People just don't always know how to receive it.",
    "I went to bed early last night.",
]

TRANSCRIPT_MIN_HEIGHT = 420
TRANSCRIPT_MAX_HEIGHT = 560

APP_CSS = """
#witgym-main { max-width: 1200px; margin: 0 auto; width: 100%; }

.witgym-header {
    display: flex; flex-direction: column; align-items: center;
    text-align: center; gap: 0.35rem; margin-bottom: 0.75rem;
}
.witgym-logo { width: 56px; height: 56px; flex-shrink: 0; }
.witgym-title { font-size: 2.15rem; font-weight: 700; margin: 0; color: #3d3429; }
.witgym-tagline { color: #6b6560; margin: 0; font-size: 1.05rem; }

.wg-transcript {
    font-size: 17px; line-height: 1.6; color: #1a1a1a;
}
.wg-empty { color: #777; font-style: italic; padding: 1.5rem 0; text-align: center; }
.wg-turn { margin-bottom: 1.5rem; }
.wg-turn--thinking { cursor: wait; }
.wg-user { color: #16a34a; font-weight: 700; margin-bottom: 0.75rem; font-size: 18px; }
.wg-thinking {
    display: flex; align-items: center; gap: 0.5rem;
    color: #6b6258; font-style: italic; font-size: 1.05rem;
    padding: 0.65rem 0.75rem; margin-top: 0.25rem;
    background: #f3efe8; border-radius: 10px; border: 1px solid #e0d8cc;
}
.wg-thinking-icon { flex-shrink: 0; animation: wg-spin 0.85s linear infinite; }
@keyframes wg-spin { to { transform: rotate(360deg); } }
@media (prefers-reduced-motion: reduce) {
    .wg-thinking-icon { animation: none; }
}
.wg-label { font-weight: 700; margin-right: 0.35rem; }
.wg-coach-divider {
    display: flex; align-items: center; gap: 0.75rem;
    margin: 1rem 0 0.85rem; color: #8a7f72; font-size: 0.72rem;
}
.wg-coach-divider-line {
    flex: 1; height: 1px; background: #d8d0c4;
}
.wg-coach-divider-label {
    white-space: nowrap; font-style: italic; color: #6b6258; font-size: 0.92rem; font-weight: 600;
}
.wg-coach-reply {
    margin-top: 1.1rem; padding: 0.9rem 1rem;
    background: #f7f3ec; border: 1px solid #d4cbb8; border-left: 3px solid #2d6a4f;
    border-radius: 12px;
}
.wg-coach-reply-header {
    font-size: 0.7rem; font-weight: 700; letter-spacing: 0.1em;
    text-transform: uppercase; color: #2d6a4f; margin-bottom: 0.45rem;
}
.wg-coach-reply-body {
    font-size: 1.15rem; line-height: 1.55; color: #2a2520;
}
.wg-coach-reply--compact { margin-top: 0.75rem; }
.wg-rule { border-top: 1px solid #e8e2d8; margin: 0.75rem 0; }
.wg-dim { color: #888; }
.wg-dim-italic { color: #888; font-style: italic; }
.wg-cyan { color: #0891b2; }
.wg-bold { font-weight: 600; }
.wg-panel { border-radius: 10px; padding: 0.65rem 0.85rem; margin: 0.5rem 0;
    border: 1px solid; font-size: 15px; }
.wg-panel-title { font-weight: 700; margin-bottom: 0.35rem; font-size: 14px; }
.wg-panel-yellow { background: #fffbeb; border-color: #fbbf24; color: #92400e; }
.wg-panel-yellow .wg-panel-title { color: #b45309; }
.wg-panel-blue { background: #eff6ff; border-color: #60a5fa; color: #1e3a5f; }
.wg-panel-blue .wg-panel-title { color: #2563eb; }
.wg-panel-green { background: #f0fdf4; border-color: #4ade80; color: #14532d; }
.wg-panel-green .wg-panel-title { color: #16a34a; }
.wg-panel-dim { background: #f5f5f4; border-color: #d6d3d1; color: #78716c; opacity: 0.85; }
.wg-meta { border-collapse: collapse; width: 100%; }
.wg-meta td { padding: 0.15rem 0.5rem 0.15rem 0; vertical-align: top; }

.wg-starter-btn button {
    width: 100%; text-align: left; white-space: normal;
    height: auto !important; min-height: 2.25rem; line-height: 1.35;
}

#wg-chat-shell,
#wg-starters-shell {
    border: 1px solid rgba(216, 212, 200, 0.95);
    background: rgba(250, 249, 246, 0.88);
    border-radius: 14px;
    overflow: hidden;
    box-shadow: 0 1px 4px rgba(61, 52, 41, 0.06);
}
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
    return f'<div class="wg-transcript"><div class="wg-empty">{html.escape(message)}</div></div>'


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
    """Preload embedder/index/model in background — keeps submit queue free."""
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
    """Fast page-load handler — never blocks on model load."""
    if _warmup_error:
        return _loading_html(f"Startup error: {_warmup_error}")
    return format_transcript_html([])


threading.Thread(target=_bg_warmup, daemon=True).start()


def _new_session():
    return {"conversation": ConversationManager(), "traces": []}


def _header_html() -> str:
    return f"""
    <div class="witgym-header">
      <div class="witgym-logo">{LOGO_SVG}</div>
      <p class="witgym-title">WitGym</p>
      <p class="witgym-tagline">Coach your comedy instincts — one situation at a time.</p>
    </div>
    """


def _clear_input():
    return gr.update(value="", interactive=True)


def _disable_input():
    return gr.update(value="", interactive=False)


def fill_starter(text: str) -> str:
    return text


def practice(user_input: str, session, progress=gr.Progress()):
    if not isinstance(session, dict):
        session = _new_session()

    user_input = (user_input or "").strip()
    if not user_input:
        yield format_transcript_html(session["traces"]), _clear_input(), session
        return

    logger.info(f"Practice: {user_input[:80]!r}")
    yield (
        format_transcript_html(session["traces"], append_html=thinking_turn_html(user_input)),
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
            f'<div style="color:#dc2626">Error: {html.escape(str(e))}</div></div>'
        )
        yield format_transcript_html(session["traces"], append_html=err_turn), _clear_input(), session
        return

    session["traces"].append((user_input, result))
    session["traces"] = session["traces"][-5:]

    yield format_transcript_html(session["traces"]), _clear_input(), session


def clear_session():
    return (
        format_transcript_html([]),
        _clear_input(),
        _new_session(),
    )


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
    with gr.Blocks(title="WitGym", fill_height=True) as demo:
        gr.HTML(_header_html())

        session_state = gr.State(_new_session())

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
                            max_lines=1,
                        )
                        with gr.Row():
                            submit_btn = gr.Button(
                                "Start Practicing Humour",
                                variant="primary",
                                scale=4,
                            )
                            clear_btn = gr.Button(
                                "Clear conversation",
                                size="sm",
                                variant="secondary",
                                scale=1,
                            )
                with gr.Column(scale=1):
                    with gr.Group(elem_id="wg-starters-shell"):
                        gr.Markdown("**Try a starter**")
                        for text in STARTERS:
                            starter_btn = gr.Button(
                                text,
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

        submit_btn.click(
            fn=practice,
            inputs=[user_input, session_state],
            outputs=[transcript, user_input, session_state],
            show_progress="full",
            show_progress_on=submit_btn,
        )
        user_input.submit(
            fn=practice,
            inputs=[user_input, session_state],
            outputs=[transcript, user_input, session_state],
            show_progress="full",
            show_progress_on=submit_btn,
        )
        clear_btn.click(
            fn=clear_session,
            outputs=[transcript, user_input, session_state],
        )

        demo.load(fn=_on_page_load, outputs=transcript, show_progress="hidden")

    return demo


demo = build_ui()
demo.queue(default_concurrency_limit=1)
demo.favicon_path = _FAVICON

if __name__ == "__main__":
    launch_kwargs = dict(favicon_path=_FAVICON, theme=_theme(), css=APP_CSS)
    if os.getenv("SPACE_ID"):
        launch_kwargs["server_name"] = "0.0.0.0"
    demo.launch(**launch_kwargs)
