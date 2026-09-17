from functools import lru_cache

import torch

from .aws_clients import bedrock_generate
from .config import settings


@lru_cache(maxsize=1)
def _hf_components():
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
    )

    torch.set_num_threads(settings.hf_torch_threads)

    tokenizer = AutoTokenizer.from_pretrained(
        settings.hf_model_id,
        cache_dir=settings.hf_cache_dir,
        use_fast=True,
    )

    model = AutoModelForCausalLM.from_pretrained(
        settings.hf_model_id,
        cache_dir=settings.hf_cache_dir,
        torch_dtype=torch.float32,
        low_cpu_mem_usage=True,
    )

    model.eval()

    return tokenizer, model


def huggingface_generate(
    system_prompt,
    user_prompt,
):
    tokenizer, model = _hf_components()

    messages = [
        {
            "role": "system",
            "content": system_prompt,
        },
        {
            "role": "user",
            "content": user_prompt,
        },
    ]

    prompt = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
    )

    model_inputs = tokenizer(
        prompt,
        return_tensors="pt",
        truncation=True,
        max_length=12000,
    )

    generation_arguments = {
        "max_new_tokens": settings.hf_max_new_tokens,
        "do_sample": settings.hf_temperature > 0,
        "repetition_penalty": 1.05,
        "pad_token_id": tokenizer.eos_token_id,
        "eos_token_id": tokenizer.eos_token_id,
    }

    if settings.hf_temperature > 0:
        generation_arguments["temperature"] = (
            settings.hf_temperature
        )
        generation_arguments["top_p"] = 0.9

    with torch.inference_mode():
        output = model.generate(
            **model_inputs,
            **generation_arguments,
        )

    generated_tokens = output[
        0,
        model_inputs["input_ids"].shape[1]:,
    ]

    return tokenizer.decode(
        generated_tokens,
        skip_special_tokens=True,
    ).strip()


def generate(system_prompt, user_prompt):
    provider = settings.llm_provider.lower().strip()

    if provider == "none":
        return ""

    if provider == "bedrock":
        return bedrock_generate(
            system_prompt,
            user_prompt,
        )

    if provider == "huggingface":
        return huggingface_generate(
            system_prompt,
            user_prompt,
        )

    raise RuntimeError(
        f"Unsupported LLM_PROVIDER="
        f"{settings.llm_provider}"
    )
