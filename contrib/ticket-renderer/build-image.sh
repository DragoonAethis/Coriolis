#!/bin/sh

if [[ "$1" == "" ]]; then
    echo "Usage: ./build-image.sh RENDERER"
    exit 1
fi

docker build -t $1-renderer -f $1.Dockerfile .
