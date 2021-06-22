# syntax=docker/dockerfile:1

FROM python:3.8-slim-buster

WORKDIR /app

COPY poetry.lock /app
COPY pyproject.toml /app


RUN pip3 install --no-cache-dir poetry
RUN poetry config virtualenvs.create false
RUN poetry install --no-interaction

COPY . /app

CMD ["python3", "-m", "tanabesugano"]
