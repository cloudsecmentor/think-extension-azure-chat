# Minimal image with Python 3.11
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Create and set workdir
WORKDIR /agent

# Install runtime dependencies
RUN pip install --no-cache-dir \
    fastapi \
    "uvicorn[standard]" \
    pydantic \
    langchain-openai \
    langchain-core \
    azure-identity \
    python-dotenv \
    httpx \
    mcp

# Copy application code
COPY app/ ./app/

# Expose the Agent port
EXPOSE 5500

# Start the server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "5500"]


