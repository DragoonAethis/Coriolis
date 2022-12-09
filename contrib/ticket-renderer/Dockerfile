FROM archlinux:base

RUN pacman -Syu --noconfirm chromium python python-jinja python-j2cli python-setuptools \
    && rm /var/cache/pacman/pkg/* \
    && useradd -u 1000 --user-group renderer \
    && mkdir /template

ADD template /template/
ADD coriolis-render.sh /usr/local/bin/coriolis-render.sh
USER renderer

VOLUME /render
CMD ["/usr/local/bin/coriolis-render.sh"]
