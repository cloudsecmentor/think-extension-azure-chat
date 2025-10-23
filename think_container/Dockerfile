FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install runtime dependencies
RUN pip install --no-cache-dir azure-cosmos python-dotenv

# Copy application code
COPY utils /app/utils
COPY main.py /app/main.py

# Default command
CMD ["python", "main.py"]


