import json
import boto3
from botocore.config import Config
from tenacity import retry, stop_after_attempt, wait_exponential
from .config import settings

_cfg = Config(retries={'max_attempts': 5, 'mode': 'adaptive'}, connect_timeout=5, read_timeout=90)
bedrock = boto3.client('bedrock-runtime', region_name=settings.aws_region, config=_cfg)
s3 = boto3.client('s3', region_name=settings.aws_region, config=_cfg)

@retry(stop=stop_after_attempt(4), wait=wait_exponential(min=1, max=10))
def embed(text: str):
    if settings.embedding_provider.lower() != 'bedrock':
        raise RuntimeError('This POC keeps the existing Bedrock Titan embedding path. Set EMBEDDING_PROVIDER=bedrock.')
    body = {'inputText': text[:50000], 'dimensions': settings.embedding_dimensions, 'normalize': True}
    result = bedrock.invoke_model(modelId=settings.embedding_model_id, body=json.dumps(body), accept='application/json', contentType='application/json')
    return json.loads(result['body'].read())['embedding']

@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
def bedrock_generate(system_prompt: str, user_prompt: str):
    if not settings.llm_model_id:
        raise RuntimeError('LLM_MODEL_ID is required when LLM_PROVIDER=bedrock')
    result = bedrock.converse(modelId=settings.llm_model_id, system=[{'text': system_prompt}], messages=[{'role': 'user', 'content': [{'text': user_prompt}]}], inferenceConfig={'maxTokens': settings.hf_max_new_tokens, 'temperature': settings.hf_temperature, 'topP': 0.9})
    return result['output']['message']['content'][0]['text']
