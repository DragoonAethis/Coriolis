#!/usr/bin/bash
cd /render || exit 1

if [[ "$TICKET_WIDTH" == "" || "$TICKET_HEIGHT" == "" ]]; then
    echo "Ticket width/height not set."
    exit 1
fi

cp /template/* .
j2 --undefined -o render.html render.html.j2 render.json

chromium \
    --headless \
    --enable-automation \
    --enable-logging=stderr \
    --log-level=0 \
    \
    --no-zygote \
    --no-sandbox \
    --disable-setuid-sandbox \
    --disable-dev-shm-usage \
    \
    --no-default-browser-check \
    --no-startup-window \
    \
    --in-process-gpu \
    --disable-gpu \
    --disable-gpu-rasterization \
    --disable-accelerated-video-decode \
    --disable-accelerated-video-encode \
    \
    --disable-domain-reliability \
    --disable-component-update \
    --disable-default-apps \
    --disable-notifications \
    --no-service-autorun \
    --disable-extensions \
    --disable-component-extensions-with-background-pages \
    \
    --password-store=basic \
    --use-mock-keychain \
    \
    --disable-breakpad \
    --metrics-recording-only \
    --disable-field-trial-config \
    \
    --disable-features=Vulkan \
    --disable-features=Translate \
    --disable-features=MediaRouter \
    --disable-features=OptimizationHints \
    --disable-features=InterestFeedContentSuggestions \
    --disable-features=CalculateNativeWinOcclusion \
    --disable-features=HeavyAdPrivacyMitigations \
    --disable-features=DialMediaRouteProvider \
    --disable-features=AutofillServerCommunication \
    --disable-features=CertificateTransparencyComponentUpdater \
    --disable-features=site-per-process \
    \
    --run-all-compositor-stages-before-draw \
    --disable-threaded-animation \
    --disable-threaded-scrolling \
    --disable-checker-imaging \
    --disable-software-rasterizer \
    --disable-hang-monitor \
    \
    --mute-audio \
    --disable-audio-input \
    --disable-audio-output \
    --disable-ipc-flooding-protection \
    --disable-background-networking \
    --disable-client-side-phishing-detection \
    --disable-background-timer-throttling \
    --disable-backgrounding-occluded-windows \
    --disable-renderer-backgrounding \
    --disable-accelerated-2d-canvas \
    --disable-partial-raster \
    --allow-running-insecure-content \
    \
    --virtual-time-budget=1000000 \
    --force-color-profile=srgb \
    --hide-scrollbars \
    \
    --screenshot="render.png" \
    --window-size=$TICKET_WIDTH,$TICKET_HEIGHT \
    "render.html"
