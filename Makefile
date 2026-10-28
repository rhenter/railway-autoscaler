TWINE_REPOSITORY ?= pypi

.PHONY: clean clean-htmlcov clean-docs clean-eggs clean-build lint deps uv-dev test check docs build check-dist publish release

clean: clean-eggs clean-build clean-htmlcov clean-docs
	@find . -iname '*.pyc' -delete
	@find . -iname '*.pyo' -delete
	@find . -iname '*~' -delete
	@find . -iname '*.swp' -delete
	@find . -iname '__pycache__' -delete
	@rm -rf .coverage .pytest_cache

clean-htmlcov:
	@rm -fr htmlcov

clean-docs:
	@rm -fr docs/
	@rm -fr docs_src/build/
	@find docs_src/source/locale -name '*.mo' -delete 2>/dev/null || true

clean-eggs:
	@find . -name '*.egg' -print0 | xargs -0 rm -rf --
	@rm -rf .eggs/

clean-build:
	@rm -fr build/
	@rm -fr dist/
	@rm -fr *.egg-info

lint:
	uv run --extra dev pre-commit run -av

deps:
	uv sync --group dev

uv-dev: deps

test:
	uv run pytest

check:
	PYTHONPATH=test-django-project:. DJANGO_SETTINGS_MODULE=test_django_project.settings uv run --extra dev python -m django check

docs:
	@rm -fr docs/
	@mkdir -p docs/
	uv run --extra dev sphinx-build -b gettext docs_src/source docs_src/build/gettext
	uv run --extra dev sphinx-intl update -p docs_src/build/gettext -l pt_BR -d docs_src/source/locale
	uv run --extra dev sphinx-build -b html -d docs_src/build/doctrees/en docs_src/source docs/en
	uv run --extra dev sphinx-build -b html -d docs_src/build/doctrees/pt-br -D language=pt_BR docs_src/source docs/pt-br
	@find docs_src/source/locale -name '*.mo' -delete
	@cp docs_src/index.html docs/index.html
	@cp docs/en/.buildinfo docs/.buildinfo
	@touch docs/.nojekyll

build: clean
	uv build

check-dist: build
	twine check dist/*

publish: check-dist
	twine upload --repository $(TWINE_REPOSITORY) dist/*

release: check-dist
	git tag `uv run python setup.py -q version`
	git push origin `uv run python setup.py -q version`
	twine upload --repository $(TWINE_REPOSITORY) dist/*
