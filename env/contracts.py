"""SI units; xyzw quaternions; positions relative to each environment origin."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from torch import Tensor


@dataclass
class Command:
    """Held for one control step. Joint ordering is explicit or the metadata ordering.

    Wrenches act at each selected body's COM, expressed in world axes.
    Position/velocity/effort are absolute physical commands, never normalized policy actions.
    """

    joint_position: "Tensor | None" = None
    joint_velocity: "Tensor | None" = None
    joint_effort: "Tensor | None" = None
    joints: tuple[str, ...] | None = None
    force: "Tensor | None" = None
    torque: "Tensor | None" = None
    bodies: tuple[str, ...] | None = None


@dataclass
class ResetState:
    root: "Tensor | None" = None  # [selected_envs, 13]: p, xyzw, linear velocity, angular velocity
    joint_position: "Tensor | None" = None
    joint_velocity: "Tensor | None" = None
    joints: tuple[str, ...] | None = None


class PhysicsScene(Protocol):
    """No reward, episode, policy, dataset or implicit autoreset belongs here."""

    def step(self, commands: dict[str, Command]) -> dict: ...
    def reset(self, states: dict[str, ResetState] | None = None, *, env_ids=None) -> dict: ...
    def state(self) -> dict: ...
    def describe(self) -> dict: ...
    def render(self, *, settle_frames: int = 0): ...
    def present(self) -> None: ...
    def close(self) -> None: ...
