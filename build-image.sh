#!/usr/bin/env bash

IMAGE_TAG="$(git rev-parse --short HEAD)"

aws ecr get-login-password --region us-west-2 | docker login --username AWS --password-stdin 096844793322.dkr.ecr.us-west-2.amazonaws.com
docker buildx build --platform linux/amd64,linux/arm64 -t 096844793322.dkr.ecr.us-west-2.amazonaws.com/shopping-cart:"$IMAGE_TAG" . --push
