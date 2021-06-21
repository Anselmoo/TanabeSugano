# syntax=docker/dockerfile:1

FROM python:3.8-slim-buster

WORKDIR /app

COPY setup.py .
COPY requirements.txt .
COPY README.md .

RUN pip3 install --no-cache-dir .

COPY . .

CMD ["python3", "-m", "tanabe"]