FROM golang:bullseye as minica-builder

RUN go install github.com/jsha/minica@latest


FROM python:3.9-slim-bullseye as fastapi-builder
WORKDIR /app
ENV POETRY_VIRTUALENVS_IN_PROJECT=true

RUN apt-get update -y && apt-get install -y build-essential libffi-dev cargo openssl curl git
RUN pip install poetry
COPY pyproject.toml poetry.lock /app/
RUN poetry install --no-dev --no-root
COPY minica_api /app/minica_api
COPY supervisord.conf /app/


FROM python:3.9-slim-bullseye as runner
RUN apt-get update -y && apt-get install -y libgcc-s1
COPY --from=minica-builder /go/bin/minica /usr/bin/
COPY --from=fastapi-builder /app /app
WORKDIR /app
EXPOSE 80

CMD [".venv/bin/supervisord", "-n", "-c", "supervisord.conf"]