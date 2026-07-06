docker run \
    --rm \
    -it \
    --network host \
    --cap-add NET_ADMIN \
    --device=/dev/video0 \
    --device=/dev/video1 \
    -v $(pwd):/app \
    telemetry