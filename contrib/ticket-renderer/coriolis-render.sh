#!/usr/bin/bash
cd /render || exit 1

if [[ "$TICKET_WIDTH" == "" || "$TICKET_HEIGHT" == "" ]]; then
    echo "Ticket width/height not set."
    exit 1
fi

cp -r /template/* .
j2 --undefined -o render.html render.html.j2 render.json

chromium \
    --headless=old \
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
    --no-first-run \
    \
    --use-vulkan \
    --disable-vulkan-fallback-to-gl-for-testing \
    --disable-accelerated-video-decode \
    --disable-accelerated-video-encode \
    --disable-renderer-backgrounding \
    \
    --disable-webgl \
    --disable-domain-reliability \
    --disable-component-update \
    --disable-default-apps \
    --disable-notifications \
    --no-service-autorun \
    --disable-extensions \
    --disable-component-extensions-with-background-pages \
    \
    --enable-features=Vulkan,NetworkServiceInProcess2 \
    --disable-features=WebGPU,Translate,MediaRouter,OptimizationHints,AcceptCHFrame,InterestFeedContentSuggestions,CalculateNativeWinOcclusion,HeavyAdPrivacyMitigations,DialMediaRouteProvider,AutofillServerCommunication,CertificateTransparencyComponentUpdater,site-per-process \
    \
    --password-store=basic \
    --use-mock-keychain \
    \
    --disable-sync \
    --disable-breakpad \
    --metrics-recording-only \
    --disable-field-trial-config \
    \
    --run-all-compositor-stages-before-draw \
    --disable-new-content-rendering-timeout \
    --disable-threaded-animation \
    --disable-threaded-scrolling \
    --disable-checker-imaging \
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
    --disable-accelerated-2d-canvas \
    --allow-running-insecure-content \
    \
    --virtual-time-budget=10000 \
    --force-color-profile=srgb \
    --hide-scrollbars \
    \
    --screenshot="render.png" \
    --window-size=$TICKET_WIDTH,$TICKET_HEIGHT \
    "render.html"
