.PHONY: clean all prodvenv proper run realclean

all: lib/minica .venv proper

lib/minica:
	$(MAKE) -C lib minica

.venv: poetry.lock
	VIRTUALENVS_IN_PROJECT=1 poetry install --no-root

prodvenv: lib/minica poetry.lock
	VIRTUALENVS_IN_PROJECT=1 poetry install --no-root --no-dev

proper: .venv
	.venv/bin/black minica_api
	.venv/bin/isort --profile=black minica_api

clean:
	$(MAKE) -C lib clean
	rm -rf certificates

realclean: clean
	rm -rf .venv