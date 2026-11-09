#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Desktop Tools Panel — start/stop launchers without opening a terminal each time."""

from __future__ import annotations

import math
import os
import shutil
import signal
import struct
import subprocess
import threading
import wave
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
SOUND_DIR = CACHE / "sounds"


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

PAYDESK = _first_existing(
    HOME / "GitHub Repository/ivac-dgepay-confirm",
) or (HOME / "GitHub Repository/ivac-dgepay-confirm")

PHONE_MGR = PDF_ROOT / "T phone_manager"

CSS = """
window {
  background: #17181b;
}
.header {
  font-size: 15px;
  font-weight: 600;
  color: #e8eaed;
  margin: 4px 0 8px 0;
}
.card {
  background: #1d1f23;
  border: 1px solid #2a2c31;
  border-radius: 12px;
  padding: 8px 10px;
  transition: background-color 150ms ease, border-color 150ms ease;
}
.card:hover {
  background: #212429;
  border-color: #3a3d44;
}
.tool-icon {
  background: #26292f;
  border-radius: 9px;
  color: #9db4ff;
  min-width: 34px;
  min-height: 34px;
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
  min-width: 104px;
  min-height: 34px;
  border-radius: 9px;
  font-weight: 500;
  font-size: 12px;
  border: 1px solid transparent;
  transition: background-color 150ms ease;
}
.btn-idle {
  background: #23252a;
  color: #c7ccd1;
  border-color: #34373d;
}
.btn-idle:hover {
  background: #2c2f35;
}
.btn-running {
  background: #2e7d32;
  color: #ffffff;
}
.btn-running:hover {
  background: #357a38;
}
.btn-busy {
  background: #f0a022;
  color: #1a1b1e;
}
.btn-status:focus-visible,
.btn-log:focus-visible,
.btn-mute:focus-visible {
  outline: 2px solid #6ea8ff;
  outline-offset: 2px;
}
.btn-log {
  min-width: 40px;
  min-height: 34px;
  border-radius: 9px;
  background: #23252a;
  color: #c7ccd1;
  border: 1px solid #34373d;
  transition: background-color 150ms ease;
}
.btn-log:hover {
  background: #2c2f35;
}
.btn-mute {
  color: #9aa0a6;
}
.footer {
  font-size: 11px;
  color: #8a9096;
  margin-top: 8px;
}
.missing {
  opacity: 0.45;
}
"""


class Sound:
    """Short synthesized click tones; no bundled audio files needed."""

    SPECS = {
        "tap": 520.0,
        "run": 660.0,
        "stop": 420.0,
    }

    def __init__(self) -> None:
        self.enabled = True
        self._player = self._find_player()
        self._files: dict[str, Path] = {}
        self._prepare()

    @staticmethod
    def _find_player() -> list[str] | None:
        for cmd in (
            ["paplay"],
            ["pw-play"],
            ["aplay", "-q"],
            ["canberra-gtk-play", "-f"],
            ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet"],
        ):
            if shutil.which(cmd[0]):
                return cmd
        return None

    def _prepare(self) -> None:
        try:
            SOUND_DIR.mkdir(parents=True, exist_ok=True)
        except OSError:
            return
        for kind, freq in self.SPECS.items():
            path = SOUND_DIR / f"{kind}.wav"
            if not path.is_file():
                try:
                    self._generate(path, freq)
                except OSError:
                    continue
            self._files[kind] = path

    @staticmethod
    def _generate(path: Path, freq: float, ms: int = 130) -> None:
        rate = 44100
        total = int(rate * ms / 1000)
        attack = max(1, int(rate * 0.008))
        phase = 0.0
        with wave.open(str(path), "w") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(rate)
            frames = bytearray()
            for i in range(total):
                progress = i / total
                f = freq * (1.0 + 0.45 * progress)
                phase += 2.0 * math.pi * f / rate
                env_in = min(1.0, i / attack)
                env_out = max(0.0, 1.0 - progress)
                env = env_in * env_out * env_out
                sample = math.sin(phase) * env * 0.35
                frames += struct.pack("<h", int(sample * 32767))
            w.writeframes(bytes(frames))

    def play(self, kind: str) -> None:
        if not self.enabled or not self._player:
            return
        path = self._files.get(kind)
        if not path or not path.is_file():
            return
        try:
            subprocess.Popen(
                self._player + [str(path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError:
            pass


SOUND = Sound()


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
    icon: str = "application-x-executable-symbolic"
    match: str = ""
    start_cmd: list[str] = field(default_factory=list)
    cwd: Path | None = None
    env_extra: dict[str, str] = field(default_factory=dict)
    required: list[Path] = field(default_factory=list)
    url: str = ""

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
        if self.is_running():
            return
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
            icon="view-paged-symbolic",
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
            icon="send-to-symbolic",
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
            icon="document-edit-symbolic",
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
            icon="system-run-symbolic",
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
            icon="view-refresh-symbolic",
            start_cmd=["bash", str(IVAC / "Restart_Bot.sh")],
            cwd=IVAC,
            required=[IVAC / "Restart_Bot.sh"],
        ),
        Tool(
            id="restart_panel",
            name="IVAC Restart Panel",
            subtitle="WebHost · one-shot",
            kind="oneshot",
            icon="view-refresh-symbolic",
            start_cmd=["bash", str(IVAC / "Restart_Panel.sh")],
            cwd=IVAC,
            required=[IVAC / "Restart_Panel.sh"],
        ),
        Tool(
            id="browser_arrange",
            name="Browser Auto Arrange",
            subtitle="Chrome×7 + Edge×7",
            kind="oneshot",
            icon="web-browser-symbolic",
            start_cmd=["bash", str(BROWSER_ARRANGE / "Browser-Auto-Arrange.sh")],
            cwd=BROWSER_ARRANGE,
            required=[BROWSER_ARRANGE / "Browser-Auto-Arrange.sh"],
        ),
        Tool(
            id="phone_manager",
            name="Phone Manager",
            subtitle="localhost:5056",
            kind="daemon",
            icon="phone-symbolic",
            match="T phone_manager/app.py",
            start_cmd=[str(PDF_PY), str(PHONE_MGR / "app.py")],
            cwd=PHONE_MGR,
            required=[PHONE_MGR / "app.py"],
            url="http://127.0.0.1:5056",
            env_extra={"MT_NO_BROWSER": "1"},
        ),
        Tool(
            id="paydesk",
            name="Pay Desk",
            subtitle="localhost:8787",
            kind="daemon",
            icon="web-browser-symbolic",
            match=" -m paydesk",
            start_cmd=["bash", str(PAYDESK / "Run_Paydesk.sh")],
            cwd=PAYDESK,
            required=[PAYDESK / "Run_Paydesk.sh"],
            url="http://127.0.0.1:8787",
            env_extra={"PAYDESK_NO_BROWSER": "1"},
        ),
    ]
    return tools


TOOLS: list[Tool] = build_tools()


class ToolRow(Gtk.Box):
    def __init__(self, tool: Tool, open_log: Callable[[Tool], None]):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.tool = tool
        self._busy = False
        self._busy_label = "Running…"
        self.add_css_class("card")
        self.set_margin_top(3)
        self.set_margin_bottom(3)
        if not tool.available():
            self.add_css_class("missing")

        icon = Gtk.Image.new_from_icon_name(tool.icon)
        icon.set_pixel_size(18)
        icon.add_css_class("tool-icon")
        icon.set_valign(Gtk.Align.CENTER)
        self.append(icon)

        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        text.set_hexpand(True)
        text.set_valign(Gtk.Align.CENTER)
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
        self.btn.set_valign(Gtk.Align.CENTER)
        self.btn.connect("clicked", self._on_click)
        self.append(self.btn)

        log_btn = Gtk.Button()
        log_btn.set_icon_name("text-x-generic-symbolic")
        log_btn.set_tooltip_text("Open log")
        log_btn.add_css_class("btn-log")
        log_btn.set_valign(Gtk.Align.CENTER)
        log_btn.connect("clicked", self._on_log, open_log)
        self.append(log_btn)

        self.refresh()

    def _on_log(self, _btn, open_log: Callable[[Tool], None]) -> None:
        SOUND.play("tap")
        open_log(self.tool)

    def set_busy(self, busy: bool, label: str = "Running…") -> None:
        self._busy = busy
        self._busy_label = label
        self.refresh()

    def refresh(self) -> None:
        self.btn.remove_css_class("btn-idle")
        self.btn.remove_css_class("btn-running")
        self.btn.remove_css_class("btn-busy")
        if not self.tool.available():
            self.btn.set_label("Missing")
            self.btn.add_css_class("btn-idle")
            self.btn.set_sensitive(False)
            return
        if self._busy:
            self.btn.set_label(self._busy_label)
            self.btn.add_css_class("btn-busy")
            self.btn.set_sensitive(False)
            return
        self.btn.set_sensitive(True)
        if self.tool.kind == "oneshot":
            self.btn.set_label("⏵  Run")
            self.btn.add_css_class("btn-idle")
            return
        if self.tool.is_running():
            self.btn.set_label("●  Running")
            self.btn.add_css_class("btn-running")
        else:
            self.btn.set_label("Stopped")
            self.btn.add_css_class("btn-idle")

    def _on_click(self, *_args) -> None:
        if self._busy or not self.tool.available():
            return
        if self.tool.kind == "oneshot":
            SOUND.play("tap")
            self.set_busy(True)

            def done(_code: int) -> None:
                SOUND.play("run")
                self.set_busy(False)
                self.refresh()

            self.tool.run_oneshot(done)
            return
        # Use the label the user clicked, not a second process check.
        # A fast second click used to start the app and then immediately stop it.
        wants_stop = self.btn.get_label().startswith("●")
        if wants_stop:
            SOUND.play("stop")
            self.set_busy(True, "Stopping…")
            self.tool.stop()
            GLib.timeout_add(250, self._settle, False, 12)
            return
        SOUND.play("run")
        self.set_busy(True, "Starting…")
        if self.tool.is_running():
            self._open_page()
        else:
            self.tool.start()
            if self.tool.url:
                GLib.timeout_add(800, self._open_page)
        GLib.timeout_add(250, self._settle, True, 12)

    def _open_page(self) -> bool:
        if self.tool.url:
            try:
                Gio.AppInfo.launch_default_for_uri(self.tool.url, None)
            except GLib.Error:
                subprocess.Popen(
                    ["xdg-open", self.tool.url],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
        return False

    def _settle(self, want_running: bool, tries: int) -> bool:
        running = self.tool.is_running()
        if running == want_running or tries <= 0:
            self.set_busy(False)
            return False
        GLib.timeout_add(250, self._settle, want_running, tries - 1)
        return False


class ToolsPanel(Adw.ApplicationWindow):
    def __init__(self, app: Adw.Application):
        super().__init__(application=app, title="Tools Panel")
        self.set_default_size(440, 600)
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

        self.mute_btn = Gtk.ToggleButton()
        self.mute_btn.set_icon_name("audio-volume-high-symbolic")
        self.mute_btn.set_tooltip_text("Mute click sound")
        self.mute_btn.add_css_class("btn-mute")
        self.mute_btn.add_css_class("flat")
        self.mute_btn.connect("toggled", self._on_mute)
        header.pack_end(self.mute_btn)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
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
            label="Green = Running · Stopped / Run stays neutral · click to toggle",
            xalign=0,
        )
        foot.add_css_class("footer")
        root.append(foot)

        view = Adw.ToolbarView()
        view.add_top_bar(header)
        view.set_content(root)
        self.set_content(view)

        GLib.timeout_add_seconds(2, self._tick)

    def _on_mute(self, btn: Gtk.ToggleButton) -> None:
        muted = btn.get_active()
        SOUND.enabled = not muted
        btn.set_icon_name(
            "audio-volume-muted-symbolic" if muted else "audio-volume-high-symbolic"
        )
        btn.set_tooltip_text("Unmute click sound" if muted else "Mute click sound")
        if not muted:
            SOUND.play("tap")

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
