FROM debian:bookworm-slim

# Bookworm, not Alpine. BusyBox find, sed, and du are a third syntax.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        coreutils \
        findutils \
        grep \
        gawk \
        sed \
        tar \
        gzip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /work
