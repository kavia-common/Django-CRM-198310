FROM ubuntu:24.04

# invalidate cache
ARG APP_NAME

# test arg
RUN test -n "$APP_NAME"

# install system packages
RUN apt-get update -y
RUN apt-get install -y \
  python3-pip \
  python3-venv \
  build-essential \
  libpq-dev \
  libmariadbclient-dev \
  libjpeg62-dev \
  zlib1g-dev \
  libwebp-dev \
  curl \
  net-tools \
  postgresql-client

# setup user
RUN useradd -ms /bin/bash ubuntu
USER ubuntu

# install app
RUN mkdir -p /home/ubuntu/"$APP_NAME"/"$APP_NAME"
WORKDIR /home/ubuntu/"$APP_NAME"/"$APP_NAME"
COPY . .
RUN python3 -m venv ../venv
RUN . ../venv/bin/activate
RUN /home/ubuntu/"$APP_NAME"/venv/bin/pip install -U pip
RUN /home/ubuntu/"$APP_NAME"/venv/bin/pip install -r requirements.txt
RUN /home/ubuntu/"$APP_NAME"/venv/bin/pip install gunicorn

# setup path (kept for legacy compatibility)
ENV PATH="${PATH}:/home/ubuntu/$APP_NAME/$APP_NAME/scripts"

# New repo-local scripts live in backend/scripts. In container we will also mount/copy
# them under /app/backend/scripts via docker-compose or build context.
#
# Default working directory for runtime is repo root, but compose will override as needed.
WORKDIR /app

# Default entrypoint uses the repo-local backend/scripts/entrypoint.sh; compose can override.
ENTRYPOINT ["/bin/sh", "/app/backend/scripts/entrypoint.sh"]

USER ubuntu
