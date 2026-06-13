"""Character-specific DiceBear avataaars URLs + inline SVG fallback."""
import base64

_BASE = "https://api.dicebear.com/9.x/avataaars/svg"

# Character-specific params using exact DiceBear v9 avataaars enum values.
# Colors are 6-char hex (no #). hairColor/clothesColor/skinColor are hex arrays.
# top values: shortFlat, shaggy, sides, curvy, bun, straight01, theCaesar, shortRound
# mouth values: smile, serious, twinkle, disbelief, eating, default, concerned
# eyebrows values: raisedExcited, angry, upDown, angryNatural, defaultNatural, frownNatural
# accessories values: prescription02, kurt (use accessoriesProbability=100 to force show)
# facialHair values: beardLight, beardMajestic, moustacheMagnum (use facialHairProbability=100)
_CHAR_PARAMS: dict[str, str] = {
    # Michael Scott (Steve Carell): white, dark brown short hair, suit, big grin
    "michael": (
        "top=shortFlat&hairColor=4a312c&mouth=smile&eyebrows=raisedExcited"
        "&clothing=blazerAndShirt&clothesColor=929598"
        "&eyes=happy&accessoriesProbability=0&facialHairProbability=0"
        "&skinColor=ffdbb4"
    ),
    # Dwight Schrute (Rainn Wilson): white, FULL dark hair (not bald), rectangular glasses
    # top=shortFlat gives full head of hair; sides=bald-on-top which is wrong for Dwight
    "dwight": (
        "top=shortFlat&hairColor=2c1b18&mouth=serious&eyebrows=angry"
        "&accessories=prescription02&accessoriesProbability=100"
        "&clothing=blazerAndShirt&clothesColor=262e33&facialHairProbability=0"
        "&skinColor=ffdbb4"
    ),
    # Jim Halpert (John Krasinski): white, medium brown shaggy hair, smirk
    "jim": (
        "top=shaggy&hairColor=4a312c&mouth=twinkle&eyebrows=upDown"
        "&clothing=blazerAndSweater&clothesColor=5199e4"
        "&accessoriesProbability=0&facialHairProbability=0"
        "&skinColor=ffdbb4"
    ),
    # Pam Beesly (Jenna Fischer): white, strawberry blonde/light auburn hair
    # hairColor c8956c = light warm auburn, NOT dark brown
    "pam": (
        "top=curvy&hairColor=c8956c&mouth=smile&eyebrows=defaultNatural"
        "&clothing=shirtCrewNeck&clothesColor=ffafb9"
        "&accessoriesProbability=0&facialHairProbability=0"
        "&skinColor=ffdbb4"
    ),
    # Kevin Malone (Brian Baumgartner): white, short curly dark hair, eating expression
    "kevin": (
        "top=shortCurly&hairColor=2c1b18&mouth=eating&eyebrows=default"
        "&clothing=graphicShirt&clothesColor=929598"
        "&accessoriesProbability=0&facialHairProbability=0"
        "&skinColor=ffdbb4"
    ),
    # Andy Bernard (Ed Helms): white, blonde, big smile, blue blazer
    "andy": (
        "top=shortFlat&hairColor=d6b370&mouth=smile&eyebrows=raisedExcited"
        "&clothing=blazerAndSweater&clothesColor=25557c"
        "&accessoriesProbability=0&facialHairProbability=0"
        "&skinColor=ffdbb4"
    ),
    # Stanley Hudson (Leslie David Baker): dark-skinned Black male, caesar/very short hair, mustache
    "stanley": (
        "top=theCaesar&hairColor=2c1b18&mouth=disbelief&eyebrows=frownNatural"
        "&facialHair=moustacheMagnum&facialHairProbability=100&facialHairColor=2c1b18"
        "&clothing=blazerAndShirt&clothesColor=3c4f5c&accessoriesProbability=0"
        "&skinColor=ae5d29"
    ),
    # Angela Martin (Angela Kinsey): white/very pale, blonde bun, stern expression
    "angela": (
        "top=bun&hairColor=d6b370&mouth=concerned&eyebrows=angryNatural"
        "&clothing=blazerAndSweater&clothesColor=e6e6e6"
        "&accessoriesProbability=0&facialHairProbability=0"
        "&skinColor=ffdbb4"
    ),
    # Ryan Howard (B.J. Novak): white, dark hair, light beard, smug smirk
    "ryan": (
        "top=shortRound&hairColor=2c1b18&mouth=twinkle&eyebrows=default"
        "&facialHair=beardLight&facialHairProbability=100&facialHairColor=2c1b18"
        "&clothing=blazerAndSweater&clothesColor=262e33&accessoriesProbability=0"
        "&skinColor=ffdbb4"
    ),
    # Kelly Kapoor (Mindy Kaling): South Asian/Indian, long dark hair, pink, enthusiastic
    "kelly": (
        "top=straight01&hairColor=2c1b18&mouth=smile&eyebrows=raisedExcited"
        "&clothing=shirtCrewNeck&clothesColor=ff488e"
        "&accessoriesProbability=0&facialHairProbability=0&skinColor=d08b5b"
    ),
}

# Fallback SVG palette (used if DiceBear unavailable via onerror=)
_FALLBACK_STYLES: dict[str, tuple[str, str]] = {
    "michael": ("#b91c1c", "🎤"),
    "dwight":  ("#14532d", "🥸"),
    "jim":     ("#1e3a5f", "😏"),
    "pam":     ("#7e3fa8", "🎨"),
    "kevin":   ("#c2410c", "🍩"),
    "andy":    ("#b45309", "🎵"),
    "stanley": ("#292524", "📰"),
    "angela":  ("#92400e", "🐱"),
    "ryan":    ("#1e1b4b", "💼"),
    "kelly":   ("#9d174d", "💅"),
}


def char_avatar_url(name: str) -> str:
    """DiceBear avataaars URL with character-specific cartoon features."""
    key = name.lower().split()[0]
    params = _CHAR_PARAMS.get(key, f"seed={name}")
    seed = name.replace(" ", "")
    return f"{_BASE}?seed={seed}&{params}&backgroundColor=transparent"


def char_avatar_svg(name: str) -> str:
    """Fallback inline SVG data URI (colored circle + initial + emoji)."""
    key = name.lower().split()[0]
    bg, emoji = _FALLBACK_STYLES.get(key, ("#2d6a4f", "🎭"))
    initial = name[0].upper()
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 80 80">'
        f'<circle cx="40" cy="40" r="40" fill="{bg}"/>'
        f'<circle cx="40" cy="40" r="38" fill="none" stroke="rgba(255,255,255,0.15)" stroke-width="2"/>'
        f'<text x="40" y="34" text-anchor="middle" dominant-baseline="middle" '
        f'font-size="24" font-family="Georgia,serif" font-weight="700" fill="#fff">{initial}</text>'
        f'<text x="40" y="60" text-anchor="middle" font-size="20">{emoji}</text>'
        '</svg>'
    )
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()
