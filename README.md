<!-- SPDX-License-Identifier: GPL-3.0-or-later -->

![SFTP Tools](images/sftp-tools.webp)

# SFTP Tools

[![CI](https://github.com/RobertoTorino/sftp-tool/actions/workflows/ci.yml/badge.svg)](https://github.com/RobertoTorino/sftp-tool/actions/workflows/ci.yml)
[![License: GPL-3.0-or-later](https://img.shields.io/badge/license-GPL--3.0--or--later-blue)](LICENSE)

SFTP Tools for Windows moves files between your Windows computer and a Linux computer over SSH, and manages the
SSH server (`sshd`) of that computer. It has two tabs:

- **SFTP Client:** your folders on the left, the server's on the right. Upload and download files and whole
  folders, with a transfer queue, a speed limit and a choice of what to do when a file already exists.
- **Server Manager:** connect to a Linux host, see whether `sshd` runs, start or stop it, and edit
  `/etc/ssh/sshd_config`.

The host you connect to only needs a reachable `sshd`; it does not need the app.

## Install

On the [releases page](https://github.com/RobertoTorino/sftp-tool/releases), download
`sftp-tools-<version>-windows.zip` and its `.sha256` file from the latest release. Check the download
(`certutil -hashfile <zip> SHA256` must print the number in the `.sha256` file), unzip it, and start
`SFTP-Tools.exe`. It needs no Python.

The program is not signed, so Windows may show a SmartScreen warning the first time: choose *More info*, then
*Run anyway*.

## What the host needs

`sshd` running, and the firewall open for it: [Set up the host](#set-up-the-host) has the commands. Its SSH server
must sign with SHA-2 (OpenSSH 7.2 from 2016 or newer, as every current system has); an older server that only offers
SHA-1 (`ssh-rsa`) is refused, and so is an RSA key that can only sign with SHA-1.

## Using it

1. Fill in the host, the port (22), your user name and either a password or the path of a private key. A key is
   the better choice; with a key, the password field holds the key's passphrase.
2. Press **Connect** in the window's header. The first time, the app shows the server's fingerprint and asks
   whether you trust it. Yes adds it to `~/.ssh/known_hosts`; no makes no connection.
3. Double-click folders to open them, or type a path. Select files or folders and press **Upload →** or
   **← Download**, or use the right-click menu. Ctrl-click and Shift-click select more than one. The right-click
   menu also deletes, after a question.
4. To upload, you can also drag files and folders onto the server's list, from the list on the left or from
   Explorer. They go to the server folder that is open, and are copied, never moved.
5. The lists under the folders show the queued, failed and successful transfers. Closing the app while transfers
   are queued or running asks first, because it cancels them.

The window's header shows three states: your own system, the SFTP connection and the state of `sshd` on the host
the Server Manager is connected to; beside them, **Connect** connects the SFTP Client (and disconnects it again).
The password rules stand at the right of the password field and show, as you type, what is still missing. A red
dot at the right of the title appears after an error was logged; click it to open the log.

**Profiles.** *Save profile* keeps the host, port, user name and key path under a name. Passwords and key
passphrases are never saved. The SFTP Client and the Server Manager each have their own list.

**Passwords.** A password without a key must have at least 8 characters, one capital, one number and one special
character, or the app does not connect. An empty password is fine with a key.

### Server Manager

Connect, and the app asks `sshd` for its state: running or stopped. The button next to it starts or stops it.
*Load sshd_config* reads `/etc/ssh/sshd_config` into the editor. *Save sshd_config* checks the text with
`sshd -t`, keeps the old file as `sshd_config.bak`, installs the new one and offers to restart `sshd`.

These steps need `sudo` without a password on the host (`sudo -n`). When the host asks for one, the app shows
the error and changes nothing.

## Set up the host

On a Fedora-based host (Bazzite, for example), once, in a terminal:

```sh
rpm -q openssh-server                       # if it is missing: sudo rpm-ostree install openssh-server, then reboot
sudo systemctl enable --now sshd
systemctl is-active sshd                    # prints "active"
sudo firewall-cmd --list-services           # ssh must be in the list
sudo firewall-cmd --permanent --add-service=ssh && sudo firewall-cmd --reload   # only when it is not
hostname -I                                 # the address to connect to
```

Use the address of the Ethernet or Wi-Fi connection that is in use, and your account name (`whoami`). Keep both
computers on a network you trust, and do not forward port 22 from your router to the internet.

Password logins can be switched off on a recent Fedora-based system. To switch them on, create a file for it, and
restart `sshd`:

```sh
echo "PasswordAuthentication yes" | sudo tee /etc/ssh/sshd_config.d/10-enable-passwords.conf
sudo systemctl restart sshd
```

### Logging in with a key

Windows has an OpenSSH client with `ssh-keygen`, but no `ssh-copy-id`. In PowerShell:

```powershell
ssh-keygen -t ed25519
type $env:USERPROFILE\.ssh\id_ed25519.pub | ssh yourusername@HOST_ADDRESS "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys"
```

Then give the key's path in the app (`~/.ssh/id_ed25519`), or leave the field empty to use your SSH agent and the
default keys.

## Settings

*Edit, Settings…* has these, saved when you press Save:

| Setting | Default | What it does |
|---|---|---|
| Default local folder | home folder | The folder the left list starts in. |
| Connection timeout | 10 s | How long to wait for a connection (1 to 300). |
| TCP keep-alive | 15 s | How often to send a keep-alive on an idle connection (1 to 300). |
| Reconnect attempts, delay | 2, 5 s | Retries after a failed connection (0 to 10), and the pause between them (1 to 60). A host key you have not trusted is never retried. |
| Show hidden files | off | Lists names that start with a dot. |
| If file exists | Ask | Ask, overwrite or skip when the target exists. With more than one file, *Ask* offers to do the same for the others. |
| Speed limit | unlimited | Limit in KB/s per transfer. |
| File size format | Auto, 1 decimal, separator | Auto (1024-based), binary (KiB, MiB) or decimal (KB, MB); decimals 0 to 3; thousands separator. |
| Date format, time format | YYYY-MM-DD, HH:MM:SS | How modification times are shown. |
| Beep when transfer completes | on | Qt's beep. |
| Filter invalid Windows filename characters | on | A download replaces `< > : " \| ? *` in names with the replacement character (`_`), so the files can be copied to Windows later. |
| Enable SFTP compression | on | zlib compression on the connection. |
| Auto-clear successful transfers | on | Removes finished transfers from the list. |
| Preserve file modification times | on | Downloaded files get the remote modification time. |
| Log level, max log file size | INFO, 10 MB | What is logged, and the size at which the log rotates (three backups are kept). |

## Files

| What | Where |
|---|---|
| Settings | `C:\Users\<you>\.config\sftp-tools\settings.json` (delete it to go back to the defaults) |
| Profiles | `C:\Users\<you>\.config\sftp-tools\profiles.json` (SFTP Client), `server-profiles.json` (Server Manager) |
| The log | `C:\Users\<you>\.local\share\sftp-tools\sftp-tools.log` |
| Trusted hosts | `C:\Users\<you>\.ssh\known_hosts`, never removed by the app |

Settings, profiles and the log of a version that was called BC-250 SFTP Tools (in the `bc250-sftp-tools` folders)
move to these folders the first time the app starts.

To remove the app, delete `SFTP-Tools.exe`; delete the two `sftp-tools` folders to remove your settings too.

## Development

```sh
python -m venv .venv && .venv/Scripts/python -m pip install -r requirements-dev.txt   # Linux: .venv/bin/python
.venv/Scripts/python -m sftp_tools                                                     # run it from the checkout
.venv/Scripts/python -m pytest -q tests
```

`python tools/build_windows_exe.py windist` builds the executable (on Windows, with `pyinstaller` and `pillow`
installed). A release: set `VERSION` (and `__version__` in `sftp_tools/__init__.py`), add the CHANGELOG entry, push,
and push the tag `v<version>`; `.github/workflows/release.yml` tests, builds and publishes it.

## License

GPL-3.0-or-later, see [LICENSE](LICENSE). The Inter font is under the SIL Open Font License
(`sftp_tools/core/fonts/Inter-LICENSE.txt`).
