import os
import sys
from utils.env import read_inputs, validate_inputs
from datetime import datetime
import time
from azure.cosmos import exceptions
from dotenv import load_dotenv, find_dotenv

from utils.cosmos import upsert_chat_history


load_dotenv(find_dotenv())



def main():
    try:
        inputs = read_inputs()
        validate_inputs(inputs)

        content = f"this is original text {datetime.now().isoformat()}: \n\n{inputs.content}"
        status, new_id = upsert_chat_history(
            content=content,
            thread_id=inputs.thread,
            user_id=inputs.user,
            item_id=inputs.id,
        )
        print({"status": status, "id": new_id, "threadId": inputs.thread})

        time.sleep(10)
        content = f"this is text for chain of thought {datetime.now().isoformat()}: bla-bla-bla"
        status, new_id = upsert_chat_history(
            content=content,
            thread_id=inputs.thread,
            user_id=inputs.user,
            role_type="function",
            name="think_extension_chain_of_thought",
        )
        print({"status": status, "id": new_id, "threadId": inputs.thread})

        time.sleep(10)
        content = f"this is additional text for chain of thought {datetime.now().isoformat()}: bla-bla-bla"
        status, new_id = upsert_chat_history(
            content=content,
            thread_id=inputs.thread,
            user_id=inputs.user,
            item_id=new_id,
            role_type="function",
            name="think_extension_chain_of_thought",
        )
        print({"status": status, "id": new_id, "threadId": inputs.thread})

        time.sleep(10)
        content = f"this is final result of the think extension {datetime.now().isoformat()}: bla-bla-bla"
        status, new_id = upsert_chat_history(
            content=content,
            thread_id=inputs.thread,
            user_id=inputs.user,
            role_type="assistant",
            name="think_extension_final_result",
        )
        print({"status": status, "id": new_id, "threadId": inputs.thread})


    except exceptions.CosmosHttpResponseError as e:
        print({"error": str(e), "status_code": getattr(e, "status_code", 500)})
        sys.exit(1)
    except Exception as e:
        print({"error": str(e)})
        sys.exit(1)


if __name__ == "__main__":
    main()


