# syntax=docker/dockerfile:1

FROM python:3.13.0b4-slim-bullseye

WORKDIR /app

# Copying the poetry files first to cache the dependencies installation
COPY poetry.lock pyproject.toml /app/

# Install poetry
RUN python -m pip install --upgrade pip \
	&& python -m pip install --no-cache-dir poetry

# Install dependencies using poetry
RUN python -m poetry config virtualenvs.create false \
	&& python -m poetry install --no-dev

# Copy the rest of the application code
COPY . /app

CMD ["python3", "-m", "tanabesugano"]
