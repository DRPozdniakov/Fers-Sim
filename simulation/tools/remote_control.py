"""
FERS Remote Control Server for Isaac Sim 5.1.0
Run this ONCE in Script Editor. Then send Python commands from any TCP client.

Listens on port 8224. Send Python code as plain text, get results back.
"""
import socket
import threading
import io
import sys
import traceback

PORT = 8224


def handle_client(conn, addr):
    """Handle one client connection."""
    print(f"[REMOTE] Client connected: {addr}")
    try:
        while True:
            data = conn.recv(65536)
            if not data:
                break
            code = data.decode("utf-8").strip()
            if not code:
                continue
            if code == "PING":
                conn.sendall(b"PONG\n")
                continue

            # Capture stdout
            old_stdout = sys.stdout
            old_stderr = sys.stderr
            capture = io.StringIO()
            sys.stdout = capture
            sys.stderr = capture

            try:
                exec(code, globals())
            except Exception:
                traceback.print_exc(file=capture)

            sys.stdout = old_stdout
            sys.stderr = old_stderr

            result = capture.getvalue()
            if result:
                conn.sendall(result.encode("utf-8"))
            else:
                conn.sendall(b"OK\n")
    except (ConnectionResetError, BrokenPipeError):
        pass
    finally:
        conn.close()
        print(f"[REMOTE] Client disconnected: {addr}")


def start_server():
    """Start TCP server in background thread."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("0.0.0.0", PORT))
    server.listen(5)
    print(f"[REMOTE] Listening on port {PORT}")
    print(f"[REMOTE] From local machine: ssh tunnel port {PORT}, then:")
    print(f'[REMOTE]   python -c "import socket; s=socket.socket(); s.connect((\'localhost\',{PORT})); s.sendall(b\'print(42)\\n\'); print(s.recv(4096))"')

    while True:
        conn, addr = server.accept()
        t = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
        t.start()


# Start in background thread so Isaac Sim keeps running
t = threading.Thread(target=start_server, daemon=True)
t.start()
print("[REMOTE] Server started in background")
