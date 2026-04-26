import sys, os, json, time, re, random, tempfile, subprocess, ipaddress, threading, queue, shutil, base64, urllib.parse, ssl, socket
from dataclasses import dataclass
from typing import List, Optional, Dict

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QFileDialog, QSpinBox, QDoubleSpinBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar, QCheckBox,
    QMessageBox, QFrame, QSplitter, QScrollArea, QTextEdit
)

DOWN_URL  = "https://speed.cloudflare.com/__down?bytes={bytes}"
TRACE_URL = "https://speed.cloudflare.com/cdn-cgi/trace"

# -------------------- Data --------------------

@dataclass
class Result:
    ip: str
    ping_ms: float
    dl_mbps: Optional[float]
    ul_mbps: Optional[float]
    colo: str
    score: float
    status: str  # "GOOD", "DL-only", "UL-only", "Below"

# -------------------- Helpers --------------------

def is_windows() -> bool:
    return os.name == "nt"

def ping_ip_windows(ip: str, timeout_ms: int = 900) -> Optional[float]:
    try:
        p = subprocess.run(["ping", "-n", "1", "-w", str(timeout_ms), ip],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           text=True, encoding="utf-8", errors="ignore")
        if p.returncode != 0:
            return None
        out = p.stdout
        m = re.search(r"time[=<]\s*(\d+)\s*ms", out, re.IGNORECASE)
        if m:
            return float(m.group(1))
        if re.search(r"time<\s*1ms", out, re.IGNORECASE):
            return 1.0
        return None
    except Exception:
        return None

def curl_download_mbps(socks_port: int, bytes_to_dl: int, timeout_s: int) -> Optional[float]:
    proxy = f"socks5h://127.0.0.1:{socks_port}"
    cmd = ["curl.exe", "-L", "--silent", "--show-error", "--max-time", str(timeout_s),
           "-x", proxy, "-o", "NUL", "-w", "%{speed_download}", DOWN_URL.format(bytes=bytes_to_dl)]
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL,
                                      text=True, encoding="utf-8", errors="ignore").strip()
        bps = float(out)
        return (bps * 8) / 1_000_000.0
    except Exception:
        return None

def curl_upload_mbps_file(socks_port: int, upload_bytes: int, timeout_s: int, upload_url: str) -> Optional[float]:
    """
    UL method (Windows-safe):
      - create temp file of size upload_bytes
      - curl POST --data-binary @file to upload_url
    """
    proxy = f"socks5h://127.0.0.1:{socks_port}"
    path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False) as tf:
            path = tf.name
            tf.write(b"0" * min(upload_bytes, 1024 * 1024))
        if upload_bytes > 1024 * 1024:
            with open(path, "ab") as f:
                f.truncate(upload_bytes)

        cmd = ["curl.exe", "--silent", "--show-error", "--max-time", str(timeout_s),
               "-x", proxy,
               "-X", "POST",
               "--data-binary", f"@{path}",
               "-o", "NUL",
               "-w", "%{speed_upload}",
               upload_url]
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL,
                                      text=True, encoding="utf-8", errors="ignore").strip()
        bps = float(out)
        return (bps * 8) / 1_000_000.0
    except Exception:
        return None
    finally:
        if path:
            try:
                os.remove(path)
            except Exception:
                pass

def curl_colo(socks_port: int, timeout_s: int) -> str:
    proxy = f"socks5h://127.0.0.1:{socks_port}"
    cmd = ["curl.exe", "--silent", "--show-error", "--max-time", str(timeout_s),
           "-x", proxy, TRACE_URL]
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL,
                                      text=True, encoding="utf-8", errors="ignore")
        m = re.search(r"^colo=([A-Z0-9]+)\s*$", out, re.MULTILINE)
        return m.group(1) if m else "-"
    except Exception:
        return "-"

def score_it(ping_ms: float, dl: float, ul: float) -> float:
    return (dl * 0.75) + (ul * 0.25) - (ping_ms / 50.0)

def parse_targets_text(text: str) -> List[str]:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("#")]
    ips: List[str] = []
    for line in lines:
        if "-" in line and "/" not in line:
            a, b = line.split("-", 1)
            s, e = int(ipaddress.ip_address(a.strip())), int(ipaddress.ip_address(b.strip()))
            if e < s:
                s, e = e, s
            for i in range(s, e + 1):
                ips.append(str(ipaddress.ip_address(i)))
        elif "/" in line:
            net = ipaddress.ip_network(line, strict=False)
            for ip in net.hosts():
                ips.append(str(ip))
        else:
            ipaddress.ip_address(line)
            ips.append(line)

    seen = set()
    out = []
    for ip in ips:
        if ip not in seen:
            seen.add(ip)
            out.append(ip)
    return out

def import_targets_file(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()

def start_xray_with_config(xray_exe: str, cfg_path: str) -> subprocess.Popen:
    cmd = [xray_exe, "run", "-c", cfg_path]
    return subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
    )

def kill_proc_hard(p: subprocess.Popen):
    try:
        if p.poll() is None:
            # aggressive on Windows (kills child tree)
            if is_windows():
                try:
                    subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    return
                except Exception:
                    pass
            p.terminate()
            try:
                p.wait(timeout=0.8)
            except subprocess.TimeoutExpired:
                pass
        if p.poll() is None:
            p.kill()
    except Exception:
        pass

def tls_handshake_ok(ip: str, port: int, sni: str, timeout_s: float = 2.0) -> bool:
    """
    Fast TLS handshake test (direct, no proxy).
    Good for quickly skipping dead IPs before starting xray.
    """
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with socket.create_connection((ip, port), timeout=timeout_s) as sock:
            with ctx.wrap_socket(sock, server_hostname=sni or None) as ssock:
                ssock.do_handshake()
        return True
    except Exception:
        return False

# -------------------- URI parsing --------------------

class UriError(Exception):
    pass

def _b64url_decode(s: str) -> bytes:
    s = s.strip()
    pad = '=' * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)

def parse_vless_uri(uri: str) -> dict:
    # vless://uuid@host:port?param=...#name
    try:
        u = urllib.parse.urlparse(uri)
        if not u.username:
            raise UriError("Missing UUID")
        uuid = u.username
        host = u.hostname
        port = int(u.port or 443)
        q = urllib.parse.parse_qs(u.query)

        security = (q.get("security", ["none"])[0] or "none").lower()

        # v2rayN: type=ws / grpc / xhttp / tcp ...
        net = (q.get("type", ["tcp"])[0] or "tcp").lower()

        path = q.get("path", ["/"])[0] or "/"
        sni = q.get("sni", [q.get("servername", [""])[0]])[0] or ""
        host_hdr = q.get("host", [""])[0] or ""
        fp = q.get("fp", ["chrome"])[0] or "chrome"
        alpn = q.get("alpn", ["h2,http/1.1"])[0]

        # gRPC extras
        service_name = q.get("serviceName", [q.get("servicename", [""])[0]])[0] or ""
        authority = q.get("authority", [""])[0] or ""

        # XHTTP extras
        xhttp_mode = (q.get("mode", ["auto"])[0] or "auto").lower()

        if not host:
            raise UriError("Missing host")

        if net == "grpc" and not service_name and path and path != "/":
            service_name = path.lstrip("/")

        if net == "grpc" and not authority:
            authority = host_hdr or sni or host

        # XHTTP often needs host header; prefer explicit host param
        xhttp_host = host_hdr or sni or host

        return {
            "proto": "vless",
            "uuid": uuid,
            "server_host": host,
            "server_port": port,
            "security": security,
            "network": net,              # ws / grpc / xhttp / tcp...
            "ws_path": path,

            "grpc_service": service_name,
            "grpc_authority": authority,

            "xhttp_path": path,
            "xhttp_host": xhttp_host,
            "xhttp_mode": xhttp_mode,

            "sni": sni if sni else host_hdr if host_hdr else host,
            "host_hdr": host_hdr if host_hdr else (sni if sni else host),
            "fp": fp,
            "alpn": [a.strip() for a in alpn.split(",") if a.strip()] or ["h2", "http/1.1"],
        }
    except Exception as e:
        raise UriError(str(e))

def parse_vmess_uri(uri: str) -> dict:
    # vmess://base64(json)
    try:
        b64 = uri.split("://", 1)[1].strip()
        data = _b64url_decode(b64).decode("utf-8", errors="ignore")
        j = json.loads(data)

        host = j.get("add") or j.get("host") or j.get("sni")
        port = int(j.get("port") or 443)
        uuid = j.get("id")
        net = (j.get("net") or "tcp").lower()

        path = j.get("path") or "/"

        grpc_service = j.get("serviceName") or j.get("grpc_service") or ""
        if net == "grpc" and not grpc_service and path and path != "/":
            grpc_service = str(path).lstrip("/")

        tls = (j.get("tls") or "").lower()
        sni = j.get("sni") or host
        host_hdr = j.get("host") or sni or host
        fp = j.get("fp") or "chrome"

        grpc_authority = j.get("authority") or host_hdr or sni or host

        # XHTTP best-effort
        xhttp_mode = (j.get("mode") or "auto").lower() if isinstance(j.get("mode"), str) else "auto"
        xhttp_host = host_hdr or sni or host

        alpn = j.get("alpn") or "h2,http/1.1"
        alpn_list = [a.strip() for a in str(alpn).split(",") if a.strip()] or ["h2", "http/1.1"]

        if not host or not uuid:
            raise UriError("VMess missing add/id")

        return {
            "proto": "vmess",
            "uuid": uuid,
            "server_host": host,
            "server_port": port,
            "security": "tls" if tls == "tls" else "none",
            "network": net,
            "ws_path": path,

            "grpc_service": grpc_service,
            "grpc_authority": grpc_authority,

            "xhttp_path": path,
            "xhttp_host": xhttp_host,
            "xhttp_mode": xhttp_mode,

            "sni": sni or host,
            "host_hdr": host_hdr or host,
            "fp": fp,
            "alpn": alpn_list,
        }
    except Exception as e:
        raise UriError(str(e))

def parse_uri(uri: str) -> dict:
    uri = uri.strip()
    if uri.lower().startswith("vless://"):
        return parse_vless_uri(uri)
    if uri.lower().startswith("vmess://"):
        return parse_vmess_uri(uri)
    raise UriError("Paste a VLESS or VMess URI (vless:// or vmess://)")

# -------------------- XRAY config builder --------------------

def build_xray_config_from_profile(profile: dict, server_ip: str, socks_port: int) -> dict:
    proto = profile["proto"]
    net = profile["network"]
    sec = profile["security"]

    outbound = {
        "tag": "proxy",
        "protocol": proto,
        "settings": {}
    }

    outbound["settings"]["vnext"] = [{
        "address": server_ip,
        "port": int(profile["server_port"]),
        "users": [{
            "id": profile["uuid"],
            "encryption": "none" if proto == "vless" else "auto",
            "security": "auto"
        }]
    }]

    stream: Dict = {"network": net}

    if sec == "tls":
        stream["security"] = "tls"
        stream["tlsSettings"] = {
            "allowInsecure": True,
            "serverName": profile.get("sni") or "",
            "alpn": profile.get("alpn") or ["h2", "http/1.1"],
            "fingerprint": profile.get("fp", "chrome")
        }

    if net == "ws":
        stream["wsSettings"] = {
            "path": profile.get("ws_path") or "/",
            "headers": {"Host": profile.get("host_hdr") or profile.get("sni") or ""}
        }

    if net == "grpc":
        service = (profile.get("grpc_service") or "").strip()
        authority = (profile.get("grpc_authority") or "").strip()

        grpc_settings = {"serviceName": service, "multiMode": False}
        if authority:
            grpc_settings["authority"] = authority

        stream["grpcSettings"] = grpc_settings

    if net == "xhttp":
        # minimal xhttp settings needed for most links
        xhttp_path = profile.get("xhttp_path") or profile.get("ws_path") or "/"
        xhttp_host = profile.get("xhttp_host") or profile.get("host_hdr") or profile.get("sni") or ""
        xhttp_mode = (profile.get("xhttp_mode") or "auto").lower()

        stream["xhttpSettings"] = {
            "path": xhttp_path,
            "host": xhttp_host,
            "mode": xhttp_mode,
        }

    outbound["streamSettings"] = stream

    cfg = {
        "log": {"loglevel": "warning"},
        "inbounds": [{
            "tag": "socks",
            "listen": "127.0.0.1",
            "port": socks_port,
            "protocol": "mixed",
            "settings": {"auth": "noauth", "udp": True}
        }],
        "outbounds": [
            outbound,
            {"tag": "direct", "protocol": "freedom"},
            {"tag": "block", "protocol": "blackhole"}
        ],
        "routing": {
            "domainStrategy": "AsIs",
            "rules": [{
                "type": "field",
                "port": "0-65535",
                "outboundTag": "proxy"
            }]
        }
    }
    return cfg

# -------------------- UI widgets --------------------

class TopCard(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("TopCard")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(12)

        self.rank = QLabel("①")
        self.rank.setFixedWidth(28)
        self.rank.setAlignment(Qt.AlignCenter)

        self.icon = QLabel("⚡")
        self.icon.setFixedWidth(34)
        self.icon.setAlignment(Qt.AlignCenter)

        self.title = QLabel("-")
        self.title.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self.meta = QLabel("")
        self.meta.setStyleSheet("color:#9bb0ff;")

        left = QVBoxLayout()
        left.addWidget(self.title)
        left.addWidget(self.meta)

        self.score = QLabel("")
        self.score.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.score.setMinimumWidth(90)

        lay.addWidget(self.rank)
        lay.addWidget(self.icon)
        lay.addLayout(left, 1)
        lay.addWidget(self.score)

    def set_data(self, i: int, r: Result):
        ranks = ["①","②","③","④","⑤","⑥","⑦","⑧","⑨","⑩"]
        self.rank.setText(ranks[i] if i < 10 else str(i+1))

        if r.ip == "-":
            self.icon.setText("•")
            self.title.setText("-")
            self.meta.setText("")
            self.score.setText("")
            return

        if r.score > 25:
            self.icon.setText("🚀")
        elif r.score > 15:
            self.icon.setText("⚡")
        else:
            self.icon.setText("🌐")

        self.title.setText(f"{r.ip}   •   {r.status}")
        dl = "-" if r.dl_mbps is None else f"{r.dl_mbps:.2f}"
        ul = "-" if r.ul_mbps is None else f"{r.ul_mbps:.2f}"
        self.meta.setText(f"📍 {r.colo}   |   🏓 {r.ping_ms:.0f}ms   |   ⬇ {dl}   |   ⬆ {ul}")
        self.score.setText(f"{r.score:.2f}")

# -------------------- Worker Threads --------------------

class ProcRegistry:
    def __init__(self):
        self.lock = threading.Lock()
        self.procs: Dict[int, subprocess.Popen] = {}

    def set(self, wid: int, p: Optional[subprocess.Popen]):
        with self.lock:
            if p is None:
                self.procs.pop(wid, None)
            else:
                self.procs[wid] = p

    def kill_all(self):
        with self.lock:
            procs = list(self.procs.values())
            self.procs.clear()
        for p in procs:
            kill_proc_hard(p)

class ScannerWorker:
    def __init__(self, wid: int, ip_q: queue.Queue, out_q: queue.Queue, stop_evt: threading.Event,
                 xray_exe: str, profile: dict, socks_port: int,
                 ping_timeout_ms: int, dl_bytes: int, ul_bytes: int,
                 curl_timeout: int, colo_timeout: int,
                 min_dl: float, min_ul: float,
                 proc_reg: ProcRegistry,
                 upload_url: str,
                 quick_tls: bool):
        self.wid = wid
        self.ip_q = ip_q
        self.out_q = out_q
        self.stop_evt = stop_evt
        self.xray_exe = xray_exe
        self.profile = profile
        self.socks_port = socks_port
        self.ping_timeout_ms = ping_timeout_ms
        self.dl_bytes = dl_bytes
        self.ul_bytes = ul_bytes
        self.curl_timeout = curl_timeout
        self.colo_timeout = colo_timeout
        self.min_dl = min_dl
        self.min_ul = min_ul
        self.proc_reg = proc_reg
        self.upload_url = upload_url
        self.quick_tls = quick_tls

    def run(self):
        while not self.stop_evt.is_set():
            try:
                ip = self.ip_q.get_nowait()
            except queue.Empty:
                return

            rtt = ping_ip_windows(ip, self.ping_timeout_ms)
            if rtt is None or self.stop_evt.is_set():
                continue

            # quick TLS handshake (skip early)
            if self.quick_tls and (self.profile.get("security") == "tls"):
                sni = self.profile.get("sni") or self.profile.get("host_hdr") or self.profile.get("server_host") or ""
                port = int(self.profile.get("server_port") or 443)
                if not tls_handshake_ok(ip, port, sni, timeout_s=2.0):
                    continue

            cfg = build_xray_config_from_profile(self.profile, ip, self.socks_port)

            with tempfile.TemporaryDirectory(prefix="cfui_") as td:
                cfg_path = os.path.join(td, "xray.json")
                with open(cfg_path, "w", encoding="utf-8") as f:
                    json.dump(cfg, f, ensure_ascii=False, indent=2)

                p = start_xray_with_config(self.xray_exe, cfg_path)
                self.proc_reg.set(self.wid, p)

                time.sleep(0.85)
                if self.stop_evt.is_set():
                    kill_proc_hard(p); self.proc_reg.set(self.wid, None); return

                if p.poll() is not None:
                    self.proc_reg.set(self.wid, None)
                    continue

                dl = curl_download_mbps(self.socks_port, self.dl_bytes, self.curl_timeout)
                if self.stop_evt.is_set():
                    kill_proc_hard(p); self.proc_reg.set(self.wid, None); return

                ul = None
                if self.ul_bytes and self.ul_bytes > 0:
                    ul = curl_upload_mbps_file(self.socks_port, self.ul_bytes, self.curl_timeout, self.upload_url)

                colo = "-"
                if (dl is not None) or (ul is not None):
                    colo = curl_colo(self.socks_port, self.colo_timeout)

                kill_proc_hard(p)
                self.proc_reg.set(self.wid, None)

                # hide pure fails (no noise)
                if dl is None and ul is None:
                    continue

                dl_ok = (dl is not None) and (dl >= self.min_dl)
                ul_ok = (ul is not None) and (ul >= self.min_ul)

                if dl is not None and ul is None:
                    status = "DL-only"
                elif ul is not None and dl is None:
                    status = "UL-only"
                elif dl_ok and ul_ok:
                    status = "GOOD"
                else:
                    status = "Below"

                if dl is not None and ul is not None:
                    score = score_it(rtt, dl, ul)
                elif dl is not None:
                    score = (dl * 0.7) - (rtt / 60.0)
                else:
                    score = (ul * 0.7) - (rtt / 60.0)

                self.out_q.put(Result(ip, rtt, dl, ul, colo, score, status))

# -------------------- Main UI --------------------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("EzAccess CloudFlare Scanner (Programmed By MacanDev | TG Channel: @EzAccess1)")
        self.resize(1320, 860)

        self.stop_evt = threading.Event()
        self.ip_q = queue.Queue()
        self.out_q = queue.Queue()
        self.threads: List[threading.Thread] = []
        self.proc_reg = ProcRegistry()

        self.all_display: List[Result] = []
        self.good_pool: List[Result] = []
        self.total = 0

        self.good_save_path: Optional[str] = None

        self._build_ui()
        self._apply_theme()
        self._apply_adaptive_font()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._drain_results)
        self.timer.start(150)

        self.top_timer = QTimer(self)
        self.top_timer.timeout.connect(self._refresh_top10)
        self.top_timer.start(500)

    def _apply_adaptive_font(self):
        screen = QApplication.primaryScreen()
        if not screen:
            return
        w = screen.size().width()
        base = 10
        if w >= 3000:
            base = 12
        elif w >= 2000:
            base = 11
        self.setFont(QFont("Segoe UI", base))

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setSpacing(10)
        outer.setContentsMargins(12, 12, 12, 12)

        top = QGridLayout()
        top.setHorizontalSpacing(10)
        top.setVerticalSpacing(8)

        self.exe_path = QLineEdit("xray.exe")
        btn_exe  = QPushButton("Browse xray.exe")
        btn_exe.clicked.connect(self._pick_exe)

        self.uri_box = QTextEdit()
        self.uri_box.setPlaceholderText("Paste VLESS or VMess URI here (vless://... or vmess://...)")
        self.uri_box.setFixedHeight(92)

        self.targets = QLineEdit("188.114.96.0/20")
        btn_targets_file = QPushButton("Import targets from file")
        btn_targets_file.clicked.connect(self._import_targets)

        self.shuffle = QCheckBox("Shuffle")
        self.shuffle.setChecked(True)

        self.limit = QSpinBox(); self.limit.setRange(0, 10_000_000); self.limit.setValue(254)
        self.workers = QSpinBox(); self.workers.setRange(1, 64); self.workers.setValue(6)
        self.socks_base = QSpinBox(); self.socks_base.setRange(1024, 65500); self.socks_base.setValue(19080)

        self.min_dl = QDoubleSpinBox(); self.min_dl.setRange(0, 10_000); self.min_dl.setValue(10.0); self.min_dl.setDecimals(2)
        self.min_ul = QDoubleSpinBox(); self.min_ul.setRange(0, 10_000); self.min_ul.setValue(2.0);  self.min_ul.setDecimals(2)

        self.show_partial = QCheckBox("Show partial (DL-only / UL-only)")
        self.show_partial.setChecked(True)

        self.show_below = QCheckBox("Show below-threshold")
        self.show_below.setChecked(False)

        self.relaxed_good = QCheckBox("Relaxed GOOD (DL-only or UL-only counts as GOOD)")
        self.relaxed_good.setChecked(True)

        self.quick_tls = QCheckBox("Quick TLS handshake before Xray")
        self.quick_tls.setChecked(True)

        self.ul_bytes = QSpinBox(); self.ul_bytes.setRange(100_000, 50_000_000); self.ul_bytes.setValue(3_000_000)
        self.dl_bytes = QSpinBox(); self.dl_bytes.setRange(100_000, 200_000_000); self.dl_bytes.setValue(20_000_000)

        self.upload_url = QLineEdit("https://speed.cloudflare.com/__up")
        self.upload_url.setPlaceholderText("Upload test URL (for UL test), e.g. https://speed.cloudflare.com/__up")

        self.topn = QSpinBox(); self.topn.setRange(1, 1000); self.topn.setValue(30)

        self.save_good = QCheckBox("Save GOOD pool realtime to file")
        self.save_good.setChecked(False)
        btn_pick_save = QPushButton("Pick save file")
        btn_pick_save.clicked.connect(self._pick_save_file)

        self.start_btn = QPushButton("Start Scan")
        self.stop_btn  = QPushButton("Stop Safely")
        self.stop_btn.setEnabled(False)
        self.start_btn.clicked.connect(self.start_scan)
        self.stop_btn.clicked.connect(self.stop_scan_safely)

        row = 0
        top.addWidget(QLabel("XRAY exe:"), row, 0); top.addWidget(self.exe_path, row, 1); top.addWidget(btn_exe, row, 2)
        row += 1
        top.addWidget(QLabel("VLESS/VMess URI:"), row, 0); top.addWidget(self.uri_box, row, 1, 1, 2)
        row += 1
        top.addWidget(QLabel("Targets (CIDR/range/IP):"), row, 0); top.addWidget(self.targets, row, 1); top.addWidget(btn_targets_file, row, 2)
        row += 1
        top.addWidget(self.shuffle, row, 2)
        top.addWidget(QLabel("Limit:"), row, 0); top.addWidget(self.limit, row, 1); top.addWidget(QLabel("0 = all"), row, 2, Qt.AlignRight)
        row += 1
        top.addWidget(QLabel("Workers:"), row, 0); top.addWidget(self.workers, row, 1); top.addWidget(self.show_partial, row, 2)
        row += 1
        top.addWidget(QLabel("SOCKS base port:"), row, 0); top.addWidget(self.socks_base, row, 1); top.addWidget(self.quick_tls, row, 2)
        row += 1
        top.addWidget(QLabel("DL bytes:"), row, 0); top.addWidget(self.dl_bytes, row, 1); top.addWidget(self.show_below, row, 2)
        row += 1
        top.addWidget(QLabel("UL bytes:"), row, 0); top.addWidget(self.ul_bytes, row, 1); top.addWidget(self.relaxed_good, row, 2)
        row += 1
        top.addWidget(QLabel("Upload test URL:"), row, 0); top.addWidget(self.upload_url, row, 1, 1, 2)
        row += 1
        top.addWidget(QLabel("Min DL (Mbps):"), row, 0); top.addWidget(self.min_dl, row, 1)
        row += 1
        top.addWidget(QLabel("Min UL (Mbps):"), row, 0); top.addWidget(self.min_ul, row, 1)
        row += 1
        top.addWidget(self.save_good, row, 0); top.addWidget(btn_pick_save, row, 1)
        row += 1
        top.addWidget(QLabel("Export top N (v2rayN URIs):"), row, 0); top.addWidget(self.topn, row, 1)
        row += 1
        top.addWidget(self.start_btn, row, 1); top.addWidget(self.stop_btn, row, 2)

        outer.addLayout(top)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        outer.addWidget(self.progress)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)

        left_wrap = QWidget()
        left_lay = QVBoxLayout(left_wrap)
        left_lay.setContentsMargins(0, 0, 0, 0)
        left_lay.setSpacing(8)
        left_lay.addWidget(QLabel("🏆 Top 10 (Realtime)"))

        cards_container = QWidget()
        cards_lay = QVBoxLayout(cards_container)
        cards_lay.setContentsMargins(0, 0, 0, 0)
        cards_lay.setSpacing(8)

        self.cards: List[TopCard] = []
        for _ in range(10):
            c = TopCard()
            self.cards.append(c)
            cards_lay.addWidget(c)
        cards_lay.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(cards_container)
        left_lay.addWidget(scroll, 1)

        right_wrap = QWidget()
        right_lay = QVBoxLayout(right_wrap)
        right_lay.setContentsMargins(0, 0, 0, 0)
        right_lay.setSpacing(8)
        right_lay.addWidget(QLabel("Results (only DL/UL outcomes, no fail spam)"))

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["IP", "Status", "Ping", "DL", "UL", "Colo", "Score"])
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        right_lay.addWidget(self.table, 1)

        splitter.addWidget(left_wrap)
        splitter.addWidget(right_wrap)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([360, 920])

        outer.addWidget(splitter, 1)

        btm = QHBoxLayout()
        self.export_btn = QPushButton("Export v2rayN URIs (Top N)")
        self.export_btn.clicked.connect(self.export_top_v2rayn_only)
        btm.addWidget(self.export_btn)

        self.status = QLabel("Ready.")
        self.status.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        btm.addWidget(self.status, 1)
        outer.addLayout(btm)

    def _apply_theme(self):
        self.setStyleSheet("""
            QMainWindow { background: #0b0f19; }
            QLabel { color: #e7ecff; }
            QLineEdit, QSpinBox, QDoubleSpinBox, QTextEdit {
                background: #101a2b;
                color: #e7ecff;
                border: 1px solid #23324e;
                border-radius: 10px;
                padding: 6px 10px;
            }
            QCheckBox { color: #e7ecff; }
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                            stop:0 #3b82f6, stop:1 #22c55e);
                color: #07101f;
                font-weight: 800;
                border: 0px;
                border-radius: 12px;
                padding: 10px 14px;
            }
            QPushButton:disabled {
                background: #24324f;
                color: #7f8aa5;
            }
            QProgressBar {
                background: #101a2b;
                border: 1px solid #23324e;
                border-radius: 10px;
                color: #e7ecff;
                text-align: center;
                height: 18px;
            }
            QProgressBar::chunk {
                border-radius: 10px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                            stop:0 #a855f7, stop:1 #22c55e);
            }
            QTableWidget {
                background: #0f172a;
                color: #e7ecff;
                gridline-color: #23324e;
                border: 1px solid #23324e;
                border-radius: 12px;
            }
            QHeaderView::section {
                background: #101a2b;
                color: #a5b4fc;
                border: 0px;
                padding: 8px;
                font-weight: 800;
            }
            QFrame#TopCard {
                background: #101a2b;
                border: 1px solid #23324e;
                border-radius: 14px;
            }
        """)

    def _pick_exe(self):
        p, _ = QFileDialog.getOpenFileName(self, "Select xray.exe", "", "EXE (*.exe)")
        if p:
            self.exe_path.setText(p)

    def _import_targets(self):
        p, _ = QFileDialog.getOpenFileName(self, "Select targets file", "", "Text (*.txt *.list *.conf *.cfg);;All (*.*)")
        if not p:
            return
        try:
            txt = import_targets_file(p)
            self.targets.setText(txt.strip())
        except Exception as e:
            QMessageBox.critical(self, "Import error", str(e))

    def _pick_save_file(self):
        p, _ = QFileDialog.getSaveFileName(self, "Save GOOD pool as", "good_pool.txt", "Text (*.txt)")
        if p:
            self.good_save_path = p

    def _get_profile_or_error(self) -> Optional[dict]:
        uri = self.uri_box.toPlainText().strip()
        if not uri:
            QMessageBox.critical(self, "Error", "Paste a VLESS or VMess URI first.")
            return None
        try:
            profile = parse_uri(uri)
            if profile.get("network") not in ("ws", "grpc", "xhttp"):
                QMessageBox.warning(self, "Warning", "Transport is not WS/gRPC/XHTTP.")
            if profile.get("security") != "tls":
                QMessageBox.warning(self, "Warning", "URI is not TLS. CDN IP usage usually needs TLS+SNI.")
            if profile.get("network") == "grpc":
                if not (profile.get("grpc_service") or "").strip():
                    QMessageBox.warning(self, "Warning", "gRPC without serviceName often fails.")
            if profile.get("network") == "xhttp":
                # path+host recommended
                if not (profile.get("xhttp_path") or "").strip():
                    QMessageBox.warning(self, "Warning", "XHTTP path is empty (usually required).")
            return profile
        except Exception as e:
            QMessageBox.critical(self, "URI Error", str(e))
            return None

    def start_scan(self):
        exe = self.exe_path.text().strip()
        if not os.path.exists(exe) and shutil.which(exe) is None:
            QMessageBox.critical(self, "Error", "xray.exe not found (path or same folder).")
            return

        profile = self._get_profile_or_error()
        if not profile:
            return

        try:
            ips = parse_targets_text(self.targets.text())
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Bad targets:\n{e}")
            return

        if self.shuffle.isChecked():
            random.shuffle(ips)

        lim = self.limit.value()
        if lim > 0:
            ips = ips[:lim]

        if not ips:
            QMessageBox.critical(self, "Error", "No IPs to test.")
            return

        self.stop_evt.clear()
        self.proc_reg.kill_all()

        self.all_display.clear()
        self.good_pool.clear()
        self.table.setRowCount(0)

        self.total = len(ips)
        self.progress.setValue(0)
        self.status.setText("Scanning...")

        self.ip_q = queue.Queue()
        self.out_q = queue.Queue()
        for ip in ips:
            self.ip_q.put(ip)

        workers = self.workers.value()
        socks_base = self.socks_base.value()

        ping_timeout_ms = 900
        dl_bytes = int(self.dl_bytes.value())
        ul_bytes = int(self.ul_bytes.value())

        curl_timeout = 20
        colo_timeout = 10

        min_dl = float(self.min_dl.value())
        min_ul = float(self.min_ul.value())

        upload_url = self.upload_url.text().strip()
        if not (upload_url.lower().startswith("http://") or upload_url.lower().startswith("https://")):
            QMessageBox.critical(self, "Error", "Upload URL must start with http:// or https://")
            return

        self.threads = []
        for wid in range(workers):
            socks_port = socks_base + wid
            w = ScannerWorker(
                wid=wid, ip_q=self.ip_q, out_q=self.out_q, stop_evt=self.stop_evt,
                xray_exe=exe, profile=profile, socks_port=socks_port,
                ping_timeout_ms=ping_timeout_ms,
                dl_bytes=dl_bytes, ul_bytes=ul_bytes,
                curl_timeout=curl_timeout, colo_timeout=colo_timeout,
                min_dl=min_dl, min_ul=min_ul,
                proc_reg=self.proc_reg,
                upload_url=upload_url,
                quick_tls=self.quick_tls.isChecked()
            )
            t = threading.Thread(target=w.run, daemon=True)
            self.threads.append(t)
            t.start()

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

    def stop_scan_safely(self):
        self.stop_evt.set()
        self.proc_reg.kill_all()
        self.status.setText("Stopped safely (XRAY procs killed).")
        self.stop_btn.setEnabled(False)
        self.start_btn.setEnabled(True)

    def _append_good_to_file(self):
        if not self.save_good.isChecked():
            return
        if not self.good_save_path:
            # auto-pick default in cwd
            self.good_save_path = os.path.join(os.getcwd(), "good_pool.txt")
        try:
            lines = []
            for r in sorted(self.good_pool, key=lambda x: x.score, reverse=True):
                dl = "-" if r.dl_mbps is None else f"{r.dl_mbps:.2f}"
                ul = "-" if r.ul_mbps is None else f"{r.ul_mbps:.2f}"
                lines.append(f"{r.ip}\t{r.status}\tping={r.ping_ms:.0f}ms\tdl={dl}\tul={ul}\tcolo={r.colo}\tscore={r.score:.2f}")
            with open(self.good_save_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
        except Exception:
            pass

    def _drain_results(self):
        if self.total > 0:
            remaining = self.ip_q.qsize() if self.ip_q else 0
            done = self.total - remaining
            pct = int((done / self.total) * 100)
            self.progress.setValue(max(0, min(100, pct)))

        changed = False
        while True:
            try:
                r: Result = self.out_q.get_nowait()
            except queue.Empty:
                break

            relaxed = self.relaxed_good.isChecked()
            is_good = (r.status == "GOOD") or (relaxed and r.status in ("DL-only", "UL-only"))

            if r.status == "Below" and not self.show_below.isChecked():
                continue
            if r.status in ("DL-only", "UL-only") and not self.show_partial.isChecked():
                continue

            self.all_display.append(r)
            self._add_row(r)
            changed = True

            if is_good:
                self.good_pool.append(r)
                self._append_good_to_file()

        if changed:
            self.status.setText(f"GOOD(pool): {len(self.good_pool)} | shown: {len(self.all_display)} | {self.progress.value()}%")

        if not self.start_btn.isEnabled():
            alive = any(t.is_alive() for t in self.threads)
            if (not alive) and self.ip_q.qsize() == 0:
                self.stop_btn.setEnabled(False)
                self.start_btn.setEnabled(True)
                self.status.setText(f"Done. GOOD(pool): {len(self.good_pool)} | shown: {len(self.all_display)}")

    def _add_row(self, r: Result):
        row = self.table.rowCount()
        self.table.insertRow(row)

        def put(col, txt):
            it = QTableWidgetItem(txt)
            it.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, col, it)

        put(0, r.ip)
        put(1, r.status)
        put(2, f"{r.ping_ms:.0f}")
        put(3, "-" if r.dl_mbps is None else f"{r.dl_mbps:.2f}")
        put(4, "-" if r.ul_mbps is None else f"{r.ul_mbps:.2f}")
        put(5, r.colo)
        put(6, f"{r.score:.2f}")

        self.table.sortItems(6, Qt.DescendingOrder)

    def _refresh_top10(self):
        if not self.good_pool:
            for i, c in enumerate(self.cards):
                c.set_data(i, Result("-", 0, None, None, "-", 0.0, ""))
            return

        top = sorted(self.good_pool, key=lambda x: x.score, reverse=True)[:10]
        for i in range(10):
            if i < len(top):
                self.cards[i].set_data(i, top[i])
            else:
                self.cards[i].set_data(i, Result("-", 0, None, None, "-", 0.0, ""))

    def export_top_v2rayn_only(self):
        uri = self.uri_box.toPlainText().strip()
        if not uri:
            QMessageBox.information(self, "No URI", "Paste URI first.")
            return
        if not self.good_pool:
            QMessageBox.information(self, "No results", "No results in GOOD pool yet.")
            return

        topn = int(self.topn.value())
        pool_sorted = sorted(self.good_pool, key=lambda x: x.score, reverse=True)[:topn]

        out_lines = []
        if uri.lower().startswith("vless://"):
            base = urllib.parse.urlparse(uri)
            q = urllib.parse.parse_qs(base.query)
            qstr = urllib.parse.urlencode({k: v[0] for k, v in q.items()}, doseq=False)
            frag = f"#{base.fragment}" if base.fragment else ""
            for r in pool_sorted:
                out_lines.append(
                    f"vless://{base.username}@{r.ip}:{base.port or 443}?{qstr}{frag}-score-{r.score:.2f}-{r.status}"
                )
        else:
            # vmess
            try:
                raw = _b64url_decode(uri.split("://", 1)[1]).decode("utf-8", errors="ignore")
                j = json.loads(raw)
                for r in pool_sorted:
                    jj = dict(j)
                    jj["add"] = r.ip
                    name = jj.get("ps","") or "vmess"
                    jj["ps"] = f"{name}-{r.ip}-score-{r.score:.2f}-{r.status}"
                    b = base64.b64encode(json.dumps(jj, ensure_ascii=False).encode("utf-8")).decode("utf-8")
                    out_lines.append("vmess://" + b)
            except Exception as e:
                QMessageBox.critical(self, "Export error", str(e))
                return

        p, _ = QFileDialog.getSaveFileName(self, "Save exported URIs", "top_uris.txt", "Text (*.txt)")
        if not p:
            return
        try:
            with open(p, "w", encoding="utf-8") as f:
                f.write("\n".join(out_lines) + "\n")
            QMessageBox.information(self, "Exported", f"Saved: {p}")
        except Exception as e:
            QMessageBox.critical(self, "Export error", str(e))

def main():
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()