import os
from datetime import datetime
from typing import Optional, Tuple
from uuid import uuid4

from azure.cosmos import CosmosClient, exceptions


def _get_container():
    uri = os.getenv("AZURE_COSMOSDB_URI")
    key = os.getenv("AZURE_COSMOSDB_KEY")
    db_name = os.getenv("AZURE_COSMOSDB_DB_NAME")
    container_name = os.getenv("AZURE_COSMOSDB_CONTAINER_NAME")

    missing = [
        name
        for name, value in [
            ("AZURE_COSMOSDB_URI", uri),
            ("AZURE_COSMOSDB_KEY", key),
            ("AZURE_COSMOSDB_DB_NAME", db_name),
            ("AZURE_COSMOSDB_CONTAINER_NAME", container_name),
        ]
        if not value
    ]
    if missing:
        raise RuntimeError(
            f"Missing required environment variables: {', '.join(missing)}"
        )

    client = CosmosClient(uri, credential=key)
    database = client.get_database_client(db_name)
    return database.get_container_client(container_name)


def upsert_chat_history(
    content: str,
    thread_id: str,
    user_id: str,
    item_id: Optional[str] = None,
    role_type: Optional[str] = "assistant",
    name: Optional[str] = "think_extension",
) -> Tuple[str, str]:
    """Create or update a chat message in Cosmos DB.

    Returns a tuple of (status, id).
    """
    container = _get_container()

    if item_id:
        try:
            existing = container.read_item(item=item_id, partition_key=user_id)
        except exceptions.CosmosResourceNotFoundError:
            raise RuntimeError(
                "Item not found for provided ID and USER_ID partition key"
            )

        existing_content = existing.get("content", "")
        separator = "" if not existing_content or existing_content.endswith("\n") else "\n"
        new_content = (
            f"{existing_content}{separator}{content}" if content else existing_content
        )

        existing["content"] = new_content
        existing["updatedAt"] = datetime.now().isoformat()

        updated = container.replace_item(item=existing["id"], body=existing)
        return "updated", updated.get("id")

    if not content:
        raise RuntimeError("CONTENT must be provided when creating a new item")

    item = {
        "id": str(uuid4()),
        "createdAt": datetime.now().isoformat(),
        "updatedAt": datetime.now().isoformat(),
        "isDeleted": False,
        "type": "CHAT_MESSAGE",
        "userId": user_id,
        "content": content,
        "name": name,
        "role": role_type,
        "threadId": thread_id,
    }

    print(item)
    created = container.upsert_item(body=item)
    return "created", created.get("id")


