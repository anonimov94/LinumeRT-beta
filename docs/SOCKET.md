# Interfejs socket (JSON-lines)

SPDX-License-Identifier: GPL-2.0-or-later

Najprostszy interfejs: jedna linia = jeden obiekt JSON zakończony `\n`. Nie wymaga FastAPI.

```
linumertd serve --no-http --socket-port 8765            # TCP 127.0.0.1
linumertd serve --no-http --socket-unix /tmp/lrt.sock   # gniazdo Unix (0600, bez tokenu)
```
Poza localhost TCP wymaga tokenu (`--token`/`LRT_TOKEN`).

| Klient → serwer | Odpowiedź |
|---|---|
| `{"id":1,"command":"system.info","params":{}}` | `{"id":1,"ok":true,"result":{...}}` lub `{"id":1,"ok":false,"error":{"code","message"}}` |
| `{"type":"auth","token":"..."}` (gdy serwer ma token) | `{"type":"auth","ok":true}` |
| `{"type":"ping"}` | `{"type":"pong"}` |
| `{"id":2,"method":"state.get"}` | pełna migawka tematów |
| `{"type":"subscribe","topics":["machine"]}` | `{"type":"subscribed"}`, potem push `{"type":"state","version","topics"}` (20 Hz, sklejane) |

Na początek serwer wysyła `{"type":"hello","session","schema","version","auth_required"}`.
Kontrakt (lista operacji ze schematami): `{"id":1,"command":"system.contract"}`.
Rozłączenie zatrzymuje jogi tej sesji (deadman). Linia ≤ 1 MiB. Błędy mają te same kody co REST.

Python: `from linumert_headless.transport.socket import SocketClient` →
`SocketClient("127.0.0.1", 8765).call("machine.state")`.
Z powłoki: `printf '{"id":1,"command":"system.info"}\n' | nc 127.0.0.1 8765`.
