# syntax=docker/dockerfile:1

FROM python:3.11-slim

WORKDIR /app

COPY uv.lock /app
COPY pyproject.toml /app


RUN pip3 install --no-cache-dir uv &&\
    uv sync

COPY . /app

CMD ["uv", "run", "python", "-m", "tanabesugano"]
