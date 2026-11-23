import json
import os
import re
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8000"))
PROJECT_ROOT = Path(__file__).resolve().parent
NOW_GG_BASE_URL = "https://doctoraux.com"

# Shared session cookie store so all proxy requests retain now.gg cookies
SESSION_COOKIES: dict[str, str] = {}

# Cached guest auth token so all game sessions are authenticated instantly
GUEST_TOKEN_CACHE: dict[str, any] = {"token": "", "expiry": 0}

def get_guest_token() -> str:
    """Fetch or return cached now.gg guest authorization token."""
    now = time.time()
    try:
        exp_val = float(GUEST_TOKEN_CACHE.get("expiry", 0))
    except (ValueError, TypeError):
        exp_val = 0.0

    if GUEST_TOKEN_CACHE["token"] and now < (exp_val - 300):
        return GUEST_TOKEN_CACHE["token"]
    try:
        req = Request(
            f"{NOW_GG_BASE_URL}/accounts/auth/v2/access-token?implicitGuestLogin=true",
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
                "Origin": "https://doctoraux.com",
                "Referer": "https://doctoraux.com/",
            }
        )
        with urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            tok = data.get("access_token")
            raw_exp = data.get("access_token_expiry")
            try:
                exp = float(raw_exp) if raw_exp is not None else (now + 86400)
            except (ValueError, TypeError):
                exp = now + 86400
            if tok:
                GUEST_TOKEN_CACHE["token"] = tok
                GUEST_TOKEN_CACHE["expiry"] = exp
                SESSION_COOKIES["ng_token_v2"] = tok
                SESSION_COOKIES["ng_token_expiry_v2"] = str(int(exp))
                return tok
    except Exception as e:
        print(f"[AUTH ERROR] Failed to fetch guest token from now.gg: {e}")
    return GUEST_TOKEN_CACHE["token"]

SHIM_SCRIPT = rb"""
<style id="athyx-fullscreen-cleaner">
  /* Force full viewport and pitch black background */
  html, body, #__next {
    width: 100vw !important;
    height: 100vh !important;
    max-width: 100vw !important;
    max-height: 100vh !important;
    margin: 0 !important;
    padding: 0 !important;
    overflow: hidden !important;
    background: #000 !important;
  }

  /* Completely eliminate top header bar and search */
  header, nav, [class*="Header"], [class*="nonStickyHeader"], .gLZcnl, #top-bar-list, [class*="search-bar"], [class*="top-bar"] {
    display: none !important;
    height: 0 !important;
    min-height: 0 !important;
    visibility: hidden !important;
    pointer-events: none !important;
  }

  /* Completely eliminate the bottom control bar, rating bar, and footers */
  #ng-control-bar, [id*="control-bar"], [class*="control-bar"], [class*="ControlBar"],
  div#ng-control-bar, div#ng-control-bar.footer,
  .footer, footer, [class*="Footer"],
  .copyright-footer, [class*="copyright-footer"],
  [class*="topBarApps"] {
    display: none !important;
    height: 0 !important;
    min-height: 0 !important;
    visibility: hidden !important;
    pointer-events: none !important;
    opacity: 0 !important;
    margin: 0 !important;
    padding: 0 !important;
  }

  /* Eliminate external Google / GPT ad frames and popups */
  #div-gpt-ad, [id*="div-gpt-ad"], iframe[src*="doubleclick"], iframe[src*="googlesyndication"], iframe[src*="googleadservices"],
  .google-auto-placed, #google-rewarded-video, [id*="ad_iframe"], [class*="ima-ad"] {
    display: none !important;
    width: 0 !important;
    height: 0 !important;
    visibility: hidden !important;
    pointer-events: none !important;
    opacity: 0 !important;
  }

  /* Neutralize Error Modals and Background Preloaders */
  [class*="ErrorModal"], [class*="error-modal"], .app-page-error, .desktopErr, .mobileErr {
    display: none !important;
    visibility: hidden !important;
  }

  /* Completely eliminate background preloader videos and StyledPreview */
  video.BgVideo, video.preloader-video, .StyledPreview, [class*="StyledPreview"], video[src*=".mp4"], video[src*="launch-video"] {
    display: none !important;
    visibility: hidden !important;
    pointer-events: none !important;
    width: 0 !important;
    height: 0 !important;
    opacity: 0 !important;
    z-index: -9999 !important;
  }

  /* Ensure WebRTC stream video and canvas are strictly VISIBLE and fill the viewport */
  canvas, video:not(.BgVideo):not(.preloader-video):not([src*=".mp4"]) {
    position: fixed !important;
    inset: 0 !important;
    top: 0 !important;
    left: 0 !important;
    width: 100vw !important;
    height: 100vh !important;
    max-width: 100vw !important;
    max-height: 100vh !important;
    transform: none !important;
    object-fit: contain !important;
    display: block !important;
    visibility: visible !important;
    opacity: 1 !important;
    z-index: 999999 !important;
    background: #000 !important;
  }
</style>

<script>
(function() {
  // 0. Synchronously seed guest auth token and session flags before Next.js boots
  try {
    sessionStorage.setItem("allowFpsRotation", "true");
    sessionStorage.setItem("partnerName", "nowgg");
    window.allowFpsRotation = true;
    window.partnerName = "nowgg";
    window.requireHomepageLaunch = false;
    window.enablePlayPage = true;
    window.enableUnifiedPage = false;
    if (window.__SEED_TOKEN__) {
      sessionStorage.setItem("ng_token_v2", window.__SEED_TOKEN__);
      localStorage.setItem("ng_token_v2", window.__SEED_TOKEN__);
      localStorage.setItem("ng_token_expiry_v2", String(window.__SEED_EXPIRY__ || ""));
      document.cookie = "ng_token_v2=" + window.__SEED_TOKEN__ + "; path=/; max-age=86400";
      document.cookie = "ng_token_expiry_v2=" + (window.__SEED_EXPIRY__ || "") + "; path=/; max-age=86400";
    }
  } catch(e) {}

  // 1. Mock Google AdBlocker checker & Google Tag & Self-Completing IMA Mock
  window.googlefc = window.googlefc || { getAdBlockerStatus: function() { return 0; } };
  try {
    var imaMock = {
      AdsLoader: function() {
        return {
          requestAds: function() {},
          contentComplete: function() {},
          addEventListener: function(type, handler) {
            if (type === 'adsManagerLoaded') {
              setTimeout(function() {
                try {
                  handler({
                    getAdsManager: function() {
                      return {
                        init: function() {},
                        start: function() {},
                        stop: function() {},
                        destroy: function() {},
                        collapse: function() {},
                        addEventListener: function(t, h) {
                          if (t === 'allAdsCompleted' || t === 'complete' || t === 'adError' || t === 'contentResumeRequested') {
                            setTimeout(h, 10);
                          }
                        }
                      };
                    }
                  });
                } catch(e) {}
              }, 10);
            }
          }
        };
      },
      AdsRequest: function() {},
      AdsRenderingSettings: function() {},
      ViewMode: { NORMAL: 'normal', FULLSCREEN: 'fullscreen' },
      AdDisplayContainer: function() { return { initialize: function() {}, destroy: function() {} }; }
    };
    window.google = window.google || {};
    Object.defineProperty(window.google, 'ima', {
      get: function() { return imaMock; },
      set: function() {},
      configurable: true
    });
  } catch(e) {}
  window.googletag = window.googletag || {
    cmd: [],
    display: function() {},
    pubads: function() {
      return {
        addEventListener: function() {},
        enableSingleRequest: function() {},
        disableInitialLoad: function() {},
        refresh: function() {},
        clear: function() {}
      };
    },
    enableServices: function() {}
  };

  // 2. TCF API shim to prevent GDPR consent errors
  window.__tcfapi = function(cmd, ver, cb) {
    if (typeof cb === 'function') {
      cb({
        tcString: 'CP12345',
        gdprApplies: false,
        eventStatus: 'tcloaded',
        cmpLoaded: true,
        cmpStatus: 'loaded'
      }, true);
    }
  };
  window._tcfapi = window.__tcfapi;

  // 3. URL rewrite helper: convert now.gg / doctoraux.com main origin absolute URLs to local proxy relative path
  function rewriteUrl(url) {
    if (!url || typeof url !== 'string') return url;
    try {
      if (url.startsWith('https://now.gg/') || url.startsWith('http://now.gg/')) {
        return url.replace(/^https?:\/\/now\.gg/, '');
      }
      if (url.startsWith('https://www.now.gg/') || url.startsWith('http://www.now.gg/')) {
        return url.replace(/^https?:\/\/www\.now\.gg/, '');
      }
      if (url.startsWith('https://doctoraux.com/') || url.startsWith('http://doctoraux.com/')) {
        return url.replace(/^https?:\/\/doctoraux\.com/, '');
      }
      if (url.includes('now.gg') || url.includes('doctoraux.com')) {
        var parsed = new URL(url, window.location.href);
        if (parsed.hostname.includes('now.gg') || parsed.hostname.includes('doctoraux.com')) {
          return parsed.pathname + parsed.search + parsed.hash;
        }
      }
    } catch (e) {}
    return url;
  }

  // 4. Intercept fetch
  var origFetch = window.fetch;
  window.fetch = function(input, init) {
    if (typeof input === 'string') {
      input = rewriteUrl(input);
    } else if (input && input.url) {
      var newUrl = rewriteUrl(input.url);
      if (newUrl !== input.url) {
        input = new Request(newUrl, input);
      }
    }
    return origFetch.call(this, input, init);
  };

  // 5. Intercept XMLHttpRequest
  var origOpen = XMLHttpRequest.prototype.open;
  XMLHttpRequest.prototype.open = function(method, url) {
    var rest = Array.prototype.slice.call(arguments, 2);
    return origOpen.apply(this, [method, rewriteUrl(url)].concat(rest));
  };

  // 6. Intercept sendBeacon
  if (navigator.sendBeacon) {
    var origBeacon = navigator.sendBeacon;
    navigator.sendBeacon = function(url, data) {
      return origBeacon.call(this, rewriteUrl(url), data);
    };
  }

  // 7. Ensure stream video is playing and prevent any external redirects
  function ensureStreamVisible() {
    var videos = document.querySelectorAll('video');
    for (var j = 0; j < videos.length; j++) {
      var v = videos[j];
      if (v.classList.contains('BgVideo') || v.classList.contains('preloader-video') || (v.src && (v.src.endsWith('.mp4') || v.src.includes('gcdn.co') || v.src.includes('launch-video')))) {
        try {
          v.pause();
          v.style.setProperty('display', 'none', 'important');
          v.style.setProperty('visibility', 'hidden', 'important');
          v.style.setProperty('pointer-events', 'none', 'important');
        } catch(e) {}
      } else {
        if (v.paused) {
          try {
            var p = v.play();
            if (p && p.catch) p.catch(function() {});
          } catch(e) {}
        }
        v.style.setProperty('display', 'block', 'important');
        v.style.setProperty('visibility', 'visible', 'important');
        v.style.setProperty('opacity', '1', 'important');
        v.style.setProperty('z-index', '999999', 'important');
        v.style.setProperty('position', 'fixed', 'important');
        v.style.setProperty('inset', '0', 'important');
        v.style.setProperty('width', '100vw', 'important');
        v.style.setProperty('height', '100vh', 'important');
        v.style.setProperty('background', '#000', 'important');
      }
    }
  }

  // Intercept any link clicks so nothing ever navigates out of proxy to raw now.gg
  document.addEventListener('click', function(e) {
    var a = e.target && e.target.closest('a');
    if (a) {
      var href = (a.href || '').toLowerCase();
      if (href.includes('now.gg') || href.includes('doctoraux.com') || href.includes('popular') || href.startsWith('http')) {
        e.preventDefault();
        e.stopPropagation();
      }
    }
  }, true);

  // Auto-click play button when present
  function autoLaunchStream() {
    var btn = document.getElementById('ng-play-browser-btn') || document.getElementById('ng-getting-ready-btn');
    if (btn) {
      try {
        btn.click();
      } catch(e) {}
    }
    ensureStreamVisible();
  }

  document.addEventListener('DOMContentLoaded', function() {
    autoLaunchStream();
    setInterval(autoLaunchStream, 400);
  });
  window.addEventListener('load', autoLaunchStream);
})();
</script>
"""

def clean_set_cookie(header_val: str) -> str:
    """Strip Domain and Secure flags so the local browser accepts the cookie."""
    cleaned = re.sub(r'(?i)domain=[^;]+;?\s*', '', header_val)
    cleaned = re.sub(r'(?i)secure;?\s*', '', cleaned)
    return cleaned


def strip_ads_from_next_data(html_body: bytes) -> bytes:
    """Modify __NEXT_DATA__ JSON in the HTML to disable all ads and ad layouts."""
    try:
        html_str = html_body.decode('utf-8', errors='ignore')
        m = re.search(r'(<script id="__NEXT_DATA__"[^>]*>)(.*?)(</script>)', html_str)
        if not m:
            return html_body
        prefix, data_json, suffix = m.groups()
        data = json.loads(data_json)
        pp = data.get('props', {}).get('pageProps', {})
        pp['isMultiPanelAdsEnabled'] = False
        pp['showNewAdsLayout'] = False
        pp['isServerSideDesktopAdsEnabled'] = False
        pp['requireHomepageLaunch'] = False
        pp['pageType'] = 'PlayPage'
        pp['isAppPage'] = False
        pp['serviceStatus'] = None
        pp['error'] = None
        pp['errorStatus'] = None
        pp['errorStatusCode'] = None

        app_info = pp.get('appInfo', {})
        app_info['showNewAdsLayout'] = False
        app_info['isServerSideDesktopAdsEnabled'] = False
        app_info['requireRewardedAdsOrPremium'] = False
        app_info['requireHomepageLaunch'] = False
        app_info['enablePlayPage'] = True
        app_info['enableUnifiedPage'] = False
        app_info['enablePlayModeWithPd'] = False
        app_info['status'] = 'Success'
        app_info['state'] = 'active'
        pff = app_info.get('playFeFeatures', {})
        pff['forcedRewardedAds'] = False
        pff['requireRewardedAdsOrPremium'] = False
        pff['ads'] = {
            'desktop': {
                'enableDisplayAds': False,
                'enablePrerollAds': False,
                'enableMidrollAds': False,
                'enableRewardedAds': False,
            },
            'mobile': {
                'enableDisplayAds': False,
                'enablePrerollAds': False,
                'enableMidrollAds': False,
                'enableRewardedAds': False,
            },
        }
        ui = pff.get('uiConfig', {})
        ui['enableHeader'] = False
        ui['enableIframeHeader'] = False
        ui['enableSearch'] = False
        ui['enableSupportWidget'] = False
        if 'footer' in ui and isinstance(ui['footer'], dict):
            ui['footer']['enabled'] = False

        new_json = json.dumps(data)
        new_html = html_str[:m.start()] + prefix + new_json + suffix + html_str[m.end():]
        return new_html.encode('utf-8')
    except Exception:
        return html_body


def fetch_now_gg(
    path: str,
    query: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
) -> tuple[int, list[tuple[str, str]], bytes]:
    """Fetch a now.gg resource, maintaining session cookies and returning response."""
    # Clean query parameters so now.gg receives clean now.gg referrers
    if query:
        query = query.replace("http%3A%2F%2F127.0.0.1%3A8000%2Fstream", "https%3A%2F%2Fnow.gg")
        query = query.replace("http%3A%2F%2F127.0.0.1%3A8000", "https%3A%2F%2Fnow.gg")
        query = query.replace("http://127.0.0.1:8000/stream", "https://now.gg")
        query = query.replace("http://127.0.0.1:8000", "https://now.gg")

    target = f"{NOW_GG_BASE_URL}{path}"
    if query:
        target = f"{target}?{query}"

    request_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "Referer": "https://doctoraux.com/",
        "Origin": "https://doctoraux.com",
        "Host": "doctoraux.com",
        "Accept": "*/*",
    }
    if headers:
        for k, v in headers.items():
            k_low = k.lower()
            if k_low not in {"host", "origin", "referer", "accept-encoding"}:
                request_headers[k] = v

    # Enforce matching frontend version so now.gg backend does not return 205 Version Mismatch
    request_headers["x-ngg-fe-version"] = "berlin-v1.54.400-arm.5"

    # Ensure Authorization header is ALWAYS populated for now.gg session requests
    token = get_guest_token()
    if token:
        auth_keys = [k for k in request_headers if k.lower() == "authorization"]
        if not auth_keys:
            request_headers["Authorization"] = f"NowV2 {token}"
        elif not request_headers[auth_keys[0]].strip() or request_headers[auth_keys[0]].strip() in {"NowV2", "Bearer"}:
            request_headers[auth_keys[0]] = f"NowV2 {token}"
        if "x-ngg-playuser-token" not in request_headers or not request_headers["x-ngg-playuser-token"]:
            request_headers["x-ngg-playuser-token"] = token
        SESSION_COOKIES["ng_token_v2"] = token

    # Inject stored session cookies if present
    cookie_parts = []
    if "Cookie" in request_headers:
        cookie_parts.append(request_headers["Cookie"])
    if SESSION_COOKIES:
        for ck, cv in SESSION_COOKIES.items():
            cookie_parts.append(f"{ck}={cv}")
    if cookie_parts:
        request_headers["Cookie"] = "; ".join(cookie_parts)

    request = Request(
        target,
        data=body,
        headers=request_headers,
        method=method,
    )
    try:
        with urlopen(request, timeout=30) as response:
            raw_headers = list(response.headers.items())
            # Parse Set-Cookie into SESSION_COOKIES
            for k, v in raw_headers:
                if k.lower() == "set-cookie":
                    name_val = v.split(";")[0].strip()
                    if "=" in name_val:
                        ck, cv = name_val.split("=", 1)
                        SESSION_COOKIES[ck] = cv
            return (response.status, raw_headers, response.read())
    except HTTPError as error:
        raw_headers = list(error.headers.items())
        err_body = error.read()
        return (error.code, raw_headers, err_body)
    except URLError as error:
        raise RuntimeError(f"Unable to reach now.gg: {error.reason}") from error


class AppHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self._handle_request()

    def do_POST(self):
        self._handle_request()

    def do_OPTIONS(self):
        # Always grant preflight CORS requests immediately
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS, HEAD, PATCH")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Credentials", "true")
        self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()

    def do_HEAD(self):
        self._handle_request()

    def _handle_request(self):
        parsed = urlsplit(self.path)
        clean_path = parsed.path.lstrip("/")
        local_file = PROJECT_ROOT / clean_path
        if parsed.path == "/" or clean_path == "index.html":
            self._serve_file("index.html", "text/html; charset=utf-8")
            return

        # Serve local assets if requested (like games_data.js, icons, etc.)
        if local_file.is_file() and not parsed.path.startswith("/stream/"):
            mime = "text/plain; charset=utf-8"
            if clean_path.endswith(".js"): mime = "application/javascript; charset=utf-8"
            elif clean_path.endswith(".json"): mime = "application/json; charset=utf-8"
            elif clean_path.endswith(".css"): mime = "text/css; charset=utf-8"
            elif clean_path.endswith(".html"): mime = "text/html; charset=utf-8"
            elif clean_path.endswith(".png"): mime = "image/png"
            elif clean_path.endswith(".jpg") or clean_path.endswith(".jpeg"): mime = "image/jpeg"
            elif clean_path.endswith(".webp"): mime = "image/webp"
            elif clean_path.endswith(".svg"): mime = "image/svg+xml"
            elif clean_path.endswith(".ico"): mime = "image/x-icon"
            self._serve_file(clean_path, mime)
            return

        # Direct handler for accounts access-token to guarantee immediate authentication without CORS issues
        if "accounts/auth/v2/access-token" in parsed.path:
            token = get_guest_token()
            try:
                exp = int(float(GUEST_TOKEN_CACHE.get("expiry") or (time.time() + 86400)))
            except (ValueError, TypeError):
                exp = int(time.time() + 86400)
            resp_data = {
                "success": True,
                "code": "EXISTING_GUEST_USER",
                "msg": "Guest user login successful",
                "access_token": token,
                "access_token_expiry": exp,
            }
            body = json.dumps(resp_data).encode("utf-8")
            self._send_response(200, [
                ("Content-Type", "application/json; charset=utf-8"),
                ("Access-Control-Allow-Origin", "*"),
                ("Access-Control-Allow-Methods", "GET, POST, OPTIONS"),
                ("Access-Control-Allow-Headers", "*"),
                ("Set-Cookie", f"ng_token_v2={token}; Path=/; Max-Age=86400; SameSite=Lax"),
                ("Set-Cookie", f"ng_token_expiry_v2={exp}; Path=/; Max-Age=86400; SameSite=Lax"),
            ], body)
            return

        # Direct handler for createPlayUser to return valid guest play user token
        if "play/v1/createPlayUser" in parsed.path:
            token = get_guest_token()
            resp_data = {
                "status": "SuccessUserCreated",
                "playUserToken": token,
                "nowbuxCreditLimitExceeded": False,
            }
            body = json.dumps(resp_data).encode("utf-8")
            self._send_response(200, [
                ("Content-Type", "application/json; charset=utf-8"),
                ("Access-Control-Allow-Origin", "*"),
                ("Access-Control-Allow-Methods", "GET, POST, OPTIONS"),
                ("Access-Control-Allow-Headers", "*"),
                ("Access-Control-Allow-Credentials", "true"),
            ], body)
            return

        # Direct handler for telemetry push
        if "play/v1/push" in parsed.path:
            self._send_response(200, [
                ("Content-Type", "application/json; charset=utf-8"),
                ("Access-Control-Allow-Origin", "*"),
                ("Access-Control-Allow-Methods", "GET, POST, OPTIONS"),
                ("Access-Control-Allow-Headers", "*"),
            ], b'{"status":"Success"}')
            return

        if parsed.path.startswith("/stream/play/") and not parsed.path.startswith("/stream/play/v1/"):
            subpath = parsed.path[13:]
            query_str = f"?{parsed.query}" if parsed.query else ""
            target_url = f"/stream/apps/{subpath}.html{query_str}"
            self.send_response(302)
            self.send_header("Location", target_url)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            return

        if parsed.path.startswith("/stream/"):
            path = parsed.path[7:]
        else:
            path = parsed.path
        self._proxy_request(path, parsed.query, self.command)

    def _serve_file(self, filename: str, content_type: str = "text/html; charset=utf-8"):
        file_path = PROJECT_ROOT / filename
        try:
            body = file_path.read_bytes()
        except OSError:
            self._send_response(404, [("Content-Type", "text/plain; charset=utf-8")], b"Not Found")
            return

        self._send_response(200, [("Content-Type", content_type)], body)

    def _proxy_request(self, path: str, query: str, method: str):
        content_length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(content_length) if content_length else None

        ignored_forward_headers = {
            "host", "content-length", "connection", "accept-encoding",
            "x-forwarded-for", "x-forwarded-proto", "x-forwarded-host", "x-forwarded-port",
            "x-railway-request-id", "x-railway-edge", "cf-connecting-ip", "cf-ray", "cf-visitor"
        }
        forwarded_headers = {
            key: value
            for key, value in self.headers.items()
            if key.lower() not in ignored_forward_headers
        }

        try:
            status, raw_headers, resp_body = fetch_now_gg(
                path,
                query,
                method=method,
                headers=forwarded_headers,
                body=body,
            )
        except RuntimeError as error:
            self._send_response(502, [("Content-Type", "text/plain; charset=utf-8")], str(error).encode())
            return

        # Prepare response headers
        out_headers: list[tuple[str, str]] = []
        is_html = False
        is_js = False

        header_items = raw_headers.items() if isinstance(raw_headers, dict) else raw_headers
        for item in header_items:
            if isinstance(item, tuple) and len(item) == 2:
                key, value = item
            else:
                continue
            k_low = key.lower()
            if k_low in {
                "transfer-encoding",
                "content-security-policy",
                "content-security-policy-report-only",
                "x-frame-options",
                "strict-transport-security",
            }:
                continue
            if k_low == "set-cookie":
                out_headers.append((key, clean_set_cookie(value)))
                continue
            if k_low == "location":
                loc = value
                loc = re.sub(r'^https?://(?:www\.)?(?:now\.gg|doctoraux\.com)', '', loc)
                if not loc.startswith('/stream') and not loc.startswith('http'):
                    loc = '/stream' + ('' if loc.startswith('/') else '/') + loc
                out_headers.append((key, loc))
                continue
            if k_low == "content-type":
                val_low = value.lower()
                if "text/html" in val_low:
                    is_html = True
                elif "javascript" in val_low:
                    is_js = True
            out_headers.append((key, value))

        if path.endswith(".js"):
            is_js = True

        out_headers.append(("Access-Control-Allow-Origin", "*"))
        out_headers.append(("Access-Control-Allow-Credentials", "true"))

        # Patch JavaScript chunks to eliminate launch checks and domain blocks
        if is_js and resp_body:
            resp_body = resp_body.replace(b'n.requireHomepageLaunch', b'false')
            resp_body = resp_body.replace(b'l.requireHomepageLaunch', b'false')
            resp_body = resp_body.replace(b'.requireHomepageLaunch', b'.__fLaunch')
            resp_body = resp_body.replace(b'(0,n.jsx)(u,{...e})', b'(0,n.jsx)(h,{...e})')
            # Disable ErrorModal and nullify error displays
            resp_body = resp_body.replace(b'ErrorModal:()=>eP', b'ErrorModal:()=>(()=>null)')
            resp_body = resp_body.replace(b'default:()=>ez', b'default:()=>(()=>null)')
            # Safely replace SET_ERROR action types without corrupting SET_ERROR_DESCRIPTION or SET_ERROR_FROM_EXCEPTION
            resp_body = re.sub(rb'type:\s*[a-zA-Z]\.A\.SET_ERROR(?:_[A-Z]+)?(?=[,}\s])', rb'type:"IGNORE_ERROR"', resp_body)
            # Neutralize external navigation redirects to now.gg in error handlers and home buttons
            resp_body = re.sub(rb'window\.location\.href\s*=\s*i\?\(0,[a-zA-Z0-9_]+\.Ay\)\("https://now\.gg"\):"https://now\.gg"', rb'void(0)', resp_body)
            resp_body = re.sub(rb'window\.location\.href\s*=\s*\(0,[a-zA-Z0-9_]+\.Ay\)\("https://now\.gg","ErrorPage"\)', rb'void(0)', resp_body)
            resp_body = re.sub(rb'window\.location\.href\s*=\s*\(0,[a-zA-Z0-9_]+\.Ay\)\(i,"ErrorPage"\)', rb'void(0)', resp_body)
            # Neutralize host redirect in t8
            resp_body = resp_body.replace(
                b'let a=n.playPageHost;if(a&&"now.gg"!==a&&"stagingngg.net"!==a&&a!==(null==(t=null==window?void 0:window.location)?void 0:t.hostname)){let e=(0,L.Ay)(window.location.href.replace(null==(i=null==window?void 0:window.location)?void 0:i.hostname,a));"now.us"===a||(e=e.replace(".html","").replace("/apps/","/play/")),window.location.href=e;return}',
                b'/* bypassed playPageHost redirect */'
            )
            # Auto-resolve login state on initial load
            resp_body = resp_body.replace(b'isLoggedIn:!1,isLoginResolved:!1', b'isLoggedIn:!0,isLoginResolved:!0')
            # Neutralize 205 Version Mismatch and StartSession reload loops
            resp_body = resp_body.replace(b'205===E.status', b'false')
            resp_body = resp_body.replace(b'205 === E.status', b'false')
            resp_body = resp_body.replace(b'window.nggVersionMismatch=!0', b'window.nggVersionMismatch=!1')
            resp_body = resp_body.replace(b'return f(e),!0', b'return false')
            resp_body = resp_body.replace(b'(0,u.xW)("StartSession")', b'null')
            resp_body = resp_body.replace(b'(0,h.xW)("StartSessionTryAgain")', b'null')
            resp_body = resp_body.replace(b'(0,u.xW)("StartSessionTryAgain")', b'null')
            # Auto-launch PlayNow in chunk 3176
            resp_body = resp_body.replace(
                b'playCtaText:i,isFortnite:o}=e,[r,s]=(0,a.useState)(!1)',
                b'playCtaText:i,isFortnite:o}=e,[r,s]=(0,a.useState)(!0);(0,a.useEffect)(()=>{try{t()}catch(e){}},[])'
            )

        # Strip ads and inject shim into HTML responses
        if is_html and resp_body:
            resp_body = strip_ads_from_next_data(resp_body)
            # Neutralize raw anchor links to external now.gg / doctoraux.com
            resp_body = resp_body.replace(b'href="https://now.gg', b'data-orig-href="https://now.gg')
            resp_body = resp_body.replace(b'href="https://www.now.gg', b'data-orig-href="https://www.now.gg')
            resp_body = resp_body.replace(b'href="https://doctoraux.com', b'data-orig-href="https://doctoraux.com')
            resp_body = resp_body.replace(b'href="http://www.roblox.com"', b'href="javascript:void(0)"')
            token = get_guest_token()
            try:
                expiry = int(float(GUEST_TOKEN_CACHE.get("expiry") or (time.time() + 86400)))
            except (ValueError, TypeError):
                expiry = int(time.time() + 86400)
            seed_script = f'<script>window.__SEED_TOKEN__ = "{token}"; window.__SEED_EXPIRY__ = {expiry};</script>'.encode('utf-8')
            full_shim = seed_script + SHIM_SCRIPT
            head_idx = resp_body.find(b"<head>")
            if head_idx != -1:
                resp_body = resp_body[:head_idx + 6] + full_shim + resp_body[head_idx + 6:]
            else:
                head_idx2 = resp_body.find(b"<head ")
                if head_idx2 != -1:
                    close_tag = resp_body.find(b">", head_idx2)
                    if close_tag != -1:
                        resp_body = resp_body[:close_tag + 1] + full_shim + resp_body[close_tag + 1:]
                else:
                    resp_body = full_shim + resp_body

        self._send_response(status, out_headers, resp_body)

    def _send_response(self, status: int, headers: list[tuple[str, str]], body: bytes):
        self.send_response(status)
        for name, value in headers:
            if name.lower() != "content-length":
                self.send_header(name, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args):
        # Keep logs silent to prevent console spam
        pass


def run_server(host: str = HOST, port: int = PORT):
    server = ThreadingHTTPServer((host, port), AppHandler)
    print(f"Serving BypassNow.gg at http://{host}:{server.server_address[1]}")
    return server


if __name__ == "__main__":
    server = run_server()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
