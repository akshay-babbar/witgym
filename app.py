"""WitGym Gradio demo — dark gym landing, ivory practice screen."""
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
from witgym.debug_render import (
    format_transcript_html,
    thinking_turn_html,
    StreamingTurnState,
    apply_stream_event,
    format_transcript_with_streaming,
)
from witgym import config
from witgym.avatars import char_avatar_url, char_avatar_svg
from witgym.tts import synthesize_line

INDEX_PATH = os.getenv("WITGYM_INDEX_PATH", config.INDEX_PATH)
_FAVICON = Path(__file__).parent / "assets" / "favicon.png"

# Character data: (name, role-label, card-bg, avatar-url, bio-title, bio-desc)
CHARACTERS = [
    ("Michael",  "comedian",    "#5a1a0a", char_avatar_url("Michael"),
     "Regional Manager",
     "Needs to be the funniest person in the room — always. Even at funerals."),
    ("Dwight",   "contrarian",  "#2d3d1a", char_avatar_url("Dwight"),
     "Assistant (to the) Regional Manager",
     "Treats every situation as a threat to be neutralised through superior preparation."),
    ("Jim",      "wit",         "#1a2d4a", char_avatar_url("Jim"),
     "Sales Representative",
     "Deflects chaos with a raised eyebrow and impeccable comedic timing."),
    ("Pam",      "empath",      "#5a1a4a", char_avatar_url("Pam"),
     "Receptionist → Office Administrator",
     "Finds the kindest possible way to say the unsayable thing everyone else is thinking."),
    ("Kevin",    "literalist",  "#3d1a5a", char_avatar_url("Kevin"),
     "Accountant",
     "Cuts to the literal truth everyone else is too sophisticated to say out loud."),
    ("Andy",     "overclaimer", "#7a3010", char_avatar_url("Andy"),
     "Sales Representative",
     "Overclaims, overshares, and somehow — through sheer confidence — lands it."),
    ("Stanley",  "cynic",       "#0f2d1a", char_avatar_url("Stanley"),
     "Sales Representative",
     "Has seen it all. Cares about essentially none of it. Will now return to his crossword."),
    ("Angela",   "moralist",    "#2a2a0a", char_avatar_url("Angela"),
     "Head of Accounting",
     "Holds the line on decorum, propriety and cats while everything collapses around her."),
    ("Ryan",     "hustler",     "#1f0a2d", char_avatar_url("Ryan"),
     "Temp → VP → Temp → Temp",
     "Dresses up insecurity as strategy. The hustle is the product."),
    ("Kelly",    "enthusiast",  "#6a0a3a", char_avatar_url("Kelly"),
     "Customer Service Representative",
     "Turns raw enthusiasm into an overwhelming and surprisingly effective force of nature."),
]

STARTERS = [
    ("Status",         "I just got promoted to manager and I have no idea what I'm doing."),
    ("Social",         "My coworker keeps stealing my lunch from the fridge."),
    ("Delusion",       "I'm pretending to understand cryptocurrency at dinner parties."),
    ("Anxiety",        "I've been ignoring a voicemail so long it feels like a legal risk."),
    ("Self-aware",     "I sent a complaint about my manager to my manager."),
    ("Coach me",       "Help me respond when someone asks about my job and I don't know what to say."),
]

from witgym.prompts import DRILL_KEYS as _DRILL_KEYS
_drill_text = {v: k for k, v in _DRILL_KEYS.items()}
DRILL_ACTIONS = [
    ("sharpen it",       _drill_text["sharpen"]),
    ("different angle",  _drill_text["angle"]),
    ("explain the joke", _drill_text["explain"]),
]

TRANSCRIPT_MIN_HEIGHT = 440
TRANSCRIPT_MAX_HEIGHT = 580

# ── Mascot SVG ────────────────────────────────────────────────────────────────
_MASCOT = """<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg" class="wg-mascot" width="96" height="96" aria-hidden="true">
  <circle cx="50" cy="50" r="44" fill="#f0ebe0" stroke="#d4cfc0" stroke-width="1.5"/>
  <rect x="7"  y="34" width="35" height="22" rx="6" fill="#1a3d2b"/>
  <rect x="58" y="34" width="35" height="22" rx="6" fill="#1a3d2b"/>
  <rect x="42" y="42" width="16" height="6"  rx="2" fill="#1a3d2b"/>
  <path d="M34 68 Q50 80 66 68" stroke="#5c4a3a" stroke-width="3" fill="none" stroke-linecap="round"/>
</svg>"""

APP_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=EB+Garamond:ital,wght@0,400;0,600;1,400&display=swap');

/* ── Global dark base ──────────────────────────────────────────────────── */
body, .gradio-container, .main { background: #141414 !important; }
footer { display: none !important; height: 0 !important; padding: 0 !important; margin: 0 !important; overflow: hidden !important; }

/* ── Light mode (activated on START TRAINING) ──────────────────────────── */
body.wg-light-mode,
body.wg-light-mode .gradio-container,
body.wg-light-mode .main { background: #f5f0e8 !important; }
body.wg-light-mode footer { display: none !important; }

:root {
  --wg-bg:     #141414;
  --wg-surf:   #1e1e1e;
  --wg-surf2:  #252525;
  --wg-border: #2e2e2e;
  --wg-yellow: #f5c518;
  --wg-green:  #2d6a4f;
  --wg-white:  #f0f0f0;
  --wg-muted:  #777;
  --wg-r:      10px;
}

/* ── Light-mode CSS variable scope — ALL var(--wg-*) inside #wg-practice
   resolve to light values without needing per-class overrides. This is the
   structural fix: dark :root vars don't cascade into the light practice screen.
   We also override Gradio's dark-theme vars (--body-text-color, etc.) so that
   Gradio's own .prose * { color: var(--body-text-color) } rule renders dark text,
   not near-white (#f0f0f0) on our ivory background. */
#wg-practice {
  --wg-bg:     #fffff8;
  --wg-surf:   #faf9f6;
  --wg-surf2:  #f0ece4;
  --wg-border: #e0d8cc;
  --wg-white:  #2a2118;
  --wg-muted:  #9e9288;
  --wg-yellow: #b45309;
  /* --wg-green and --wg-r stay the same across modes */
  /* Gradio dark-theme CSS vars — override so .prose * inherits dark text */
  --body-text-color:         #2a2118;
  --body-text-color-subdued: #6b6258;
  --block-text-color:        #2a2118;
  --block-label-text-color:  #6b6258;
  --input-text:              #2a2118;
  --color-text-body:         #2a2118;
}

/* ── Landing / Hero ─────────────────────────────────────────────────────── */
#wg-landing { background: transparent !important; border: none !important; }
/* Collapse Gradio's default gap between HTML components in landing */
#wg-landing > .svelte-1plpy97, #wg-landing > div { gap: 0 !important; }
#wg-landing .gap-4 { gap: 0 !important; }
#wg-landing .block { padding: 0 !important; margin: 0 !important; min-height: 0 !important; box-shadow: none !important; border: none !important; }

.wg-hero {
  position: relative;
  display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  /* Dot grid scoped to hero only — footer gap below START TRAINING stays solid dark */
  background:
    radial-gradient(circle, rgba(245,197,24,0.18) 1px, transparent 2px) center/24px 24px,
    var(--wg-bg);
  padding: 0.75rem 1rem 0.75rem; text-align: center;
}

/* ● REC indicator — bigger, more visible flicker */
.wg-rec {
  position: absolute; top: 1.5rem; right: 1.75rem;
  display: flex; align-items: center; gap: 0.5rem;
  font-family: 'Courier New', monospace;
  font-size: 0.8rem; font-weight: 700;
  color: #e53e3e; letter-spacing: 0.22em; z-index: 1;
}
.wg-rec-dot {
  width: 12px; height: 12px; border-radius: 50%;
  background: #e53e3e;
  box-shadow: 0 0 8px rgba(229,62,62,0.6);
  animation: wg-pulse 1.4s ease-in-out infinite;
}
@keyframes wg-pulse {
  0%,100% { opacity: 1;   box-shadow: 0 0 8px rgba(229,62,62,0.6); }
  50%      { opacity: 0.1; box-shadow: 0 0 2px rgba(229,62,62,0.1); }
}

/* Kicker */
.wg-kicker {
  font-family: 'EB Garamond', Georgia, serif; font-style: italic;
  font-size: 0.78rem; letter-spacing: 0.22em;
  color: var(--wg-yellow); text-transform: uppercase;
  margin-bottom: 0.25rem; position: relative; z-index: 1;
}

/* Vertical logo: mascot → WIT → GYM stacked, all centered */
.wg-logo-row {
  display: flex; flex-direction: column; align-items: center; gap: 0;
  position: relative; z-index: 1;
}
/* Mascot */
.wg-mascot { position: relative; z-index: 1; margin-bottom: 0.25rem;
  filter: drop-shadow(0 4px 24px rgba(45,106,79,0.4)); }

/* WIT and GYM stacked vertically, each on its own line */
.wg-wordmark { display: flex; flex-direction: column; align-items: center;
  line-height: 0.9; position: relative; z-index: 1; }
/* Huge font — fills ~260px of the 720px viewport so content organically fills height,
   eliminating the empty footer gap without fighting Svelte's height binding. */
.wg-wordmark-wit, .wg-wordmark-gym {
  font-family: 'Bebas Neue', Impact, 'Arial Black', sans-serif;
  font-size: clamp(5rem, 12vw, 8.5rem); letter-spacing: 0.03em; display: block;
}
/* Hardcoded hex + !important: Gradio 6 SSR on HF Spaces injects theme CSS after APP_CSS,
   causing same-specificity cascade override of var(--wg-white/yellow). */
.wg-wordmark-wit { color: #f0f0f0 !important; text-shadow: 0 0 40px rgba(0,0,0,0.6); }
.wg-wordmark-gym { color: #f5c518 !important; text-shadow: 0 2px 20px rgba(0,0,0,0.8), 0 0 60px rgba(0,0,0,0.5); }

.wg-hero-tagline {
  font-family: 'EB Garamond', Georgia, serif; font-style: italic;
  font-size: 1rem; color: rgba(240,240,240,0.7);
  margin-bottom: 1.75rem; position: relative; z-index: 1;
}

.wg-start-hint {
  font-size: 0.72rem; color: var(--wg-muted); margin: 0.15rem 0 0 !important;
  font-style: italic; text-align: center;
  background: transparent !important;
}

/* ── Scroll cue: clickable circle button between tagline and CTA ─────────── */
.wg-scroll-cue {
  display: flex; flex-direction: column; justify-content: center; align-items: center;
  gap: 0.3rem; padding: 0.5rem 1rem 0.75rem; background: transparent !important;
  cursor: pointer; transition: transform .22s ease;
  position: relative; z-index: 1;
}
.wg-scroll-cue:hover { transform: translateY(5px); }
.wg-scroll-circle {
  width: 46px; height: 46px; border-radius: 50%;
  border: 1.5px solid rgba(74,222,128,0.35);
  background: rgba(45,106,79,0.08);
  display: flex; align-items: center; justify-content: center;
  transition: border-color .2s, box-shadow .2s;
}
.wg-scroll-cue:hover .wg-scroll-circle {
  border-color: rgba(74,222,128,0.85);
  box-shadow: 0 0 18px rgba(74,222,128,0.28);
}
.wg-scroll-arrow-svg {
  animation: wg-arrow-fall 1.9s ease-in-out infinite;
  filter: drop-shadow(0 0 4px rgba(74,222,128,0.45));
}
.wg-scroll-label {
  font-family: 'EB Garamond', Georgia, serif; font-style: italic;
  font-size: 0.68rem; color: rgba(74,222,128,0.45);
  letter-spacing: 0.2em; text-transform: uppercase;
  transition: color .2s;
}
.wg-scroll-cue:hover .wg-scroll-label { color: rgba(74,222,128,0.8); }
@keyframes wg-arrow-fall {
  0%,100% { transform: translateY(0);   opacity: 0.55; }
  50%      { transform: translateY(7px); opacity: 1;    }
}

/* ── Real Gradio START TRAINING button ──────────────────────────────────── */
#wg-start-btn { justify-content: center !important; background: transparent !important; padding: 0 !important; }
#wg-start-btn button {
  font-family: 'Bebas Neue', Impact, sans-serif !important;
  font-size: 1.1rem !important; letter-spacing: 0.22em !important;
  background: var(--wg-green) !important; color: #fff !important;
  border: none !important; border-radius: 50px !important;
  padding: 0.55rem 3rem !important;
  transition: background .2s, transform .15s !important;
}
#wg-start-btn button:hover { background: #235a40 !important; transform: translateY(-2px) !important; }

/* ── Coaching panel ─────────────────────────────────────────────────────── */
.wg-coach-panel {
  width: 100%; padding: 0.2rem 1rem 0.15rem;
  background: var(--wg-bg); border-top: none;
}
.wg-coach-divider {
  display: flex; align-items: center; gap: 1rem; margin-bottom: 0.2rem;
}
.wg-coach-div-line { flex: 1; height: 1px; background: #3a3a3a; }
.wg-coach-div-text {
  font-family: 'Bebas Neue', Impact, sans-serif;
  font-size: 0.82rem; letter-spacing: 0.3em; color: var(--wg-yellow); white-space: nowrap;
}
.wg-char-grid {
  display: flex; flex-wrap: wrap; justify-content: center;
  gap: 0.65rem; max-width: 900px; margin: 0 auto;
}
.wg-char-card {
  display: flex; flex-direction: column; align-items: center; gap: 0.3rem;
  background: var(--wg-surf2); border-radius: var(--wg-r);
  padding: 0.65rem 0.4rem 0.55rem; width: 82px;
  border: 1px solid var(--wg-border);
  cursor: pointer; transition: border-color .15s, transform .15s, box-shadow .15s;
}
.wg-char-card:hover {
  border-color: var(--wg-yellow); transform: translateY(-4px);
  box-shadow: 0 8px 24px rgba(245,197,24,0.15);
}
.wg-char-card img { width: 58px; height: 58px; border-radius: 8px; background: transparent; }
.wg-char-name {
  font-family: 'Bebas Neue', sans-serif; font-size: 0.73rem;
  letter-spacing: 0.06em; color: var(--wg-white); text-align: center;
}
.wg-char-role {
  font-family: 'EB Garamond', serif; font-style: italic;
  font-size: 0.58rem; color: var(--wg-muted); text-align: center;
}

/* ── Practice screen header (compact, centered) ─────────────────────────── */
@keyframes wg-header-drop {
  0%   { transform: translateY(-10px) scaleY(0.82); opacity: 0; }
  65%  { transform: translateY(2px) scaleY(1.04);  opacity: 1; }
  100% { transform: translateY(0) scaleY(1); }
}
.wg-practice-bar {
  display: flex; align-items: center; justify-content: center; gap: 0.75rem;
  padding: 0.75rem 1.25rem; border-bottom: 1px solid #d8d0c4;
  background: #faf9f6;
  animation: wg-header-drop 0.42s cubic-bezier(.22,.68,0,1.35) both;
}
.wg-practice-logo {
  font-family: 'Bebas Neue', Impact, sans-serif;
  font-size: 1.5rem; letter-spacing: 0.1em; color: #3d3429; line-height: 1;
}
.wg-practice-logo span { color: var(--wg-green); }
.wg-practice-sub {
  font-family: 'EB Garamond', Georgia, serif; font-style: italic;
  font-size: 0.8rem; color: #9e9288;
}

/* ── Practice screen: ivory/light override ──────────────────────────────── */
#wg-practice { background: #fffff8 !important; }

/* Target Gradio's internal wrappers that carry the dark theme background */
#wg-practice .block,
#wg-practice .gap,
#wg-practice .form,
#wg-practice .scroll-hide,
#wg-practice .styler,
#wg-practice > div,
#wg-practice .gradio-group {
  background: #faf9f6 !important;
  border-color: #e0d8cc !important;
}
#wg-practice #wg-chat-shell,
#wg-practice #wg-chat-shell .block,
#wg-practice #wg-chat-shell .gap {
  background: #faf9f6 !important; border-color: #e0d8cc !important;
}
#wg-practice .wg-transcript { color: #2a2118 !important; }
#wg-practice .wg-user { color: #2d6a4f !important; }
#wg-practice .wg-thinking {
  background: #f5f2eb !important; border-color: rgba(200,190,175,0.5) !important; color: #6b6258 !important;
}
#wg-practice .wg-coach-reply {
  background: #f0fdf4 !important; border-color: #4ade80 !important; border-left-color: #2d6a4f !important;
}
#wg-practice .wg-coach-reply-header { color: #2d6a4f !important; }
#wg-practice .wg-coach-reply-body   { color: #14532d !important; font-size: 1.55rem !important; font-weight: 600 !important; }
#wg-practice .wg-panel-yellow { background: #fffbeb !important; border-color: #fbbf24 !important; color: #78350f !important; }
#wg-practice .wg-panel-yellow .wg-panel-title { color: #b45309 !important; }
#wg-practice .wg-panel-blue   { background: #eff6ff !important; border-color: #60a5fa !important; color: #1e3a5f !important; }
#wg-practice .wg-panel-blue   .wg-panel-title { color: #2563eb !important; }
#wg-practice .wg-panel-green  { background: #f0fdf4 !important; border-color: #4ade80 !important; color: #14532d !important; }
#wg-practice .wg-panel-green  .wg-panel-title { color: #16a34a !important; }
#wg-practice .wg-panel-dim    { background: #f5f5f4 !important; border-color: #d6d3d1 !important; color: #78716c !important; }
#wg-practice .wg-dim   { color: #9e9288 !important; }
#wg-practice .wg-cyan  { color: #0891b2 !important; }
#wg-practice .wg-dim-italic { color: #9e9288 !important; font-style: italic; }
#wg-practice .wg-debug-toggle-line   { background: #e0d8cc !important; }
#wg-practice .wg-debug-toggle-label {
  border-color: #e0d8cc !important; background: #f5f2eb !important; color: #9e9288 !important;
}
#wg-practice .wg-debug-toggle-label:hover { color: #6b6258 !important; }
#wg-practice .wg-rule { border-color: #e0d8cc !important; }
#wg-practice .wg-empty { color: #9e9288 !important; }
#wg-practice #wg-sidebar {
  background: #faf9f6 !important; border-color: #e0d8cc !important;
}
#wg-practice .wg-sidebar-label { color: #9e9288 !important; }
#wg-practice .wg-starter-btn button {
  background: #fff !important; border-color: #e0d8cc !important;
  color: #3d3429 !important;
}
#wg-practice .wg-starter-btn button:hover {
  border-color: var(--wg-green) !important; background: #f0fdf4 !important;
}
#wg-practice textarea,
#wg-practice input,
#wg-practice input[type="text"],
#wg-practice .gradio-container textarea,
#wg-practice .gradio-container input[type="text"] {
  background: #fff !important; color: #2a2118 !important; border-color: #e0d8cc !important;
}
#wg-practice textarea::placeholder,
#wg-practice input::placeholder { color: #9e9288 !important; }
/* Hide native placeholder in chat shell — flicker overlay replaces it */
#wg-chat-shell textarea::placeholder { color: transparent !important; }
#wg-practice button.secondary,
#wg-practice .gradio-container button.secondary {
  background: #f5f2eb !important; border-color: #e0d8cc !important; color: #3d3429 !important;
}
#wg-practice label span,
#wg-practice .gradio-container label span { color: #6b6258 !important; }

/* Main layout */
#witgym-main { max-width: 1200px; margin: 0 auto; padding: 0.75rem 0.5rem 1rem; }

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
  font-family: 'Bebas Neue', sans-serif; font-size: 0.88rem;
  letter-spacing: 0.15em; color: var(--wg-muted); margin-bottom: 0.4rem;
}
.wg-starter-btn button {
  width: 100%; text-align: left; white-space: normal;
  height: auto !important; min-height: 2.1rem; line-height: 1.3;
  padding: 0.38rem 0.55rem !important;
  font-size: 0.82rem !important; font-family: 'EB Garamond', serif !important;
  border-radius: 7px !important;
  background: var(--wg-surf2) !important; border: 1px solid var(--wg-border) !important;
  color: rgba(240,240,240,.82) !important; transition: border-color .15s;
}
.wg-starter-btn button:hover { border-color: var(--wg-yellow) !important; }

/* Chat shell */
#wg-chat-shell {
  background: var(--wg-surf) !important; border: 1px solid var(--wg-border) !important;
  border-radius: var(--wg-r) !important; overflow: hidden;
}

/* Transcript (dark default, overridden in #wg-practice) */
.wg-transcript { font-size: 16px; line-height: 1.65; color: var(--wg-white); }
.wg-empty {
  color: var(--wg-muted); font-style: italic; font-family: 'EB Garamond', serif;
  padding: 2.5rem 1.5rem; text-align: center;
  display: flex; flex-direction: column; align-items: center; gap: 0.6rem;
}
.wg-empty-icon { font-size: 2rem; opacity: 0.4; }
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
  font-family: 'Bebas Neue', sans-serif; font-size: 0.8rem;
  letter-spacing: 0.15em; color: var(--wg-yellow); margin-bottom: 0.4rem;
}
.wg-coach-reply-body {
  font-family: 'EB Garamond', Georgia, serif;
  font-size: 1.55rem; line-height: 1.55; color: #c6f6d5; font-weight: 600;
}
.wg-coach-reply--compact { margin-top: 0.5rem; }

.wg-mode-badge {
  font-family: 'Bebas Neue', sans-serif; font-size: 0.72rem;
  letter-spacing: 0.18em; padding: 0.15rem 0.55rem; border-radius: 20px;
  display: inline-block; margin-bottom: 0.4rem;
}
.wg-mode-banter { background: #1a3d2b; color: #4ade80; border: 1px solid #2d6a4f; }
.wg-mode-wit    { background: #3d2a00; color: #fcd34d; border: 1px solid #92400e; }
.wg-mode-coach  { background: #050e1e; color: #93c5fd; border: 1px solid #1e3558; }

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
  margin: 0.35rem 0; border: 1px solid; font-size: 14px;
}
.wg-panel-title {
  font-family: 'Bebas Neue', sans-serif; font-size: 0.82rem;
  letter-spacing: 0.08em; margin-bottom: 0.35rem;
}
/* Clickable chips */
.wg-chip-clickable {
  cursor: pointer; transition: filter .15s, transform .1s;
}
.wg-chip-clickable:hover { filter: brightness(1.25); transform: scale(1.06); }
.wg-panel-yellow { background: #1a1000; border-color: #6b3a0a; color: #fcd34d; }
.wg-panel-yellow .wg-panel-title { color: #fbbf24; }
.wg-panel-blue   { background: #050e1e; border-color: #1e3558; color: #93c5fd; }
.wg-panel-blue   .wg-panel-title { color: #60a5fa; }
.wg-panel-green  { background: #041409; border-color: #145228; color: #86efac; }
.wg-panel-green  .wg-panel-title { color: #4ade80; }
.wg-panel-dim    { background: #111; border-color: var(--wg-border); color: var(--wg-muted); }
.wg-clickable    { cursor: pointer; transition: opacity .15s, transform .1s; }
.wg-clickable:hover { opacity: 0.85; transform: scale(1.01); }

/* Scene card: gentle border-pulse + arrow float to signal interactivity */
@keyframes wg-scene-beckon {
  0%,100% { box-shadow: 0 0 0 0 rgba(96,165,250,0);    border-color: #1e3558; }
  50%      { box-shadow: 0 0 0 5px rgba(96,165,250,0.2); border-color: #60a5fa; }
}
@keyframes wg-arrow-float {
  0%,100% { transform: translate(0,0);       opacity: 0.6; }
  50%      { transform: translate(2px,-2px);  opacity: 1;   }
}
.wg-panel-blue.wg-clickable {
  animation: wg-scene-beckon 2.8s ease-in-out infinite;
}
.wg-scene-arrow { display: inline-block; animation: wg-arrow-float 2.8s ease-in-out infinite; }
/* Pause animations when user hovers — reduces distraction mid-read */
.wg-panel-blue.wg-clickable:hover { animation: none; }
.wg-panel-blue.wg-clickable:hover .wg-scene-arrow { animation: none; opacity: 1; }
.wg-meta { border-collapse: collapse; width: 100%; }
.wg-meta td { padding: 0.1rem 0.5rem 0.1rem 0; vertical-align: top; }
.wg-rule { border-top: 1px solid var(--wg-border); margin: 0.75rem 0; }

/* ── Coaching notes toggle attention flicker (plays 4× on new turns) ────── */
@keyframes wg-toggle-beckon {
  0%,100% { color: var(--wg-muted); box-shadow: none; }
  40%,60%  { color: var(--wg-yellow); box-shadow: 0 0 10px rgba(245,197,24,0.35); border-color: rgba(245,197,24,0.5); }
}
.wg-debug-toggle--new .wg-debug-toggle-label {
  animation: wg-toggle-beckon 1.1s ease-in-out 0.4s 4 forwards;
}
#wg-practice .wg-debug-toggle--new .wg-debug-toggle-label {
  animation: wg-toggle-beckon-light 1.1s ease-in-out 0.4s 4 forwards;
}
@keyframes wg-toggle-beckon-light {
  0%,100% { color: #9e9288; box-shadow: none; }
  40%,60%  { color: #b45309; box-shadow: 0 0 8px rgba(180,83,9,0.25); border-color: rgba(180,83,9,0.4); }
}

/* ── Metadata chips (dark-mode defaults) ────────────────────────────────── */
.wg-chip-row { display: flex; flex-wrap: wrap; gap: 0.4rem; margin: 0.45rem 0 0.35rem; }
.wg-chip {
  font-family: 'Bebas Neue', sans-serif; font-size: 0.69rem; letter-spacing: 0.1em;
  padding: 0.18rem 0.55rem; border-radius: 20px; display: inline-block; line-height: 1.5;
}
.wg-chip-cyan   { background: #0d2d33; color: #67e8f9; border: 1px solid #164e63; }
.wg-chip-purple { background: #1e1030; color: #c4b5fd; border: 1px solid #4c1d95; }
.wg-chip-orange { background: #2d1a00; color: #fbbf24; border: 1px solid #92400e; }
.wg-chip-green  { background: #0a2018; color: #4ade80; border: 1px solid #1a3d2b; }
.wg-chip-label  { font-size: 0.68rem; color: var(--wg-muted); align-self: center; font-family: 'EB Garamond', serif; font-style: italic; }
.wg-avoided {
  font-size: 0.82rem; color: var(--wg-muted); margin: 0.3rem 0 0.45rem;
  padding: 0.25rem 0; border-top: 1px dashed rgba(255,255,255,0.07);
}
/* Expandable capsules (dark-mode) */
.wg-capsule {
  border: 1px solid var(--wg-border); border-radius: 7px;
  margin-top: 0.38rem; overflow: hidden;
}
.wg-capsule-head {
  cursor: pointer; padding: 0.38rem 0.65rem;
  font-family: 'Bebas Neue', sans-serif; font-size: 0.69rem; letter-spacing: 0.1em;
  color: #888; user-select: none;
  display: flex; justify-content: space-between; align-items: center;
  transition: color .15s, background .15s;
}
.wg-capsule-head:hover { color: var(--wg-white); background: rgba(255,255,255,0.04); }
.wg-capsule-body {
  padding: 0.5rem 0.65rem; font-size: 0.92rem;
  color: rgba(240,240,240,0.88); line-height: 1.55;
  border-top: 1px solid var(--wg-border); background: var(--wg-surf2);
}
.wg-capsule-body.wg-collapsed { display: none; }
.wg-cap-chev { font-size: 0.6rem; transition: transform .18s; display: inline-block; }
.wg-capsule--open .wg-cap-chev { transform: rotate(90deg); }

/* ── Shared shimmer + attention keyframes ────────────────────────────────── */
/* Shimmer: light highlight sweeps L→R — signals "this surface has depth" */
@keyframes wg-shimmer-slide {
  0%   { transform: translateX(-160%); }
  100% { transform: translateX(160%); }
}
/* Chevron bobs toward hidden content — pure motion affordance */
@keyframes wg-chev-beckon {
  0%,100% { transform: translateX(0); }
  40%     { transform: translateX(6px); }
}
/* Border breathes with a warm glow — signals "this boundary is crossable" */
@keyframes wg-capsule-glow {
  0%,100% { border-color: var(--wg-border); box-shadow: none; }
  50%     { border-color: rgba(245,197,24,0.7); box-shadow: 0 0 0 2.5px rgba(245,197,24,0.18); }
}
/* Chip pop-in: slight scale bounce then settles — signals "I'm interactive" */
@keyframes wg-chip-pop {
  0%   { transform: scale(0.88); opacity: 0.6; }
  60%  { transform: scale(1.08); opacity: 1; }
  100% { transform: scale(1);    opacity: 1; }
}
/* Chip shimmer: same sweep but stronger amber */
@keyframes wg-chip-shimmer {
  0%   { transform: translateX(-180%); }
  100% { transform: translateX(180%); }
}

/* ── Capsule attention (border glow + head shimmer + chevron bob) ─────────── */
.wg-capsule--new {
  animation: wg-capsule-glow 1.2s ease-in-out 0.4s 3 both;
}
.wg-capsule--new .wg-capsule-head {
  position: relative; overflow: hidden;
}
.wg-capsule--new .wg-capsule-head::after {
  content: ''; position: absolute; inset: 0; pointer-events: none;
  background: linear-gradient(90deg, transparent 15%, rgba(245,197,24,0.55) 50%, transparent 85%);
  transform: translateX(-160%);
  animation: wg-shimmer-slide 1.1s ease-in-out 0.7s 3 both;
}
.wg-capsule--new .wg-cap-chev {
  animation: wg-chev-beckon 0.5s ease-in-out 0.3s 6 both;
}
/* Kill all animations once the user engages */
.wg-capsule--new.wg-capsule--open,
.wg-capsule--new.wg-capsule--open .wg-capsule-head::after,
.wg-capsule--new.wg-capsule--open .wg-cap-chev { animation: none; }

/* Light-mode capsule overrides */
@keyframes wg-capsule-glow-light {
  0%,100% { border-color: #e0d8cc; box-shadow: none; }
  50%     { border-color: rgba(180,83,9,0.6); box-shadow: 0 0 0 2.5px rgba(180,83,9,0.14); }
}
#wg-practice .wg-capsule--new {
  animation: wg-capsule-glow-light 1.2s ease-in-out 0.4s 3 both;
}
#wg-practice .wg-capsule--new .wg-capsule-head::after {
  background: linear-gradient(90deg, transparent 15%, rgba(180,83,9,0.45) 50%, transparent 85%);
}

/* ── Chip attention: pop-in scale bounce + shimmer sweep ─────────────────── */
.wg-chip-clickable {
  position: relative; overflow: hidden;
  animation: wg-chip-pop 0.45s cubic-bezier(.22,.68,0,1.4) both;
}
/* Stagger the three chips */
.wg-chip-row .wg-chip-clickable:nth-child(1) { animation-delay: 0.05s; }
.wg-chip-row .wg-chip-clickable:nth-child(2) { animation-delay: 0.18s; }
.wg-chip-row .wg-chip-clickable:nth-child(3) { animation-delay: 0.31s; }
/* Shimmer on each chip after its pop-in */
.wg-chip-clickable::after {
  content: ''; position: absolute; inset: 0; pointer-events: none; border-radius: inherit;
  background: linear-gradient(90deg, transparent 10%, rgba(255,255,255,0.55) 50%, transparent 90%);
  transform: translateX(-180%);
  animation: wg-chip-shimmer 0.9s ease-in-out 0.55s 2 both;
}
.wg-chip-row .wg-chip-clickable:nth-child(2)::after { animation-delay: 0.68s; }
.wg-chip-row .wg-chip-clickable:nth-child(3)::after { animation-delay: 0.81s; }

/* ── Coaching notes toggle shimmer ──────────────────────────────────────── */
.wg-debug-toggle--new .wg-debug-toggle-label {
  position: relative; overflow: hidden;
}
.wg-debug-toggle--new .wg-debug-toggle-label::after {
  content: ''; position: absolute; inset: 0; pointer-events: none; border-radius: inherit;
  background: linear-gradient(90deg, transparent 15%, rgba(245,197,24,0.5) 50%, transparent 85%);
  transform: translateX(-160%);
  animation: wg-shimmer-slide 1.3s ease-in-out 0.2s 3 both;
}
#wg-practice .wg-debug-toggle--new .wg-debug-toggle-label::after {
  background: linear-gradient(90deg, transparent 15%, rgba(180,83,9,0.38) 50%, transparent 85%);
}

/* ── Light-mode overrides for chips + capsules ──────────────────────────── */
#wg-practice .wg-chip-cyan   { background: #ecfeff; color: #0e7490; border-color: #a5f3fc; }
#wg-practice .wg-chip-purple { background: #f5f3ff; color: #7c3aed; border-color: #ddd6fe; }
#wg-practice .wg-chip-orange { background: #fffbeb; color: #b45309; border-color: #fde68a; }
#wg-practice .wg-chip-green  { background: #f0fdf4; color: #16a34a; border-color: #bbf7d0; }
#wg-practice .wg-chip-label  { color: #9e9288; }
#wg-practice .wg-avoided     { color: #9e9288; border-top-color: rgba(0,0,0,0.07); }
#wg-practice .wg-capsule      { border-color: #e0d8cc; }
#wg-practice .wg-capsule-head { color: #9e9288 !important; }
#wg-practice .wg-capsule-head:hover { color: #3d3429 !important; background: rgba(0,0,0,0.025) !important; }
#wg-practice .wg-capsule-body { background: #faf9f6 !important; color: #3d3429 !important; border-top-color: #e0d8cc !important; }

/* ── Light-mode overrides for mode badges ───────────────────────────────── */
#wg-practice .wg-mode-banter { background: #dcfce7 !important; color: #15803d !important; border-color: #86efac !important; }
#wg-practice .wg-mode-wit    { background: #fef9c3 !important; color: #92400e !important; border-color: #fde047 !important; }
#wg-practice .wg-mode-coach  { background: #dbeafe !important; color: #1d4ed8 !important; border-color: #93c5fd !important; }
.wg-dim { color: var(--wg-muted); }
.wg-dim-italic { color: var(--wg-muted); font-style: italic; }
.wg-cyan { color: #22d3ee; font-weight: 500; }
.wg-bold { font-weight: 600; }

/* ── Slide-in animation on new turns ───────────────────────────────────── */
@keyframes wg-slide-in {
  from { opacity: 0; transform: translateY(10px); }
  to   { opacity: 1; transform: translateY(0); }
}
.wg-turn { animation: wg-slide-in 0.35s ease-out both; }

/* ── Reveal animation on winning coach reply ────────────────────────────── */
@keyframes wg-reply-reveal {
  from { opacity: 0; transform: translateY(6px); }
  to   { opacity: 1; transform: translateY(0); }
}
.wg-coach-reply--new .wg-coach-reply-body {
  animation: wg-reply-reveal 0.6s ease-out 0.15s both;
}

/* Flash on "another take" swap */
@keyframes wg-alt-flash {
  0%,100% { opacity: 1; }
  40%      { opacity: 0.3; }
}
.wg-coach-reply--alt .wg-coach-reply-body {
  animation: wg-alt-flash 0.35s ease-out;
}

/* ── Twist potential meter ──────────────────────────────────────────────── */
.wg-twist-meter {
  display: flex; align-items: center; gap: 0.5rem;
  margin: 0.6rem 0 0.75rem;
  font-family: 'Bebas Neue', sans-serif; font-size: 0.72rem; letter-spacing: 0.12em;
}
.wg-twist-label { color: var(--wg-muted); white-space: nowrap; }
.wg-twist-bar {
  flex: 1; height: 4px; background: var(--wg-border); border-radius: 2px; overflow: hidden;
}
.wg-twist-fill {
  height: 100%; border-radius: 2px;
  background: linear-gradient(to right, var(--wg-green), var(--wg-yellow));
  transition: width 0.8s ease-out;
}
.wg-twist-score { color: var(--wg-yellow); min-width: 2.5rem; text-align: right; }

/* Light-mode overrides for meter */
#wg-practice .wg-twist-bar { background: #e0d8cc !important; }
#wg-practice .wg-twist-score { color: #b45309 !important; }
#wg-practice .wg-twist-label { color: #9e9288 !important; }


/* ── Drill chips ─────────────────────────────────────────────────────────── */
.wg-drill-chips {
  display: flex; flex-wrap: wrap; gap: 0.45rem;
  margin: 0.6rem 0 0.2rem;
}
.wg-drill-chip {
  font-family: 'EB Garamond', serif; font-style: italic;
  font-size: 0.82rem; cursor: pointer; user-select: none;
  padding: 0.22rem 0.7rem; border-radius: 20px;
  border: 1px solid var(--wg-border); color: var(--wg-muted);
  background: var(--wg-surf2);
  transition: border-color .15s, color .15s, background .15s;
}
.wg-drill-chip:hover {
  border-color: var(--wg-yellow); color: var(--wg-yellow);
  background: rgba(245,197,24,0.06);
}
#wg-practice .wg-drill-chip {
  border-color: #e0d8cc !important; color: #9e9288 !important;
  background: #f5f2eb !important;
}
#wg-practice .wg-drill-chip:hover {
  border-color: #b45309 !important; color: #b45309 !important;
  background: rgba(180,83,9,0.06) !important;
}

/* ── Persona label + another-take ──────────────────────────────────────── */
.wg-persona-label {
  font-style: italic; font-family: 'EB Garamond', serif;
  font-size: 0.78rem; color: var(--wg-yellow); letter-spacing: 0;
  font-weight: 400;
}
#wg-practice .wg-persona-label { color: #b45309 !important; }

.wg-another-take {
  float: right; cursor: pointer; font-family: 'EB Garamond', serif;
  font-size: 0.75rem; font-style: italic; letter-spacing: 0;
  color: rgba(245,197,24,0.6);
  transition: color .15s;
  user-select: none;
}
.wg-another-take:hover { color: var(--wg-yellow); }
#wg-practice .wg-another-take { color: #b4960a !important; }
#wg-practice .wg-another-take:hover { color: #78350f !important; }

/* ── Step-cycle loading messages ────────────────────────────────────────── */
.wg-step-cycle {
  position: relative; display: inline-block;
  height: 1.4em; min-width: 200px; overflow: hidden; vertical-align: middle;
}
.wg-step-cycle span {
  position: absolute; left: 0; top: 0;
  opacity: 0;
  animation: wg-step-show 6s linear infinite;
  white-space: nowrap;
}
.wg-step-cycle span:nth-child(2) { animation-delay: 2s; }
.wg-step-cycle span:nth-child(3) { animation-delay: 4s; }
@keyframes wg-step-show {
  0%   { opacity: 0; transform: translateY(4px); }
  6%   { opacity: 0.8; transform: translateY(0); }
  28%  { opacity: 0.8; transform: translateY(0); }
  34%  { opacity: 0; transform: translateY(-4px); }
  100% { opacity: 0; }
}

/* ── Subtle stage spotlight on practice bg ──────────────────────────────── */
#wg-practice::before {
  content: ''; position: absolute; inset: 0; pointer-events: none; z-index: 0;
  background: radial-gradient(ellipse 70% 35% at 50% 0%, rgba(45,106,79,0.05) 0%, transparent 70%);
}
#wg-practice { position: relative; }

/* ── Comic-style modal ──────────────────────────────────────────────────── */
/* Same structural fix as #wg-practice: Gradio injects
   .prose * { color: var(--body-text-color) } which resolves to #f0f0f0 (dark
   theme) on every child element. The modal is outside #wg-practice so that
   scope doesn't apply. Override the same Gradio CSS vars here so child text
   inherits dark-on-ivory correctly — no per-element !important hacks needed. */
#wg-modal {
  --body-text-color:         #2a2118;
  --body-text-color-subdued: #6b6258;
  --block-text-color:        #2a2118;
  --block-label-text-color:  #6b6258;
  --input-text:              #2a2118;
  --color-text-body:         #2a2118;
  color: #2a2118;
}
#wg-modal-overlay {
  position: fixed; inset: 0; z-index: 9999;
  background: rgba(0,0,0,0.65); backdrop-filter: blur(5px);
  display: none; align-items: center; justify-content: center; padding: 1rem;
}
#wg-modal {
  background: #fffff8;
  background-image: radial-gradient(rgba(0,0,0,0.04) 1px, transparent 1px);
  background-size: 20px 20px;
  border-radius: 18px; max-width: 680px; width: 100%;
  padding: 1.75rem 1.75rem 1.5rem; position: relative;
  box-shadow: 0 24px 64px rgba(0,0,0,0.45), 0 0 0 2px rgba(0,0,0,0.08);
  font-family: 'EB Garamond', Georgia, serif;
  max-height: 90vh; overflow-y: auto;
}
.wg-modal-x {
  position: absolute; top: 1rem; right: 1rem;
  width: 32px; height: 32px; border-radius: 50%;
  background: #1a1a1a; color: #fff; border: none;
  font-size: 1rem; cursor: pointer; display: flex; align-items: center; justify-content: center;
  transition: background .15s;
}
.wg-modal-x:hover { background: #333; }
.wg-pop-show {
  font-family: 'Bebas Neue', sans-serif; font-size: 1rem;
  letter-spacing: 0.2em; color: #2d6a4f !important; margin-bottom: 1rem;
  border-bottom: 2px solid #e0d8cc; padding-bottom: 0.5rem;
}
.wg-pop-row { display: flex; gap: 1.25rem; margin-bottom: 1rem; align-items: flex-start; }
.wg-pop-char { display: flex; flex-direction: column; align-items: center; gap: 0.3rem; flex-shrink: 0; }
.wg-pop-avatar { width: 110px; height: 110px; border-radius: 12px; background: #f5f0e6; }
.wg-pop-name {
  font-family: 'Bebas Neue', sans-serif; font-size: 1rem;
  letter-spacing: 0.08em; color: #2a2118 !important; text-align: center;
}
.wg-pop-title {
  font-size: 0.72rem; color: #9e9288 !important; text-align: center; font-style: italic;
  max-width: 110px; line-height: 1.3;
}
.wg-pop-right { flex: 1; display: flex; flex-direction: column; gap: 0.65rem; }
.wg-pop-setup {
  font-style: italic; color: #6b6258 !important; font-size: 0.95rem; line-height: 1.5;
}
.wg-pop-bubble {
  background: #fff; border: 2.5px solid #1a1a1a; border-radius: 14px;
  padding: 0.85rem 1rem;
  font-family: 'Bebas Neue', Impact, sans-serif;
  font-size: 1.15rem; line-height: 1.3; letter-spacing: 0.02em; color: #1a1a1a !important;
  position: relative;
}
.wg-pop-bubble::before {
  content: ''; position: absolute; left: -14px; top: 50%; transform: translateY(-50%);
  border: 7px solid transparent; border-right-color: #1a1a1a;
}
.wg-pop-bubble::after {
  content: ''; position: absolute; left: -10px; top: 50%; transform: translateY(-50%);
  border: 6px solid transparent; border-right-color: #fff;
}
.wg-pop-why {
  background: #eff6ff; border: 1px solid #60a5fa;
  border-radius: 10px; padding: 0.75rem 1rem; margin-top: 0.25rem;
}
.wg-pop-why-title {
  font-family: 'Bebas Neue', sans-serif; font-size: 0.82rem;
  letter-spacing: 0.12em; color: #2563eb !important; margin-bottom: 0.35rem;
}
.wg-pop-why-body { font-size: 0.95rem; color: #1e3a5f !important; line-height: 1.55; }
/* Bio modal (character card click — no scene context) */
.wg-pop-bio {
  font-size: 1.05rem; color: #3d3429 !important; line-height: 1.6; font-style: italic;
  background: #f5f0e6; border-left: 3px solid #2d6a4f;
  padding: 0.75rem 1rem; border-radius: 0 10px 10px 0;
}

/* ── Arcade Character Selector ─────────────────────────────────────────────── */
.wg-arcade {
  display: flex; align-items: center; justify-content: center;
  gap: 0.5rem; padding: 0.05rem 0 0; max-width: 700px; margin: 0 auto;
}
.wg-arcade-stage {
  display: flex; align-items: center; justify-content: center;
  gap: 0.75rem; flex: 1;
}
.wg-arcade-arrow {
  background: rgba(10,20,14,0.72) !important;
  border: 1.5px solid #4ade80 !important;
  color: #4ade80 !important;
  font-size: 2rem !important;
  border-radius: 50% !important;
  width: 48px !important; height: 48px !important;
  display: flex !important; align-items: center !important; justify-content: center !important;
  cursor: pointer !important;
  transition: background .15s, box-shadow .15s, transform .1s !important;
  flex-shrink: 0 !important; line-height: 1 !important; padding: 0 !important;
  box-shadow: 0 0 12px rgba(74,222,128,0.35), inset 0 0 8px rgba(74,222,128,0.08) !important;
  backdrop-filter: blur(8px) !important;
  -webkit-backdrop-filter: blur(8px) !important;
  outline: none !important;
}
.wg-arcade-arrow:hover {
  background: rgba(74,222,128,0.15) !important;
  border-color: #86efac !important;
  box-shadow: 0 0 22px rgba(74,222,128,0.6), inset 0 0 12px rgba(74,222,128,0.15) !important;
  transform: scale(1.12) !important;
  color: #86efac !important;
}
.wg-arcade-center {
  background: var(--wg-surf2); border: 2px solid var(--wg-yellow);
  border-radius: 14px; padding: 0.35rem 0.8rem 0.35rem;
  display: flex; flex-direction: column; align-items: center; gap: 0.15rem;
  cursor: pointer; min-width: 150px; max-width: 175px;
  box-shadow: 0 0 28px rgba(245,197,24,0.22);
  transition: box-shadow .2s, border-color .2s;
  animation: wg-arcade-glow 2.4s ease-in-out infinite;
}
.wg-arcade-center:hover {
  box-shadow: 0 0 45px rgba(245,197,24,0.45);
  animation: none;
}
@keyframes wg-arcade-glow {
  0%,100% { box-shadow: 0 0 18px rgba(245,197,24,0.18); border-color: var(--wg-yellow); }
  50%      { box-shadow: 0 0 36px rgba(245,197,24,0.4);  border-color: #fde68a; }
}
.wg-arcade-avatar-wrap { position: relative; }
.wg-arcade-img {
  width: 76px; height: 76px; border-radius: 10px;
  background: rgba(255,255,255,0.05); object-fit: cover;
  transition: opacity .18s;
}
.wg-arcade-name {
  font-family: 'Bebas Neue', sans-serif; font-size: 1.15rem; letter-spacing: 0.12em;
  color: var(--wg-yellow) !important; text-align: center; margin-top: 0.1rem;
}
.wg-arcade-role {
  font-family: 'EB Garamond', serif; font-style: italic;
  font-size: 0.7rem; color: var(--wg-muted); text-align: center; letter-spacing: 0.1em;
}
.wg-arcade-bio {
  display: none;
}
.wg-arcade-select-hint {
  font-family: 'Bebas Neue', sans-serif; font-size: 0.55rem; letter-spacing: 0.22em;
  color: #4ade80; margin-top: 0.1rem; opacity: 0.7;
}
/* Peek (adjacent) cards */
.wg-arcade-peek {
  display: flex; flex-direction: column; align-items: center; gap: 0.25rem;
  opacity: 0.42; filter: blur(1.5px); transform: scale(0.78);
  transition: opacity .2s, filter .2s, transform .2s;
  pointer-events: none;
}
.wg-arcade-peek img { width: 52px; height: 52px; border-radius: 8px; }
.wg-arcade-peek-name {
  font-family: 'Bebas Neue', sans-serif; font-size: 0.65rem;
  letter-spacing: 0.1em; color: var(--wg-muted); text-align: center;
}
/* Dot indicators */
.wg-arcade-dots {
  display: flex; justify-content: center; gap: 0.5rem; margin: 0.6rem 0 0.25rem;
}
.wg-arcade-dot {
  width: 6px; height: 6px; border-radius: 50%;
  background: rgba(255,255,255,0.2); transition: background .2s, transform .2s;
}
.wg-arcade-dot--active {
  background: var(--wg-yellow); transform: scale(1.4);
}
/* Slide animation */
@keyframes wg-arcade-slide-in-right {
  0%   { opacity: 0; transform: translateX(40px) scale(0.92); }
  100% { opacity: 1; transform: translateX(0) scale(1); }
}
@keyframes wg-arcade-slide-in-left {
  0%   { opacity: 0; transform: translateX(-40px) scale(0.92); }
  100% { opacity: 1; transform: translateX(0) scale(1); }
}
.wg-arcade-center.wg-arcade--slide-right { animation: wg-arcade-slide-in-right 0.22s ease-out both; }
.wg-arcade-center.wg-arcade--slide-left  { animation: wg-arcade-slide-in-left 0.22s ease-out both; }

/* ── Practice header coach identity ─────────────────────────────────────── */
.wg-coach-avatar-wrap { display: flex; align-items: center; flex-shrink: 0; }
.wg-coach-avatar-img { width: 42px; height: 42px; border-radius: 8px; object-fit: cover; }
.wg-coach-id { display: flex; flex-direction: column; justify-content: center; }

/* ── Coach reply: avatar + NAME SAYS ────────────────────────────────────── */
.wg-coach-reply { position: relative; }
.wg-coach-reply-header--char {
  display: flex; align-items: center; gap: 0.45rem;
}
.wg-coach-reply-avatar {
  width: 28px; height: 28px; border-radius: 6px; flex-shrink: 0;
  background: rgba(255,255,255,0.08);
}
#wg-practice .wg-coach-reply-avatar { background: rgba(0,0,0,0.05); }

/* ── Reply action buttons ────────────────────────────────────────────────── */
.wg-reply-actions {
  position: absolute; top: 0.5rem; right: 0.6rem;
  display: inline-flex; align-items: center; gap: 0.5rem; z-index: 3;
}
.wg-action-btn {
  -webkit-appearance: none !important; appearance: none !important;
  display: inline-flex; align-items: center; justify-content: center;
  width: 2.15rem; height: 2.15rem; min-width: 2.15rem;
  background: rgba(245,240,232,0.88) !important;
  border: 1px solid rgba(45,106,79,0.12) !important;
  border-radius: 0.72rem !important;
  box-shadow: none !important;
  cursor: pointer;
  color: rgba(94, 84, 72, 0.88); opacity: 0.92;
  transition: opacity .15s, color .15s, transform .15s, border-color .15s, background-color .15s;
  padding: 0 !important; line-height: 1; font: inherit;
  outline: none !important;
}
.wg-action-btn:hover {
  opacity: 1; color: #9c5c19; transform: translateY(-1px);
  border-color: rgba(180,83,9,0.22) !important;
  background: rgba(255, 250, 241, 0.98) !important;
}
#wg-practice .wg-action-btn { color: rgba(94, 84, 72, 0.88); background: rgba(245,240,232,0.9) !important; }
#wg-practice .wg-action-btn:hover { color: #b45309; background: rgba(255,250,241,0.98) !important; }
.wg-action-btn:focus,
.wg-action-btn:focus-visible {
  outline: none !important;
  box-shadow: 0 0 0 2px rgba(45,106,79,0.14) !important;
}
.wg-speak-btn.wg-speaking { opacity: 1; color: var(--wg-green); }
#wg-practice .wg-speak-btn.wg-speaking { color: #2d6a4f; }
.wg-action-icon { width: 0.86rem; height: 0.86rem; display: block; flex-shrink: 0; pointer-events: none; }
.wg-coach-reply.wg-speaking .wg-coach-reply-avatar,
.wg-coach-reply.wg-speaking #wg-coach-avatar,
.wg-coach-reply.wg-speaking .wg-coach-reply-header svg {
  animation: wg-coach-speaking 0.9s ease-in-out infinite;
  transform-origin: center;
}
@keyframes wg-coach-speaking {
  0%, 100% { transform: translateY(0) scale(1); }
  35% { transform: translateY(-1px) scale(1.04); }
  65% { transform: translateY(1px) scale(0.99); }
}

/* ── Hidden char state textbox ───────────────────────────────────────────── */
#wg-char-hidden { position: absolute; width: 0; height: 0; overflow: hidden; opacity: 0; pointer-events: none; }

/* ── Floating roast messages — JS-spawned, multi-directional ─────────────── */
.wg-roast-chip {
  position: fixed; z-index: 50; pointer-events: none;
  font-family: 'EB Garamond', Georgia, serif; font-style: italic;
  font-size: 0.75rem; color: rgba(245,197,24,0.9);
  background: rgba(20,20,20,0.78); border: 1px solid rgba(245,197,24,0.28);
  border-radius: 20px; padding: 0.28rem 0.8rem;
  opacity: 0; transition: none;
  animation: wg-roast-float-in 4s ease-out forwards;
}
@keyframes wg-roast-float-in {
  0%   { opacity: 0; }
  15%  { opacity: 1; }
  75%  { opacity: 1; }
  100% { opacity: 0; }
}

/* ── Sidebar bubble head ─────────────────────────────────────────────────── */
@keyframes wg-bubble-bob {
  0%, 100% { transform: translateY(0) rotate(0deg); }
  50%       { transform: translateY(-6px) rotate(0.4deg); }
}
.wg-bubble-head {
  display: flex; flex-direction: column; align-items: center;
  padding: 1.4rem 0.5rem 0.6rem; user-select: none;
}
.wg-bubble-head-inner {
  animation: wg-bubble-bob 2.8s ease-in-out infinite;
  transition: transform 0.22s ease;
  cursor: pointer;
}
.wg-bubble-head-inner:hover {
  animation-play-state: paused;
  transform: scale(1.1) rotate(5deg) !important;
}
.wg-bubble-avatar-large {
  width: 90px; height: 90px; border-radius: 50%;
  border: 2.5px solid var(--wg-green);
  box-shadow: 0 0 18px rgba(74,222,128,0.22), 0 3px 10px rgba(0,0,0,0.35);
  object-fit: cover; display: block;
}
.wg-bubble-char-name {
  font-family: 'Bebas Neue', sans-serif; letter-spacing: 0.18em;
  font-size: 0.68rem; color: var(--wg-muted);
  margin-top: 0.5rem; text-align: center;
}
#wg-practice .wg-bubble-avatar-large {
  border-color: #2d6a4f;
  box-shadow: 0 0 16px rgba(45,106,79,0.18), 0 2px 8px rgba(0,0,0,0.1);
}
#wg-practice .wg-bubble-char-name { color: #9e9288; }

/* ── Sci-fi flicker input overlay ────────────────────────────────────────── */
.wg-flicker-wrap { position: relative; }
.wg-flicker-overlay {
  position: absolute; top: 0; left: 0; right: 0; bottom: 0;
  pointer-events: none; padding: 0.55rem 0.75rem;
  font-family: 'EB Garamond', serif; font-size: 1rem; color: #2a2118;
  opacity: 0.5; line-height: 1.5; display: flex; align-items: center;
  z-index: 2;
}
.wg-flicker-cursor {
  display: inline-block; width: 2px; height: 1.1em;
  background: #2a2118; margin-left: 1px; vertical-align: middle;
  animation: wg-cursor-blink 0.9s step-end infinite;
}
@keyframes wg-cursor-blink { 0%,100% { opacity: 1; } 50% { opacity: 0; } }
/* Glow border on idle textarea */
#wg-chat-shell textarea:not(:focus) {
  box-shadow: 0 0 0 1.5px rgba(45,106,79,0.25) !important;
  transition: box-shadow .4s;
}
#wg-chat-shell textarea:focus {
  box-shadow: 0 0 0 2px rgba(45,106,79,0.55) !important;
}
#wg-practice #wg-chat-shell textarea:not(:focus) {
  box-shadow: 0 0 0 1.5px rgba(45,106,79,0.18) !important;
}
#wg-practice #wg-chat-shell textarea:focus {
  box-shadow: 0 0 0 2px rgba(45,106,79,0.4) !important;
}
"""

# ── Global JS — injected into page <head> via gr.HTML(head=...) ──────────────
# Using head= instead of value= because <script> tags in gr.HTML value are NOT
# executed by Gradio 6.x (they're set via innerHTML). head= is the correct API.
# All three functions use a SINGLE modal (#wg-modal-overlay) at top DOM level
# so it's never hidden by a parent column's display:none.
_GLOBAL_JS = """
/* Event delegation for debug toggle (dynamic elements) */
document.addEventListener('click', function(e) {
  var toggle = e.target.closest('.wg-debug-toggle');
  if (!toggle) return;
  var body = toggle.nextElementSibling;
  if (!body) return;
  var ch = toggle.querySelector('.wg-debug-chevron');
  var collapsed = body.classList.toggle('wg-collapsed');
  if (ch) ch.textContent = collapsed ? '▶' : '▼';
});

/* Capsule expand/collapse */
document.addEventListener('click', function(e) {
  var head = e.target.closest('.wg-capsule-head');
  if (!head) return;
  var cap = head.closest('.wg-capsule');
  var body = head.nextElementSibling;
  if (body) body.classList.toggle('wg-collapsed');
  if (cap)  cap.classList.toggle('wg-capsule--open');
});

/* Scroll-cue click → smooth scroll to CTA */
document.addEventListener('click', function(e) {
  if (!e.target.closest('.wg-scroll-cue')) return;
  var btn = document.querySelector('#wg-start-btn');
  if (btn) btn.scrollIntoView({ behavior: 'smooth', block: 'center' });
});

/* Another take — cycle through pre-computed candidates */
window.wgAnotherTake = function(btn) {
  var card = btn.closest('.wg-coach-reply');
  if (!card) return;
  try {
    var alts = JSON.parse(card.dataset.alts || '[]');
    if (!alts.length) return;
    var idx = parseInt(card.dataset.altIdx || '0') % alts.length;
    var alt = alts[idx];
    var body = card.querySelector('.wg-coach-reply-body');
    var lbl = card.querySelector('.wg-persona-label');
    if (body) body.textContent = alt.text;
    if (lbl) lbl.textContent = alt.persona;
    card.dataset.altIdx = (idx + 1) % alts.length;
    card.classList.add('wg-coach-reply--alt');
    setTimeout(function(){ card.classList.remove('wg-coach-reply--alt'); }, 400);
  } catch(e) {}
};

/* Sound effects — Web Audio API, no external files */
/* Office-vibe piano: 4-note ascending motif (D4→G4→A4→D5), triangle wave */
window.wgPlayBell = function() {
  try {
    var ctx = new (window.AudioContext || window.webkitAudioContext)();
    var notes = [294, 392, 440, 587];
    var times = [0, 0.16, 0.30, 0.46];
    var durs  = [0.14, 0.14, 0.14, 0.38];
    notes.forEach(function(freq, i) {
      var o = ctx.createOscillator(), g = ctx.createGain();
      o.connect(g); g.connect(ctx.destination);
      o.type = 'triangle'; o.frequency.value = freq;
      var t = ctx.currentTime + times[i];
      g.gain.setValueAtTime(0, t);
      g.gain.linearRampToValueAtTime(0.085, t + 0.018);
      g.gain.exponentialRampToValueAtTime(0.001, t + durs[i]);
      o.start(t); o.stop(t + durs[i]);
    });
  } catch(e) {}
};
/* Warm C-major chord (C4+E4+G4) on coach reply — affirming, piano-like */
window.wgPlayClack = function() {
  try {
    var ctx = new (window.AudioContext || window.webkitAudioContext)();
    [262, 330, 392].forEach(function(freq) {
      var o = ctx.createOscillator(), g = ctx.createGain();
      o.connect(g); g.connect(ctx.destination);
      o.type = 'triangle'; o.frequency.value = freq;
      g.gain.setValueAtTime(0, ctx.currentTime);
      g.gain.linearRampToValueAtTime(0.052, ctx.currentTime + 0.02);
      g.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.55);
      o.start(); o.stop(ctx.currentTime + 0.55);
    });
  } catch(e) {}
};
/* MutationObserver: play clack when a new coach reply is added */
(function(){
  var last = 0;
  function observe() {
    var t = document.querySelector('.wg-transcript');
    if (!t) { setTimeout(observe, 600); return; }
    new MutationObserver(function(){
      var n = document.querySelectorAll('.wg-coach-reply').length;
      if (n > last) { last = n; window.wgPlayClack && wgPlayClack(); }
    }).observe(t, {childList:true, subtree:true});
  }
  observe();
})();

/* Drill chip: prefill textbox then auto-submit */
window.wgDrill = function(text) {
  var ta = document.querySelector('#wg-chat-shell textarea');
  if (!ta) return;
  var setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value');
  if (setter && setter.set) setter.set.call(ta, text);
  ta.dispatchEvent(new Event('input', { bubbles: true }));
  ta.focus();
  ta.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  /* Auto-submit via the main button (elem_id lands on the <button> directly in Gradio) */
  setTimeout(function() {
    var btn = document.querySelector('#wg-submit-btn');
    if (btn && !btn.disabled) btn.click();
  }, 60);
};


window.wgClose = function() {
  var o = document.getElementById('wg-modal-overlay');
  if (o) o.style.display = 'none';
};
window.wgOpenChip = function(title, definition) {
  var o = document.getElementById('wg-modal-overlay');
  var b = document.getElementById('wg-modal-body');
  if (!o || !b) return;
  b.innerHTML = '<div class="wg-pop-show">' + title + '</div>'
    + '<div class="wg-pop-bio" style="font-style:normal;font-size:1.05rem">' + definition + '</div>';
  o.style.display = 'flex';
};
window.wgOpenBio = function(name, title, desc, avatarUrl) {
  var o = document.getElementById('wg-modal-overlay');
  var b = document.getElementById('wg-modal-body');
  if (!o || !b) return;
  b.innerHTML = '<div class="wg-pop-show">THE COACHING PANEL</div>'
    + '<div class="wg-pop-row">'
    + '<div class="wg-pop-char">'
    + '<img class="wg-pop-avatar" src="' + avatarUrl + '" alt="' + name + '"/>'
    + '<div class="wg-pop-name">' + name + '</div>'
    + '<div class="wg-pop-title">' + title + '</div>'
    + '</div>'
    + '<div class="wg-pop-right">'
    + '<div class="wg-pop-bio">' + desc + '</div>'
    + '</div></div>';
  o.style.display = 'flex';
};
window.wgOpenScene = function(character, show, setup, response, why, avatarUrl, title) {
  var o = document.getElementById('wg-modal-overlay');
  var b = document.getElementById('wg-modal-body');
  if (!o || !b) return;
  b.innerHTML = '<div class="wg-pop-show">' + show + '</div>'
    + '<div class="wg-pop-row">'
    + '<div class="wg-pop-char">'
    + '<img class="wg-pop-avatar" src="' + avatarUrl + '" alt="' + character + '"/>'
    + '<div class="wg-pop-name">' + character + '</div>'
    + '<div class="wg-pop-title">' + title + '</div>'
    + '</div>'
    + '<div class="wg-pop-right">'
    + '<div class="wg-pop-setup">&ldquo;' + setup + '&rdquo;</div>'
    + '<div class="wg-pop-bubble">' + response + '</div>'
    + '</div></div>'
    + '<div class="wg-pop-why">'
    + '<div class="wg-pop-why-title">WHY IT WORKS</div>'
    + '<div class="wg-pop-why-body">' + why + '</div>'
    + '</div>';
  o.style.display = 'flex';
};

/* ── Arcade character selector ─────────────────────────────────────────── */
(function() {
  var _chars = null;
  var _idx = 1; // Start on Michael (index 1), AI is index 0

  function _getChars() {
    if (_chars) return _chars;
    var el = document.getElementById('wg-chars-data');
    if (!el) return null;
    try { var ta = document.createElement('textarea'); ta.innerHTML = el.textContent || el.innerHTML; _chars = JSON.parse(ta.value); } catch(e) { _chars = []; }
    return _chars;
  }

  function _renderDots(n, active) {
    var el = document.getElementById('wg-arcade-dots');
    if (!el) return;
    var html = '';
    for (var i = 0; i < n; i++) {
      html += '<div class="wg-arcade-dot' + (i === active ? ' wg-arcade-dot--active' : '') + '"></div>';
    }
    el.innerHTML = html;
  }

  function _renderPeek(side, idx, chars) {
    var el = document.getElementById('wg-arcade-peek-' + side);
    if (!el) return;
    if (!chars || chars.length < 2) { el.innerHTML = ''; return; }
    var c = chars[idx];
    if (!c) { el.innerHTML = ''; return; }
    var fallback = c.fallbackUrl || '';
    el.innerHTML = '<img src="' + c.avatarUrl + '" alt="' + c.name + '"'
      + (fallback ? ` onerror="this.onerror=null;this.src=${fallback}"` : '') + '/>'
      + '<div class="wg-arcade-peek-name">' + c.name + '</div>';
  }

  window.wgArcadeRender = function(direction) {
    var chars = _getChars();
    if (!chars || !chars.length) return;
    var c = chars[_idx];
    var center = document.getElementById('wg-arcade-center');
    var img = document.getElementById('wg-arcade-img');
    var name = document.getElementById('wg-arcade-name');
    var role = document.getElementById('wg-arcade-role');
    var bio = document.getElementById('wg-arcade-bio');
    if (!center || !img || !name) return;

    if (direction && center) {
      var cls = direction === 1 ? 'wg-arcade--slide-right' : 'wg-arcade--slide-left';
      center.classList.remove('wg-arcade--slide-right', 'wg-arcade--slide-left');
      void center.offsetWidth;
      center.classList.add(cls);
    }

    img.src = c.avatarUrl || '';
    img.alt = c.name;
    if (c.fallbackUrl) {
      img.onerror = function() { this.onerror = null; this.src = c.fallbackUrl; };
    }
    name.textContent = c.name === 'AI' ? 'LET AI CHOOSE' : c.name.toUpperCase();
    if (role) role.textContent = c.role;
    if (bio) bio.textContent = c.bio;

    _renderDots(chars.length, _idx);
    var leftIdx = (_idx - 1 + chars.length) % chars.length;
    var rightIdx = (_idx + 1) % chars.length;
    _renderPeek('left', leftIdx, chars);
    _renderPeek('right', rightIdx, chars);
  };

  window.wgArcadeMove = function(dir) {
    var chars = _getChars();
    if (!chars || !chars.length) return;
    _idx = (_idx + dir + chars.length) % chars.length;
    window.wgArcadeRender(dir);
    window.wgPlaySelect && window.wgPlaySelect();
  };

  window.wgArcadeSelect = function() {
    var chars = _getChars();
    if (!chars || !chars.length) return;
    var c = chars[_idx];
    window._wgSelectedChar = c;
    // Write char name into Gradio hidden textbox via React/Svelte setter
    var hidden = document.querySelector('#wg-char-hidden textarea, #wg-char-hidden input[type="text"]');
    if (hidden) {
      var setter = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(hidden), 'value');
      if (setter && setter.set) setter.set.call(hidden, c.name);
      hidden.dispatchEvent(new Event('input', {bubbles: true}));
    }
    // Play confirm sound then trigger start (start_btn.click reads char_hidden + updates session)
    window.wgPlayConfirm && window.wgPlayConfirm();
    setTimeout(function() {
      var startBtn = document.querySelector('#wg-start-btn button');
      if (startBtn) startBtn.click();
    }, 180);
  };

  // Keyboard navigation
  document.addEventListener('keydown', function(e) {
    var arcade = document.getElementById('wg-arcade');
    if (!arcade || arcade.closest('#wg-practice')) return;
    if (e.key === 'ArrowLeft')  { e.preventDefault(); window.wgArcadeMove(-1); }
    if (e.key === 'ArrowRight') { e.preventDefault(); window.wgArcadeMove(1);  }
    if (e.key === 'Enter' && arcade.offsetParent !== null) { e.preventDefault(); window.wgArcadeSelect(); }
  });

  // Init on DOM ready
  function _init() {
    var chars = _getChars();
    if (!chars) { setTimeout(_init, 300); return; }
    window.wgArcadeRender(0);
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', _init);
  } else {
    setTimeout(_init, 100);
  }
})();

/* ── Arcade sound effects ─────────────────────────────────────────────────── */
window.wgPlaySelect = function() {
  try {
    var ctx = new (window.AudioContext || window.webkitAudioContext)();
    var now = ctx.currentTime;
    // Whoosh: sawtooth sweep from 120→320 Hz over 0.18s
    var sweep = ctx.createOscillator(), sg = ctx.createGain();
    sweep.connect(sg); sg.connect(ctx.destination);
    sweep.type = 'sawtooth';
    sweep.frequency.setValueAtTime(120, now);
    sweep.frequency.linearRampToValueAtTime(320, now + 0.18);
    sg.gain.setValueAtTime(0, now);
    sg.gain.linearRampToValueAtTime(0.04, now + 0.02);
    sg.gain.exponentialRampToValueAtTime(0.001, now + 0.18);
    sweep.start(now); sweep.stop(now + 0.18);
    // Metallic ping: two detuned sine waves at 1200 + 1207 Hz (beating)
    [1200, 1207].forEach(function(f, i) {
      var o = ctx.createOscillator(), g = ctx.createGain();
      o.connect(g); g.connect(ctx.destination);
      o.type = 'sine'; o.frequency.value = f;
      var t = now + 0.12;
      g.gain.setValueAtTime(0, t);
      g.gain.linearRampToValueAtTime(0.06, t + 0.005);
      g.gain.exponentialRampToValueAtTime(0.001, t + 0.28);
      o.start(t); o.stop(t + 0.28);
    });
  } catch(e) {}
};
window.wgPlayConfirm = function() {
  try {
    var ctx = new (window.AudioContext || window.webkitAudioContext)();
    [[392, 0, 0.12], [523, 0.14, 0.12], [784, 0.28, 0.22]].forEach(function(p) {
      var o = ctx.createOscillator(), g = ctx.createGain();
      o.connect(g); g.connect(ctx.destination);
      o.type = 'triangle'; o.frequency.value = p[0];
      var t = ctx.currentTime + p[1];
      g.gain.setValueAtTime(0, t);
      g.gain.linearRampToValueAtTime(0.07, t + 0.02);
      g.gain.exponentialRampToValueAtTime(0.001, t + p[2]);
      o.start(t); o.stop(t + p[2]);
    });
  } catch(e) {}
};

/* ── Update practice header with selected coach ─────────────────────────── */
window.wgUpdateCoachHeader = function() {
  var c = window._wgSelectedChar;
  if (!c) return;

  // Always update sidebar bubble head regardless of character type
  var bubbleImg = document.getElementById('wg-bubble-avatar-large');
  var bubbleName = document.getElementById('wg-bubble-char-name');
  if (bubbleImg) {
    bubbleImg.src = c.avatarUrl || '';
    bubbleImg.alt = c.name;
    if (c.fallbackUrl) bubbleImg.onerror = function() { this.onerror = null; this.src = c.fallbackUrl; };
    bubbleImg.style.display = 'block';
  }
  if (bubbleName) bubbleName.textContent = c.name === 'AI' ? 'AI COACH' : c.name.toUpperCase() + ' COACH';

  if (c.name === 'AI') return; // keep default mug + WITGYM text for practice bar header

  var mugWrap = document.querySelector('#wg-coach-avatar-wrap svg.wg-mascot-like, #wg-coach-avatar-wrap svg');
  if (mugWrap) mugWrap.style.display = 'none';
  var img = document.getElementById('wg-coach-avatar');
  if (img) {
    img.src = c.avatarUrl || '';
    img.alt = c.name;
    if (c.fallbackUrl) img.onerror = function() { this.onerror = null; this.src = c.fallbackUrl; };
    img.style.display = 'block';
  }
  var nameEl = document.getElementById('wg-coach-name');
  if (nameEl) nameEl.innerHTML = c.name.toUpperCase() + ' <span style="color:var(--wg-green)">COACH</span>';
  var roleEl = document.getElementById('wg-coach-role');
  if (roleEl) roleEl.textContent = c.role + ' · comedy coaching engine';
};

/* ── Copy button ──────────────────────────────────────────────────────────── */
window.wgCopy = function(btn) {
  var body = btn.closest('.wg-coach-reply') && btn.closest('.wg-coach-reply').querySelector('.wg-coach-reply-body');
  if (!body) return;
  var text = body.textContent.trim();
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(function() {
      window.wgSetActionIcon(btn, 'copied');
      setTimeout(function() { window.wgSetActionIcon(btn, 'copy'); }, 1400);
    });
  } else {
    var ta = document.createElement('textarea');
    ta.value = text; document.body.appendChild(ta);
    ta.select(); document.execCommand('copy'); document.body.removeChild(ta);
    window.wgSetActionIcon(btn, 'copied');
    setTimeout(function() { window.wgSetActionIcon(btn, 'copy'); }, 1400);
  }
};

window.wgStopSpeaking = function() {
  if (window._wgAudioPlayer) {
    try {
      window._wgAudioPlayer.pause();
      window._wgAudioPlayer.currentTime = 0;
    } catch (e) {}
    window._wgAudioPlayer = null;
  }
  if (window.speechSynthesis) {
    window.speechSynthesis.cancel();
  }
  if (window._wgSpeakingBtn) {
    window._wgSpeakingBtn.classList.remove('wg-speaking');
    window.wgSetActionIcon(window._wgSpeakingBtn, 'play');
  }
  if (window._wgSpeakingReply) {
    window._wgSpeakingReply.classList.remove('wg-speaking');
  }
  window._wgSpeakingBtn = null;
  window._wgSpeakingReply = null;
};

window.wgSetActionIcon = function(btn, kind) {
  if (!btn) return;
  if (kind === 'copy') {
    btn.innerHTML =
      '<svg viewBox="0 0 20 20" class="wg-action-icon" aria-hidden="true">' +
      '<rect x="7" y="4" width="8" height="10" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.8"></rect>' +
      '<path d="M5 7H4.5A1.5 1.5 0 0 0 3 8.5v7A1.5 1.5 0 0 0 4.5 17h5A1.5 1.5 0 0 0 11 15.5V15" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"></path>' +
      '</svg>';
    return;
  }
  if (kind === 'copied') {
    btn.innerHTML =
      '<svg viewBox="0 0 20 20" class="wg-action-icon" aria-hidden="true">' +
      '<path d="M4.5 10.5 8 14l7.5-8" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"></path>' +
      '</svg>';
    return;
  }
  if (kind === 'stop') {
    btn.innerHTML =
      '<svg viewBox="0 0 20 20" class="wg-action-icon" aria-hidden="true">' +
      '<rect x="5.2" y="5.2" width="9.6" height="9.6" rx="1.8" fill="currentColor"></rect>' +
      '</svg>';
    return;
  }
  btn.innerHTML =
    '<svg viewBox="0 0 20 20" class="wg-action-icon" aria-hidden="true">' +
    '<path d="M6 4.8v10.4c0 .9 1 1.45 1.77.96l8-5.2a1.15 1.15 0 0 0 0-1.92l-8-5.2A1.15 1.15 0 0 0 6 4.8Z" fill="currentColor"></path>' +
    '</svg>';
};

window.wgVoiceProfile = function(charName) {
  var key = (charName || 'AI').toLowerCase();
  var profiles = {
    ai:      { rate: 1.02, pitch: 1.0, keywords: ['google', 'samantha', 'aria', 'female', 'zira'], fallbackKeywords: ['google', 'samantha', 'aria', 'zira'], gender: 'neutral' },
    jim:     { rate: 1.03, pitch: 0.96, keywords: ['daniel', 'alex', 'tom', 'male'], fallbackKeywords: ['daniel', 'alex', 'tom', 'fred', 'jorge', 'ralph'], gender: 'male' },
    pam:     { rate: 0.98, pitch: 1.08, keywords: ['samantha', 'victoria', 'karen', 'female'], fallbackKeywords: ['samantha', 'victoria', 'karen', 'zira', 'aria'], gender: 'female' },
    michael: { rate: 1.08, pitch: 1.05, keywords: ['fred', 'junior', 'male'], fallbackKeywords: ['fred', 'alex', 'daniel', 'jorge'], gender: 'male' },
    dwight:  { rate: 0.92, pitch: 0.82, keywords: ['alex', 'david', 'male'], fallbackKeywords: ['alex', 'david', 'fred', 'ralph'], gender: 'male' },
    kevin:   { rate: 0.86, pitch: 0.84, keywords: ['jorge', 'male'], fallbackKeywords: ['jorge', 'ralph', 'fred', 'alex'], gender: 'male' },
    andy:    { rate: 1.12, pitch: 1.12, keywords: ['fred', 'male'], fallbackKeywords: ['fred', 'daniel', 'alex', 'tom'], gender: 'male' },
    stanley: { rate: 0.83, pitch: 0.75, keywords: ['ralph', 'male'], fallbackKeywords: ['ralph', 'jorge', 'alex', 'fred'], gender: 'male' },
    angela:  { rate: 0.94, pitch: 1.14, keywords: ['samantha', 'female'], fallbackKeywords: ['samantha', 'victoria', 'karen', 'zira'], gender: 'female' },
    ryan:    { rate: 1.01, pitch: 0.9, keywords: ['alex', 'male'], fallbackKeywords: ['alex', 'daniel', 'tom', 'fred'], gender: 'male' },
    kelly:   { rate: 1.14, pitch: 1.2, keywords: ['victoria', 'female'], fallbackKeywords: ['victoria', 'karen', 'samantha', 'zira'], gender: 'female' }
  };
  return profiles[key] || profiles.ai;
};

window.wgPickVoice = function(profile, reply) {
  if (!window.speechSynthesis || !window.speechSynthesis.getVoices) return null;
  var voices = window.speechSynthesis.getVoices() || [];
  if (!voices.length) return null;
  var preferred = (profile.keywords || []).map(function(k) { return k.toLowerCase(); });
  for (var i = 0; i < preferred.length; i++) {
    var match = voices.find(function(voice) {
      var hay = (voice.name + ' ' + (voice.lang || '')).toLowerCase();
      return hay.indexOf(preferred[i]) !== -1;
    });
    if (match) return match;
  }
  var fallback = (profile.fallbackKeywords || []).map(function(k) { return k.toLowerCase(); });
  for (var j = 0; j < fallback.length; j++) {
    var fallbackMatch = voices.find(function(voice) {
      var hay = (voice.name + ' ' + (voice.lang || '')).toLowerCase();
      return hay.indexOf(fallback[j]) !== -1;
    });
    if (fallbackMatch) return fallbackMatch;
  }
  var gender = (reply && reply.dataset && reply.dataset.voiceGender) || profile.gender || 'neutral';
  if (gender !== 'neutral') return null;
  return voices.find(function(voice) { return /^en(-|_)/i.test(voice.lang || ''); }) || voices[0];
};

window.wgSpeak = function(btn) {
  var reply = btn.closest('.wg-coach-reply');
  var body = reply && reply.querySelector('.wg-coach-reply-body');
  if (!reply || !body) return;
  var text = body.textContent.trim();
  if (!text) return;
  if (window._wgSpeakingBtn === btn) {
    window.wgStopSpeaking();
    return;
  }
  window.wgStopSpeaking();

  var audioSrc = reply.dataset.audio || '';
  if (audioSrc) {
    try {
      var audio = new Audio(audioSrc);
      audio.onplay = function() {
        window._wgSpeakingBtn = btn;
        window._wgSpeakingReply = reply;
        window._wgAudioPlayer = audio;
        btn.classList.add('wg-speaking');
        window.wgSetActionIcon(btn, 'stop');
        reply.classList.add('wg-speaking');
      };
      audio.onended = window.wgStopSpeaking;
      audio.onerror = function() {
        window._wgAudioPlayer = null;
        window.wgStopSpeaking();
      };
      var playPromise = audio.play();
      if (playPromise && playPromise.catch) {
        playPromise.catch(function() {
          window._wgAudioPlayer = null;
          window.wgStopSpeaking();
        });
      }
      return;
    } catch (e) {}
  }

  if (reply.dataset.allowBrowserVoice !== 'true') return;

  if (!window.speechSynthesis || typeof SpeechSynthesisUtterance === 'undefined') return;
  var profile = window.wgVoiceProfile(reply.dataset.char || 'AI');
  var utterance = new SpeechSynthesisUtterance(text);
  utterance.rate = profile.rate;
  utterance.pitch = profile.pitch;
  utterance.voice = window.wgPickVoice(profile, reply);
  if (!utterance.voice && profile.gender !== 'neutral') {
    return;
  }
  utterance.onstart = function() {
    window._wgSpeakingBtn = btn;
    window._wgSpeakingReply = reply;
    btn.classList.add('wg-speaking');
    window.wgSetActionIcon(btn, 'stop');
    reply.classList.add('wg-speaking');
  };
  utterance.onend = window.wgStopSpeaking;
  utterance.onerror = window.wgStopSpeaking;
  window.speechSynthesis.speak(utterance);
};

try {
  if (window.speechSynthesis && window.speechSynthesis.getVoices) {
    window.speechSynthesis.getVoices();
    if ('onvoiceschanged' in window.speechSynthesis) {
      window.speechSynthesis.onvoiceschanged = function() {
        window.speechSynthesis.getVoices();
      };
    }
  }
} catch (e) {}

/* ── Sci-fi flickering input placeholder ─────────────────────────────────── */
/* ── Roast chip spawner — multi-directional ───────────────────────────────── */
window.wgSpawnRoasts = function() {
  var QUIPS = [
    "“That’s what she said.”",
    "“Identity theft is not a joke, Jim.”",
    "“Bears. Beats. Battlestar Galactica.”",
    "“How the turntables…”",
    "“Would I rather be feared or loved? Easy. Both.”",
    "“Fool me once, strike one.”",
    "“I am Beyonc\xe9, always.”",
    "“The worst thing about prison? The dementors.”",
  ];
  // Spawn positions: edge zones (bottom-right, bottom-left, top-right, left-mid, right-mid)
  var ZONES = [
    function() { return { bottom: (8 + Math.random()*15) + '%', right: (2 + Math.random()*8) + '%' }; },
    function() { return { bottom: (8 + Math.random()*15) + '%', left: (2 + Math.random()*8) + '%' }; },
    function() { return { top: (8 + Math.random()*12) + '%', right: (2 + Math.random()*10) + '%' }; },
    function() { return { top: (30 + Math.random()*20) + '%', left: (1 + Math.random()*5) + '%' }; },
    function() { return { top: (30 + Math.random()*20) + '%', right: (1 + Math.random()*5) + '%' }; },
  ];
  var qi = Math.floor(Math.random() * QUIPS.length);
  var pos = ZONES[Math.floor(Math.random() * ZONES.length)]();
  var el = document.createElement('div');
  el.className = 'wg-roast-chip';
  el.textContent = QUIPS[qi];
  Object.assign(el.style, pos);
  document.body.appendChild(el);
  setTimeout(function() { el.parentNode && el.parentNode.removeChild(el); }, 4200);
};

window.wgInitRoasts = function() {
  if (window._roastTimer) clearInterval(window._roastTimer);
  // First chip immediately, then every 5–9s randomly
  window.wgSpawnRoasts();
  function scheduleNext() {
    window._roastTimer = setTimeout(function() {
      if (document.getElementById('wg-practice') &&
          window.getComputedStyle(document.getElementById('wg-practice')).display !== 'none') {
        window.wgSpawnRoasts();
      }
      scheduleNext();
    }, 5000 + Math.random() * 4000);
  }
  scheduleNext();
};

window.wgInitFlicker = function() {
  var shell = document.getElementById('wg-chat-shell');
  if (!shell) return;
  var ta = shell.querySelector('textarea');
  if (!ta) return;

  var PHRASES = [
    "I just got promoted and have no idea what I'm doing…",
    "My coworker keeps stealing my lunch from the fridge…",
    "I'm pretending to understand cryptocurrency at dinner parties…",
    "I've been ignoring a voicemail so long it feels like a legal risk…",
    "I sent a complaint about my manager to my manager…",
    "Help me respond when someone asks about my job and I don't know what to say…",
  ];

  var overlay = document.createElement('div');
  overlay.className = 'wg-flicker-overlay';
  var textNode = document.createTextNode('');
  var cursor = document.createElement('span');
  cursor.className = 'wg-flicker-cursor';
  overlay.appendChild(textNode);
  overlay.appendChild(cursor);

  // Insert overlay relative to textarea
  var wrap = ta.parentNode;
  if (wrap) {
    wrap.style.position = 'relative';
    wrap.insertBefore(overlay, ta.nextSibling);
  }

  var phraseIdx = 0, charIdx = 0, typing = true, paused = false, timerId = null;

  function step() {
    if (paused || ta.value.trim()) { overlay.style.display = 'none'; return; }
    overlay.style.display = '';
    var phrase = PHRASES[phraseIdx];
    if (typing) {
      if (charIdx <= phrase.length) {
        textNode.nodeValue = phrase.slice(0, charIdx);
        charIdx++;
        timerId = setTimeout(step, 38 + Math.random() * 20);
      } else {
        typing = false;
        timerId = setTimeout(step, 1800);
      }
    } else {
      if (charIdx > 0) {
        charIdx--;
        textNode.nodeValue = phrase.slice(0, charIdx);
        timerId = setTimeout(step, 22);
      } else {
        phraseIdx = (phraseIdx + 1) % PHRASES.length;
        typing = true;
        timerId = setTimeout(step, 300);
      }
    }
  }

  ta.addEventListener('focus', function() {
    paused = true; overlay.style.display = 'none';
  });
  ta.addEventListener('blur', function() {
    if (!ta.value.trim()) { paused = false; textNode.nodeValue = ''; charIdx = 0; typing = true; step(); }
  });
  ta.addEventListener('input', function() {
    if (ta.value.trim()) { overlay.style.display = 'none'; }
    else { paused = false; textNode.nodeValue = ''; charIdx = 0; typing = true; step(); }
  });
  // Gradio clears textarea programmatically after submit (no 'input' event fires)
  // Detect this via keydown Enter + delayed poll
  ta.addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      setTimeout(function() {
        if (!ta.value.trim()) {
          paused = false; textNode.nodeValue = ''; charIdx = 0; typing = true;
          overlay.style.display = ''; step();
        }
      }, 400);
    }
  });

  step();
};
"""
_GLOBAL_JS_SCRIPT_TAG = "<script>" + _GLOBAL_JS + "</script>"

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
        from witgym.tts import _get_pipeline
        _get_pipeline()  # pre-warm Kokoro so first TTS call isn't slow
    except Exception as e:
        logger.exception("Background warmup failed")
        _warmup_error = _format_warmup_error(e)


threading.Thread(target=_bg_warmup, daemon=True).start()


def _new_session():
    return {"conversation": ConversationManager(), "traces": [], "last_wit_response": None, "selected_char": "AI"}


def _on_page_load():
    if _warmup_error:
        return (
            '<div class="wg-transcript"><div class="wg-empty">'
            f'<div class="wg-empty-icon">⚠️</div><div class="wg-empty-text">{html.escape(_warmup_error)}</div>'
            '</div></div>'
        )
    return format_transcript_html([], show_debug=False)


# ── HTML generators ───────────────────────────────────────────────────────────

def _coaching_panel_html() -> str:
    import json as _json
    # Build JS character data array — includes "AI" as zeroth card
    mascot_data_uri = char_avatar_svg("AI")  # reuse existing SVG helper with generic key
    chars_js = [
        {
            "name": "AI",
            "role": "optimized",
            "avatarUrl": mascot_data_uri,
            "bio": "Let the engine pick the sharpest voice for your situation.",
            "title": "AI-Optimized Coach",
        }
    ]
    for name, role, _bg, avatar_url, bio_title, bio_desc in CHARACTERS:
        fallback = char_avatar_svg(name)
        chars_js.append({
            "name": name,
            "role": role,
            "avatarUrl": avatar_url,
            "fallbackUrl": fallback,
            "bio": bio_desc,
            "title": bio_title,
        })

    chars_json = _json.dumps(chars_js)

    return (
        f'<div class="wg-coach-panel" id="wg-coaching">'
        f'<div class="wg-coach-divider">'
        f'<span class="wg-coach-div-line"></span>'
        f'<span class="wg-coach-div-text">— CHOOSE YOUR COACH —</span>'
        f'<span class="wg-coach-div-line"></span>'
        f'</div>'
        # Arcade carousel scaffold — all state/animation driven by wgInitArcade() JS
        f'<div class="wg-arcade" id="wg-arcade">'
        f'<button class="wg-arcade-arrow wg-arcade-arrow--left" onclick="wgArcadeMove(-1)" aria-label="Previous character">&#8249;</button>'
        f'<div class="wg-arcade-stage">'
        f'<div class="wg-arcade-peek wg-arcade-peek--left" id="wg-arcade-peek-left"></div>'
        f'<div class="wg-arcade-center" id="wg-arcade-center" onclick="wgArcadeSelect()">'
        f'<div class="wg-arcade-avatar-wrap"><img id="wg-arcade-img" class="wg-arcade-img" src="" alt=""/></div>'
        f'<div id="wg-arcade-name" class="wg-arcade-name"></div>'
        f'<div id="wg-arcade-role" class="wg-arcade-role"></div>'
        f'<div id="wg-arcade-bio" class="wg-arcade-bio"></div>'
        f'<div class="wg-arcade-select-hint">PRESS ENTER OR CLICK TO SELECT</div>'
        f'</div>'
        f'<div class="wg-arcade-peek wg-arcade-peek--right" id="wg-arcade-peek-right"></div>'
        f'</div>'
        f'<button class="wg-arcade-arrow wg-arcade-arrow--right" onclick="wgArcadeMove(1)" aria-label="Next character">&#8250;</button>'
        f'</div>'
        # Dot indicators
        f'<div class="wg-arcade-dots" id="wg-arcade-dots"></div>'
        # Embed character data for JS
        f'<script id="wg-chars-data" type="application/json">{html.escape(chars_json)}</script>'
        f'</div>'
    )


_SCROLL_CUE_HTML = (
    '<div class="wg-scroll-cue" role="button" tabindex="0" aria-label="Scroll to begin training"'
    ' onclick="document.getElementById(\'wg-coaching\').scrollIntoView({behavior:\'smooth\'})">'
    '<div class="wg-scroll-circle">'
    '<svg class="wg-scroll-arrow-svg" viewBox="0 0 24 28" width="20" height="24" '
    'fill="none" xmlns="http://www.w3.org/2000/svg">'
    '<line x1="12" y1="2" x2="12" y2="20" stroke="rgba(74,222,128,0.75)" '
    'stroke-width="1.8" stroke-linecap="round"/>'
    '<polyline points="5,13 12,22 19,13" fill="none" stroke="rgba(74,222,128,0.75)" '
    'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>'
    '</svg>'
    '</div>'
    '<span class="wg-scroll-label">begin</span>'
    '</div>'
)


def _landing_html() -> str:
    return (
        f'<div class="wg-hero">'
        f'<div class="wg-rec"><span class="wg-rec-dot"></span>REC</div>'
        f'<div class="wg-kicker">Paste awkward &mdash; get one line that lands</div>'
        f'<div class="wg-logo-row">'
        f'{_MASCOT}'
        f'<div class="wg-wordmark">'
        f'<div class="wg-wordmark-wit">WIT</div>'
        f'<div class="wg-wordmark-gym">GYM</div>'
        f'</div>'
        f'</div>'
        f'</div>'
    )


_MUG_SVG = (
    '<svg viewBox="0 0 44 44" xmlns="http://www.w3.org/2000/svg" width="32" height="32" aria-hidden="true" style="flex-shrink:0">'
    '<rect x="6" y="16" width="24" height="22" rx="3" fill="#f5f0e8" stroke="#c8bfaf" stroke-width="1.2"/>'
    '<path d="M30 22 Q40 22 40 28 Q40 34 30 34" fill="none" stroke="#c8bfaf" stroke-width="2.5" stroke-linecap="round"/>'
    '<rect x="4" y="12" width="28" height="6" rx="3" fill="#ede6d8" stroke="#c8bfaf" stroke-width="1"/>'
    '<text x="18" y="27" text-anchor="middle" font-family="Arial Black,Impact,sans-serif" font-size="4.5" font-weight="900" fill="#2d6a4f">WORLD\'S</text>'
    '<text x="18" y="33" text-anchor="middle" font-family="Arial Black,Impact,sans-serif" font-size="4.5" font-weight="900" fill="#2d6a4f">BEST COACH</text>'
    '<path d="M13 10 Q14 7 13 4" fill="none" stroke="rgba(180,83,9,0.4)" stroke-width="1.2" stroke-linecap="round"/>'
    '<path d="M18 9 Q19 6 18 3" fill="none" stroke="rgba(180,83,9,0.4)" stroke-width="1.2" stroke-linecap="round"/>'
    '<path d="M23 10 Q24 7 23 4" fill="none" stroke="rgba(180,83,9,0.4)" stroke-width="1.2" stroke-linecap="round"/>'
    '</svg>'
)


_ROAST_FLOAT_HTML = '<div id="wg-roast-host" aria-hidden="true"></div>'


def _sidebar_bubble_head_html() -> str:
    ai_src = char_avatar_svg("AI")
    return (
        '<div class="wg-bubble-head">'
        '<div class="wg-bubble-head-inner">'
        f'<img id="wg-bubble-avatar-large" class="wg-bubble-avatar-large" src="{ai_src}" alt="AI Coach"/>'
        '</div>'
        '<div class="wg-bubble-char-name" id="wg-bubble-char-name">AI COACH</div>'
        '</div>'
    )


def _practice_header_html() -> str:
    # IDs wg-coach-avatar, wg-coach-name, wg-coach-role are injected by wgUpdateCoachHeader() JS
    # on start_btn click — no Gradio re-render needed.
    return (
        '<div class="wg-practice-bar">'
        '<div id="wg-coach-avatar-wrap" class="wg-coach-avatar-wrap">'
        + _MUG_SVG +
        '<img id="wg-coach-avatar" class="wg-coach-avatar-img" src="" alt="" style="display:none"/>'
        '</div>'
        '<div class="wg-coach-id">'
        '<div id="wg-coach-name" class="wg-practice-logo">WIT<span>GYM</span></div>'
        '<div id="wg-coach-role" class="wg-practice-sub">Comedy Coaching Engine</div>'
        '</div>'
        ''
        '</div>'
    )


# ── Single modal scaffold — rendered at top DOM level (outside any Column) ────
# position:fixed so parent visibility doesn't matter.
# JS is injected via head= param on the gr.HTML that renders this.
_MODAL_SCAFFOLD = (
    '<div id="wg-modal-overlay" onclick="if(event.target===this)wgClose()">'
    '<div id="wg-modal">'
    '<button class="wg-modal-x" onclick="wgClose()">✕</button>'
    '<div id="wg-modal-body"></div>'
    '</div>'
    '</div>'
)


def fill_starter(text: str) -> str:
    return text


def practice(user_input: str, session, show_debug: bool, progress=gr.Progress()):
    if not isinstance(session, dict):
        session = _new_session()
    user_input = (user_input or "").strip()
    selected_char = session.get("selected_char", "AI")
    if not user_input:
        yield format_transcript_html(session["traces"], show_debug=show_debug, selected_char=selected_char), gr.update(value="", interactive=True), session
        return

    logger.info(f"Practice: {user_input[:80]!r} | char={selected_char}")
    yield (
        format_transcript_html(session["traces"], append_html=thinking_turn_html(user_input), show_debug=show_debug, selected_char=selected_char),
        gr.update(value="", interactive=False),
        session,
    )

    progress(0.05, desc="That's what she said — analysing…")
    engine = WitGymEngine(
        resources=_get_shared(),
        conversation=session["conversation"],
        last_wit_response=session.get("last_wit_response"),
        character=selected_char,
    )
    stream_state = StreamingTurnState(user_input=user_input)
    try:
        for event in engine.respond_stream(user_input):
            apply_stream_event(stream_state, event)
            if event.phase == "metadata":
                progress(0.2, desc="Reading the room like Jim reads Dwight…")
            elif event.phase == "banter":
                progress(0.5, desc="Banter mode activated…")
            elif event.phase == "coaching_ask":
                progress(0.5, desc="Consulting the coaching panel…")
            elif event.phase == "scenes":
                progress(0.35, desc="Checking the beet farm playbook…")
            elif event.phase == "candidate_start":
                progress(0.5, desc=f"Channeling {event.persona}…")
            elif event.phase == "ranked":
                progress(0.85, desc="Picking the sharpest line (not that one, Toby)…")
            elif event.phase == "final_start":
                progress(0.92, desc="Polishing — almost there…")
            elif event.phase == "done" and event.response:
                session["traces"].append((user_input, event.response))
                session["traces"] = session["traces"][-5:]
                session["last_wit_response"] = engine._last_wit_response
                yield (
                    format_transcript_html(session["traces"], show_debug=show_debug, selected_char=selected_char),
                    gr.update(value="", interactive=True),
                    session,
                )
                audio_url = synthesize_line(event.response.selected, selected_char)
                if audio_url:
                    event.response.tts_audio_url = audio_url
                    session["traces"][-1] = (user_input, event.response)
                    final_html = format_transcript_html(session["traces"], show_debug=show_debug, selected_char=selected_char)
                    # Strip audio from session so gr.State doesn't carry ~500KB per turn
                    event.response.tts_audio_url = None
                    yield (final_html, gr.update(value="", interactive=True), session)
                return
            yield (
                format_transcript_with_streaming(session["traces"], stream_state, show_debug=show_debug, selected_char=selected_char),
                gr.update(value="", interactive=False),
                session,
            )
    except Exception as e:
        logger.exception("Engine error")
        err = (
            f'<div class="wg-turn"><div class="wg-user"><span class="wg-label">You</span> '
            f'{html.escape(user_input)}</div>'
            f'<div style="color:#dc2626;padding:.5rem 0">Error: {html.escape(str(e))}</div></div>'
        )
        yield format_transcript_html(session["traces"], append_html=err, show_debug=show_debug, selected_char=selected_char), gr.update(value="", interactive=True), session
        return


def clear_session(show_debug: bool):
    return format_transcript_html([], show_debug=show_debug), gr.update(value="", interactive=True), _new_session()


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
            body_text_color="#f0f0f0",
            input_background_fill="#1a1a1a",
            input_border_color="#2e2e2e",
            border_color_primary="#2e2e2e",
        )
    )


def _set_char_in_session(char_name: str, session):
    """Called when arcade SELECT fires — stores chosen character in session state."""
    if not isinstance(session, dict):
        session = _new_session()
    session = dict(session)
    session["selected_char"] = char_name or "AI"
    logger.info(f"Coach selected: {session['selected_char']}")
    return session


def build_ui():
    with gr.Blocks(title="WitGym", css=APP_CSS, theme=_theme(), head=_GLOBAL_JS_SCRIPT_TAG) as demo:
        # Modal scaffold at top DOM level — position:fixed, never hidden by Column visibility toggling.
        # JS is injected via launch(head=...) below, not here, for SSR compatibility.
        gr.HTML(value=_MODAL_SCAFFOLD)

        session_state    = gr.State(_new_session())
        show_debug_state = gr.State(False)  # punchline first; user can expand coaching notes

        # ── Landing screen ────────────────────────────────────────
        with gr.Column(visible=True, elem_id="wg-landing") as landing_col:
            gr.HTML(_landing_html())
            gr.HTML(_coaching_panel_html())
            with gr.Row(elem_id="wg-start-btn"):
                start_btn = gr.Button("START TRAINING →", variant="primary", size="lg")

        # Hidden Textbox: JS writes selected char name here before arcade confirm fires
        char_hidden = gr.Textbox(visible=True, elem_id="wg-char-hidden", value="AI")

        # ── Practice screen ───────────────────────────────────────
        with gr.Column(visible=False, elem_id="wg-practice") as practice_col:
            gr.HTML(_practice_header_html())
            # Floating roast messages (fixed bottom-right)
            gr.HTML(_ROAST_FLOAT_HTML)

            with gr.Column(elem_id="witgym-main"):
                with gr.Row(equal_height=True):
                    with gr.Column(scale=3):
                        with gr.Group(elem_id="wg-chat-shell"):
                            transcript = gr.HTML(
                                value=format_transcript_html([], show_debug=False),
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
                                elem_id="wg-user-input",
                            )
                            with gr.Row():
                                submit_btn = gr.Button(
                                    "Flex Your Wit →", variant="primary", scale=4,
                                    elem_id="wg-submit-btn",
                                )
                                clear_btn = gr.Button("Start over →", size="sm", variant="secondary", scale=1)


                    with gr.Column(scale=1, elem_id="wg-sidebar"):
                        gr.HTML('<div class="wg-sidebar-label">Try a situation</div>')
                        for tag, text in STARTERS:
                            sb = gr.Button(
                                f"{tag.lower()} · {text}", size="sm", variant="secondary",
                                elem_classes=["wg-starter-btn"],
                            )
                            sb.click(
                                fn=fill_starter, inputs=[gr.State(text)], outputs=user_input, queue=False,
                            ).then(
                                fn=practice,
                                inputs=[user_input, session_state, show_debug_state],
                                outputs=[transcript, user_input, session_state],
                                show_progress="full", show_progress_on=submit_btn,
                            )
                        gr.HTML(_sidebar_bubble_head_html())

        # ── Event wiring ──────────────────────────────────────────

        start_btn.click(
            fn=lambda char, s: (gr.update(visible=False), gr.update(visible=True), {**s, "selected_char": char or "AI"}),
            inputs=[char_hidden, session_state],
            outputs=[landing_col, practice_col, session_state],
            queue=False,
            js=(
                "() => {"
                "  document.body.classList.add('wg-light-mode');"
                "  wgPlayBell && wgPlayBell();"
                "  setTimeout(function(){ wgUpdateCoachHeader && wgUpdateCoachHeader(); }, 80);"
                "  setTimeout(function(){ wgInitFlicker && wgInitFlicker(); wgInitRoasts && wgInitRoasts(); }, 150);"
                "  return [];"
                "}"
            ),
        )
        submit_btn.click(
            fn=practice,
            inputs=[user_input, session_state, show_debug_state],
            outputs=[transcript, user_input, session_state],
            show_progress="full", show_progress_on=submit_btn,
        )
        user_input.submit(
            fn=practice,
            inputs=[user_input, session_state, show_debug_state],
            outputs=[transcript, user_input, session_state],
            show_progress="full", show_progress_on=submit_btn,
        )
        clear_btn.click(
            fn=clear_session,
            inputs=[show_debug_state],
            outputs=[transcript, user_input, session_state],
        )
        demo.load(fn=_on_page_load, outputs=transcript, show_progress="hidden")

    return demo


demo = build_ui()
demo.queue(default_concurrency_limit=1)
demo.favicon_path = _FAVICON

if __name__ == "__main__":
    kwargs = dict(
        favicon_path=_FAVICON,
        css=APP_CSS,
        theme=_theme(),
        head=_GLOBAL_JS_SCRIPT_TAG,
    )
    if os.getenv("SPACE_ID"):
        kwargs["server_name"] = "0.0.0.0"
    demo.launch(**kwargs)
