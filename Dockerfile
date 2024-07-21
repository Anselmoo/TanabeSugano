# syntax=docker/dockerfile:1

FROM python:3.13.0b4-slim-bullseye

WORKDIR /app

COPY poetry.lock /app
COPY pyproject.toml /app


RUN pip3 install .

COPY . /app

CMD ["python3", "-m", "tanabesugano"]
