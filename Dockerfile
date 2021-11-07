FROM golang:alpine as minica-builder

RUN go install github.com/jsha/minica@latest


FROM python:3.9-alpine as fastapi-builder
WORKDIR /app
ENV PIPENV_VENV_IN_PROJECT=1
COPY Pipfile Pipfile.lock /app/
RUN apk add build-base libffi libffi-dev \
    && pip install pipenv \
    && pipenv install
COPY minica-api /app/minica-api


FROM python:3.9-alpine as runner
COPY --from=minica-builder /go/bin/minica /usr/bin/
COPY --from=fastapi-builder /app /app
WORKDIR /app

CMD [".venv/bin/uvicorn", "minica-api.main:app", "--host", "0.0.0.0"]