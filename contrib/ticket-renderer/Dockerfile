FROM archlinux:base

RUN pacman -Syu --noconfirm \
      chromium mesa vulkan-swrast \
      python python-jinja python-j2cli python-setuptools \
      noto-fonts noto-fonts-cjk noto-fonts-emoji \
    && rm /var/cache/pacman/pkg/* \
    && useradd -u 1000 --user-group renderer \
    && mkdir /template

ADD template /template/
ADD coriolis-render.sh /usr/local/bin/coriolis-render.sh
USER renderer

VOLUME /render
CMD ["/usr/local/bin/coriolis-render.sh"]
