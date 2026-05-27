FROM python:3.14.5-alpine3.22
LABEL maintainer="gabriellafonso.dev@gmail.com"

ENV PYTHONDONTWRITEBYTECODE 1

ENV PYTHONUNBUFFERED 1

COPY server /server
COPY scripts /scripts

WORKDIR /server

RUN chmod +x /scripts/commands.sh && \
    chmod -R a+rw /server

EXPOSE 8000

RUN python -m venv /venv && \
    /venv/bin/pip install --upgrade pip && \
    /venv/bin/pip install -r /server/requirements.txt && \
    adduser --disabled-password --no-create-home duser

ENV PATH="/scripts:/venv/bin:${PATH}"

CMD ["commands.sh"]