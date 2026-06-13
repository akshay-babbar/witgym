"""Format WitGymResponse traces for Gradio — styled HTML transcript."""
import html
import json
from typing import List, Tuple, Any
from witgym.schemas import WitGymResponse

_DICEBEAR = "https://api.dicebear.com/9.x/avataaars/svg"

# Maps character first-name or full-name → (title, dicebear-seed, bg)
_CHAR_META: dict[str, tuple[str, str]] = {
    "michael":  ("Regional Manager",                   "MichaelScott"),
    "dwight":   ("Assistant (to the) Reg. Manager",    "DwightSchrute"),
    "jim":      ("Sales Representative",               "JimHalpert"),
    "pam":      ("Receptionist",                       "PamBeesly"),
    "kevin":    ("Accountant",                         "KevinMalone"),
    "andy":     ("Sales Representative",               "AndyBernard"),
    "stanley":  ("Sales Representative",               "StanleyHudson"),
    "angela":   ("Head of Accounting",                 "AngelaMartin"),
    "ryan":     ("Temp → VP → Temp",                   "RyanHoward"),
    "kelly":    ("Customer Service Rep",               "KellyKapoor"),
    "michael scott":  ("Regional Manager",             "MichaelScott"),
    "dwight schrute": ("Asst. (to the) Reg. Manager", "DwightSchrute"),
    "jim halpert":    ("Sales Representative",         "JimHalpert"),
    "pam beesly":     ("Receptionist",                 "PamBeesly"),
    "kevin malone":   ("Accountant",                   "KevinMalone"),
    "andy bernard":   ("Sales Representative",         "AndyBernard"),
    "stanley hudson": ("Sales Representative",         "StanleyHudson"),
    "angela martin":  ("Head of Accounting",           "AngelaMartin"),
    "ryan howard":    ("Temp → VP → Temp",             "RyanHoward"),
    "kelly kapoor":   ("Customer Service Rep",         "KellyKapoor"),
}


def _avatar_url(character: str) -> str:
    key = character.lower().strip()
    seed = _CHAR_META.get(key, (None, character.replace(" ", "")))[1]
    return f"{_DICEBEAR}?seed={seed}&backgroundColor=transparent"


def _char_title(character: str) -> str:
    key = character.lower().strip()
    return _CHAR_META.get(key, ("The Office",))[0]


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
        f'<div class="wg-thinking">{_THINKING_ICON}<span>Your humor coach is thinking…</span></div>'
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
            f'<div class="wg-panel-title">Retrieved Scene {i} — {_esc(show)} · click to expand ↗</div>',
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


def format_trace_html(result: WitGymResponse, user_input: str, show_debug: bool = True) -> str:
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

    parts += [
        '<div class="wg-debug-toggle">',
        '<span class="wg-debug-toggle-line"></span>',
        f'<span class="wg-debug-toggle-label">Coaching notes <span class="wg-debug-chevron">{chevron}</span></span>',
        '<span class="wg-debug-toggle-line"></span>',
        '</div>',
        f'<div class="wg-debug-body{collapsed_cls}">',
        _debug_panels_html(result),
        '</div>',
        '<div class="wg-coach-reply">',
        '<div class="wg-coach-reply-header">Your humor coach</div>',
        f'<div class="wg-coach-reply-body">{_esc(result.selected)}</div>',
        '</div>',
        '<div class="wg-rule"></div></div>',
    ]
    return "".join(parts)


# JS for coaching-note toggle AND scene popup
_PAGE_JS = """<script>
(function(){
  // Collapsible coaching notes
  document.querySelectorAll('.wg-debug-toggle').forEach(function(t){
    if(t._wg) return; t._wg=true;
    t.addEventListener('click',function(){
      var b=t.nextElementSibling;
      var ch=t.querySelector('.wg-debug-chevron');
      var c=b.classList.toggle('wg-collapsed');
      if(ch) ch.textContent=c?'▶':'▼';
    });
  });

  // Scene popup — wgOpenScene may already be defined by landing scaffold; extend it
  if(!window.wgOpenScene){
    window.wgClose=function(){
      var o=document.getElementById('wg-modal-overlay');
      if(o) o.style.display='none';
    };
    window.wgOpenScene=function(character,show,setup,response,why,avatarUrl,title){
      var o=document.getElementById('wg-modal-overlay');
      var b=document.getElementById('wg-modal-body');
      if(!o||!b) return;
      b.innerHTML='<div class="wg-pop-show">'+show+'</div>'
        +'<div class="wg-pop-row">'
        +'<div class="wg-pop-char"><img class="wg-pop-avatar" src="'+avatarUrl+'"/>'
        +'<div class="wg-pop-name">'+character+'</div>'
        +'<div class="wg-pop-title">'+title+'</div></div>'
        +'<div class="wg-pop-right">'
        +'<div class="wg-pop-setup">“'+setup+'”</div>'
        +'<div class="wg-pop-bubble">'+response+'</div>'
        +'</div></div>'
        +'<div class="wg-pop-why"><div class="wg-pop-why-title">WHY IT WORKS</div>'
        +'<div class="wg-pop-why-body">'+why+'</div></div>';
      o.style.display='flex';
    };
    document.addEventListener('click',function(e){
      if(e.target===document.getElementById('wg-modal-overlay')) window.wgClose();
    });
  } else {
    // wgOpenScene already defined (landing scaffold); just wire scene popup to it
    var _orig=window.wgOpenScene;
    window.wgOpenScene=function(character,show,setup,response,why,avatarUrl,title){
      var o=document.getElementById('wg-modal-overlay');
      var b=document.getElementById('wg-modal-body');
      if(!o||!b){ _orig&&_orig(character,show,setup,response,why,avatarUrl,title); return; }
      b.innerHTML='<div class="wg-pop-show">'+show+'</div>'
        +'<div class="wg-pop-row">'
        +'<div class="wg-pop-char"><img class="wg-pop-avatar" src="'+avatarUrl+'"/>'
        +'<div class="wg-pop-name">'+character+'</div>'
        +'<div class="wg-pop-title">'+title+'</div></div>'
        +'<div class="wg-pop-right">'
        +'<div class="wg-pop-setup">“'+setup+'”</div>'
        +'<div class="wg-pop-bubble">'+response+'</div>'
        +'</div></div>'
        +'<div class="wg-pop-why"><div class="wg-pop-why-title">WHY IT WORKS</div>'
        +'<div class="wg-pop-why-body">'+why+'</div></div>';
      o.style.display='flex';
    };
  }
})();
</script>"""

# Modal scaffold injected into the practice screen transcript
# (The landing already has it; we need it here too for when the user is on the practice screen)
_PRACTICE_MODAL = """
<div id="wg-modal-overlay" style="display:none" onclick="if(event.target===this)wgClose()">
  <div id="wg-modal">
    <button class="wg-modal-x" onclick="wgClose()">✕</button>
    <div id="wg-modal-body"></div>
  </div>
</div>
"""


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
        blocks = [
            format_trace_html(
                r if isinstance(r, WitGymResponse) else WitGymResponse.model_validate(r),
                user_input,
                show_debug=show_debug,
            )
            for user_input, r in recent
        ]
        body = "".join(blocks) + append_html

    return f'{_PRACTICE_MODAL}<div class="wg-transcript">{body}</div>{_PAGE_JS}'


# Legacy helpers
def format_trace(result: WitGymResponse, user_input: str) -> str:
    lines = [f"**You:** {user_input}", f"**WitGym:** {result.selected}", ""]
    if result.route != "smalltalk":
        meta = result.metadata
        lines.append(f"_archetype={meta.archetype.value}, tension={meta.tension_type.value}_")
    return "\n".join(lines)


def format_logs(traces: List[Tuple[str, Any]], max_turns: int = 5) -> str:
    return format_transcript_html(traces, max_turns)
