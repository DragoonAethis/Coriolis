#!/usr/bin/bash
cd /render || exit 1

if [[ "$TICKET_WIDTH" == "" || "$TICKET_HEIGHT" == "" ]]; then
    echo "Ticket width/height not set."
    exit 1
fi

cp -r /template/* .
python /usr/local/bin/coriolis-render.py

if [[ -f "render.png" ]]; then
    if [[ "$OPTIMIZE_PNGQUANT" == "1" ]]; then
        pngquant --force --skip-if-larger --output "render-sm.png" "render.png"
    fi

    if [[ -f "render-sm.png" ]]; then
        mv "render-sm.png" "render.png"
    fi
fi
