# chatbot_flow.py
# Generates: chatbot_flow.png

from diagrams import Diagram, Cluster, Edge
from diagrams.generic.blank import Blank

with Diagram("Async Chatbot Flow (FastAPI + Polling)", show=False, filename="chatbot_flow", outformat="png"):
    # Client side
    with Cluster("Client"):
        client = Blank("User")
        submit = Blank("POST /think\n{ history, user_query }")
        poll1  = Blank("POST /think\n{ id }")
        poll2  = Blank("POST /think\n{ id }")
        poll3  = Blank("POST /think\n{ id }")

        client >> Edge(label="ask") >> submit

    # Server side
    with Cluster("FastAPI app"):
        endpoint = Blank("Endpoint: /think")
        with Cluster("Background Processing"):
            worker = Blank("Mock LLM Task\n(simulated delay)")
        with Cluster("Ephemeral Store"):
            store = Blank("Requests Map\n{id: status/result}")

    # Initial submission
    submit >> Edge(label="create job\nstore: {id: pending}") >> endpoint
    endpoint >> Edge(label="generate id") >> store
    store >> Edge(label='202 Accepted\n{ "id": "<uuid>" }') >> submit

    # Polling loop (not ready responses)
    submit >> Edge(label="wait X sec") >> poll1
    poll1 >> Edge(label="lookup(id)") >> endpoint
    endpoint >> Edge(label='if pending') >> store
    store >> Edge(label='200 OK\n{ "reply": "not ready" }', style="dashed") >> poll1

    poll1 >> Edge(label="wait X sec") >> poll2
    poll2 >> Edge(label="lookup(id)") >> endpoint
    endpoint >> Edge(label='if pending') >> store
    store >> Edge(label='200 OK\n{ "reply": "not ready" }', style="dashed") >> poll2

    # Completion
    # Background worker finishes and writes result
    worker >> Edge(label="finish & write\n{id: completed, result}") >> store

    poll2 >> Edge(label="wait X sec") >> poll3
    poll3 >> Edge(label="lookup(id)") >> endpoint
    endpoint >> Edge(label="if completed") >> store
    store >> Edge(label='200 OK\n{ "reply": "<final answer>" }') >> poll3
    store >> Edge(label="forget id\ncleanup") >> Blank("")

    # Concurrency hint (optional): multiple users / tasks
    with Cluster("Concurrent Requests (example)"):
        user2 = Blank("User B")
        submit2 = Blank("POST /think\n{ history, user_query }")
        user2 >> submit2
        submit2 >> Edge(label="new id") >> endpoint
        Blank("BG Task #2") >> store
