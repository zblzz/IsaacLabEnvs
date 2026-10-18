"""GPU integration checks for force units, world axes, snapshot ownership and partial reset."""

import json
from pathlib import Path

from isaaclab_envs import AssetCfg, Command, ResetState, SceneCfg, make_scene
from isaaclab_envs.runtime import Runtime


def main():
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("outputs/physics_contract.json"))
    args = parser.parse_args()
    cfg = SceneCfg(
        assets={
            "probe": AssetCfg(
                kind="rigid",
                mass=1,
                size=(0.2, 0.2, 0.2),
                gravity=False,
                position=(0, 0, 1),
                quaternion=(0, 0, 0.7071067811865475, 0.7071067811865475),
            )
        },
        num_envs=4,
        physics_dt=0.005,
        decimation=4,
    )
    with Runtime():
        import torch

        with make_scene(cfg) as scene:
            first = scene.state()
            spinning = first["probe"]["root"].clone()
            spinning[:, 10:] = torch.tensor([1.0, 2.0, 3.0], device=cfg.device)
            scene.reset({"probe": ResetState(root=spinning)})
            force = torch.zeros((4, 1, 3), device=cfg.device)
            force[..., 0] = 1
            for _ in range(20):
                state = scene.step({"probe": Command(force=force)})
            velocity = state["probe"]["root"][:, 7:10]
            expected = torch.tensor([0.4, 0, 0], device=cfg.device).expand_as(velocity)
            torch.testing.assert_close(velocity, expected, atol=0.005, rtol=0.01)
            assert not torch.allclose(state["probe"]["root"][:, 3:7], first["probe"]["root"][:, 3:7])
            torch.testing.assert_close(
                first["probe"]["root"][:, :3], torch.tensor([0.0, 0.0, 1.0], device=cfg.device).expand(4, 3)
            )
            ids = torch.tensor([0, 2], device=cfg.device)
            other = torch.tensor([1, 3], device=cfg.device)
            reset = scene.reset(env_ids=ids)
            torch.testing.assert_close(reset["probe"]["root"][ids], first["probe"]["root"][ids])
            torch.testing.assert_close(reset["probe"]["root"][other], state["probe"]["root"][other])
            next_state = scene.step({})
            torch.testing.assert_close(
                next_state["probe"]["root"][:, 7:10], reset["probe"]["root"][:, 7:10], atol=1e-5, rtol=1e-5
            )
            result = dict(
                world_force=True,
                physical_units=True,
                subset_reset=True,
                environment_coordinates=True,
                snapshot_ownership=True,
                wrench_cleared=True,
                measured_velocity=velocity.tolist(),
            )
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(result, indent=2) + "\n")
            print("PHYSICS_CONTRACT", json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
