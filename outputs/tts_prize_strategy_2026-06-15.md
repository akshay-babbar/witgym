# WitGym TTS Strategy — June 15, 2026

## Objective

Choose the Pareto-optimal speech path for WitGym that:

- fixes the current gender mismatch and robotic quality,
- preserves the strongest odds of winning in `Thousand Token Wood`,
- can improve eligibility for sponsor prizes where sensible,
- and complies with the Build Small rule set.

## Bottom Line

The current browser `speechSynthesis` implementation is acceptable only as a fallback. It is not a competitive final demo voice layer because:

- voice selection is OS-dependent, so character-to-gender matching is unreliable,
- realism is capped by the local browser voice inventory,
- and it does not meaningfully strengthen any sponsor-prize story.

The best move depends on what we are optimizing for:

### Best short-term fix

Keep browser speech only as a fallback, but hard-filter to male/female voices so Michael never comes out sounding female. This is the cheapest repair, but it will still sound synthetic.

### Best realism-per-hour

Integrate `hexgrad/Kokoro-82M` as the real TTS layer and keep `speechSynthesis` as fallback only. Kokoro is tiny, open-weight, Apache-licensed, and explicitly positioned as a fast, cost-efficient TTS model with 82M parameters. It is the best quality-to-integration trade-off for a hackathon polish layer.

### Best sponsor-prize angle

If the goal is specifically the `Best MiniCPM Build` prize, the strongest option is `openbmb/MiniCPM-o-2_6`. It is an 8B omni model with speech conversation, configurable voices, and voice cloning. But it should not be bolted on as a decorative read-aloud layer. The Build Small FAQ says sponsor models do not need to be exclusive, but they must be a **core** part of the experience.

## Critical Rule Clarification

The Build Small rule is **not** “cumulative weights across the whole stack must stay under 32B.”

As of June 15, 2026, the field guide says:

- each model must be under 32B,
- you may combine several models,
- and the sponsor’s model can coexist with others if it is a core part of the product.

That means all of these are structurally allowed:

- `Qwen3.5-27B` + `Kokoro-82M`
- `Qwen3.5-27B` + `Pocket-TTS-100M`
- `Qwen3.5-27B` + `MiniCPM-o-2_6`

## Option Analysis

### Option A — Browser speech only

Pros:

- zero model download,
- fastest patch,
- keeps current UI intact.

Cons:

- not realistic,
- gender correctness is brittle,
- no sponsor upside,
- demo quality remains weak.

Verdict:

Use only as fallback. Not enough for final demo polish.

### Option B — Kokoro-82M

Pros:

- only 82M parameters,
- Apache-2.0 licensed,
- Hugging Face-hosted and widely deployed,
- much more realistic than browser speech,
- small enough to add without any rule anxiety.

Cons:

- not a sponsor model,
- not the strongest path if the goal is specifically the MiniCPM prize,
- still better for preset voices than actor-style cloning.

Verdict:

Best overall TTS upgrade if the main goal is a better demo without destabilizing WitGym’s humor engine.

### Option C — Kyutai Pocket-TTS

Pros:

- 100M parameters,
- CPU-friendly,
- low latency,
- explicit support for voice cloning,
- can run in-browser/client-side according to the model card.

Cons:

- gated-access model card flow,
- voice cloning adds legal/product risk if pointed at Office actors,
- not a sponsor model,
- more operational complexity than Kokoro for a last-mile polish feature.

Verdict:

Interesting if voice cloning is essential, but not the cleanest hackathon choice. Better than browser speech, less obviously Pareto-optimal than Kokoro.

### Option D — Parler-TTS Mini v1

Pros:

- explicit natural-speech control via text descriptions,
- controllable gender, pitch, speed, and recording quality,
- Apache-2.0 licensed.

Cons:

- heavier integration shape than Kokoro,
- less direct fit for fast hackathon shipping,
- not a sponsor model.

Verdict:

Good controllability, but not the best fastest path.

### Option E — MiniCPM-o-2_6

Pros:

- qualifies for the OpenBMB sponsor prize,
- field guide explicitly says omni variants count,
- 8B total parameters,
- supports configurable voices, speech conversation, and voice cloning,
- creates a much stronger “voice/audio app” story than plain TTS garnish.

Cons:

- larger integration and product shift,
- its own published voice-cloning metrics trail specialized TTS systems like F5-TTS and CosyVoice,
- using it only as a playback step is probably too shallow to be the “core” of a MiniCPM prize submission.

Verdict:

Best sponsor-prize lever, but only if we reframe WitGym so MiniCPM is central to the interaction, not just a narrator.

## Recommendation

### Pareto-optimal recommendation

1. Immediately patch the current browser fallback so gender is correct.
2. Replace browser speech as the primary voice path with `Kokoro-82M`.
3. Keep `Qwen3.5-27B` as the humor engine unless we deliberately decide to chase the MiniCPM sponsor prize.

This yields:

- the best humor quality,
- a large improvement in perceived polish,
- low implementation risk,
- and continued eligibility for general-track prizes plus `Off Brand`, `Best Demo`, `Best Use of Codex`, and possibly `Bonus Quest Champion`.

### If we want the MiniCPM prize specifically

Use `MiniCPM-o-2_6` as a core model, not a sidecar:

- add voice-first interaction,
- let the user talk to the coach,
- and show that MiniCPM handles real speech I/O as part of the product concept.

Without that product shift, adding MiniCPM just for readout is probably too weak a sponsor story.

## Concrete Next Step

If we are optimizing for maximum expected hackathon return in the remaining time:

- do **not** pursue actor-voice cloning,
- do **not** replace Qwen for text generation right now,
- do implement `Kokoro-82M` as primary TTS,
- and keep the browser voice as a fallback with explicit male/female filtering.

That is the strongest quality-per-risk move.
