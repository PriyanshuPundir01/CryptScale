from __future__ import annotations

import argparse
import hashlib
import hmac
import math
import os
import re
import secrets
import string
import sys
import time
from dataclasses import dataclass
from datetime import timedelta
from enum import Enum
from functools import wraps
from typing import Dict, List, Optional

from dotenv import load_dotenv
from flask import (
    Flask,
    jsonify,
    render_template,
    request,
    session,
    redirect,
    url_for,
    abort,
)
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import werkzeug
if not hasattr(werkzeug, "__version__"):
    try:
        import importlib.metadata
        werkzeug.__version__ = importlib.metadata.version("werkzeug")
    except Exception:
        werkzeug.__version__ = "3.0.0"
from werkzeug.security import generate_password_hash, check_password_hash

try:
    import requests as _req
    _REQUESTS_OK = True
except ImportError:
    _REQUESTS_OK = False

load_dotenv()

base_dir = os.path.abspath(os.path.dirname(__file__))
templates_dir = os.path.join(base_dir, "templates")
static_dir = os.path.join(base_dir, "static")

app = Flask(
    __name__,
    template_folder=templates_dir,
    static_folder=static_dir
)

app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)

debug_mode = os.environ.get("FLASK_DEBUG", "0").lower() in ("1", "true", "yes")
app.config["DEBUG"] = debug_mode
app.config["TESTING"] = False
app.config["MAX_CONTENT_LENGTH"] = int(os.environ.get("MAX_CONTENT_LENGTH", 1024 * 1024))

app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("SESSION_COOKIE_SECURE", "0").lower() in ("1", "true", "yes")
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(minutes=int(os.environ.get("SESSION_LIFETIME_MINUTES", "30")))

allowed_origins_env = os.environ.get("ALLOWED_ORIGINS", "")
allowed_origins = [o.strip() for o in allowed_origins_env.split(",") if o.strip()]
if not allowed_origins:
    allowed_origins = ["http://127.0.0.1:5001", "http://localhost:5001"]

CORS(
    app,
    resources={r"/api/*": {"origins": allowed_origins}},
    supports_credentials=False,
    methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"]
)

limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["300 per minute", "2000 per hour"],
    storage_uri=os.environ.get("RATELIMIT_STORAGE_URI", "memory://")
)

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
_env_admin_hash = os.environ.get("ADMIN_PASSWORD_HASH")
if _env_admin_hash:
    ADMIN_PASSWORD_HASH = _env_admin_hash
else:
    _raw_admin_pwd = os.environ.get("ADMIN_PASSWORD", "CryptScale#Admin2026")
    ADMIN_PASSWORD_HASH = generate_password_hash(_raw_admin_pwd, method="pbkdf2:sha256:600000")

COMMON_PASSWORDS: set[str] = {
    "password", "password1", "password123", "123456", "12345678", "123456789",
    "qwerty", "qwerty123", "abc123", "letmein", "monkey", "iloveyou",
    "admin", "welcome", "login", "passw0rd", "master", "dragon",
    "sunshine", "princess", "football", "shadow", "superman", "michael",
    "jessica", "batman", "trustno1", "baseball", "hockey", "killer",
    "george", "jordan", "harley", "ranger", "dakota", "test123",
    "1q2w3e4r", "111111", "1234qwer", "pass1234", "pass123", "starwars",
    "mustang", "access", "hello", "matrix", "hunter", "charlie", "default",
    "iloveyou1", "secret", "trustme", "freedom", "superman1"
}

KEYBOARD_PATTERNS: list[str] = [
    "qwerty", "qwertyuiop", "asdfgh", "asdfghjkl",
    "zxcvbn", "zxcvbnm", "1234567890", "0987654321",
    "abcdef", "abcdefgh", "1qaz2wsx", "123qwe",
]

AMBIGUOUS_CHARS = set("Il1O0`~'\"|/\\")

class Strength(Enum):
    CRITICAL    = ("CRITICAL",    "#ff3b5c", 0, "rgba(255, 59, 92, 0.25)", "Very Vulnerable")
    WEAK        = ("WEAK",        "#ff7a3d", 1, "rgba(255, 122, 61, 0.25)", "Weak Defense")
    MODERATE    = ("MODERATE",    "#ffb800", 2, "rgba(255, 184, 0, 0.25)", "Fair Security")
    STRONG      = ("STRONG",      "#00e599", 3, "rgba(0, 229, 153, 0.25)", "Strong Armor")
    VERY_STRONG = ("VERY STRONG", "#00f0ff", 4, "rgba(0, 240, 255, 0.3)",  "Cryptographically Solid")

    def __init__(self, label: str, color: str, tier: int, glow: str, subtitle: str):
        self.label = label
        self.color = color
        self.tier  = tier
        self.glow  = glow
        self.subtitle = subtitle

@dataclass
class Criteria:
    len_8:       bool = False
    len_12:      bool = False
    len_16:      bool = False
    has_lower:   bool = False
    has_upper:   bool = False
    has_digit:   bool = False
    has_special: bool = False
    not_common:  bool = True
    no_pattern:  bool = True

    def to_dict(self) -> dict:
        return {
            "len_8":       self.len_8,
            "len_12":      self.len_12,
            "len_16":      self.len_16,
            "has_lower":   self.has_lower,
            "has_upper":   self.has_upper,
            "has_digit":   self.has_digit,
            "has_special": self.has_special,
            "not_common":  self.not_common,
            "no_pattern":  self.no_pattern,
        }

@dataclass
class Assessment:
    strength:     Strength
    score:        int
    max_score:    int
    entropy_bits: float
    crack_time:   str
    crack_time_online: str
    criteria:     Criteria
    composition:  Dict[str, int]
    feedback:     List[str]
    is_common:    bool = False
    has_pattern:  bool = False

    def to_dict(self) -> dict:
        return {
            "rating":       self.strength.label,
            "subtitle":     self.strength.subtitle,
            "color":        self.strength.color,
            "glow":         self.strength.glow,
            "tier":         self.strength.tier,
            "score":        self.score,
            "max_score":    self.max_score,
            "score_pct":    int((self.score / self.max_score) * 100),
            "entropy":      round(self.entropy_bits, 1),
            "crack_time":   self.crack_time,
            "crack_time_online": self.crack_time_online,
            "criteria":     self.criteria.to_dict(),
            "composition":  self.composition,
            "feedback":     self.feedback,
            "is_common":    self.is_common,
            "has_pattern":  self.has_pattern,
        }

def sanitize_input(val: any, max_length: int = 1024) -> str:
    if val is None:
        return ""
    if not isinstance(val, str):
        val = str(val)
    val = val.replace("\x00", "")
    if len(val) > max_length:
        val = val[:max_length]
    return val

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("is_admin") or session.get("user") != ADMIN_USERNAME:
            if request.path.startswith("/api/") or request.path.startswith("/admin/api/") or request.is_json:
                return jsonify({"error": "Unauthorized. Admin privileges required.", "status": 401}), 401
            return redirect(url_for("admin_login", next=request.path))
        return f(*args, **kwargs)
    return decorated_function

def generate_csrf_token() -> str:
    if "_csrf_token" not in session:
        session["_csrf_token"] = secrets.token_hex(32)
    return session["_csrf_token"]

@app.context_processor
def inject_csrf_token():
    return dict(csrf_token=generate_csrf_token())

@app.after_request
def add_security_headers(response):
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "font-src 'self' https://fonts.gstatic.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "script-src 'self'; "
        "img-src 'self' data:; "
        "connect-src 'self' https://api.pwnedpasswords.com; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self';"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=(), payment=()"
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
    if not app.debug:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers.pop("Server", None)
    return response

@app.errorhandler(429)
def ratelimit_handler(e):
    if request.path.startswith("/api/"):
        return jsonify({
            "error": "Rate limit exceeded. Please wait before making more requests.",
            "status": 429
        }), 429
    return render_template("429.html"), 429

@app.errorhandler(400)
def bad_request_handler(e):
    if request.path.startswith("/api/"):
        return jsonify({"error": "Bad request", "status": 400}), 400
    return render_template("429.html"), 400

@app.errorhandler(404)
def not_found_handler(e):
    if request.path.startswith("/api/"):
        return jsonify({"error": "Resource not found", "status": 404}), 404
    return redirect(url_for("home"))

@app.errorhandler(500)
def internal_error_handler(e):
    if request.path.startswith("/api/"):
        return jsonify({"error": "An internal error occurred", "status": 500}), 500
    return redirect(url_for("home"))

def calculate_entropy(password: str) -> float:
    if not password:
        return 0.0
    pool = 0
    if re.search(r"[a-z]", password): pool += 26
    if re.search(r"[A-Z]", password): pool += 26
    if re.search(r"\d",    password): pool += 10
    if re.search(f"[{re.escape(string.punctuation)}]", password): pool += 32
    if re.search(r"\s",    password): pool += 1
    return len(password) * math.log2(pool) if pool else 0.0

def estimate_crack_time(entropy_bits: float) -> str:
    if entropy_bits <= 0:
        return "Instantly"
    try:
        seconds = (2.0 ** min(entropy_bits, 128)) / 10_000_000_000.0
    except OverflowError:
        return "Centuries+"

    if seconds < 0.001:       return "< 1 millisecond"
    if seconds < 1:           return f"~{int(seconds * 1000)} ms"
    if seconds < 60:          return f"~{int(seconds)} seconds"
    if seconds < 3600:        return f"~{int(seconds / 60)} minutes"
    if seconds < 86400:       return f"~{int(seconds / 3600)} hours"
    if seconds < 31536000:    return f"~{int(seconds / 86400)} days"
    if seconds < 3153600000:  return f"~{int(seconds / 31536000):,} years"
    return "Centuries+"

def estimate_online_crack_time(entropy_bits: float) -> str:
    if entropy_bits <= 0:
        return "Instantly"
    try:
        seconds = (2.0 ** min(entropy_bits, 128)) / 100.0
    except OverflowError:
        return "Centuries+"

    if seconds < 60:          return f"~{int(seconds)} seconds"
    if seconds < 3600:        return f"~{int(seconds / 60)} minutes"
    if seconds < 86400:       return f"~{int(seconds / 3600)} hours"
    if seconds < 31536000:    return f"~{int(seconds / 86400)} days"
    if seconds < 3153600000:  return f"~{int(seconds / 31536000):,} years"
    return "Centuries+"

def apply_realistic_crack_override(
    entropy_bits: float,
    is_common: bool,
    has_pattern: bool,
) -> tuple[str, str]:
    if is_common:
        return "< 1 second (dictionary)", "< 1 second (dictionary)"

    if has_pattern:
        effective_bits = min(entropy_bits, 17.0)
        gpu  = estimate_crack_time(effective_bits)
        web  = estimate_online_crack_time(effective_bits)
        return gpu, web

    return estimate_crack_time(entropy_bits), estimate_online_crack_time(entropy_bits)

def detect_pattern(password: str) -> bool:
    lower = password.lower()
    if re.search(r"(.)\1{2,}", lower):
        return True
    for pat in KEYBOARD_PATTERNS:
        if pat in lower or pat[::-1] in lower:
            return True
    return False

def generate_secure_password(
    length: int = 16,
    include_upper: bool = True,
    include_lower: bool = True,
    include_digits: bool = True,
    include_symbols: bool = True,
    exclude_ambiguous: bool = False
) -> str:
    length = max(8, min(20, length))

    lowers = string.ascii_lowercase
    uppers = string.ascii_uppercase
    digits = string.digits
    symbols = "!@#$%^&*()-_=+[]{}<>?"

    if exclude_ambiguous:
        lowers = "".join(c for c in lowers if c not in AMBIGUOUS_CHARS)
        uppers = "".join(c for c in uppers if c not in AMBIGUOUS_CHARS)
        digits = "".join(c for c in digits if c not in AMBIGUOUS_CHARS)
        symbols = "".join(c for c in symbols if c not in AMBIGUOUS_CHARS)

    pool = ""
    guaranteed = []

    if include_lower and lowers:
        pool += lowers
        guaranteed.append(secrets.choice(lowers))
    if include_upper and uppers:
        pool += uppers
        guaranteed.append(secrets.choice(uppers))
    if include_digits and digits:
        pool += digits
        guaranteed.append(secrets.choice(digits))
    if include_symbols and symbols:
        pool += symbols
        guaranteed.append(secrets.choice(symbols))

    if not pool:
        pool = string.ascii_letters + string.digits + "!@#$%^&*"
        guaranteed = [secrets.choice(pool)]

    filler_count = max(0, length - len(guaranteed))
    filler = [secrets.choice(pool) for _ in range(filler_count)]
    chars = guaranteed + filler

    for i in range(len(chars) - 1, 0, -1):
        j = secrets.randbelow(i + 1)
        chars[i], chars[j] = chars[j], chars[i]

    return "".join(chars[:length])

def check_hibp_database(password: str) -> dict:
    if not password:
        return {"breached": None, "count": 0, "error": "No password provided"}
    if not _REQUESTS_OK:
        return {"breached": None, "count": 0, "error": "requests module not installed"}

    sha1 = hashlib.sha1(password.encode("utf-8")).hexdigest().upper()
    prefix, suffix = sha1[:5], sha1[5:]

    headers = {"User-Agent": "CryptScale-SecurityEngine/2.0"}
    hibp_key = os.environ.get("HIBP_API_KEY")
    if hibp_key:
        headers["hibp-api-key"] = hibp_key

    try:
        resp = _req.get(
            f"https://api.pwnedpasswords.com/range/{prefix}",
            headers=headers,
            timeout=5,
        )
        if resp.status_code == 200:
            for line in resp.text.splitlines():
                if ":" in line:
                    h, count = line.split(":")
                    if h.strip() == suffix:
                        return {"breached": True, "count": int(count.strip())}
            return {"breached": False, "count": 0}
        return {"breached": None, "count": 0, "error": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"breached": None, "count": 0, "error": "Breach database service unreachable"}

def assess_password(password: str) -> Assessment:
    if not password:
        return Assessment(
            strength=Strength.CRITICAL,
            score=0,
            max_score=8,
            entropy_bits=0.0,
            crack_time="Instantly",
            crack_time_online="Instantly",
            criteria=Criteria(),
            composition={"lower": 0, "upper": 0, "digits": 0, "symbols": 0, "length": 0},
            feedback=["Type a password or generate one to begin complexity analysis."],
        )

    c_lower = len(re.findall(r"[a-z]", password))
    c_upper = len(re.findall(r"[A-Z]", password))
    c_digit = len(re.findall(r"\d", password))
    c_special = len(re.findall(f"[{re.escape(string.punctuation)}]", password))
    length = len(password)

    has_lower   = c_lower > 0
    has_upper   = c_upper > 0
    has_digit   = c_digit > 0
    has_special = c_special > 0
    is_common   = password.lower() in COMMON_PASSWORDS
    has_pattern = detect_pattern(password)

    criteria = Criteria(
        len_8=length >= 8,
        len_12=length >= 12,
        len_16=length >= 16,
        has_lower=has_lower,
        has_upper=has_upper,
        has_digit=has_digit,
        has_special=has_special,
        not_common=not is_common,
        no_pattern=not has_pattern,
    )

    score = 0
    if length >= 8:   score += 1
    if length >= 12:  score += 1
    if length >= 16:  score += 1
    if has_lower:     score += 1
    if has_upper:     score += 1
    if has_digit:     score += 1
    if has_special:   score += 1
    if not is_common and not has_pattern: score += 1

    if is_common:   score = max(0, score - 3)
    if has_pattern: score = max(0, score - 1)

    entropy = calculate_entropy(password)

    feedback: List[str] = []
    if is_common:
        feedback.append("⚠️ This is a widely known dictionary password — easily cracked!")
    if has_pattern:
        feedback.append("⚠️ Detected predictable patterns or keyboard walks (e.g. 'qwerty', '1234').")
    if length < 8:
        feedback.append("❌ Password length is below minimum (8+ characters required).")
    elif length < 12:
        feedback.append("💡 Recommendation: Increase length to 12–20 characters for higher entropy.")
    if not has_upper:   feedback.append("Add uppercase letters (A–Z).")
    if not has_lower:   feedback.append("Add lowercase letters (a–z).")
    if not has_digit:   feedback.append("Add numerical digits (0–9).")
    if not has_special: feedback.append("Add special characters (!@#$%...).")

    if entropy < 30 or score <= 2 or is_common:
        strength = Strength.CRITICAL
    elif entropy < 50 or score <= 4:
        strength = Strength.WEAK
    elif entropy < 70 or score <= 6:
        strength = Strength.MODERATE
    elif entropy < 90 or score <= 7:
        strength = Strength.STRONG
    else:
        strength = Strength.VERY_STRONG
        if not feedback:
            feedback.append("🛡️ Cryptographically solid! Highly resistant to brute-force attacks.")

    crack_time, crack_time_online = apply_realistic_crack_override(
        entropy, is_common, has_pattern
    )

    return Assessment(
        strength=strength,
        score=score,
        max_score=8,
        entropy_bits=entropy,
        crack_time=crack_time,
        crack_time_online=crack_time_online,
        criteria=criteria,
        composition={
            "lower": c_lower,
            "upper": c_upper,
            "digits": c_digit,
            "symbols": c_special,
            "length": length
        },
        feedback=feedback,
        is_common=is_common,
        has_pattern=has_pattern,
    )

@app.route("/", methods=["GET"])
def home():
    return render_template("index.html")

@app.route("/api/check", methods=["POST"])
@limiter.limit("120 per minute")
def api_check():
    data = request.get_json(silent=True) or {}
    raw_pwd = data.get("password", "")
    pwd = sanitize_input(raw_pwd, max_length=1024)
    return jsonify(assess_password(pwd).to_dict())

@app.route("/api/generate", methods=["POST"])
@limiter.limit("60 per minute")
def api_generate():
    data = request.get_json(silent=True) or {}
    raw_length = data.get("length", 16)
    try:
        length = int(raw_length)
    except (ValueError, TypeError):
        length = 16

    length = max(8, min(20, length))

    inc_upper = bool(data.get("include_upper", True))
    inc_lower = bool(data.get("include_lower", True))
    inc_digits = bool(data.get("include_digits", True))
    inc_symbols = bool(data.get("include_symbols", True))
    exc_ambig = bool(data.get("exclude_ambiguous", False))

    pwd = generate_secure_password(
        length=length,
        include_upper=inc_upper,
        include_lower=inc_lower,
        include_digits=inc_digits,
        include_symbols=inc_symbols,
        exclude_ambiguous=exc_ambig
    )

    assessment = assess_password(pwd).to_dict()

    return jsonify({
        "password": pwd,
        "length": len(pwd),
        "assessment": assessment
    })

@app.route("/api/hibp", methods=["POST"])
@limiter.limit("15 per minute")
def api_hibp():
    data = request.get_json(silent=True) or {}
    raw_pwd = data.get("password", "")
    pwd = sanitize_input(raw_pwd, max_length=1024)
    return jsonify(check_hibp_database(pwd))

@app.route("/admin", methods=["GET"])
def admin_root():
    if session.get("is_admin") and session.get("user") == ADMIN_USERNAME:
        return redirect(url_for("admin_dashboard"))
    return redirect(url_for("admin_login"))

@app.route("/admin/login", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def admin_login():
    if session.get("is_admin") and session.get("user") == ADMIN_USERNAME:
        return redirect(url_for("admin_dashboard"))

    error = None
    if request.method == "POST":
        submitted_token = request.form.get("csrf_token", "")
        session_token = session.get("_csrf_token", "")
        if not submitted_token or not hmac.compare_digest(submitted_token, session_token):
            return render_template("admin_login.html", error="Invalid security token. Please refresh."), 400

        username = sanitize_input(request.form.get("username", ""), max_length=64).strip()
        password = sanitize_input(request.form.get("password", ""), max_length=256)

        user_match = hmac.compare_digest(username, ADMIN_USERNAME)
        pwd_match = check_password_hash(ADMIN_PASSWORD_HASH, password)

        if user_match and pwd_match:
            session.clear()
            session.permanent = True
            session["is_admin"] = True
            session["user"] = ADMIN_USERNAME
            session["login_time"] = int(time.time())
            session["_csrf_token"] = secrets.token_hex(32)
            next_url = request.args.get("next")
            if next_url and next_url.startswith("/admin"):
                return redirect(next_url)
            return redirect(url_for("admin_dashboard"))

        time.sleep(0.3)
        error = "Invalid administrator credentials."

    return render_template("admin_login.html", error=error)

@app.route("/admin/logout", methods=["GET", "POST"])
@admin_required
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))

@app.route("/admin/dashboard", methods=["GET"])
@admin_required
def admin_dashboard():
    return render_template(
        "admin_dashboard.html",
        admin_user=session.get("user"),
        debug_mode=app.debug
    )

@app.route("/admin/api/status", methods=["GET"])
@admin_required
def admin_api_status():
    return jsonify({
        "status": "healthy",
        "security": {
            "debug_mode": app.debug,
            "rate_limiting": True,
            "security_headers": True,
            "cors_configured": True,
            "allowed_origins": allowed_origins,
            "session_secure": app.config["SESSION_COOKIE_SECURE"],
            "password_hashing": "pbkdf2:sha256",
            "csrf_protection": True
        },
        "system": {
            "version": "2.1.0-hardened",
            "python_version": sys.version.split()[0]
        }
    })

def _cli_main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    parser = argparse.ArgumentParser(
        prog="CryptScale",
        description="CryptScale — Modern Password Auditor & Generator",
    )
    parser.add_argument("--check", metavar="PASSWORD", help="Audit a password's strength")
    parser.add_argument("--generate", action="store_true", help="Generate a strong password (min 8, max 20)")
    parser.add_argument("--length", type=int, default=16, help="Password length between 8 and 20 (default: 16)")
    parser.add_argument("--no-symbols", action="store_true", help="Exclude symbols")
    parser.add_argument("--hibp", action="store_true", help="Check against HIBP breach database")
    args = parser.parse_args()

    if args.generate:
        length = max(8, min(20, args.length))
        pwd = generate_secure_password(length=length, include_symbols=not args.no_symbols)
        print(f"\nGenerated Strong Password ({length} chars): {pwd}\n")
        res = assess_password(pwd)
        _print_cli(res)
        sys.exit(0)

    if args.check:
        res = assess_password(args.check)
        _print_cli(res)
        if args.hibp:
            print("Checking HIBP breach database... ", end="", flush=True)
            h = check_hibp_database(args.check)
            if h.get("breached") is False:
                print("\033[92m[SAFE] Not found in known breaches.\033[0m\n")
            elif h.get("breached"):
                print(f"\033[91m[BREACHED] Found in {h['count']:,} breach(es)!\033[0m\n")
            else:
                print(f"\033[93m{h.get('error')}\033[0m\n")
        sys.exit(0)

def _print_cli(res: Assessment) -> None:
    r = res.to_dict()
    sep = "=" * 52
    print(f"  {sep}")
    print(f"  Rating     : {r['rating']} — {r['subtitle']}")
    print(f"  Score      : {r['score']}/{r['max_score']} ({r['score_pct']}%)")
    print(f"  Entropy    : {r['entropy']} bits")
    print(f"  GPU Crack  : {r['crack_time']}")
    print(f"  Web Crack  : {r['crack_time_online']}")
    print(f"  {sep}")
    print("  Criteria Breakdown:")
    for k, v in [
        ("8+ characters (Min)",   r["criteria"]["len_8"]),
        ("12+ characters",        r["criteria"]["len_12"]),
        ("16+ characters",        r["criteria"]["len_16"]),
        ("Lowercase letters",     r["criteria"]["has_lower"]),
        ("Uppercase letters",     r["criteria"]["has_upper"]),
        ("Numerical digits",      r["criteria"]["has_digit"]),
        ("Special symbols",       r["criteria"]["has_special"]),
        ("Not in common wordlist",r["criteria"]["not_common"]),
        ("No keyboard patterns",  r["criteria"]["no_pattern"]),
    ]:
        status = "\033[92m[PASS]\033[0m" if v else "\033[91m[FAIL]\033[0m"
        print(f"    {status:14} {k}")
    if r["feedback"]:
        print("\n  Security Feedback:")
        for fb in r["feedback"]:
            print(f"    • {fb}")
    print(f"  {sep}\n")

if __name__ == "__main__":
    if any(arg in sys.argv for arg in ("--check", "--generate")):
        _cli_main()

    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "5001"))
    app.run(host=host, port=port, debug=debug_mode)
