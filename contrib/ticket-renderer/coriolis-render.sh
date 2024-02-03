#!/usr/bin/bash
cd /render || exit 1

if [[ "$TICKET_WIDTH" == "" || "$TICKET_HEIGHT" == "" ]]; then
    echo "Ticket width/height not set."
    exit 1
fi

cp -r /template/* .
python /usr/local/bin/coriolis-render.py
