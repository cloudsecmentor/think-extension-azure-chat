# pip install azure-ai-projects==1.0.0b10
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
import sys

project_client = AIProjectClient.from_connection_string(
    credential=DefaultAzureCredential(),
    conn_str="swedencentral.api.azureml.ms;7a483184-4ad6-4b16-924f-e3ba0869823e;rg-aifoundry-poc;ai-foundry-poc05-project01")

agent = project_client.agents.get_agent("asst_EzkLTzkGBvT8vO7Fm0eoqW8G")

thread = project_client.agents.create_thread()
print(f"Thread created: {thread.id}")

message = project_client.agents.create_message(
    thread_id=thread.id,
    role="user",
    # content="Hi Web_Search_Agent"
    # get content from the script argument
    content=sys.argv[1]
)

run = project_client.agents.create_and_process_run(
    thread_id=thread.id,
    agent_id=agent.id)
messages = project_client.agents.list_messages(thread_id=thread.id)

# close the thread
project_client.agents.delete_thread(thread_id=thread.id)
print(f"Thread deleted: {thread.id}")

for text_message in messages.text_messages:
    print(text_message.as_dict())