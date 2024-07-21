# syntax=docker/dockerfile:1

FROM python:3.13.0b4-slim-bullseye

WORKDIR /app

# Copying the poetry files first to cache the dependencies installation
COPY poetry.lock pyproject.toml /app/

# Install poetry
RUN pip install poetry

# Install dependencies using poetry
RUN poetry config virtualenvs.create false \
	&& poetry install --no-dev

# Copy the rest of the application code
COPY . /app

CMD ["python3", "-m", "tanabesugano"]
