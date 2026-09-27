FROM python:3.13-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

ENV PIP_ROOT_USER_ACTION=ignore
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=config.settings

# nginx serves /static/ and /media/ in front of gunicorn (which binds
# internally to 127.0.0.1:8001). supervisord manages both processes.
# `netcat-openbsd` stays for entrypoint readiness checks.
RUN apt-get update -y \
    && apt-get install -y --no-install-recommends \
        curl \
        netcat-openbsd \
        nginx \
        supervisor \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && rm -f /etc/nginx/sites-enabled/default \
    && ln -sf /dev/stdout /var/log/nginx/access.log \
    && ln -sf /dev/stderr /var/log/nginx/error.log

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY docker/nginx.conf /etc/nginx/conf.d/app.conf
COPY docker/supervisord.conf /etc/supervisord.conf

COPY entrypoint.sh .
RUN chmod +x /app/entrypoint.sh

COPY . .

EXPOSE 8000

# Probe through nginx (8000) to confirm the full request path is serving.
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/api/openapi.json || exit 1

CMD ["/app/entrypoint.sh"]
