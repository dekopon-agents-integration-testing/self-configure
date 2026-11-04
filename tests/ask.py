import json
import socket
import sys
import uuid

s = socket.socket(socket.AF_UNIX)
s.settimeout(180)
s.connect("/tmp/chat.sock")
s.sendall(
    (
        json.dumps(
            {
                "subject": "drn:tel:number::"
                + ("16035550101" if sys.argv[1] == "tester" else "16035550102"),
                "conversation": {"kind": "directMessage", "id": str(uuid.uuid4())},
                "text": sys.stdin.read(),
            }
        )
        + "\n"
    ).encode()
)
size = 0
for line in s.makefile("rb"):
    size += len(line)
    assert size <= 65536, "transport output limit"
    obj = json.loads(line)
    if "reply" in obj:
        print(json.dumps(obj))
        break
else:
    raise RuntimeError("no final reply")
