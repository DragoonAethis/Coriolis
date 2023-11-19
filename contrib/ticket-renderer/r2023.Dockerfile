FROM archlinux:base

RUN pacman -Syu --noconfirm \
      chromium mesa vulkan-swrast \
      python python-jinja python-j2cli python-setuptools \
      noto-fonts noto-fonts-cjk noto-fonts-emoji \
    && rm /var/cache/pacman/pkg/* \
    && useradd -u 1000 --user-group renderer \
    && mkdir /template

USER renderer
ADD coriolis-render.sh /usr/local/bin/coriolis-render.sh

ENV TICKET_WIDTH=1008
ENV TICKET_HEIGHT=1512
ADD template-r2023 /template/

VOLUME /render
CMD ["/usr/local/bin/coriolis-render.sh"]
