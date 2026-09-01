"""Item routes, against the in-memory repository.

No Postgres and no sockets: the repository boundary is the seam, so these
cover request validation, status codes and serialisation without a container
anywhere in the loop.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import InMemoryItemRepository


@pytest.mark.asyncio
async def test_create_item_returns_201_and_the_stored_row(
    client: AsyncClient, repository: InMemoryItemRepository
) -> None:
    response = await client.post("/v1/items", json={"name": "widget"})

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "widget"
    assert uuid.UUID(body["id"])
    assert body["created_at"]
    assert [r.name for r in repository.records] == ["widget"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {},  # name is required
        {"name": ""},  # min_length=1
        {"name": "x" * 201},  # max_length=200
        {"name": "ok", "extra": "nope"},  # extra="forbid"
    ],
)
async def test_create_item_rejects_bad_payloads(
    client: AsyncClient, payload: dict[str, str]
) -> None:
    assert (await client.post("/v1/items", json=payload)).status_code == 422


@pytest.mark.asyncio
async def test_list_items_is_empty_before_anything_is_created(client: AsyncClient) -> None:
    response = await client.get("/v1/items")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_list_items_returns_newest_first(client: AsyncClient) -> None:
    for name in ("one", "two", "three"):
        assert (await client.post("/v1/items", json={"name": name})).status_code == 201

    response = await client.get("/v1/items")

    assert response.status_code == 200
    assert [item["name"] for item in response.json()] == ["three", "two", "one"]


@pytest.mark.asyncio
async def test_list_items_honours_limit(client: AsyncClient) -> None:
    for name in ("one", "two", "three"):
        await client.post("/v1/items", json={"name": name})

    response = await client.get("/v1/items", params={"limit": 2})

    assert response.status_code == 200
    assert len(response.json()) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("limit", [0, 201, "many"])
async def test_list_items_rejects_out_of_range_limit(client: AsyncClient, limit: int | str) -> None:
    assert (await client.get("/v1/items", params={"limit": limit})).status_code == 422


@pytest.mark.asyncio
async def test_get_item_returns_the_created_item(client: AsyncClient) -> None:
    created = (await client.post("/v1/items", json={"name": "widget"})).json()

    response = await client.get(f"/v1/items/{created['id']}")

    assert response.status_code == 200
    assert response.json() == created


@pytest.mark.asyncio
async def test_get_unknown_item_is_404(client: AsyncClient) -> None:
    response = await client.get(f"/v1/items/{uuid.uuid4()}")
    assert response.status_code == 404
    assert response.json()["detail"] == "item not found"


@pytest.mark.asyncio
async def test_get_item_with_a_malformed_id_is_422(client: AsyncClient) -> None:
    assert (await client.get("/v1/items/not-a-uuid")).status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "path"),
    [("GET", "/v1/items"), ("GET", "/v1/items/" + str(uuid.uuid4()))],
)
async def test_item_routes_degrade_to_503_without_a_database(
    bare_client: AsyncClient, method: str, path: str
) -> None:
    """No DATABASE_URL is a degraded process, not a broken one.

    The probes still pass; only the routes that genuinely need storage fail,
    and they fail with a status a load balancer understands rather than a 500.
    """
    response = await bare_client.request(method, path)
    assert response.status_code == 503
    assert "DATABASE_URL" in response.json()["detail"]


@pytest.mark.asyncio
async def test_create_item_is_503_without_a_database(bare_client: AsyncClient) -> None:
    response = await bare_client.post("/v1/items", json={"name": "widget"})
    assert response.status_code == 503
