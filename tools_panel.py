#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Desktop Tools Panel — start/stop launchers without opening a terminal each time."""

from __future__ import annotations

import math
import os
import shutil
import signal
import socket
import struct
import subprocess
import sys
import threading
import time
import traceback
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk, Gio, Pango  # noqa: E402

HOME = Path.home()
APP_ROOT = Path(__file__).resolve().parent
APP_ID = "com.safwan.ToolsPanel"


def _natural_height(widget: Gtk.Widget, width: int) -> int:
    """GTK 4 measure() is (min, natural) or four values with baselines."""
    measured = widget.measure(Gtk.Orientation.VERTICAL, width)
    if isinstance(measured, tuple) and len(measured) >= 2:
        return int(measured[1])
    return 0


def _hand_cursor(widget: Gtk.Widget) -> None:
    """Show the hand pointer on clickable controls."""
    try:
        widget.set_cursor_from_name("pointer")
    except Exception:
        pass
CACHE = HOME / ".cache" / "tools-panel"
CACHE.mkdir(parents=True, exist_ok=True)
SOUND_DIR = CACHE / "sounds"
CRASH_LOG = CACHE / "crash.log"
ICON_THEME_DIR = APP_ROOT / "icons"
ICON_NAME = APP_ID


def _tool_icon_widget(icon: str) -> Gtk.Widget:
    """Theme icon or brand file (png/svg) centered on a readable tile."""
    path = Path(icon)
    if not path.is_absolute():
        cand = ICON_THEME_DIR / icon
        if cand.is_file():
            path = cand
    is_brand = path.is_file() and path.suffix.lower() in {
        ".png",
        ".svg",
        ".jpg",
        ".jpeg",
        ".webp",
    }
    if is_brand:
        image = Gtk.Image.new_from_file(str(path))
        image.set_pixel_size(26)
    else:
        image = Gtk.Image.new_from_icon_name(icon)
        image.set_pixel_size(20)

    image.set_halign(Gtk.Align.CENTER)
    image.set_valign(Gtk.Align.CENTER)

    # CenterBox keeps the logo in the middle of the square tile.
    tile = Gtk.CenterBox()
    tile.add_css_class("tool-icon")
    if is_brand:
        tile.add_css_class("tool-icon-brand")
    tile.set_halign(Gtk.Align.CENTER)
    tile.set_valign(Gtk.Align.CENTER)
    tile.set_hexpand(False)
    tile.set_vexpand(False)
    tile.set_size_request(38, 38)
    tile.set_center_widget(image)
    return tile


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

BROWSER_BOT = _first_existing(
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
  min-width: 38px;
  min-height: 38px;
}
.tool-icon-brand {
  background: #f1f3f5;
  color: transparent;
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
button, .btn-status, .btn-log, .btn-mute, .group-header {
  cursor: pointer;
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
.group-line {
  min-height: 1px;
  margin: 6px 8px;
  background: rgba(255, 255, 255, 0.07);
}
.tool-group {
  border-radius: 14px;
  padding: 6px 8px 8px 8px;
  border: 1px solid transparent;
}
.group-payment {
  background: rgba(56, 120, 200, 0.14);
  border-color: rgba(110, 168, 255, 0.22);
}
.group-ivac {
  background: rgba(180, 120, 40, 0.14);
  border-color: rgba(240, 160, 34, 0.22);
}
.group-files {
  background: rgba(60, 130, 90, 0.14);
  border-color: rgba(90, 180, 120, 0.22);
}
.group-header {
  padding: 2px 4px 4px 4px;
  border-radius: 10px;
  background: transparent;
  border: none;
  color: #d7dde3;
}
.group-header:hover {
  background: rgba(255, 255, 255, 0.05);
}
.group-title {
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.02em;
  color: #d7dde3;
}
.group-meta {
  font-size: 11px;
  color: #9aa0a6;
}
.group-chevron {
  color: #9aa0a6;
  min-width: 28px;
  min-height: 28px;
}
.group-body {
  margin-top: 2px;
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
    # Only the processes that are up right now. A later Start must not be killed.
    pids = _pgrep(match)
    subprocess.run(["pkill", "-f", match], check=False)

    def _force() -> bool:
        for pid in pids:
            try:
                os.kill(pid, 0)
            except OSError:
                continue
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
        return False

    if pids:
        GLib.timeout_add(400, _force)


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
            icon="chrome-icon.svg",
            start_cmd=["bash", str(BROWSER_ARRANGE / "Browser-Auto-Arrange.sh")],
            cwd=BROWSER_ARRANGE,
            required=[BROWSER_ARRANGE / "Browser-Auto-Arrange.sh"],
        ),
        Tool(
            id="browser_bot",
            name="Payment Browser Bot",
            subtitle="localhost:8787",
            kind="daemon",
            icon="playwright-logo.svg",
            match=" -m bot",
            start_cmd=["bash", str(BROWSER_BOT / "Run_Payment_Browser_Bot.sh")],
            cwd=BROWSER_BOT,
            required=[BROWSER_BOT / "Run_Payment_Browser_Bot.sh"],
            url="http://127.0.0.1:8787",
            env_extra={"PAYMENT_BROWSER_BOT_NO_BROWSER": "1"},
        ),
        Tool(
            id="checkout_solver",
            name="Checkout Checker",
            subtitle="localhost:8771",
            kind="daemon",
            icon="dgepay-mark.png",
            match="checkout-solver/ui.py",
            start_cmd=[
                str(_python_for(BROWSER_BOT, ".venv", ".venv-linux")),
                str(BROWSER_BOT / "checkout-solver" / "ui.py"),
            ],
            cwd=BROWSER_BOT / "checkout-solver",
            required=[BROWSER_BOT / "checkout-solver" / "ui.py"],
            url="http://127.0.0.1:8771",
            env_extra={"CHECKOUT_NO_BROWSER": "1"},
        ),
    ]
    return tools


TOOLS: list[Tool] = build_tools()


@dataclass(frozen=True)
class ToolGroup:
    id: str
    title: str
    style: str
    tool_ids: list[str]
    collapsible: bool = True
    default_expanded: bool = True


# Order: payment browsers on top, IVAC in the middle, PDF/phone last.
GROUPS: list[ToolGroup] = [
    ToolGroup(
        id="payment",
        title="Payment browsers",
        style="group-payment",
        tool_ids=["browser_arrange", "browser_bot", "checkout_solver"],
        collapsible=False,
        default_expanded=True,
    ),
    ToolGroup(
        id="ivac",
        title="IVAC / Solver",
        style="group-ivac",
        tool_ids=["solver", "restart_bot", "restart_panel"],
        collapsible=False,
        default_expanded=True,
    ),
    ToolGroup(
        id="files",
        title="PDF / Phone",
        style="group-files",
        tool_ids=["pdf_mapper", "pdf_upload", "folder_rename", "phone_manager"],
        collapsible=True,
        default_expanded=False,
    ),
]


def _load_group_state() -> dict[str, bool]:
    path = CACHE / "group_state.json"
    defaults = {g.id: g.default_expanded for g in GROUPS}
    if not path.is_file():
        return defaults
    try:
        import json

        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return defaults
        state = dict(defaults)
        for group in GROUPS:
            if not group.collapsible:
                state[group.id] = True
                continue
            if group.id in data:
                state[group.id] = bool(data[group.id])
        return state
    except (OSError, ValueError, TypeError):
        return defaults


def _save_group_state(state: dict[str, bool]) -> None:
    path = CACHE / "group_state.json"
    try:
        import json

        # Only persist collapsible groups
        collapsible_ids = {g.id for g in GROUPS if g.collapsible}
        slim = {k: bool(v) for k, v in state.items() if k in collapsible_ids}
        path.write_text(json.dumps(slim, indent=2) + "\n", encoding="utf-8")
    except OSError:
        pass


class ToolGroupBox(Gtk.Box):
    def __init__(
        self,
        group: ToolGroup,
        tools: list[Tool],
        open_log: Callable[[Tool], None],
        expanded: bool,
        on_toggle: Callable[[str, bool], None],
    ):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.group = group
        self._expanded = True if not group.collapsible else expanded
        self._on_toggle = on_toggle
        self.rows: list[ToolRow] = []
        self.add_css_class("tool-group")
        self.add_css_class(group.style)

        header_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        header_row.set_hexpand(True)

        title = Gtk.Label(label=group.title, xalign=0)
        title.add_css_class("group-title")
        title.set_hexpand(True)
        header_row.append(title)

        self.chevron = Gtk.Image()
        self.chevron.add_css_class("group-chevron")
        if group.collapsible:
            header_row.append(self.chevron)

        self.body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.body.add_css_class("group-body")
        for tool in tools:
            row = ToolRow(tool, open_log)
            self.rows.append(row)
            self.body.append(row)

        if group.collapsible:
            header = Gtk.Button()
            header.add_css_class("group-header")
            header.add_css_class("flat")
            header.set_hexpand(True)
            header.set_tooltip_text("Show / hide this group")
            header.connect("clicked", self._toggle)
            header.set_child(header_row)
            _hand_cursor(header)
            self.append(header)
        else:
            header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
            header.add_css_class("group-header")
            header.set_hexpand(True)
            header.append(header_row)
            self.append(header)

        # Inline with the other groups (not a popover). Collapse leaves empty
        # space below on Wayland — that is intentional / acceptable.
        self.append(self.body)
        self._apply_expanded()

    def _apply_expanded(self) -> None:
        self.body.set_visible(self._expanded)
        if self.group.collapsible:
            self.chevron.set_from_icon_name(
                "pan-down-symbolic" if self._expanded else "pan-end-symbolic"
            )

    def _toggle(self, *_args) -> None:
        if not self.group.collapsible:
            return
        SOUND.play("tap")
        self._expanded = not self._expanded
        self._apply_expanded()
        self._on_toggle(self.group.id, self._expanded)


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

        self.set_hexpand(True)
        self.set_halign(Gtk.Align.FILL)

        icon = _tool_icon_widget(tool.icon)
        icon.set_valign(Gtk.Align.CENTER)
        self.append(icon)

        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        text.set_hexpand(True)
        text.set_halign(Gtk.Align.FILL)
        text.set_valign(Gtk.Align.CENTER)
        name = Gtk.Label(label=tool.name, xalign=0)
        name.add_css_class("row-name")
        name.set_ellipsize(Pango.EllipsizeMode.END)
        name.set_hexpand(True)
        sub_label = tool.subtitle if tool.available() else f"{tool.subtitle} · missing"
        self.sub = Gtk.Label(label=sub_label, xalign=0)
        self.sub.add_css_class("row-sub")
        self.sub.set_ellipsize(Pango.EllipsizeMode.END)
        self.sub.set_hexpand(True)
        text.append(name)
        text.append(self.sub)
        self.append(text)

        self.btn = Gtk.Button()
        self.btn.add_css_class("btn-status")
        self.btn.set_valign(Gtk.Align.CENTER)
        self.btn.connect("clicked", self._on_click)
        _hand_cursor(self.btn)
        self.append(self.btn)

        log_btn = Gtk.Button()
        log_btn.set_icon_name("text-x-generic-symbolic")
        log_btn.set_tooltip_text("Open log")
        log_btn.add_css_class("btn-log")
        log_btn.set_valign(Gtk.Align.CENTER)
        log_btn.connect("clicked", self._on_log, open_log)
        _hand_cursor(log_btn)
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
            self.sub.set_label(f"{self.tool.subtitle} · missing")
            self.add_css_class("missing")
            self.btn.set_label("Missing")
            self.btn.add_css_class("btn-idle")
            self.btn.set_sensitive(False)
            return
        self.sub.set_label(self.tool.subtitle)
        self.remove_css_class("missing")
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
        try:
            if not self.tool.is_running():
                self.tool.start()
        finally:
            # Settle even if opening the page fails. A blocking browser launch
            # used to leave this button on "Starting…" for good.
            GLib.timeout_add(250, self._settle, True, 12)
            if self.tool.url:
                GLib.timeout_add(200, self._open_when_ready, 25)

    def _endpoint(self) -> tuple[str, int] | None:
        if not self.tool.url:
            return None
        host = "127.0.0.1"
        port = 80
        rest = self.tool.url.split("://", 1)[-1]
        hostport = rest.split("/", 1)[0]
        try:
            if hostport.startswith("["):
                host = hostport.split("]")[0][1:]
                if "]:" in hostport:
                    port = int(hostport.rsplit(":", 1)[-1])
            elif ":" in hostport:
                host, port_text = hostport.rsplit(":", 1)
                port = int(port_text)
            else:
                host = hostport
        except ValueError:
            return None
        return host, port

    def _port_open(self) -> bool:
        endpoint = self._endpoint()
        if endpoint is None:
            return False
        host, port = endpoint
        try:
            with socket.create_connection((host, port), 0.2):
                return True
        except OSError:
            return False

    def _open_when_ready(self, tries: int) -> bool:
        if self._port_open() or tries <= 0:
            self._open_page()
            return False
        GLib.timeout_add(200, self._open_when_ready, tries - 1)
        return False

    def _open_page(self) -> bool:
        if not self.tool.url:
            return False
        # xdg-open returns at once. UriLauncher.launch() on the click thread
        # waits on a portal reply and never comes back, so the button stays busy.
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


class StatusNotifierTray:
    """Top-bar icon via StatusNotifierItem (ubuntu-appindicators). Fail-soft."""

    OBJECT_PATH = "/StatusNotifierItem"
    WATCHER = "org.kde.StatusNotifierWatcher"
    WATCHER_PATH = "/StatusNotifierWatcher"
    WATCHER_IFACE = "org.kde.StatusNotifierWatcher"
    ITEM_IFACE = "org.kde.StatusNotifierItem"

    INTROSPECTION_XML = f"""
    <node>
      <interface name="{ITEM_IFACE}">
        <method name="Activate">
          <arg type="i" name="x" direction="in"/>
          <arg type="i" name="y" direction="in"/>
        </method>
        <method name="SecondaryActivate">
          <arg type="i" name="x" direction="in"/>
          <arg type="i" name="y" direction="in"/>
        </method>
        <method name="ContextMenu">
          <arg type="i" name="x" direction="in"/>
          <arg type="i" name="y" direction="in"/>
        </method>
        <method name="Scroll">
          <arg type="i" name="delta" direction="in"/>
          <arg type="s" name="orientation" direction="in"/>
        </method>
        <property name="Category" type="s" access="read"/>
        <property name="Id" type="s" access="read"/>
        <property name="Title" type="s" access="read"/>
        <property name="Status" type="s" access="read"/>
        <property name="WindowId" type="u" access="read"/>
        <property name="IconName" type="s" access="read"/>
        <property name="IconThemePath" type="s" access="read"/>
        <property name="IconPixmap" type="a(iiay)" access="read"/>
        <property name="ItemIsMenu" type="b" access="read"/>
        <property name="Menu" type="o" access="read"/>
        <property name="ToolTip" type="(sa(iiay)ss)" access="read"/>
        <signal name="NewTitle"/>
        <signal name="NewIcon"/>
        <signal name="NewStatus">
          <arg type="s" name="status"/>
        </signal>
        <signal name="NewToolTip"/>
      </interface>
    </node>
    """

    def __init__(self, app: "App"):
        self.app = app
        self._conn: Gio.DBusConnection | None = None
        self._reg_id = 0
        self._watcher_id = 0
        self._ok = False
        # Do NOT point IconThemePath at a folder with spaces — ubuntu-appindicators
        # fails lookup there and then hides the tray icon entirely.
        # Icons live in ~/.local/share/icons (no spaces) + IconPixmap backup.
        local_icon = HOME / ".local/share/icons/hicolor/22x22/apps" / f"{ICON_NAME}.png"
        self._icon_name = ICON_NAME if local_icon.is_file() else "applications-system"
        self._icon_theme = ""
        self._icon_pixmap = self._build_icon_pixmap()
        try:
            self._conn = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            node = Gio.DBusNodeInfo.new_for_xml(self.INTROSPECTION_XML)
            import warnings

            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                self._reg_id = self._conn.register_object(
                    self.OBJECT_PATH,
                    node.interfaces[0],
                    self._on_method,
                    self._on_get_property,
                    None,
                )
            self._watcher_id = Gio.bus_watch_name_on_connection(
                self._conn,
                self.WATCHER,
                Gio.BusNameWatcherFlags.NONE,
                self._on_watcher_appeared,
                self._on_watcher_vanished,
            )
            self._ok = True
        except Exception:
            self._log_fail("tray init")
            self.unregister()

    @staticmethod
    def _log_fail(where: str) -> None:
        try:
            with CRASH_LOG.open("a", encoding="utf-8") as fh:
                fh.write(f"[tray:{where}]\n{traceback.format_exc()}\n")
        except OSError:
            pass

    def _on_watcher_appeared(self, conn: Gio.DBusConnection, *_args) -> None:
        try:
            conn.call_sync(
                self.WATCHER,
                self.WATCHER_PATH,
                self.WATCHER_IFACE,
                "RegisterStatusNotifierItem",
                GLib.Variant("(s)", (self.OBJECT_PATH,)),
                None,
                Gio.DBusCallFlags.NONE,
                3000,
                None,
            )
        except Exception:
            try:
                conn.call_sync(
                    self.WATCHER,
                    self.WATCHER_PATH,
                    self.WATCHER_IFACE,
                    "RegisterStatusNotifierItem",
                    GLib.Variant("(s)", (conn.get_unique_name(),)),
                    None,
                    Gio.DBusCallFlags.NONE,
                    3000,
                    None,
                )
            except Exception:
                self._log_fail("register")

    def _on_watcher_vanished(self, *_args) -> None:
        return

    def _on_method(self, _conn, _sender, _path, _iface, method, _params, invocation):
        try:
            if method in ("Activate", "SecondaryActivate", "ContextMenu"):
                GLib.idle_add(self.app.toggle_window)
            invocation.return_value(None)
        except Exception:
            self._log_fail(f"method:{method}")
            try:
                invocation.return_value(None)
            except Exception:
                pass

    @staticmethod
    def _build_icon_pixmap() -> GLib.Variant:
        """ARGB pixmap so the host can draw us even if theme lookup fails."""
        try:
            gi.require_version("GdkPixbuf", "2.0")
            from gi.repository import GdkPixbuf  # noqa: WPS433

            candidates = [
                HOME / ".local/share/icons/hicolor/22x22/apps" / f"{ICON_NAME}.png",
                HOME / ".local/share/icons/hicolor/24x24/apps" / f"{ICON_NAME}.png",
                ICON_THEME_DIR / "hicolor/22x22/apps" / f"{ICON_NAME}.png",
            ]
            path = next((p for p in candidates if p.is_file()), None)
            if path is None:
                return GLib.Variant("a(iiay)", [])
            pb = GdkPixbuf.Pixbuf.new_from_file_at_size(str(path), 22, 22)
            w, h = pb.get_width(), pb.get_height()
            rowstride = pb.get_rowstride()
            n_ch = pb.get_n_channels()
            pixels = pb.get_pixels()
            out = bytearray(w * h * 4)
            i = 0
            for y in range(h):
                row = y * rowstride
                for x in range(w):
                    p = row + x * n_ch
                    r = pixels[p]
                    g = pixels[p + 1]
                    b = pixels[p + 2]
                    a = pixels[p + 3] if n_ch >= 4 else 255
                    # Network byte order ARGB
                    out[i : i + 4] = bytes((a, r, g, b))
                    i += 4
            return GLib.Variant("a(iiay)", [(w, h, bytes(out))])
        except Exception:
            return GLib.Variant("a(iiay)", [])

    def _tooltip_variant(self) -> GLib.Variant:
        # GVariant text form avoids PyGObject tuple packing bugs for a(iiay).
        text = (
            f'("{self._icon_name}", @a(iiay) [], "Tools Panel", '
            f'"Click to show / hide")'
        )
        return GLib.Variant.parse(
            GLib.VariantType.new("(sa(iiay)ss)"),
            text,
            None,
            None,
        )

    def _on_get_property(self, _conn, _sender, _path, _iface, name):
        try:
            if name == "Category":
                return GLib.Variant("s", "ApplicationStatus")
            if name == "Id":
                return GLib.Variant("s", APP_ID)
            if name == "Title":
                return GLib.Variant("s", "Tools Panel")
            if name == "Status":
                return GLib.Variant("s", "Active")
            if name == "WindowId":
                return GLib.Variant("u", 0)
            if name == "IconName":
                return GLib.Variant("s", self._icon_name)
            if name == "IconThemePath":
                return GLib.Variant("s", self._icon_theme)
            if name == "IconPixmap":
                return self._icon_pixmap
            if name == "ItemIsMenu":
                return GLib.Variant("b", False)
            if name == "Menu":
                return GLib.Variant("o", "/")
            if name == "ToolTip":
                return self._tooltip_variant()
            return GLib.Variant("s", "")
        except Exception:
            self._log_fail(f"property:{name}")
            return GLib.Variant("s", "")

    def unregister(self) -> None:
        conn = self._conn
        if conn is None:
            return
        try:
            if self._watcher_id:
                Gio.bus_unwatch_name(self._watcher_id)
        except Exception:
            pass
        try:
            if self._reg_id:
                conn.unregister_object(self._reg_id)
        except Exception:
            pass
        self._watcher_id = 0
        self._reg_id = 0
        self._conn = None
        self._ok = False


class ToolsPanel(Adw.ApplicationWindow):
    def __init__(self, app: Adw.Application):
        super().__init__(application=app, title="Tools Panel")
        # PDF/Phone expands inline. Wayland may leave empty space after collapse —
        # that is fine. Grow on expand so tools are not clipped.
        self.set_default_size(465, -1)
        self.set_resizable(False)
        self.set_hide_on_close(True)

        css = Gtk.CssProvider()
        css.load_from_data(CSS.encode("utf-8"))
        Gtk.StyleContext.add_provider_for_display(
            self.get_display(),
            css,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

        header = Adw.HeaderBar()
        header.set_title_widget(Adw.WindowTitle(title="Tools Panel"))
        self._header = header

        quit_btn = Gtk.Button()
        quit_btn.set_icon_name("application-exit-symbolic")
        quit_btn.set_tooltip_text("Quit Tools Panel")
        quit_btn.add_css_class("flat")
        quit_btn.connect("clicked", lambda *_: app.activate_action("quit", None))
        _hand_cursor(quit_btn)
        header.pack_start(quit_btn)

        self.mute_btn = Gtk.ToggleButton()
        self.mute_btn.set_icon_name("audio-volume-high-symbolic")
        self.mute_btn.set_tooltip_text("Mute click sound")
        self.mute_btn.add_css_class("btn-mute")
        self.mute_btn.add_css_class("flat")
        self.mute_btn.connect("toggled", self._on_mute)
        _hand_cursor(self.mute_btn)
        header.pack_end(self.mute_btn)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        root.set_margin_top(10)
        root.set_margin_bottom(8)
        root.set_margin_start(12)
        root.set_margin_end(12)
        root.set_vexpand(False)
        root.set_valign(Gtk.Align.START)
        self._content_root = root

        self.rows: list[ToolRow] = []
        self._group_state = _load_group_state()
        by_id = {tool.id: tool for tool in TOOLS}
        for group in GROUPS:
            tools = [by_id[tool_id] for tool_id in group.tool_ids if tool_id in by_id]
            expanded = True if not group.collapsible else self._group_state.get(
                group.id, group.default_expanded
            )
            box = ToolGroupBox(
                group,
                tools,
                self._open_log,
                expanded=expanded,
                on_toggle=self._on_group_toggle,
            )
            self.rows.extend(box.rows)
            root.append(box)

        view = Adw.ToolbarView()
        view.add_top_bar(header)
        view.set_content(root)
        self.set_content(view)

        GLib.timeout_add_seconds(2, self._tick)

    def _grow_for_content(self) -> bool:
        """Only grow the window when expanding — never shrink (empty gap OK)."""
        width = self.get_width()
        if width <= 1:
            width = 455
        root = self._content_root
        header = self._header
        if root is None or header is None:
            return False
        root_h = _natural_height(root, width)
        header_h = _natural_height(header, width)
        need = int(root_h + header_h)
        if need > 1 and self.get_height() < need:
            self.set_default_size(width, need)
        return False

    def _on_mute(self, btn: Gtk.ToggleButton) -> None:
        muted = btn.get_active()
        SOUND.enabled = not muted
        btn.set_icon_name(
            "audio-volume-muted-symbolic" if muted else "audio-volume-high-symbolic"
        )
        btn.set_tooltip_text("Unmute click sound" if muted else "Mute click sound")
        if not muted:
            SOUND.play("tap")

    def _on_group_toggle(self, group_id: str, expanded: bool) -> None:
        self._group_state[group_id] = expanded
        _save_group_state(self._group_state)
        if expanded:
            GLib.timeout_add(16, self._grow_for_content)

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
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.FLAGS_NONE,
        )
        self._tray: StatusNotifierTray | None = None
        self._holding = False

    def do_startup(self):
        Adw.Application.do_startup(self)
        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.connect("activate", self._on_quit)
        self.add_action(quit_action)
        toggle_action = Gio.SimpleAction.new("toggle", None)
        toggle_action.connect("activate", lambda *_: self.toggle_window())
        self.add_action(toggle_action)
        # Stay alive when the window is hidden (tray click can bring it back).
        self.hold()
        self._holding = True

    def do_activate(self):
        win = self.props.active_window
        if not win:
            win = ToolsPanel(self)
        if self._tray is None:
            self._tray = StatusNotifierTray(self)
        win.present()

    def toggle_window(self) -> None:
        try:
            win = self.props.active_window
            if win is None:
                self.activate()
                return
            if win.is_visible():
                win.set_visible(False)
            else:
                win.present()
        except Exception:
            try:
                with CRASH_LOG.open("a", encoding="utf-8") as fh:
                    fh.write(f"[toggle]\n{traceback.format_exc()}\n")
            except OSError:
                pass
            self.activate()

    def _on_quit(self, *_args) -> None:
        try:
            if self._tray is not None:
                self._tray.unregister()
                self._tray = None
        except Exception:
            pass
        for win in list(self.get_windows()):
            try:
                win.set_hide_on_close(False)
                win.destroy()
            except Exception:
                pass
        if self._holding:
            self.release()
            self._holding = False
        self.quit()


def _install_excepthook() -> None:
    def _hook(exc_type, exc, tb) -> None:
        try:
            CRASH_LOG.write_text(
                "".join(traceback.format_exception(exc_type, exc, tb)),
                encoding="utf-8",
            )
        except OSError:
            pass
        sys.__excepthook__(exc_type, exc, tb)

    sys.excepthook = _hook


def main() -> int:
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    _install_excepthook()
    return App().run(None)


if __name__ == "__main__":
    raise SystemExit(main())
