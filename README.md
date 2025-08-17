# think-extension-azure-chat  
Thinking extension service for [AzureChat](https://github.com/microsoft/azurechat)  

This repository presents the **Think Extension**, a service developed to enhance AzureChat by enabling asynchronous processing for complex, long-running AI tasks. Instead of modifying AzureChat itself, the Think Extension leverages its function-calling mechanisms to execute tasks asynchronously and return results once complete.  

---

## 📖 Overview: Extending AzureChat’s Capabilities  
[AzureChat](https://github.com/microsoft/azurechat) is an accelerator for building enterprise AI applications, making it possible to deploy a fully functional corporate chatbot in under an hour. It provides enterprise-grade security, authentication, secret management, built-in user roles, Retrieval-Augmented Generation (RAG), accessibility features, and seamless tool integration.  

While AzureChat is powerful, it primarily supports **synchronous chat**. Many enterprise AI tasks—such as deep research—require **long-running, asynchronous operations**, which this Think Extension provides.  

---

## ⚙️ How the Think Extension Works  

The Think Extension operates as an **external service**, integrating with AzureChat via external function calls.  

1. **Asynchronous Request Handling**  
   - AzureChat forwards a complex query to the Think Extension.  
   - The Think Extension returns an immediate ID (`HTTP 202 Accepted`) acknowledging the request.  
   - AzureChat polls the service with the ID until the result is ready.  

2. **Service Structure**  
   - **API Container**: Handles incoming requests, returns IDs, forwards work to the Agent.  
   - **Agent Container**: Core intelligence. Interacts with Azure OpenAI Foundry and tools.  
   - **Tool Containers**: MCP servers for specific tasks (e.g., web search, document retrieval).  

3. **Agent–Tool Interaction**  
   - The Agent requests tools as needed, integrates their outputs, and feeds results back to the LLM.  
   - The LLM composes a final response.  

4. **Final Response Delivery**  
   - The complete answer is stored in the API container.  
   - AzureChat retrieves it by polling with the original ID.  

This separation keeps AzureChat clean while supporting scalability (e.g., multiple agents, external databases like Cosmos DB).  

---

## 🔍 LLM Behavior Observations  
- **GPT-4**: Reliably shows when it uses a tool and bases answers on its output.  
- **GPT-5**: Sometimes skips tool usage but formats responses *as if* the tool was invoked. While answers may be correct, logs reveal the tool wasn’t actually called.  

---

## 💻 FastAPI Asynchronous Chatbot Interface  

This repo includes a **FastAPI app** implementing an asynchronous, polling-based chatbot interface with a mocked LLM.  

- Submits a new query → returns a request ID immediately (`HTTP 202 Accepted`).  
- Processes in the background.  
- Poll the same endpoint with the ID to retrieve the final result.  
- If the ID is invalid or expired, returns `404 {"detail": "Invalid or expired ID"}`.  

### Run Locally  

```bash
cd deploy
docker compose -f compose.local.yml up --build
```

API available at: [http://localhost:5000](http://localhost:5000)  

## Architecture

### Darkboard
<img src="extras/docs/think-extension.jpg" alt="Think extension" width="600" />

### Flowchart

flowchart TD
  A[User in AzureChat<br/>(submits complex query)] --> B[Think Extension API<br/>(returns Request ID · HTTP 202)]
  B -->|forwards request| C[Agent Container<br/>(LLM orchestration)]
  C --> AOAI[(Azure OpenAI Foundry)]
  C --> D1[Tool Container: Web Search (MCP)]
  C --> D2[Tool Container: Doc Retrieval (MCP)]
  C --> D3[Tool Container: Other MCP Tool]
  D1 --> C
  D2 --> C
  D3 --> C
  C --> B2[Think Extension API<br/>(stores final result)]
  B2 -.-> X[(External DB e.g., Cosmos DB):::optional]
  A <-->|poll with Request ID| B2
  A -->|retrieves final answer| E[Result displayed in AzureChat]

  subgraph "Web App: Think Extension"
    direction TB
    B
    C
    D1
    D2
    D3
    B2
  end

  classDef optional stroke-dasharray: 5 5,stroke-width:1.5px;
