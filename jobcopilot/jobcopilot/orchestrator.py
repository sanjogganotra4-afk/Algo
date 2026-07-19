"""Launch the copilot: start the backend + scoring worker and print the
dashboard URL (with a QR code for easy iPad access).

Run:  python -m jobcopilot.orchestrator
"""
from __future__ import annotations

import socket

import uvicorn

from . import config


def _lan_ip() -> str:
    """Best-effort LAN IP so you can open the dashboard from your iPad."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def _print_qr(url: str) -> None:
    try:
        import qrcode

        qr = qrcode.QRCode(border=1)
        qr.add_data(url)
        qr.make(fit=True)
        qr.print_ascii(invert=True)
    except Exception:
        pass  # QR is a nicety, not required


def main() -> None:
    # No wizard required: the server bootstraps a default profile on startup,
    # and the user uploads their CV + tunes the profile from the dashboard.
    config.ensure_dirs()
    config.ensure_profile()
    first_run = not config.RESUME_STRUCTURED_PATH.exists()

    srv = config.server_settings()
    host, port = srv["host"], srv["port"]

    lan = _lan_ip()
    local_url = f"http://127.0.0.1:{port}"
    lan_url = f"http://{lan}:{port}"

    print("\n" + "=" * 60)
    print("  Job Application Copilot")
    print("=" * 60)
    print(f"  On this laptop : {local_url}")
    if host == "0.0.0.0":
        print(f"  On your iPad   : {lan_url}   (same Wi-Fi / Tailscale)")
        print("\n  Scan to open on iPad:")
        _print_qr(lan_url)
    if first_run:
        print("\n  First run: open the dashboard, go to the Profile tab, and")
        print("  upload your .docx CV. Everything else fills in automatically.")
    print("\n  Press Ctrl+C to stop.")
    print("=" * 60 + "\n")

    uvicorn.run("jobcopilot.server:app", host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
