from math import ceil

import wcwidth
from rich.console import Console, ConsoleOptions
from rich.text import Text


class ProgressBar:
    """
    A non-live, manually adjustable progress bar.
    """

    def __init__(self, total: int = 100):
        self.total = total
        self._progress = 0
        self._task: Text | None = None
        self._should_cancel = False

    def reset(self):
        self.total = 100
        self._progress = 0
        self._task = None
        self._should_cancel = False

    def increase_progress(self):
        self._progress = min(self._progress + 1, self.total)

    def set_progress(self, new_progress: int):
        if new_progress < 0:
            new_progress = 0
        elif new_progress > self.total:
            new_progress = self.total
        self._progress = new_progress

    def set_task(self, task: str | Text | None):
        if isinstance(task, str):
            self._task = Text(task, no_wrap=True, overflow="ellipsis")
        else:
            self._task = task

    def cancel(self):
        self._should_cancel = True

    def is_cancelled(self):
        return self._should_cancel

    def __rich_console__(self, console: Console, options: ConsoleOptions):
        if self._task is not None:
            yield self._task
        progress = self._progress / self.total
        progress_percentage = f"{int(ceil(progress * 100))}%"
        bar_width = options.max_width - wcwidth.width(progress_percentage) - 1
        bar_fill = ceil(bar_width * progress)
        yield console.render_str(
            f"[blue]{'━' * bar_fill}[/blue]{'━' * (bar_width - bar_fill)} [purple bold]{progress_percentage}[/purple bold]")
