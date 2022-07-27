FROM python:3.9-slim-bullseye as fastapi-builder
WORKDIR /app
ENV POETRY_VIRTUALENVS_IN_PROJECT=true

RUN echo deb http://deb.debian.org/debian bullseye-backports main contrib non-free >> /etc/apt/sources.list
RUN apt-get update -y && apt-get install -y \
    build-essential \
    libffi-dev \
    cargo \
    openssl \
    curl \
    git \
    golang-go/bullseye-backports \
    golang-src/bullseye-backports \
    libssl-dev\
    cargo

RUN pip install poetry
COPY pyproject.toml poetry.lock /app/
RUN poetry install --no-dev --no-root
# No idea why but this supervisor dependency doesn't get installed
RUN poetry run pip install setuptools
COPY minica_api /app/minica_api
COPY supervisord.conf /app/


FROM python:3.9-slim-bullseye as runner
RUN apt-get update -y && apt-get install -y libgcc-s1
COPY --from=fastapi-builder /app /app
WORKDIR /app
EXPOSE 80

CMD [".venv/bin/supervisord", "-n", "-c", "supervisord.conf"]

LABEL org.opencontainers.image.source = "https://github.com/bjornsnoen/minica-api"
