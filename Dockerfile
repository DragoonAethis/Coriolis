# syntax=docker/dockerfile:1.7-labs
FROM python:3.12-slim-bookworm
ARG APP_HOME=/app

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# These are here just to make collectstatic work.
# Replace these values with your own configuration.
ENV DATABASE_URL="sqlite://:memory:"
ENV REDIS_URL="redis://localhost:6379"

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    echo "Initial system configuration..." \
    && apt-get update \
    && apt-get dist-upgrade -y \
    && apt-get install -y curl gettext \
    && adduser --system --uid 1000 --group --shell /bin/bash --home ${APP_HOME} django \
    && pip install --upgrade pip \
    && pip install uv

USER django
WORKDIR ${APP_HOME}

# --- Dependencies ---

COPY --chown=django:django \
    pyproject.toml uv.lock \
    ${APP_HOME}

RUN --mount=type=cache,target=${APP_HOME}/.cache,uid=1000,gid=1000 \
  echo "Creating the virtualenv and installing Python dependencies..." \
  && uv sync

# --- Application ---

COPY --chown=django:django \
  --exclude=.private \
  --exclude=.venv \
  --exclude=media \
  --exclude=static \
  . ${APP_HOME}

RUN --mount=type=cache,target=${APP_HOME}/.cache \
  echo "Installing Coriolis and creating static files..." \
  && uv sync \
  && uv run manage.py collectstatic --noinput

ENTRYPOINT ["/bin/bash"]
