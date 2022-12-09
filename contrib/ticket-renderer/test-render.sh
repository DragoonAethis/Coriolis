#!/usr/bin/bash

docker run --interactive --tty --rm \
    --pull never \
    -v "$(pwd)/test":/render \
    -w /render \
    --network none \
    --user 1000:1000 \
    --security-opt "no-new-privileges:true" \
    r2023-renderer:latest

if [[ -f "test/render.png" ]]; then
    echo "File found: $(file test/render.png)"
else
    echo "File not found."
    exit 1
fi
