import requests

from bond.endpoints.models import BaseModelCard
from bond.providers.mistral.config import MistralConfig
from bond.util import http_retry_loop, resolve_api_key


class MistralModels:
    def __init__(self, config: MistralConfig):
        self.config = config
        self.headers = {"Authorization": f"Bearer {resolve_api_key(config.api_key)}"}

    def retrieve_model(self, id: str, max_retries: int = 3) -> BaseModelCard:
        response = http_retry_loop(
            lambda: requests.get(
                f"https://api.mistral.ai/v1/models/{id}", headers=self.headers
            ),
            max_retries,
        )
        return BaseModelCard.model_validate_json(response.text)

    def list_models(self, max_retries: int = 3) -> list[BaseModelCard]:
        response = http_retry_loop(
            lambda: requests.get(
                f"https://api.mistral.ai/v1/models", headers=self.headers
            ),
            max_retries,
        )
        data = response.json()
        assert data.get("object") == "list"
        return [BaseModelCard.model_validate(d) for d in data["data"]]
