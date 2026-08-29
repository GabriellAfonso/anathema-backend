FROM python:3.14.5-alpine3.22
LABEL maintainer="gabriellafonso.dev@gmail.com"

ENV PYTHONDONTWRITEBYTECODE 1

ENV PYTHONUNBUFFERED 1

COPY server /server

WORKDIR /server

RUN chmod -R a+rw /server

EXPOSE 8000

RUN python -m venv /venv && \
    /venv/bin/pip install --upgrade pip && \
    /venv/bin/pip install -r /server/requirements.txt && \
    adduser --disabled-password --no-create-home duser

ENV PATH="/venv/bin:${PATH}"

# Production default: the image runs prod unless something overrides it, so a
# forgotten override fails safe. Dev opts into --reload via compose command:.
# --lifespan off: Channels' ProtocolTypeRouter maps only http/websocket,
# so the lifespan scope raises ValueError. No startup hooks to run anyway.
CMD ["uvicorn", "core.asgi:application", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--lifespan", "off", "--workers", "4"]
