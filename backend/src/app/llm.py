import os
from abc import ABC, abstractmethod

class LLMInterface(ABC):
    @abstractmethod
    def generate(self, prompt: str, context: str) -> str:
        pass

class DummyLLM(LLMInterface):
    def generate(self, prompt: str, context: str) -> str:
        return f"This is a mocked response based on your query: '{prompt}'.\n\nMOCKED RESPONSE: Internal policy indicates we must focus on phase 1 MVP to proceed."

class AnthropicLLM(LLMInterface):
    def __init__(self):
        from anthropic import Anthropic
        api_key = os.environ.get("ANTHROPIC_API_KEY", "dummy_key")
        self.client = Anthropic(api_key=api_key)
        
    def generate(self, prompt: str, context: str) -> str:
        system_prompt = "You are a helpful assistant. Answer ONLY based on the provided context. If the context does not contain the answer, say so."
        full_prompt = f"Context:\n{context}\n\nQuestion:\n{prompt}"
        response = self.client.messages.create(
            model="claude-3-5-sonnet-20240620",
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": full_prompt}]
        )
        return response.content[0].text

def get_llm() -> LLMInterface:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key and api_key != "dummy_key":
        return AnthropicLLM()
    return DummyLLM()
