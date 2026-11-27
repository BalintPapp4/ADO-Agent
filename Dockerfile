FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY pyproject.toml ./
COPY ado_agent ./ado_agent

RUN mkdir -p /data

EXPOSE 8080

CMD ["python", "-m", "ado_agent", "--host", "0.0.0.0", "--port", "8080", "--data-dir", "/data", "--no-browser", "--auth"]
