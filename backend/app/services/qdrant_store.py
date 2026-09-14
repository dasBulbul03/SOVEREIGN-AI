from typing import Any, cast

import httpx

from app.core.errors import AppError


class QdrantStore:
    def __init__(self, base_url: str, collection: str) -> None:
        self.base_url, self.collection = base_url.rstrip("/"), collection

    async def ensure_collection(self, dimensions: int) -> None:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(f"{self.base_url}/collections/{self.collection}")
            if response.status_code == 404:
                response = await client.put(
                    f"{self.base_url}/collections/{self.collection}",
                    json={"vectors": {"size": dimensions, "distance": "Cosine"}},
                )
            response.raise_for_status()

    async def upsert(self, points: list[dict[str, Any]]) -> None:
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.put(
                    f"{self.base_url}/collections/{self.collection}/points",
                    params={"wait": "true"},
                    json={"points": points},
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise AppError(
                "VECTOR_INDEX_FAILED", "The local vector index rejected the document.", 503, True
            ) from exc

    async def search(
        self, vector: list[float], kb_id: str, version: int, limit: int
    ) -> list[dict[str, Any]]:
        body = {
            "query": vector,
            "limit": limit,
            "with_payload": True,
            "filter": {
                "must": [
                    {"key": "knowledge_base_id", "match": {"value": kb_id}},
                    {"key": "index_version", "match": {"value": version}},
                ]
            },
        }
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{self.base_url}/collections/{self.collection}/points/query", json=body
                )
                response.raise_for_status()
                result = response.json().get("result", {})
                points = result.get("points", []) if isinstance(result, dict) else result
                return cast(list[dict[str, Any]], points)
        except httpx.HTTPError as exc:
            raise AppError(
                "VECTOR_SEARCH_FAILED", "The local vector index could not be searched.", 503, True
            ) from exc
