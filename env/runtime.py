"""Isaac Sim application ownership, separate from physics and task lifecycles."""


class Runtime:
    def __init__(
        self,
        *,
        device="cuda:0",
        headless=True,
        cameras=False,
        rendering_mode="performance",
        cpu_threads=8,
        livestream=0,
    ):
        if livestream not in (0, 2):
            raise ValueError("Use livestream=0 (off) or 2 (private-network WebRTC)")
        self.options = dict(
            device=device,
            headless=headless,
            enable_cameras=cameras,
            livestream=livestream,
            rendering_mode=rendering_mode,
            kit_args=f"--/plugins/carb.tasking.plugin/threadCount={cpu_threads}",
        )

    def __enter__(self):
        from isaaclab.app import AppLauncher

        self.launcher = AppLauncher(**self.options)
        return self

    @property
    def app(self):
        return self.launcher.app

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is not None:
            import sys

            sys.excepthook(exc_type, exc_value, traceback)
            self.app.app.post_quit(1)
        self.app.close()
