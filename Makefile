IMAGE_NAME    := hal-mcp
CONTAINER_NAME := hal-mcp
PORT          := 8000
VENV          := venv

# Fuseau horaire de l'hôte, avec repli sur Europe/Paris si indétectable.
HOST_TZ := $(shell cat /etc/timezone 2>/dev/null \
	|| (readlink -f /etc/localtime 2>/dev/null | sed -E 's#.*/zoneinfo/##') \
	|| echo Europe/Paris)
TZ ?= $(HOST_TZ)

.PHONY: help build up down restart logs enter test

help: ## Affiche cette aide
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

$(VENV)/bin/pytest: requirements-dev.txt requirements.txt
	python3 -m venv $(VENV)
	$(VENV)/bin/pip install -q --upgrade pip
	$(VENV)/bin/pip install -q -r requirements-dev.txt

test: $(VENV)/bin/pytest ## Crée un venv local (si besoin), installe les dépendances de test et lance pytest
	$(VENV)/bin/pytest

build: ## make build TZ=Europe/Paris — construit l'image Docker (fuseau de l'hôte par défaut)
	docker build -f docker/Dockerfile --build-arg TZ=$(TZ) -t $(IMAGE_NAME) .

up: ## Démarre le conteneur en arrière-plan (port $(PORT))
	docker run -d --name $(CONTAINER_NAME) -p $(PORT):8000 $(IMAGE_NAME)

down: ## Arrête et supprime le conteneur
	docker rm -f $(CONTAINER_NAME)

restart: down up ## Redémarre le conteneur (down puis up)

logs: ## Affiche les logs du conteneur en continu
	docker logs -f $(CONTAINER_NAME)

enter: ## Ouvre un shell dans le conteneur
	docker exec -it $(CONTAINER_NAME) /bin/bash
