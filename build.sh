#!/bin/sh

# Run a maubot build to package this plugin into a .mbc file for upload to a maubot server

image="dock.mau.dev/maubot/maubot"
cmd="mbc build"

if uname | grep -iwq darwin; then
    # Running on macOS.
    # Let's assume that the user has the Docker CE installed
    # which doesn't require a root password.
    echo ""
    echo "This build script is using Docker container runtime to run the build in an isolated environment."
    echo ""
    docker run --rm -it -v "$(pwd):/maubot-events" "${image}" ${cmd}

elif uname | grep -iq linux; then
    # Running on Linux.
    # there isn't a maubot aarch64 container (TODO: maybe fall back to using a python environment with maubot to run the build in this case)
    # Check whether podman is available, else fall back to docker
    # which requires root.

    if uname -m | grep -iwq aarch64; then
        echo "no maubot aarch64 container. Falling back to python (experimental/untested)"
        pip install asyncpg maubot maubot-fedora-messages mautrix pytz
        pip install -r requirements.txt
        python3 -m maubot.cli mbc build

    elif [ -f /usr/bin/podman ]; then
        echo ""
        echo "This build script is using Podman to run the build in an isolated environment."
        echo ""
        podman run --rm -it -v "$(pwd):/maubot-events:z" "${image}" ${cmd}

    elif [ -f /usr/bin/docker ]; then
        echo ""
        echo "This build script is using Docker to run the build in an isolated environment."
        echo ""

        if groups | grep -wq "docker"; then
            docker run --rm -it -v "$(pwd):/maubot-events:z" "${image}" ${cmd}
        else
            echo "You might be asked for your password."
            echo "You can avoid this by adding your user to the 'docker' group,"
            echo "but be aware of the security implications."
            echo "See https://docs.docker.com/install/linux/linux-postinstall/"
            echo ""
            sudo docker run --rm -it -v "$(pwd):/maubot-events:z" "${image}" ${cmd}
        fi
    else
        echo ""
        echo "Error: Container runtime haven't been found on your system. Fix it by:"
        echo "$ sudo dnf install podman"
        exit 1
    fi
fi