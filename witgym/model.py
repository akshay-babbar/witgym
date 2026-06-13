"""Model loading and ClichePenaltyProcessor."""
import re
import time
import torch
import gc
from threading import Thread
from typing import Iterator
import httpx
import httpcore
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    LogitsProcessor,
    LogitsProcessorList,
    TextIteratorStreamer,
)
from loguru import logger
from witgym import config


_model = None
_tokenizer = None
_inference_clients: dict[str, object] = {}


def _is_transport_error(exc: BaseException) -> bool:
    if isinstance(exc, (httpx.RemoteProtocolError, httpx.ConnectError, httpcore.RemoteProtocolError)):
        return True
    cause = getattr(exc, "__cause__", None)
    return cause is not None and _is_transport_error(cause)


def _is_extra_body_rejection(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return 400 <= exc.response.status_code < 500
    msg = str(exc).lower()
    return "extra_body" in msg or "chat_template_kwargs" in msg or "enable_thinking" in msg


def _reset_inference_client(provider: str) -> None:
    _inference_clients.pop(provider, None)


def _get_inference_client(provider: str):
    if provider not in _inference_clients:
        from huggingface_hub import InferenceClient

        _inference_clients[provider] = InferenceClient(
            model=config.LLM_MODEL_ID,
            token=config.HF_TOKEN or None,
            provider=provider,
            timeout=config.HF_API_TIMEOUT,
        )
    return _inference_clients[provider]


def load_model():
    """Load local weights + tokenizer, or (None, None) when LLM_BACKEND=hf_api."""
    global _model, _tokenizer

    if config.LLM_BACKEND == "hf_api":
        providers = ",".join(config.HF_INFERENCE_PROVIDERS)
        logger.info(
            f"HF API backend ({providers}) — "
            f"remote inference for {config.LLM_MODEL_ID}, no local weights or tokenizer"
        )
        return None, None

    if _model is not None and _tokenizer is not None:
        return _model, _tokenizer

    logger.info(f"Loading tokenizer for {config.LLM_MODEL_ID}")
    _tokenizer = AutoTokenizer.from_pretrained(
        config.LLM_MODEL_ID,
        token=config.HF_TOKEN,
        trust_remote_code=True,
    )

    logger.info(f"Loading model {config.LLM_MODEL_ID} on {config.DEVICE} ({config.DTYPE})")
    _model = AutoModelForCausalLM.from_pretrained(
        config.LLM_MODEL_ID,
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
    """Strip thinking blocks from model output (defence-in-depth)."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    text = re.sub(r"Thinking Process:.*?(?=\{|\Z)", "", text, flags=re.DOTALL)
    text = re.sub(
        r"Here'?s a thinking process:.*?(?=\n\n|\Z)",
        "",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if " \n\n" in text:
        text = text.split(" \n\n")[-1]
    return text.strip()


def _hf_api_user_content(prompt: str, config_type: str = "generate") -> str:
    """Disable Qwen thinking mode when provider rejects chat_template_kwargs."""
    prefix = ""
    if config_type in ("extract", "rank"):
        prefix = "You are a JSON extractor. No reasoning. Output JSON only.\n"
    if "Qwen3.5" in config.LLM_MODEL_ID or "Qwen3.6" in config.LLM_MODEL_ID:
        stripped = prompt.lstrip()
        if not stripped.startswith("/no_think"):
            prompt = f"/no_think\n{prompt}"
    return prefix + prompt


def _extract_hf_message_text(message) -> str:
    """Read assistant text from HF chat response."""
    content = _strip_thinking((message.content or "").strip())
    if content and not content.lower().startswith("here's a thinking"):
        return content
    reasoning = _strip_thinking((getattr(message, "reasoning", None) or "").strip())
    if reasoning:
        return reasoning
    return content


def _hf_api_extra_body() -> dict:
    if "Qwen3.5" in config.LLM_MODEL_ID or "Qwen3.6" in config.LLM_MODEL_ID:
        return {"chat_template_kwargs": {"enable_thinking": False}}
    return {}


def _hf_api_messages(prompt: str, config_type: str) -> list:
    return [{"role": "user", "content": _hf_api_user_content(prompt, config_type)}]


def _hf_chat_completion(messages: list, config_type: str, *, stream: bool = False):
    """Try provider chain with transport retries and separate extra_body handling."""
    kwargs = _generation_kwargs(config_type)
    extra = _hf_api_extra_body()
    last_exc: BaseException | None = None

    for provider in config.HF_INFERENCE_PROVIDERS:
        for attempt in range(config.HF_API_MAX_RETRIES):
            client = _get_inference_client(provider)
            use_extra = bool(extra)
            try:
                if stream:
                    return client.chat_completion(
                        messages, stream=True, **kwargs, **({"extra_body": extra} if use_extra else {})
                    )
                return client.chat_completion(
                    messages, **kwargs, **({"extra_body": extra} if use_extra else {})
                )
            except Exception as e:
                last_exc = e
                if use_extra and _is_extra_body_rejection(e) and not _is_transport_error(e):
                    logger.warning(
                        f"HF API extra_body rejected by {provider} ({e}); retrying without thinking toggle"
                    )
                    try:
                        if stream:
                            return client.chat_completion(messages, stream=True, **kwargs)
                        return client.chat_completion(messages, **kwargs)
                    except Exception as e2:
                        last_exc = e2
                        e = e2

                if _is_transport_error(e):
                    _reset_inference_client(provider)
                    backoff = 0.5 * (2 ** attempt)
                    logger.warning(
                        f"HF API transport error ({provider}, attempt {attempt + 1}): {e}; "
                        f"retry in {backoff:.1f}s"
                    )
                    time.sleep(backoff)
                    continue

                logger.warning(f"HF API error ({provider}): {e}; trying next provider")
                break

    if last_exc is not None:
        raise last_exc
    raise RuntimeError("HF API chat_completion failed with no providers configured")


def is_hf_transport_error(exc: BaseException) -> bool:
    """Public helper for graceful degradation at pipeline boundaries."""
    return _is_transport_error(exc)


def _generate_via_hf_api(prompt: str, config_type: str) -> str:
    """Route generation through Hugging Face Inference Providers."""
    messages = _hf_api_messages(prompt, config_type)
    output = _hf_chat_completion(messages, config_type, stream=False)
    raw = _extract_hf_message_text(output.choices[0].message)
    if not raw:
        logger.warning(f"HF API returned empty text (config_type={config_type})")
    return raw


def _generation_kwargs(config_type: str) -> dict:
    if config_type == "extract":
        return {"max_tokens": config.EXTRACT_MAX_NEW_TOKENS, "temperature": 0.2}
    if config_type == "generate":
        return {
            "max_tokens": config.GENERATE_MAX_NEW_TOKENS,
            "temperature": config.GENERATE_TEMP,
            "top_p": 0.95,
        }
    if config_type == "rank":
        return {"max_tokens": 128, "temperature": 0.0}
    raise ValueError(f"Unknown config_type: {config_type}")


def _local_generation_kwargs(config_type: str) -> dict:
    if config_type == "extract":
        return dict(do_sample=False, max_new_tokens=config.EXTRACT_MAX_NEW_TOKENS)
    if config_type == "generate":
        return dict(
            temperature=config.GENERATE_TEMP,
            do_sample=True,
            min_p=config.GENERATE_MIN_P,
            max_new_tokens=config.GENERATE_MAX_NEW_TOKENS,
        )
    if config_type == "rank":
        return dict(do_sample=False, max_new_tokens=10)
    raise ValueError(f"Unknown config_type: {config_type}")


def _stream_hf_api_tokens(prompt: str, config_type: str) -> Iterator[str]:
    messages = _hf_api_messages(prompt, config_type)
    stream = _hf_chat_completion(messages, config_type, stream=True)
    for chunk in stream:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        content = getattr(delta, "content", None) if delta else None
        if content:
            yield content


def generate_text_stream(
    prompt: str,
    model,
    tokenizer,
    config_type: str = "generate",
    logits_processors: LogitsProcessorList = None,
) -> Iterator[str]:
    """Token stream for generate/compress paths. Extract/rank stay non-streaming."""
    if config_type not in ("generate", "extract"):
        raise ValueError(f"Streaming not supported for config_type={config_type}")

    if config.LLM_BACKEND == "hf_api":
        yield from _stream_hf_api_tokens(prompt, config_type)
        return

    messages = [{"role": "user", "content": prompt}]
    text = _apply_chat_template_no_think(tokenizer, messages)
    inputs = tokenizer(text, return_tensors="pt").to(config.DEVICE)
    gen_kwargs = _local_generation_kwargs(config_type)
    streamer = TextIteratorStreamer(tokenizer, skip_prompt=True, skip_special_tokens=True)

    def _run_generate():
        with torch.no_grad():
            model.generate(
                **inputs,
                streamer=streamer,
                logits_processor=logits_processors or LogitsProcessorList(),
                pad_token_id=tokenizer.eos_token_id,
                **gen_kwargs,
            )

    thread = Thread(target=_run_generate, daemon=True)
    thread.start()
    for token in streamer:
        if token:
            yield token
    thread.join()

    if config.DEVICE == "mps":
        torch.mps.empty_cache()
        gc.collect()


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
    if config.LLM_BACKEND == "hf_api":
        return _generate_via_hf_api(prompt, config_type)

    messages = [{"role": "user", "content": prompt}]
    text = _apply_chat_template_no_think(tokenizer, messages)
    inputs = tokenizer(text, return_tensors="pt").to(config.DEVICE)

    gen_kwargs = _local_generation_kwargs(config_type)

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
        gc.collect()

    new_tokens = output_ids[0][inputs["input_ids"].shape[-1]:]
    raw = tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
    return _strip_thinking(raw)
