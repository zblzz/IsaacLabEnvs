"""Small, pickle-free physical state traces for inspection, not training datasets."""

import json
from pathlib import Path

import numpy as np


class Video:
    """Stream RGB frames to MP4; sample at an integer number of control steps.

    Playback time follows simulation time, independently of rendering wall time.
    A None path is a no-op and does not import the optional video dependencies.
    """

    def __init__(self, path, *, control_dt: float, every: int = 2):
        if control_dt <= 0 or every < 1:
            raise ValueError("control_dt and every must be positive")
        self.path = Path(path) if path is not None else None
        self.every = every
        self.fps = 1 / (control_dt * every)
        self.frames = 0
        self.writer = None

    def __enter__(self):
        if self.path is not None:
            import imageio.v2 as iio

            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.writer = iio.get_writer(
                self.path, fps=self.fps, codec="libx264", pixelformat="yuv420p", macro_block_size=2
            )
        return self

    def capture(self, render, step: int):
        if self.writer is not None and step % self.every == 0:
            self.writer.append_data(render())
            self.frames += 1

    def close(self):
        if self.writer is not None:
            self.writer.close()
            self.writer = None

    def __exit__(self, *exc):
        self.close()


class Trace:
    def __init__(self, description):
        self.metadata = {"version": 1, "scene": description}
        self.frames = {}

    def append(self, state):
        for entity in self.metadata["scene"]["assets"]:
            for field in ("root", "joint_position", "joint_velocity"):
                if field in state[entity]:
                    value = state[entity][field].detach().cpu().numpy().copy()
                    self.frames.setdefault(f"{entity}/{field}", []).append(value)

    def save(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            path,
            metadata=json.dumps(self.metadata),
            **{key: np.stack(frames) for key, frames in self.frames.items()},
        )


def load_trace(path):
    with np.load(path, allow_pickle=False) as source:
        metadata = json.loads(str(source["metadata"]))
        if metadata["version"] != 1:
            raise ValueError("Unsupported state trace version")
        arrays = {key: source[key].copy() for key in source.files if key != "metadata"}
    return metadata["scene"], arrays
