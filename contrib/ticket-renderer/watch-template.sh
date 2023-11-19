#!/usr/bin/env bash

TEMPLATE_DIR="template-$1"

if [[ ! -d "$TEMPLATE_DIR" ]]; then
    echo "Usage: ./watch-template.sh EVENT"
    echo "The $TEMPLATE_DIR directory does not exist."
    exit 1
fi

echo "Watching for changes in $TEMPLATE_DIR"
inotifywait -e close_write,moved_to,create -m "$TEMPLATE_DIR" |
while read events; do
  ./build-image.sh $1 && ./test-render.sh $1 $2
done
