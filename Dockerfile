FROM python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements-docker.txt .
RUN pip install --no-cache-dir -r requirements-docker.txt
COPY src ./src
COPY scripts ./scripts
COPY tests ./tests
COPY config ./config
COPY .env.example .
CMD ["streamlit", "run", "src/app/Home.py", "--server.address=0.0.0.0", "--server.port=8501"]
