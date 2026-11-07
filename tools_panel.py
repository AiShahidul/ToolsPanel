#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Desktop Tools Panel — start/stop launchers without opening a terminal each time."""

from __future__ import annotations

import os
import signal
import subprocess
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk, Gio  # noqa: E402

HOME = Path.home()
CACHE = HOME / ".cache" / "tools-panel"
CACHE.mkdir(parents=True, exist_ok=True)


def _first_existing(*candidates: Path) -> Path | None:
    for path in candidates:
        if path.is_file() or path.is_dir():
            return path
    return None


def _python_for(project: Path, *venv_names: str) -> Path:
    for name in venv_names:
        cand = project / name / "bin" / "python"
        if cand.is_file():
            return cand
    return Path("/usr/bin/python3")


PDF_ROOT = _first_existing(
    HOME / "MEGA/Google Drive (ivac AiShahidul)/Python _Forder_PDF_Edit",
) or (HOME / "MEGA/Google Drive (ivac AiShahidul)/Python _Forder_PDF_Edit")
PDF_UTIL = PDF_ROOT / "Z Utilities"
PDF_PY = _python_for(PDF_ROOT, ".venv-linux", ".venv")

IVAC = _first_existing(
    HOME / "GitHub Repository/IVAC-BOT-2.0",
    HOME / "Github All Repositories/IVAC-BOT-2.0",
) or (HOME / "GitHub Repository/IVAC-BOT-2.0")
SOLVER = IVAC / "main_py_bot/JS Solver 2.0"
SOLVER_PY = _python_for(IVAC, ".venv", ".venv-linux")

BROWSER_ARRANGE = _first_existing(
    HOME / "MEGA/IVAC Works/Browser arrange",
) or (HOME / "MEGA/IVAC Works/Browser arrange")

CSS = """
window {
  background: #1a1b1e;
}
.header {
  font-size: 15px;
  font-weight: 600;
  color: #e8eaed;
  margin: 4px 0 8px 0;
}
.row-name {
  font-size: 13px;
  color: #e8eaed;
  font-weight: 500;
}
.row-sub {
  font-size: 11px;
  color: #9aa0a6;
}
.btn-status {
  min-width: 108px;
  min-height: 34px;
  border-radius: 8px;
  font-weight: 600;
  border: none;
  color: #fff;
}
.btn-stopped {
  background: #c62828;
}
.btn-stopped:hover {
  background: #e53935;
}
.btn-running {
  background: #2e7d32;
}
.btn-running:hover {
  background: #43a047;
}
.btn-busy {
  background: #f9a825;
  color: #1a1b1e;
}
.btn-log {
  min-width: 64px;
  min-height: 34px;
}
.footer {
  font-size: 11px;
  color: #9aa0a6;
  margin-top: 8px;
}
.missing {
  opacity: 0.45;
}
"""


def _pgrep(match: str) -> list[int]:
    try:
        out = subprocess.check_output(
            ["pgrep", "-f", match],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError:
        return []
    pids: list[int] = []
    for line in out.splitlines():
        line = line.strip()
        if line.isdigit():
            pids.append(int(line))
    return pids


def _kill_match(match: str) -> None:
    subprocess.run(["pkill", "-f", match], check=False)
    GLib.timeout_add(
        400,
        lambda: subprocess.run(["pkill", "-9", "-f", match], check=False) or False,
    )


@dataclass
class Tool:
    id: str
    name: str
    subtitle: str
    kind: str  # daemon | oneshot
    match: str = ""
    start_cmd: list[str] = field(default_factory=list)
    cwd: Path | None = None
    env_extra: dict[str, str] = field(default_factory=dict)
    required: list[Path] = field(default_factory=list)

    def log_path(self) -> Path:
        return CACHE / f"{self.id}.log"

    def available(self) -> bool:
        if not self.start_cmd:
            return False
        # First token may be interpreter; check key scripts/paths
        for path in self.required:
            if not path.exists():
                return False
        return True

    def is_running(self) -> bool:
        if self.kind != "daemon" or not self.match:
            return False
        pids = _pgrep(self.match)
        self_pid = os.getpid()
        return any(p != self_pid for p in pids)

    def start(self) -> None:
        self.log_path().parent.mkdir(parents=True, exist_ok=True)
        log_f = open(self.log_path(), "ab", buffering=0)
        env = os.environ.copy()
        env["PATH"] = (
            f"{HOME}/.local/bin:{HOME}/.local/node/bin:" + env.get("PATH", "")
        )
        env.update(self.env_extra)
        if self.id == "solver" and not env.get("IVAC_NODE"):
            for cand in (
                HOME / ".local/node/bin/node",
                HOME / ".local/bin/node",
            ):
                if cand.is_file():
                    env["IVAC_NODE"] = str(cand)
                    break
        subprocess.Popen(
            self.start_cmd,
            cwd=str(self.cwd) if self.cwd else None,
            stdout=log_f,
            stderr=subprocess.STDOUT,
            env=env,
            start_new_session=True,
            close_fds=True,
        )

    def stop(self) -> None:
        if self.match:
            _kill_match(self.match)

    def run_oneshot(self, on_done: Callable[[int], None]) -> None:
        def worker() -> None:
            self.log_path().parent.mkdir(parents=True, exist_ok=True)
            with open(self.log_path(), "wb") as log_f:
                proc = subprocess.run(
                    self.start_cmd,
                    cwd=str(self.cwd) if self.cwd else None,
                    stdout=log_f,
                    stderr=subprocess.STDOUT,
                    env={**os.environ, **self.env_extra},
                    input=b"\n\n",
                )
            GLib.idle_add(on_done, proc.returncode)

        threading.Thread(target=worker, daemon=True).start()


def build_tools() -> list[Tool]:
    tools = [
        Tool(
            id="pdf_mapper",
            name="PDF Folder Mapper",
            subtitle="localhost:5057",
            kind="daemon",
            match="pdf_folder_mapper_web.py",
            start_cmd=[str(PDF_PY), str(PDF_UTIL / "pdf_folder_mapper_web.py")],
            cwd=PDF_UTIL,
            required=[PDF_UTIL / "pdf_folder_mapper_web.py"],
        ),
        Tool(
            id="pdf_upload",
            name="PDF Server Upload",
            subtitle="localhost:5058",
            kind="daemon",
            match="pdf_server_upload_web.py",
            start_cmd=[str(PDF_PY), str(PDF_UTIL / "pdf_server_upload_web.py")],
            cwd=PDF_UTIL,
            required=[PDF_UTIL / "pdf_server_upload_web.py"],
        ),
        Tool(
            id="folder_rename",
            name="Folder MAP Rename",
            subtitle="localhost:5059",
            kind="daemon",
            match="folder_map_rename_web.py",
            start_cmd=[str(PDF_PY), str(PDF_UTIL / "folder_map_rename_web.py")],
            cwd=PDF_UTIL,
            required=[PDF_UTIL / "folder_map_rename_web.py"],
        ),
        Tool(
            id="solver",
            name="IVAC Open Solver",
            subtitle="JS Solver 2.0 UI",
            kind="daemon",
            match=str(SOLVER / "ui.py"),
            start_cmd=[str(SOLVER_PY), str(SOLVER / "ui.py")],
            cwd=SOLVER,
            required=[SOLVER / "ui.py"],
        ),
        Tool(
            id="restart_bot",
            name="IVAC Restart Bot",
            subtitle="WebHost · one-shot",
            kind="oneshot",
            start_cmd=["bash", str(IVAC / "Restart_Bot.sh")],
            cwd=IVAC,
            required=[IVAC / "Restart_Bot.sh"],
        ),
        Tool(
            id="restart_panel",
            name="IVAC Restart Panel",
            subtitle="WebHost · one-shot",
            kind="oneshot",
            start_cmd=["bash", str(IVAC / "Restart_Panel.sh")],
            cwd=IVAC,
            required=[IVAC / "Restart_Panel.sh"],
        ),
        Tool(
            id="browser_arrange",
            name="Browser Auto Arrange",
            subtitle="Chrome×7 + Edge×7",
            kind="oneshot",
            start_cmd=["bash", str(BROWSER_ARRANGE / "Browser-Auto-Arrange.sh")],
            cwd=BROWSER_ARRANGE,
            required=[BROWSER_ARRANGE / "Browser-Auto-Arrange.sh"],
        ),
    ]
    return tools


TOOLS: list[Tool] = build_tools()


class ToolRow(Gtk.Box):
    def __init__(self, tool: Tool, open_log: Callable[[Tool], None]):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.tool = tool
        self._busy = False
        self.set_margin_top(4)
        self.set_margin_bottom(4)
        if not tool.available():
            self.add_css_class("missing")

        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        text.set_hexpand(True)
        name = Gtk.Label(label=tool.name, xalign=0)
        name.add_css_class("row-name")
        sub_label = tool.subtitle if tool.available() else f"{tool.subtitle} · missing"
        sub = Gtk.Label(label=sub_label, xalign=0)
        sub.add_css_class("row-sub")
        text.append(name)
        text.append(sub)
        self.append(text)

        self.btn = Gtk.Button()
        self.btn.add_css_class("btn-status")
        self.btn.connect("clicked", self._on_click)
        self.append(self.btn)

        log_btn = Gtk.Button(label="Log")
        log_btn.add_css_class("btn-log")
        log_btn.connect("clicked", lambda *_: open_log(tool))
        self.append(log_btn)

        self.refresh()

    def set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.refresh()

    def refresh(self) -> None:
        self.btn.remove_css_class("btn-stopped")
        self.btn.remove_css_class("btn-running")
        self.btn.remove_css_class("btn-busy")
        if not self.tool.available():
            self.btn.set_label("Missing")
            self.btn.add_css_class("btn-stopped")
            self.btn.set_sensitive(False)
            return
        if self._busy:
            self.btn.set_label("Running…")
            self.btn.add_css_class("btn-busy")
            self.btn.set_sensitive(False)
            return
        self.btn.set_sensitive(True)
        if self.tool.kind == "oneshot":
            self.btn.set_label("Run")
            self.btn.add_css_class("btn-stopped")
            return
        if self.tool.is_running():
            self.btn.set_label("Running")
            self.btn.add_css_class("btn-running")
        else:
            self.btn.set_label("Stopped")
            self.btn.add_css_class("btn-stopped")

    def _on_click(self, *_args) -> None:
        if self._busy or not self.tool.available():
            return
        if self.tool.kind == "oneshot":
            self.set_busy(True)

            def done(_code: int) -> None:
                self.set_busy(False)
                self.refresh()

            self.tool.run_oneshot(done)
            return
        if self.tool.is_running():
            self.tool.stop()
        else:
            if not self.tool.is_running():
                self.tool.start()
        GLib.timeout_add(500, self.refresh)


class ToolsPanel(Adw.ApplicationWindow):
    def __init__(self, app: Adw.Application):
        super().__init__(application=app, title="Tools Panel")
        self.set_default_size(440, 480)
        self.set_resizable(True)

        css = Gtk.CssProvider()
        css.load_from_data(CSS.encode("utf-8"))
        Gtk.StyleContext.add_provider_for_display(
            self.get_display(),
            css,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

        header = Adw.HeaderBar()
        header.set_title_widget(
            Adw.WindowTitle(
                title="Tools Panel",
                subtitle="Desktop · start / stop without a terminal",
            )
        )

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        root.set_margin_top(10)
        root.set_margin_bottom(14)
        root.set_margin_start(16)
        root.set_margin_end(16)

        self.rows: list[ToolRow] = []
        for tool in TOOLS:
            row = ToolRow(tool, self._open_log)
            self.rows.append(row)
            root.append(row)

        foot = Gtk.Label(
            label="Red = Stopped / Run · Green = Running · click to toggle",
            xalign=0,
        )
        foot.add_css_class("footer")
        root.append(foot)

        view = Adw.ToolbarView()
        view.add_top_bar(header)
        view.set_content(root)
        self.set_content(view)

        GLib.timeout_add_seconds(2, self._tick)

    def _tick(self) -> bool:
        for row in self.rows:
            if not row._busy:
                row.refresh()
        return True

    def _open_log(self, tool: Tool) -> None:
        path = tool.log_path()
        if not path.is_file():
            path.write_text("(no log yet)\n", encoding="utf-8")
        Gio.AppInfo.launch_default_for_uri(path.as_uri(), None)


class App(Adw.Application):
    def __init__(self):
        super().__init__(
            application_id="com.safwan.ToolsPanel",
            flags=Gio.ApplicationFlags.FLAGS_NONE,
        )

    def do_activate(self):
        win = self.props.active_window
        if not win:
            win = ToolsPanel(self)
        win.present()


def main() -> int:
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    return App().run(None)


if __name__ == "__main__":
    raise SystemExit(main())
