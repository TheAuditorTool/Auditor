"""Async task service demonstrating async/await patterns."""
import asyncio
from typing import List, AsyncIterator


async def fetch_user_data(user_id: int) -> dict:
    """Async function to fetch user data from remote API.

    This should be extracted as an async function with await expressions.
    """
    # Simulate API call
    await asyncio.sleep(0.1)

    # Multiple await expressions
    response = await get_api_response(user_id)
    data = await parse_response(response)

    # Async context manager
    async with get_database_connection() as conn:
        # Async for loop (async generator consumption)
        async for record in fetch_related_records(conn, user_id):
            data['records'].append(record)

    return data


async def get_api_response(user_id: int) -> str:
    """Fetch raw API response."""
    await asyncio.sleep(0.05)
    return f"api_data_{user_id}"


async def parse_response(response: str) -> dict:
    """Parse API response."""
    await asyncio.sleep(0.02)
    return {"data": response, "records": []}


async def get_database_connection():
    """Async context manager for database connection."""
    # This is an async context manager usage
    class AsyncDBConnection:
        async def __aenter__(self):
            await asyncio.sleep(0.01)
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            await asyncio.sleep(0.01)

    return AsyncDBConnection()


async def fetch_related_records(conn, user_id: int) -> AsyncIterator[dict]:
    """Async generator yielding related records.

    This should be extracted as an async generator function.
    """
    for i in range(5):
        await asyncio.sleep(0.01)
        yield {"id": i, "user_id": user_id}


async def process_batch_users(user_ids: List[int]) -> List[dict]:
    """Process multiple users with async for loop.

    Demonstrates async for consumption.
    """
    results = []

    # Async for loop over async generator
    async for user_data in batch_fetch_users(user_ids):
        results.append(user_data)

    return results


async def batch_fetch_users(user_ids: List[int]) -> AsyncIterator[dict]:
    """Async generator for batch user fetching."""
    for user_id in user_ids:
        data = await fetch_user_data(user_id)
        yield data


async def parallel_fetch(user_ids: List[int]) -> List[dict]:
    """Fetch multiple users in parallel with asyncio.gather.

    Multiple await expressions in complex patterns.
    """
    # Create tasks
    tasks = [fetch_user_data(uid) for uid in user_ids]

    # Await gather
    results = await asyncio.gather(*tasks)

    return results
