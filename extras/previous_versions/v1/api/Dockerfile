# Minimal image with Python 3.11
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Create and set workdir
WORKDIR /api

# Install runtime dependencies
RUN pip install --no-cache-dir \
    fastapi \
    "uvicorn[standard]" \
    pydantic \
    python-dotenv \
    httpx

# Copy application code
COPY app/ ./app/

# Expose the FastAPI default port
EXPOSE 5000

# Start the server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "5000"]
