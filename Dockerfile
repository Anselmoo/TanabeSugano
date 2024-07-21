# syntax=docker/dockerfile:1

FROM python:3.13-slim

WORKDIR /app

COPY poetry.lock /app
COPY pyproject.toml /app


RUN pip3 install --no-cache-dir poetry &&\
    poetry config virtualenvs.create false &&\
    poetry install --no-interaction

COPY . /app

CMD ["python3", "-m", "tanabesugano"]
