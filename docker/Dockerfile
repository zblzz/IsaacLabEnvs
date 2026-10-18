ARG BASE_IMAGE=nvcr.io/nvidia/isaac-lab:2.3.2
FROM ${BASE_IMAGE}
USER root
COPY docker/install_runtime.py /tmp/install_runtime.py
RUN /isaac-sim/python.sh /tmp/install_runtime.py && \
    /isaac-sim/python.sh -c "import trimesh, scipy, yaml, pytest, imageio, imageio_ffmpeg"
COPY docker/entrypoint.sh /usr/local/bin/scene-entrypoint
RUN chmod +x /usr/local/bin/scene-entrypoint
ENTRYPOINT ["/usr/local/bin/scene-entrypoint"]
