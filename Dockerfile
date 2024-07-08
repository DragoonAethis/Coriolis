# syntax=docker/dockerfile:1.7-labs
FROM python:3.12-slim-bookworm
ARG APP_HOME=/app

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# These are here just to make collectstatic work.
# Replace these values with your own configuration.
ENV DATABASE_URL="sqlite://:memory:"
ENV REDIS_URL="redis://localhost:6379"

RUN echo "Initial system configuration..." \
    && adduser --system --uid 1000 --group --shell /bin/bash --home ${APP_HOME} django \
    && pip install --upgrade pip \
    && pip install poetry~=1.8.3

USER django
WORKDIR ${APP_HOME}

# --- Dependencies ---

COPY --chown=django:django \
    pyproject.toml poetry.lock \
    ${APP_HOME}

RUN --mount=type=cache,target=${APP_HOME}/.cache,uid=1000,gid=1000 \
  echo "Creating the virtualenv and installing Python dependencies..." \
  && poetry config virtualenvs.in-project true \
  && poetry install --no-root --no-directory

# --- Application ---

COPY --chown=django:django \
  --exclude=.private \
  --exclude=.venv \
  --exclude=media \
  --exclude=static \
  . ${APP_HOME}

RUN --mount=type=cache,target=${APP_HOME}/.cache \
  echo "Installing Coriolis and creating static files..." \
  && poetry install \
  && poetry run python manage.py collectstatic --noinput

ENTRYPOINT ["/bin/bash"]
