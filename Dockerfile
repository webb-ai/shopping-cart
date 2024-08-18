#################################
############ Builder ############

FROM python:3.11-slim as builder

RUN pip install --upgrade pip && pip install poetry==1.5.1

RUN apt-get update \
    && apt-get install --no-install-recommends -y \
    build-essential \
    libcurl4-openssl-dev \
    libssl-dev \
    libpq-dev

ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_VIRTUALENVS_CREATE=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache \
    VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

COPY pyproject.toml poetry.lock ./

RUN poetry install --without dev --no-root && rm -rf $POETRY_CACHE_DIR


#################################
############ Runtime ############

FROM python:3.11-slim as runtime

ENV VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

RUN apt-get update \
    && apt-get install --no-install-recommends -y \
    libcurl4-openssl-dev \
    libssl-dev \
    libpq-dev


WORKDIR /app
ENV PYTHONPATH=/app

COPY --from=builder ${VIRTUAL_ENV} ${VIRTUAL_ENV}

COPY webbai ./webbai

