#!/usr/bin/env python3
"""
Start the VS Code Remote Tunnel service install and auto-select the GITHUB
login provider (the interactive prompt defaults to Microsoft and can't be
changed via plain terminal input since it needs arrow keys).

Runs the CLI in a PTY, sends Down+Enter when the login prompt appears, then
keeps the process alive and streams output (device code) to stdout.
"""
import os
import pty
import select
import sys
import time

CMD = [
    os.path.expanduser("~/.local/bin/code"),
    "tunnel",
    "service",
    "install",
    "--accept-server-license-terms",
    "--name",
    "writer-home",
]

pid, fd = pty.fork()
if pid == 0:
    os.execvp(CMD[0], CMD)
    sys.exit(1)

output = b""
sent_keys = False

try:
    while True:
        r, _, _ = select.select([fd], [], [], 1.0)
        if fd in r:
            try:
                data = os.read(fd, 4096)
            except OSError:
                break
            if not data:
                break
            output += data
            try:
                sys.stdout.buffer.write(data)
                sys.stdout.flush()
            except Exception:
                pass

            # Auto-select "GitHub Account" (2nd option) once the prompt appears
            if not sent_keys and b"How would you like to log in" in output:
                time.sleep(0.8)
                os.write(fd, b"\x1b[B")  # Down arrow -> GitHub Account
                time.sleep(0.3)
                os.write(fd, b"\r")      # Enter
                sent_keys = True
                output = output[-2000:]
except KeyboardInterrupt:
    pass
finally:
    try:
        os.kill(pid, 9)
    except Exception:
        pass
