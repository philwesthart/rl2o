docker run \
    --rm \
    -it \
    --network host \
    --cap-add NET_ADMIN \
    -v $(pwd):/app \
    -e DISPLAY=$DISPLAY \
    -v /tmp/.X11-unix:/tmp/.X11-unix:ro \
    rl2o
