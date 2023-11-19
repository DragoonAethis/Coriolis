#!/usr/bin/bash

TEST_INPUT_DIR="test-input"
TEST_OUTPUT_DIR="test-output"
RENDER_OUTPUT="$TEST_OUTPUT_DIR/render.png"

if [[ "$1" == "" ]]; then
    echo "Usage: ./test-render.sh RENDERER [RENDER_JOB]"
    echo "RENDER_JOB can be a .json file to copy as render.json"
    exit 1
fi

mkdir -p "$TEST_OUTPUT_DIR"
cp -r "$TEST_INPUT_DIR/"* "$TEST_OUTPUT_DIR"

if [[ "$2" != "" ]]; then
    cp -f "$2" "$TEST_OUTPUT_DIR/render.json" || exit 1
fi

docker run --interactive --tty --rm \
    --pull never \
    -v "$(pwd)/$TEST_OUTPUT_DIR":/render \
    -w /render \
    --network none \
    --user 1000:1000 \
    --security-opt "no-new-privileges:true" \
    $1-renderer:latest

if [[ -f "$RENDER_OUTPUT" ]]; then
    echo "File found: $(file $RENDER_OUTPUT)"
else
    echo "Output file $RENDER_OUTPUT not found."
    exit 1
fi
