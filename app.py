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
from witgym.debug_render import format_transcript_html, thinking_turn_html
from witgym import config

INDEX_PATH = os.getenv("WITGYM_INDEX_PATH", config.INDEX_PATH)
_FAVICON = Path(__file__).parent / "assets" / "favicon.png"

# ── DiceBear Avataaars URLs — cartoon-style, free, no copyright ──────────────
_DICEBEAR = "https://api.dicebear.com/9.x/avataaars/svg"

def _av(seed: str, **kw) -> str:
    params = "&".join(f"{k}[]={v}" for k, v in kw.items())
    return f"{_DICEBEAR}?seed={seed}&backgroundColor=transparent&{params}"

# Character data: (name, role-label, card-bg, avatar-url, bio-title, bio-desc)
CHARACTERS = [
    ("Michael",  "comedian",    "#5a1a0a",
     _av("MichaelScott",  top="shortHairShortFlat", topColor="brown",   clothingColor="black",  mouth="smile"),
     "Regional Manager",
     "Needs to be the funniest person in the room — always. Even at funerals."),
    ("Dwight",   "contrarian",  "#2d3d1a",
     _av("DwightSchrute", top="shortHairShortRound", topColor="brown",  accessories="round",    mouth="default"),
     "Assistant (to the) Regional Manager",
     "Treats every situation as a threat to be neutralised through superior preparation."),
    ("Jim",      "wit",         "#1a2d4a",
     _av("JimHalpert",    top="shortHairShortFlat", topColor="brown",   clothingColor="navy",   mouth="twinkle"),
     "Sales Representative",
     "Deflects chaos with a raised eyebrow and impeccable comedic timing."),
    ("Pam",      "empath",      "#5a1a4a",
     _av("PamBeesly",     top="longHairStraight",   topColor="brunette",clothingColor="pastelGreen", mouth="smile"),
     "Receptionist → Office Administrator",
     "Finds the kindest possible way to say the unsayable thing everyone else is thinking."),
    ("Kevin",    "literalist",  "#3d1a5a",
     _av("KevinMalone",   top="shortHairShortCurly",topColor="black",   clothingColor="gray",   mouth="eating"),
     "Accountant",
     "Cuts to the literal truth everyone else is too sophisticated to say out loud."),
    ("Andy",     "overclaimer", "#7a3010",
     _av("AndyBernard",   top="shortHairShortFlat", topColor="blonde",  clothingColor="red",    mouth="smile"),
     "Sales Representative",
     "Overclaims, overshares, and somehow — through sheer confidence — lands it."),
    ("Stanley",  "cynic",       "#0f2d1a",
     _av("StanleyHudson", top="shortHairShortFlat", topColor="black",   skinColor="darkBrown",  mouth="sad"),
     "Sales Representative",
     "Has seen it all. Cares about essentially none of it. Will now return to his crossword."),
    ("Angela",   "moralist",    "#2a2a0a",
     _av("AngelaMartin",  top="longHairBun",         topColor="blonde",  clothingColor="black",  mouth="concerned"),
     "Head of Accounting",
     "Holds the line on decorum, propriety and cats while everything collapses around her."),
    ("Ryan",     "hustler",     "#1f0a2d",
     _av("RyanHoward",    top="shortHairShortRound", topColor="black",   facialHair="beardLight",mouth="default"),
     "Temp → VP → Temp → Temp",
     "Dresses up insecurity as strategy. The hustle is the product."),
    ("Kelly",    "enthusiast",  "#6a0a3a",
     _av("KellyKapoor",   top="longHairCurvy",       topColor="black",   skinColor="brown",      mouth="smile"),
     "Customer Service Representative",
     "Turns raw enthusiasm into an overwhelming and surprisingly effective force of nature."),
]

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

# ── Mascot SVG ────────────────────────────────────────────────────────────────
_MASCOT = """<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg" class="wg-mascot" width="108" height="108" aria-hidden="true">
  <circle cx="50" cy="50" r="44" fill="#f0ebe0" stroke="#d4cfc0" stroke-width="1.5"/>
  <rect x="7"  y="34" width="35" height="22" rx="6" fill="#1a3d2b"/>
  <rect x="58" y="34" width="35" height="22" rx="6" fill="#1a3d2b"/>
  <rect x="42" y="42" width="16" height="6"  rx="2" fill="#1a3d2b"/>
  <path d="M34 68 Q50 80 66 68" stroke="#5c4a3a" stroke-width="3" fill="none" stroke-linecap="round"/>
</svg>"""

APP_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=EB+Garamond:ital,wght@0,400;0,600;1,400&display=swap');

/* ── Global dark base ──────────────────────────────────────────────────── */
body, .gradio-container, .main, footer { background: #141414 !important; }

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

/* ── Landing / Hero (exactly one viewport, no scroll) ──────────────────── */
.wg-hero {
  position: relative; height: 100svh; min-height: 560px;
  display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  background: var(--wg-bg); overflow: hidden;
  padding: 2rem 1rem; text-align: center;
}
.wg-hero::before {
  content: ''; position: absolute; inset: 0;
  background-image: radial-gradient(rgba(255,255,255,0.045) 1px, transparent 1px);
  background-size: 24px 24px; pointer-events: none;
}

/* ● REC indicator */
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
@keyframes wg-pulse { 0%,100%{opacity:1} 50%{opacity:.3} }

/* Kicker */
.wg-kicker {
  font-family: 'EB Garamond', Georgia, serif; font-style: italic;
  font-size: 0.78rem; letter-spacing: 0.22em;
  color: var(--wg-yellow); text-transform: uppercase;
  margin-bottom: 1rem; z-index: 1;
}

/* Mascot */
.wg-mascot { margin-bottom: 0.5rem; z-index: 1;
  filter: drop-shadow(0 4px 20px rgba(45,106,79,0.3)); }

/* WIT / GYM wordmark */
.wg-wordmark { display: flex; flex-direction: column; align-items: center;
  line-height: 0.88; margin-bottom: 0.9rem; z-index: 1; }
.wg-wordmark-wit, .wg-wordmark-gym {
  font-family: 'Bebas Neue', Impact, 'Arial Black', sans-serif;
  font-size: clamp(4.5rem, 18vw, 9rem); letter-spacing: 0.03em;
}
.wg-wordmark-wit { color: var(--wg-white); }
.wg-wordmark-gym { color: var(--wg-yellow); }

.wg-hero-tagline {
  font-family: 'EB Garamond', Georgia, serif; font-style: italic;
  font-size: 1rem; color: rgba(240,240,240,0.7);
  margin-bottom: 1.75rem; z-index: 1;
}

/* START TRAINING button */
#wg-start-btn { z-index: 1; justify-content: center !important; }
#wg-start-btn button {
  font-family: 'Bebas Neue', Impact, sans-serif !important;
  font-size: 1.2rem !important; letter-spacing: 0.22em !important;
  background: var(--wg-green) !important; color: #fff !important;
  border: none !important; border-radius: 50px !important;
  padding: 0.75rem 3.25rem !important;
  transition: background .2s, transform .15s;
}
#wg-start-btn button:hover { background: #235a40 !important; transform: translateY(-2px); }

.wg-start-hint {
  font-size: 0.72rem; color: var(--wg-muted); margin-top: 0.55rem;
  font-style: italic; z-index: 1;
}

/* Glassy green bouncing scroll arrow */
.wg-scroll-arrow {
  position: absolute; bottom: 1.75rem; left: 50%; transform: translateX(-50%);
  width: 40px; height: 40px; border-radius: 50%;
  background: linear-gradient(135deg, #2d6a4f 0%, #4ade80 100%);
  box-shadow: 0 0 18px rgba(74,222,128,0.45), inset 0 1px 0 rgba(255,255,255,0.2);
  display: flex; align-items: center; justify-content: center;
  cursor: pointer; z-index: 2; border: none;
  animation: wg-bounce 1.9s ease-in-out infinite;
  font-size: 1rem; color: #fff; text-decoration: none;
  backdrop-filter: blur(4px);
}
@keyframes wg-bounce {
  0%,100% { transform: translateX(-50%) translateY(0);   box-shadow: 0 0 18px rgba(74,222,128,0.45); }
  50%      { transform: translateX(-50%) translateY(9px); box-shadow: 0 0 28px rgba(74,222,128,0.65); }
}

/* ── Coaching panel ─────────────────────────────────────────────────────── */
.wg-coach-panel {
  width: 100%; padding: 2rem 1rem 2.5rem;
  background: var(--wg-bg); border-top: 1px solid #2a2a2a;
}
.wg-coach-divider {
  display: flex; align-items: center; gap: 1rem; margin-bottom: 1.5rem;
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

/* ── Practice screen header (compact) ──────────────────────────────────── */
.wg-practice-bar {
  display: flex; align-items: center; gap: 0.75rem;
  padding: 0.75rem 1.25rem; border-bottom: 1px solid #d8d0c4;
  background: #faf9f6;
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
#wg-practice #wg-chat-shell {
  background: #faf9f6 !important; border-color: #e0d8cc !important;
}
#wg-practice .wg-transcript { color: #2a2118; }
#wg-practice .wg-user { color: #2d6a4f; }
#wg-practice .wg-thinking {
  background: #f5f2eb; border-color: rgba(200,190,175,0.5); color: #6b6258;
}
#wg-practice .wg-coach-reply {
  background: #f0fdf4; border-color: #4ade80; border-left-color: #2d6a4f;
}
#wg-practice .wg-coach-reply-header { color: #2d6a4f; }
#wg-practice .wg-coach-reply-body   { color: #14532d; }
#wg-practice .wg-panel-yellow { background: #fffbeb; border-color: #fbbf24; color: #78350f; }
#wg-practice .wg-panel-yellow .wg-panel-title { color: #b45309; }
#wg-practice .wg-panel-blue   { background: #eff6ff; border-color: #60a5fa; color: #1e3a5f; }
#wg-practice .wg-panel-blue   .wg-panel-title { color: #2563eb; }
#wg-practice .wg-panel-green  { background: #f0fdf4; border-color: #4ade80; color: #14532d; }
#wg-practice .wg-panel-green  .wg-panel-title { color: #16a34a; }
#wg-practice .wg-panel-dim    { background: #f5f5f4; border-color: #d6d3d1; color: #78716c; }
#wg-practice .wg-dim   { color: #9e9288; }
#wg-practice .wg-cyan  { color: #0891b2; }
#wg-practice .wg-dim-italic { color: #9e9288; font-style: italic; }
#wg-practice .wg-debug-toggle-line   { background: #e0d8cc; }
#wg-practice .wg-debug-toggle-label {
  border-color: #e0d8cc; background: #f5f2eb; color: #9e9288;
}
#wg-practice .wg-debug-toggle-label:hover { color: #6b6258; }
#wg-practice .wg-rule { border-color: #e0d8cc; }
#wg-practice .wg-empty { color: #9e9288; }
#wg-practice #wg-sidebar {
  background: #faf9f6 !important; border-color: #e0d8cc !important;
}
#wg-practice .wg-sidebar-label { color: #9e9288; }
#wg-practice .wg-starter-btn button {
  background: #fff !important; border-color: #e0d8cc !important;
  color: #3d3429 !important;
}
#wg-practice .wg-starter-btn button:hover {
  border-color: var(--wg-green) !important; background: #f0fdf4 !important;
}
#wg-practice .gradio-container textarea,
#wg-practice .gradio-container input[type="text"] {
  background: #fff !important; color: #2a2118 !important; border-color: #e0d8cc !important;
}
#wg-practice .gradio-container textarea::placeholder,
#wg-practice .gradio-container input[type="text"]::placeholder { color: #9e9288 !important; }
#wg-practice .gradio-container button.secondary {
  background: #f5f2eb !important; border-color: #e0d8cc !important; color: #3d3429 !important;
}
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
.wg-clickable    { cursor: pointer; transition: opacity .15s, transform .1s; }
.wg-clickable:hover { opacity: 0.85; transform: scale(1.01); }
.wg-meta { border-collapse: collapse; width: 100%; }
.wg-meta td { padding: 0.1rem 0.5rem 0.1rem 0; vertical-align: top; }
.wg-rule { border-top: 1px solid var(--wg-border); margin: 0.75rem 0; }
.wg-dim { color: var(--wg-muted); }
.wg-dim-italic { color: var(--wg-muted); font-style: italic; }
.wg-cyan { color: #22d3ee; font-weight: 500; }
.wg-bold { font-weight: 600; }

/* ── Comic-style modal ──────────────────────────────────────────────────── */
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
  letter-spacing: 0.2em; color: #2d6a4f; margin-bottom: 1rem;
  border-bottom: 2px solid #e0d8cc; padding-bottom: 0.5rem;
}
.wg-pop-row { display: flex; gap: 1.25rem; margin-bottom: 1rem; align-items: flex-start; }
.wg-pop-char { display: flex; flex-direction: column; align-items: center; gap: 0.3rem; flex-shrink: 0; }
.wg-pop-avatar { width: 110px; height: 110px; border-radius: 12px; background: #f5f0e6; }
.wg-pop-name {
  font-family: 'Bebas Neue', sans-serif; font-size: 1rem;
  letter-spacing: 0.08em; color: #2a2118; text-align: center;
}
.wg-pop-title {
  font-size: 0.72rem; color: #9e9288; text-align: center; font-style: italic;
  max-width: 110px; line-height: 1.3;
}
.wg-pop-right { flex: 1; display: flex; flex-direction: column; gap: 0.65rem; }
.wg-pop-setup {
  font-style: italic; color: #6b6258; font-size: 0.95rem; line-height: 1.5;
}
.wg-pop-bubble {
  background: #fff; border: 2.5px solid #1a1a1a; border-radius: 14px;
  padding: 0.85rem 1rem;
  font-family: 'Bebas Neue', Impact, sans-serif;
  font-size: 1.15rem; line-height: 1.3; letter-spacing: 0.02em; color: #1a1a1a;
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
  letter-spacing: 0.12em; color: #2563eb; margin-bottom: 0.35rem;
}
.wg-pop-why-body { font-size: 0.95rem; color: #1e3a5f; line-height: 1.55; }
/* Bio modal (character card click — no scene context) */
.wg-pop-bio {
  font-size: 1.05rem; color: #3d3429; line-height: 1.6; font-style: italic;
  background: #f5f0e6; border-left: 3px solid #2d6a4f;
  padding: 0.75rem 1rem; border-radius: 0 10px 10px 0;
}
"""

# ── Character card popup JS (coaching panel) ──────────────────────────────────
_CHAR_MODAL_JS = """
<script>
(function(){
  function wgClose(){document.getElementById('wg-modal-overlay').style.display='none';}
  function wgOpenBio(name,title,desc,avatarUrl){
    var b=document.getElementById('wg-modal-body');
    b.innerHTML='<div class="wg-pop-show">THE COACHING PANEL</div>'
      +'<div class="wg-pop-row">'
      +'<div class="wg-pop-char">'
      +'<img class="wg-pop-avatar" src="'+avatarUrl+'"/>'
      +'<div class="wg-pop-name">'+name+'</div>'
      +'<div class="wg-pop-title">'+title+'</div>'
      +'</div>'
      +'<div class="wg-pop-right">'
      +'<div class="wg-pop-bio">'+desc+'</div>'
      +'</div></div>';
    document.getElementById('wg-modal-overlay').style.display='flex';
  }
  window.wgClose=wgClose;
  window.wgOpenBio=wgOpenBio;
  document.addEventListener('click',function(e){
    if(e.target===document.getElementById('wg-modal-overlay')) wgClose();
  });
})();
</script>
"""

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


def _on_page_load():
    if _warmup_error:
        return (
            '<div class="wg-transcript"><div class="wg-empty">'
            f'<div class="wg-empty-icon">⚠️</div><div class="wg-empty-text">{html.escape(_warmup_error)}</div>'
            '</div></div>'
        )
    return format_transcript_html([], show_debug=True)


# ── HTML generators ───────────────────────────────────────────────────────────

def _coaching_panel_html() -> str:
    cards = []
    for name, role, bg, avatar_url, bio_title, bio_desc in CHARACTERS:
        import json
        onclick = (
            f"wgOpenBio({json.dumps(name)},{json.dumps(bio_title)},{json.dumps(bio_desc)},{json.dumps(avatar_url)})"
        )
        cards.append(
            f'<div class="wg-char-card" onclick="{html.escape(onclick)}" title="{html.escape(bio_title)}">'
            f'<img src="{html.escape(avatar_url)}" alt="{html.escape(name)}" loading="lazy"/>'
            f'<span class="wg-char-name">{html.escape(name)}</span>'
            f'<span class="wg-char-role">{html.escape(role)}</span>'
            f'</div>'
        )
    return (
        f'<div class="wg-coach-panel" id="wg-coaching">'
        f'<div class="wg-coach-divider">'
        f'<span class="wg-coach-div-line"></span>'
        f'<span class="wg-coach-div-text">— COACHING PANEL —</span>'
        f'<span class="wg-coach-div-line"></span>'
        f'</div>'
        f'<div class="wg-char-grid">{"".join(cards)}</div>'
        f'</div>'
    )


def _landing_html() -> str:
    return (
        f'<div class="wg-hero">'
        f'<div class="wg-rec"><span class="wg-rec-dot"></span>REC</div>'
        f'<div class="wg-kicker">CBR-RAG Comedy Coaching Engine</div>'
        f'{_MASCOT}'
        f'<div class="wg-wordmark">'
        f'<div class="wg-wordmark-wit">WIT</div>'
        f'<div class="wg-wordmark-gym">GYM</div>'
        f'</div>'
        f'<p class="wg-hero-tagline">Coach your comedy instincts — one situation at a time.</p>'
        f'</div>'
    )


def _practice_header_html() -> str:
    return (
        '<div class="wg-practice-bar">'
        '<div class="wg-practice-logo">WIT<span>GYM</span></div>'
        '<div class="wg-practice-sub">CBR-RAG Comedy Engine</div>'
        '</div>'
    )


# ── Modal scaffold HTML (injected into landing, lives in DOM always) ──────────
_MODAL_SCAFFOLD = (
    '<div id="wg-modal-overlay">'
    '<div id="wg-modal">'
    '<button class="wg-modal-x" onclick="wgClose()">✕</button>'
    '<div id="wg-modal-body"></div>'
    '</div>'
    '</div>'
    + _CHAR_MODAL_JS
)


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
            f'<div style="color:#dc2626;padding:.5rem 0">Error: {html.escape(str(e))}</div></div>'
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
        )
    )


def build_ui():
    with gr.Blocks(title="WitGym", css=APP_CSS, theme=_theme()) as demo:
        session_state    = gr.State(_new_session())
        show_debug_state = gr.State(True)   # coaching notes ON by default

        # ── Landing screen ────────────────────────────────────────
        with gr.Column(visible=True) as landing_col:
            gr.HTML(_landing_html())
            with gr.Row(elem_id="wg-start-btn"):
                start_btn = gr.Button("START TRAINING →", variant="primary", size="lg")
            gr.HTML('<p class="wg-start-hint">Paste any real-life awkward situation to begin</p>')
            gr.HTML(
                f'<a class="wg-scroll-arrow" href="#wg-coaching" '
                f'onclick="event.preventDefault();document.getElementById(\'wg-coaching\')'
                f'.scrollIntoView({{behavior:\'smooth\'}})" aria-label="Scroll to coaching panel">▼</a>'
            )
            gr.HTML(_coaching_panel_html())
            gr.HTML(_MODAL_SCAFFOLD)

        # ── Practice screen ───────────────────────────────────────
        with gr.Column(visible=False, elem_id="wg-practice") as practice_col:
            gr.HTML(_practice_header_html())

            with gr.Column(elem_id="witgym-main"):
                with gr.Row(equal_height=True):
                    with gr.Column(scale=3):
                        with gr.Group(elem_id="wg-chat-shell"):
                            transcript = gr.HTML(
                                value=format_transcript_html([], show_debug=True),
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
                                    "Practice Wit →", variant="primary", scale=4,
                                    elem_id="wg-submit-btn",
                                )
                                clear_btn = gr.Button("New session", size="sm", variant="secondary", scale=1)

                        with gr.Row():
                            debug_toggle = gr.Checkbox(
                                label="Show coaching notes (CBR-RAG debug panels)",
                                value=True,   # ON by default
                            )

                    with gr.Column(scale=1, elem_id="wg-sidebar"):
                        gr.HTML('<div class="wg-sidebar-label">Try a situation</div>')
                        for tag, text in STARTERS:
                            sb = gr.Button(
                                f"[{tag}] {text}", size="sm", variant="secondary",
                                elem_classes=["wg-starter-btn"],
                            )
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
