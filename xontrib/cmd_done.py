"""Show long running commands durations in prompt with option to send notification when terminal is not focused. """

import functools
import subprocess as sp

from xonsh.built_ins import XSH as xsh

LONG_DURATION = xsh.env.get("XONTRIB_CD_LONG_DURATION", 5)  # seconds
TRIGGER_NOTIFICATION = xsh.env.get("XONTRIB_CD_TRIGGER_NOTIFICATION", True)
NOTIFICATION_APP_NAME = xsh.env.get("XONTRIB_CD_NOTIFICATION_APP_NAME", xsh.env.get("TITLE", "xonsh"))


def _term_program_mapping() -> dict:
    """The app name doesn't match the $TERMPROGRAM . This is to map equivalent ones in OSX"""
    defaults = {"iterm.app": "iTerm2", "apple_terminal": "Terminal", "vscode": "Code", "pycharm": "PyCharm",
                 "kate": "Kate"}
    maps = xsh.env.get("XONTRIB_CD_TERM_PROGRAM_MAP", defaults)
    return {key.lower(): val for key, val in maps.items()}


@functools.lru_cache()
def _darwin_get_app_name(term_program: str):
    maps = _term_program_mapping()
    return maps.get(term_program.lower(), term_program)


def _warn(*args, **kwargs):
    import logging

    logging.warning(*args, **kwargs)


def secs_to_readable(secs: int):
    """

    Parameters
    ----------
    secs

    >>> secs_to_readable(100)
    '1m40s'
    """
    secs = round(secs)
    readable = ""
    hours, remainder = divmod(secs, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        readable += str(hours) + "h"
    if hours or minutes:
        readable += str(minutes) + "m"
    if hours or minutes or seconds:
        readable += str(seconds) + "s"
    return readable


def is_system(system: str):
    import platform

    return platform.system() == system


@functools.lru_cache(None)
def is_linux_system():
    return is_system("Linux")


@functools.lru_cache(None)
def is_darwin_system():
    return is_system("Darwin")


def _xdotool_window_id():
    try:
        return sp.check_output(["xdotool", "getactivewindow"]).decode().strip()
    except Exception as ex:
        _warn(f"Failed to send notification {ex}. Make sure that xdotool is installed.")


def _linux_is_app_window_focused():
    winid = xsh.env.get("WINDOWID")
    if not winid:
        _warn(
            "Environment variable $WINDOWID is unset. It should be set by the terminal application on shell startup. "
            "Not able to find active window."
        )
        return False
    curr_winid = _xdotool_window_id()
    return curr_winid == winid


def _darwin_is_app_window_focused():
    appname = None

    bundle_id = xsh.env.get("__CFBundleIdentifier")
    if bundle_id:
        out = sp.check_output(["lsappinfo", "find", "bundleID=" + bundle_id]).strip()
        appname = str(out).split("\"")[1]

    if not appname:
        if term := xsh.env.get("TERM_PROGRAM"):
            appname = _darwin_get_app_name(term)

    if not appname:
        _warn(
            "xontrib-cmd-durations: "
            f"Application not found by $__CFBundleIdentifier "
            f"and because $TERM_PROGRAM ({repr(term)}) "
            f"not found in $XONTRIB_CD_TERM_PROGRAM_MAP:\n"
            f"({_term_program_mapping()})"
        )
        return False

    out = sp.check_output(["lsappinfo", "info", "-app", appname])
    if not out:
        _warn(
            f"xontrib-cmd-durations: Application {appname} not found in lsappinfo."
        )

    return b"(in front)" in out


def is_app_window_focused():
    # https://stackoverflow.com/questions/10266281/obtain-active-window-using-python
    if is_darwin_system():
        return _darwin_is_app_window_focused()

    if is_linux_system():
        return _linux_is_app_window_focused()
    return False


def notify_user(hist, readable: str):
    rtn = hist.rtns[-1]
    cmd = hist.inps[-1]

    if is_app_window_focused():
        return

    from notifypy import Notify

    noti = Notify()
    noti.application_name = xsh.shell.prompt_formatter(NOTIFICATION_APP_NAME)
    noti.title = str(f"{cmd}")
    noti.message = f'{"Failed" if rtn else "Done"} in {readable}'
    noti.send()


def long_cmd_duration():
    history = xsh.history
    if not history.tss:
        return

    start_t, end_t = history.tss[-1]
    interval = end_t - start_t

    if interval > LONG_DURATION:
        readable = secs_to_readable(interval)
        if TRIGGER_NOTIFICATION:
            notify_user(history, readable)
        return readable
    return None


xsh.env["PROMPT_FIELDS"]["long_cmd_duration"] = long_cmd_duration
