from functools import lru_cache
from .config import settings
from .aws_clients import bedrock_generate

@lru_cache(maxsize=1)
def _hf_pipeline():
    from transformers import pipeline
    device = -1 if settings.hf_device.lower() == 'cpu' else 0
    return pipeline('text-generation', model=settings.hf_model_id, tokenizer=settings.hf_model_id, device=device, model_kwargs={'low_cpu_mem_usage': True}, cache_dir=settings.hf_cache_dir)

def generate(system_prompt: str, user_prompt: str) -> str:
    provider = settings.llm_provider.lower().strip()
    if provider == 'none':
        return ''
    if provider == 'bedrock':
        return bedrock_generate(system_prompt, user_prompt)
    if provider != 'huggingface':
        raise RuntimeError(f'Unsupported LLM_PROVIDER={settings.llm_provider}')
    pipe = _hf_pipeline()
    messages = [{'role': 'system', 'content': system_prompt}, {'role': 'user', 'content': user_prompt}]
    output = pipe(messages, max_new_tokens=settings.hf_max_new_tokens, do_sample=settings.hf_temperature > 0, temperature=max(settings.hf_temperature, 0.01), return_full_text=False)
    generated = output[0]['generated_text']
    if isinstance(generated, list):
        return generated[-1].get('content', str(generated[-1]))
    return str(generated)
