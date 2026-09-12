FROM python:3.14.5-alpine3.22
LABEL maintainer="gabriellafonso.dev@gmail.com"

ENV PYTHONDONTWRITEBYTECODE 1

ENV PYTHONUNBUFFERED 1

# Ferramenta de desenvolvimento (pytest, mypy, black) fica fora da imagem por
# padrão: em produção é peso morto e superfície de ataque a troco de nada.
# O compose de dev liga com `INSTALL_DEV=true` para poder rodar teste e tipagem
# dentro do container.
ARG INSTALL_DEV=false

COPY server /server

WORKDIR /server

RUN chmod -R a+rw /server

EXPOSE 8000

RUN python -m venv /venv && \
    /venv/bin/pip install --upgrade pip && \
    /venv/bin/pip install -r /server/requirements.txt && \
    if [ "$INSTALL_DEV" = "true" ]; then \
        /venv/bin/pip install -r /server/requirements-dev.txt; \
    fi && \
    adduser --disabled-password --no-create-home duser

ENV PATH="/venv/bin:${PATH}"

# Production default: the image runs prod unless something overrides it, so a
# forgotten override fails safe. Dev opts into --reload via compose command:.
# --lifespan on: o ProtocolTypeRouter passou a mapear o escopo `lifespan`, e é
# ele que liga o relógio da vez (§15) em cada worker. Com `off`, uma partida
# parada nunca estoura.
CMD ["uvicorn", "core.asgi:application", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--lifespan", "on", "--workers", "4"]
