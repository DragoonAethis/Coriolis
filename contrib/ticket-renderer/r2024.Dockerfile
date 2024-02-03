FROM ubuntu:jammy

ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
ARG DEBIAN_FRONTEND=noninteractive
ARG TZ=Europe/Warsaw

RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y \
      python3 python-is-python3 python3-pip python3-distutils python3-jinja2 \
      fonts-noto-core fonts-noto-cjk fonts-noto-color-emoji \
      curl

RUN \
    # Playwright itself:
    pip install -U playwright && \
    # Browser binaries:
    playwright install --with-deps chromium && \
    # Workaround for https://github.com/microsoft/playwright/issues/27313
    # While the gstreamer plugin load process can be in-process, it ended up throwing
    # an error that it can't have libsoup2 and libsoup3 in the same process because
    # libgstwebrtc is linked against libsoup2. So we just remove the plugin.
    rm /usr/lib/x86_64-linux-gnu/gstreamer-1.0/libgstwebrtc.so; \
    rm -rf /var/lib/apt/lists/* && \
    adduser --system --uid 1000 renderer && \
    mkdir /template

ADD coriolis-render.sh /usr/local/bin/coriolis-render.sh
ADD coriolis-render.py /usr/local/bin/coriolis-render.py
USER renderer

ENV TICKET_WIDTH=1084
ENV TICKET_HEIGHT=1588
ADD template-r2024 /template/

VOLUME /render
CMD ["/usr/local/bin/coriolis-render.sh"]
