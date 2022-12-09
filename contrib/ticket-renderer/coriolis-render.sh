#!/usr/bin/bash
cd /render
cp /template/* .
j2 --undefined -o render.html render.html.j2 render.json

chromium \
    --headless \
    --no-sandbox \
    --disable-gpu \
    --disable-gpu-rasterization \
    --hide-scrollbars \
    --window-size=1008,1512 \
    --run-all-compositor-stages-before-draw \
    --disable-threaded-animation \
    --disable-threaded-scrolling \
    --disable-checker-imaging \
    --disable-software-rasterizer \
    --disable-dev-shm-usage \
    --virtual-time-budget=1000000 \
    --screenshot="render.png" \
    "render.html"
