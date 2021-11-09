FROM golang:alpine as minica-builder

RUN go install github.com/jsha/minica@latest


FROM python:3.9-alpine as fastapi-builder
WORKDIR /app
ENV POETRY_VIRTUALENVS_IN_PROJECT=true

COPY pyproject.toml poetry.lock /app/
RUN apk add build-base libffi libffi-dev rust cargo openssl openssl-dev
RUN pip install poetry
RUN poetry install --no-dev --no-root
COPY minica-api /app/minica-api


FROM python:3.9-alpine as runner
RUN apk add libgcc
COPY --from=minica-builder /go/bin/minica /usr/bin/
COPY --from=fastapi-builder /app /app
WORKDIR /app

CMD [".venv/bin/uvicorn", "minica-api.main:app", "--host", "0.0.0.0"]