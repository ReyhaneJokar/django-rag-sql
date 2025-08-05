import openai
from openai import OpenAI
from .config import MODEL_NAME, EMBED_MODEL, BASE_URL, API_KEY, TEMPERATURE, MAX_TOKENS

class OpenAIClient:
    def __init__(self):
        openai.api_base = BASE_URL
        openai.api_key  = API_KEY
        self.client     = OpenAI(base_url=BASE_URL, api_key=API_KEY)
        self.model      = MODEL_NAME
        self.embed_model  = EMBED_MODEL
        self.temperature = TEMPERATURE
        self.max_tokens  = MAX_TOKENS

    def generate(self, prompt: str) -> str:
        """
        endpoint /chat/completions
        """
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        return response.choices[0].message.content.strip()

    def embed_query(self, text: str) -> list[float]:
        """
        endpoint /embeddings
        """
        resp = self.client.embeddings.create(
            model=self.embed_model,
            input=[text]
        )
        if not resp.data:
            raise ValueError("No embedding data received (empty response)")
        return resp.data[0].embedding

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        # print("🔍 Embedding input texts:", texts)
        resp = self.client.embeddings.create(
            model=self.embed_model,
            input=texts
        )
        if not resp.data:
            raise ValueError("No embedding data received (empty response)")
        return [d.embedding for d in resp.data]

def load_llm(**kwargs) -> OpenAIClient:
    return OpenAIClient(**kwargs)

def load_embeddings() -> OpenAIClient:
    return OpenAIClient()