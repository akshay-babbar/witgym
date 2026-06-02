"""Model loading and ClichePenaltyProcessor."""
import re
import torch
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    LogitsProcessor,
    LogitsProcessorList,
)
from loguru import logger
from witgym import config


_model = None
_tokenizer = None


def load_model():
    """Load Qwen3.5-4B onto MPS with bfloat16. Cached after first call."""
    global _model, _tokenizer
    if _model is not None:
        return _model, _tokenizer

    logger.info(f"Loading model {config.MODEL_ID} on {config.DEVICE} ({config.DTYPE})")
    _tokenizer = AutoTokenizer.from_pretrained(
        config.MODEL_ID,
        token=config.HF_TOKEN,
        trust_remote_code=True,
    )
    _model = AutoModelForCausalLM.from_pretrained(
        config.MODEL_ID,
        dtype=config.DTYPE,
        device_map=None,          # Never device_map="auto" on MPS
        token=config.HF_TOKEN,
        trust_remote_code=True,
    )
    _model = _model.to(config.DEVICE)
    _model.eval()
    logger.info("Model loaded.")
    return _model, _tokenizer


def _apply_chat_template_no_think(tokenizer, messages: list) -> str:
    """Apply chat template with thinking disabled.

    Tries three strategies in order:
    1. enable_thinking=False as direct kwarg (Qwen3 transformers >=4.51)
    2. chat_template_kwargs={"enable_thinking": False}
    3. Prepend /no_think to message (always supported by Qwen3 chat template)
    """
    # Strategy 1: direct kwarg
    try:
        return tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=False,
        )
    except TypeError:
        pass

    # Strategy 2: chat_template_kwargs dict
    try:
        return tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
            chat_template_kwargs={"enable_thinking": False},
        )
    except (TypeError, Exception):
        pass

    # Strategy 3: /no_think prefix in the last user message (always works)
    patched = list(messages)
    patched[-1] = dict(patched[-1])
    patched[-1]["content"] = "/no_think\n" + patched[-1]["content"]
    return tokenizer.apply_chat_template(
        patched,
        tokenize=False,
        add_generation_prompt=True,
    )


def _strip_thinking(text: str) -> str:
    """Strip <think>...</think> blocks from model output (defence-in-depth)."""
    # Remove explicit think tags
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    # Remove "Thinking Process:" freeform blocks (Qwen3.5 fallback format)
    text = re.sub(r"Thinking Process:.*?(?=\{|\Z)", "", text, flags=re.DOTALL)
    return text.strip()


class ClichePenaltyProcessor(LogitsProcessor):
    """Soft penalty on the opening tokens of the obvious/boring response.

    We penalise (not hard-suppress) so the model is steered away without
    losing coherence.
    """

    def __init__(self, obvious_response: str, tokenizer):
        ids = tokenizer.encode(obvious_response, add_special_tokens=False)
        self.penalty_ids = set(ids[: config.CLICHE_PENALTY_TOKENS])
        self.penalty = config.CLICHE_LOGIT_PENALTY

    def __call__(self, input_ids: torch.LongTensor, scores: torch.FloatTensor) -> torch.FloatTensor:
        for token_id in self.penalty_ids:
            if token_id < scores.shape[-1]:
                scores[:, token_id] += self.penalty
        return scores


def generate_text(
    prompt: str,
    model,
    tokenizer,
    config_type: str = "extract",
    logits_processors: LogitsProcessorList = None,
) -> str:
    """Unified generation. config_type: 'extract' | 'generate' | 'rank'."""
    messages = [{"role": "user", "content": prompt}]
    text = _apply_chat_template_no_think(tokenizer, messages)
    inputs = tokenizer(text, return_tensors="pt").to(config.DEVICE)

    if config_type == "extract":
        # Greedy — temperature must NOT be set when do_sample=False
        gen_kwargs = dict(
            do_sample=False,
            max_new_tokens=config.EXTRACT_MAX_NEW_TOKENS,
        )
    elif config_type == "generate":
        gen_kwargs = dict(
            temperature=config.GENERATE_TEMP,
            do_sample=True,
            min_p=config.GENERATE_MIN_P,
            max_new_tokens=config.GENERATE_MAX_NEW_TOKENS,
        )
    elif config_type == "rank":
        gen_kwargs = dict(
            do_sample=False,
            max_new_tokens=10,
        )
    else:
        raise ValueError(f"Unknown config_type: {config_type}")

    with torch.no_grad():
        output_ids = model.generate(
            **inputs,
            logits_processor=logits_processors or LogitsProcessorList(),
            pad_token_id=tokenizer.eos_token_id,
            **gen_kwargs,
        )

    # Free KV cache + intermediate buffers from unified memory after each call
    if config.DEVICE == "mps":
        torch.mps.empty_cache()

    new_tokens = output_ids[0][inputs["input_ids"].shape[-1]:]
    raw = tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
    return _strip_thinking(raw)
