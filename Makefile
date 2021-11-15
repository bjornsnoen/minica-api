.PHONY: clean all prodvenv proper realclean

all: .venv proper

.venv: poetry.lock
	VIRTUALENVS_IN_PROJECT=1 poetry install --no-root

prodvenv: poetry.lock
	VIRTUALENVS_IN_PROJECT=1 poetry install --no-root --no-dev

proper: .venv
	.venv/bin/black minica_api
	.venv/bin/isort --profile=black minica_api

clean:
	rm -rf certificates dist

realclean: clean
	rm -rf .venv