# FastLAN BBS

A tiny local-network chat and file-drop server with a retro BBS look. Run it on
one machine, open the page from any device on the same network, and you can
chat, send private messages, and share files. No accounts, no internet needed.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

The server prints a URL such as `http://10.0.0.191:8000`. Open it from any
device on the same network (phone, laptop, ...). The port is set by `PORT` in
`main.py` (default 8000).

## Using it

- **Chat:** type and press Enter. Everyone connected sees the message.
- **Private messages:** pick a node in the `TO:` dropdown, click a `<NODE nn>`
  tag in the feed, or use `/msg`. Only you and the recipient see a DM.
- **Files:** click `[FILE]` or drag files onto the page, then press `[UPLOAD]`.
  A download link appears in the feed for everyone. Limit: 100 MB per file.
- **Settings (`[SET]`):** sound and volume, colour palette, scanlines,
  timestamps, font size, desktop alerts, and a reset button.
- **Notifications:** while the tab is in the background the title shows an
  unread count (`(3) FastLAN BBS`, and a flashing `(2 DM)` for private
  messages). Desktop alerts are optional and off by default.

### Commands

| Command | Does |
|---|---|
| `/help` (`/?`) | list commands |
| `/msg <node> [text]` (`/w`, `/dm`, `/pm`) | private message, or select that node |
| `/to <node\|all>` | choose who you are writing to |
| `/me <action>` | send an action (`* waves`) |
| `/who` | list online nodes |
| `/clear` (`/cls`) | clear the feed |
| `/sound [on\|off]` | toggle sound |
| `/theme [name]` | `classic`, `green`, `amber`, `cyan`, `white` |
| `//text` | send a message that starts with `/` |

## How it works

```
main.py          FastAPI server (HTTP + WebSocket)
static/index.html  the whole client: HTML, CSS and JS in one file
requirements.txt fastapi, uvicorn[standard], python-multipart
server.log       activity log (created on first run)
```

**Nodes.** There are no logins. The server gives each client IP a number
("NODE 01", "NODE 02", ...) in order of first contact. The numbers live in
memory and reset when the server restarts. Two tabs or devices behind the same
IP share one node.

**Messaging** goes over a WebSocket at `/ws`, using small JSON messages:

| Direction | Message |
|---|---|
| client -> server | `{"type":"message","text":...}` public chat |
| client -> server | `{"type":"dm","to":<node>,"text":...}` private message |
| server -> client | `hello` (your node), `users` (who is online), `message`, `dm`, `file`, `error` |

Public messages are broadcast to every connection. A DM is sent only to the
sockets of the sender and the recipient. Messages are capped at 5000
characters and are not stored: a reload clears the feed, and nobody can see
messages sent while they were away.

**Files** are uploaded with `POST /upload` and downloaded from
`GET /files/<name>`. Names are sanitised and prefixed with a timestamp and
random id. Uploads are streamed in 1 MB chunks and rejected past 100 MB. The
upload folder is a temporary directory (under `/tmp` on Linux) created at
startup and **deleted when the server exits**, so files do not survive a
restart.

**Settings** (palette, sound, font, ...) are stored in the browser's
`localStorage` on each device. Nothing about them reaches the server.

## What is saved

- **Saved on disk:** only `server.log` (git-ignored), next to `main.py`. It
  records connections, uploads and downloads, and the text of public messages.
  For private messages it records only "node X messaged node Y", never the
  text. The log has no size limit or rotation yet.
- **Not saved:** uploaded files, chat history, node numbers.

## Security notes

FastLAN is meant for a network you trust.

- There is no authentication: anyone who can reach the port can read public
  chat, upload files, and download any file whose link they have.
- Node identity is just the IP address, so it is not proof of who someone is.
- Traffic is plain HTTP/WebSocket, not encrypted.
- Do not expose the port to the internet.

## Troubleshooting

- **Page looks old or commands do nothing:** hard-refresh (`Ctrl+Shift+R`).
  The server sends `Cache-Control: no-cache`, but a tab opened before an
  update may still be running old code.
- **Other devices cannot connect:** check that they are on the same network
  and that the host firewall allows port 8000.
- **Port already in use:** another copy is running; stop it or change `PORT`.
