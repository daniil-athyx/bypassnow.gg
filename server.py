import base64
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

# Cached play user token signed by upstream now.gg per appId
PLAY_USER_TOKENS: dict[str, dict[str, any]] = {}

# Pinned active frontend version for now.gg backend API calls
CURRENT_FE_VERSION: str = "berlin-v1.54.500-arm.2"

def decode_jwt_exp(token: str) -> float:
    """Extract expiry timestamp from JWT payload."""
    try:
        parts = token.split(".")
        if len(parts) >= 2:
            padded = parts[1] + "=" * ((4 - len(parts[1]) % 4) % 4)
            payload = json.loads(base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8"))
            return float(payload.get("exp", 0))
    except Exception:
        pass
    return 0.0

def get_guest_token(force_refresh: bool = False) -> str:
    """Fetch or return cached now.gg guest authorization token."""
    global GUEST_TOKEN_CACHE
    now = time.time()
    try:
        exp_val = float(GUEST_TOKEN_CACHE.get("expiry", 0))
    except (ValueError, TypeError):
        exp_val = 0.0

    if not force_refresh and GUEST_TOKEN_CACHE["token"] and now < (exp_val - 120):
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
            exp = decode_jwt_exp(tok) if tok else 0.0
            if exp <= 0:
                exp = now + 7200
            if tok:
                GUEST_TOKEN_CACHE["token"] = tok
                GUEST_TOKEN_CACHE["expiry"] = exp
                SESSION_COOKIES["ng_token_v2"] = tok
                SESSION_COOKIES["ng_token_expiry_v2"] = str(int(exp))
                return tok
    except HTTPError as e:
        err_msg = e.read().decode('utf-8', errors='ignore')[:300]
        print(f"[AUTH ERROR] Failed to fetch guest token from now.gg: {e} -> {err_msg}")
    except Exception as e:
        print(f"[AUTH ERROR] Failed to fetch guest token from now.gg: {e}")
    return GUEST_TOKEN_CACHE["token"]

def get_play_user_token(app_id: str = "7074", force_refresh: bool = False) -> str:
    """Fetch or return cached genuine HMAC-signed playUserToken for given appId from upstream now.gg."""
    global PLAY_USER_TOKENS
    now = time.time()
    cached = PLAY_USER_TOKENS.get(str(app_id))
    if not force_refresh and cached and cached.get("token") and now < (cached.get("expiry", 0) - 120):
        return cached["token"]

    guest_tok = get_guest_token(force_refresh=force_refresh)
    if not guest_tok:
        return ""

    try:
        cpu_req = Request(
            "https://now.gg/oapi/7/play/v1/createPlayUser",
            data=json.dumps({"appId": str(app_id), "device": "desktop"}).encode("utf-8"),
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
                "x-ngg-fe-version": "berlin-v1.54.500-arm.2",
                "x-ng-app-ver": "berlin-v1.54.500-arm.2",
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"NowV2 {guest_tok}",
            },
            method="POST"
        )
        with urlopen(cpu_req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            tok = data.get("playUserToken")
            exp = decode_jwt_exp(tok) if tok else 0.0
            if exp <= 0:
                exp = now + 86400
            if tok:
                PLAY_USER_TOKENS[str(app_id)] = {"token": tok, "expiry": exp}
                return tok
    except Exception as e:
        print(f"[PLAY_USER ERROR] Failed to create play user token for app {app_id}: {e}")
    return PLAY_USER_TOKENS.get(str(app_id), {}).get("token", "")

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
  [class*="ErrorModal"], [class*="error-modal"], .app-page-error, .desktopErr, .mobileErr,
  /* Completely eliminate proxy playtime limit, topup, recharge coupon, and disconnect toast modals */
  [class*="Coupon" i], [class*="coupon" i],
  [class*="TopUp" i], [class*="topup" i],
  [class*="recharge" i], [class*="Recharge" i],
  [class*="disconnect-toast" i], [class*="DisconnectToast" i],
  [class*="time-limit" i], [class*="TimeLimit" i],
  div:has(> a[href*="mmoculture"]) {
    display: none !important;
    visibility: hidden !important;
    pointer-events: none !important;
    opacity: 0 !important;
    width: 0 !important;
    height: 0 !important;
  }

  /* Completely eliminate background preloader videos, posters, launch teasers, and fake video players */
  video.BgVideo,
  video.preloader-video,
  video[poster],
  video:has(source),
  video[src*=".mp4"],
  video[src*="launch-video"],
  /* Permanently eliminate clapboard transition video, preloader videos, and trailers */
  video.transition-video,
  video[src*="clapboard"],
  video[src*="clapboardVideo"],
  .transition-video,
  [class*="transition-video"],
  video.BgVideo,
  video.preloader-video,
  video[poster],
  video:has(source),
  video[src*=".mp4"],
  video[src*="launch-video"],
  video[src*="aptoide.mp4"],
  video[src*="Launch_1920.mp4"],
  source,
  [class*="launch-video"],
  [class*="LaunchVideo"],
  [class*="bg-video"],
  [class*="BgVideo"] {
    display: none !important;
    visibility: hidden !important;
    pointer-events: none !important;
    width: 0 !important;
    height: 0 !important;
    opacity: 0 !important;
    z-index: -9999999 !important;
  }

  /* Ensure canvas and real WebRTC game stream fill the viewport cleanly */
  canvas,
  #js-game-video,
  video#js-game-video,
  video.athyx-real-stream {
    width: 100% !important;
    height: 100% !important;
    object-fit: contain !important;
    display: block !important;
    visibility: visible !important;
    opacity: 1 !important;
  }
</style>

<script>
(function() {
  // Prevent React hydration crashes from third-party / DOM manipulation
  try {
    var _origInsertBefore = Node.prototype.insertBefore;
    Node.prototype.insertBefore = function(newNode, refNode) {
      try {
        return _origInsertBefore.call(this, newNode, refNode);
      } catch (err) {
        if (err && (err.name === 'NotFoundError' || err.code === 8)) {
          return this.appendChild(newNode);
        }
        try {
          return this.appendChild(newNode);
        } catch(e2) {
          throw err;
        }
      }
    };
    var _origRemoveChild = Node.prototype.removeChild;
    Node.prototype.removeChild = function(child) {
      try {
        return _origRemoveChild.call(this, child);
      } catch (err) {
        if (err && (err.name === 'NotFoundError' || err.code === 8)) {
          return child;
        }
        return child;
      }
    };

    // Spoof nggClientIpInfo to desktop non-proxy to bypass playtime limits
    var spoofIpInfo = {
      browserCode: 'desktop',
      isBot: false,
      isDataCenter: false,
      isVpn: false,
      country: 'US',
      countryCode: 'US'
    };
    try {
      window.nggClientIpInfo = spoofIpInfo;
      Object.defineProperty(window, 'nggClientIpInfo', {
        get: function() { return spoofIpInfo; },
        set: function() {},
        configurable: true
      });
    } catch(e) {}

    // Intercept WebRTC DataChannel to suppress timeout / disconnect messages
    try {
      if (window.RTCDataChannel) {
        var _origOnmessage = Object.getOwnPropertyDescriptor(RTCDataChannel.prototype, 'onmessage');
        if (_origOnmessage && _origOnmessage.set) {
          var _origSetOnMsg = _origOnmessage.set;
          Object.defineProperty(RTCDataChannel.prototype, 'onmessage', {
            set: function(handler) {
              if (typeof handler === 'function') {
                var wrapped = function(event) {
                  if (typeof event.data === 'string' && (
                    event.data.includes('ProxyPlaytimeExceeded') ||
                    event.data.includes('SessionTimeLimitExceeded') ||
                    event.data.includes('FailureInsufficientPlaytime')
                  )) {
                    return;
                  }
                  return handler.apply(this, arguments);
                };
                return _origSetOnMsg.call(this, wrapped);
              }
              return _origSetOnMsg.call(this, handler);
            },
            get: _origOnmessage.get,
            configurable: true
          });
        }
      }
    } catch(e) {}

    // Block any video from loading clapboardVideo.mp4
    var mediaProto = window.HTMLMediaElement ? HTMLMediaElement.prototype : (window.HTMLVideoElement ? HTMLVideoElement.prototype : null);
    if (mediaProto) {
      var _srcDesc = Object.getOwnPropertyDescriptor(mediaProto, 'src');
      if (_srcDesc && _srcDesc.set) {
        var _origSrcSet = _srcDesc.set;
        Object.defineProperty(mediaProto, 'src', {
          set: function(val) {
            if (val && typeof val === 'string' && (val.indexOf('clapboard') !== -1 || val.indexOf('transition') !== -1)) {
              return;
            }
            return _origSrcSet.call(this, val);
          },
          get: _srcDesc.get,
          configurable: true
        });
      }
    }
  } catch(e) {}

  // 0. Synchronously seed guest auth token and session flags before Next.js boots
  try {
    sessionStorage.setItem("allowFpsRotation", "true");
    sessionStorage.setItem("partnerName", "nowgg");
    window.allowFpsRotation = true;
    window.partnerName = "nowgg";
    window.requireHomepageLaunch = false;
    window.isMultiSubscriptionFlow = false;
    if (window.__SEED_TOKEN__) {
      sessionStorage.setItem("ng_token_v2", window.__SEED_TOKEN__);
      localStorage.setItem("ng_token_v2", window.__SEED_TOKEN__);
      localStorage.setItem("ng_token_expiry_v2", String(window.__SEED_EXPIRY__ || ""));
      document.cookie = "ng_token_v2=" + window.__SEED_TOKEN__ + "; path=/; max-age=86400";
      document.cookie = "ng_token_expiry_v2=" + (window.__SEED_EXPIRY__ || "") + "; path=/; max-age=86400";
    }
    if (window.__SEED_PLAY_USER_TOKEN__) {
      sessionStorage.setItem("playUserToken", window.__SEED_PLAY_USER_TOKEN__);
      localStorage.setItem("playUserToken", window.__SEED_PLAY_USER_TOKEN__);
      document.cookie = "playUserToken=" + window.__SEED_PLAY_USER_TOKEN__ + "; path=/; max-age=86400";
    }

    // Auto-grant rewarded premium 1080p stream resolution
    var futureIso = new Date(Date.now() + 7 * 86400 * 1000).toISOString();
    var rwdData = {
      "com.aptoide.partners.nowgg.store_NA": futureIso,
      "com.roblox.client_NA": futureIso,
      "com.mojang.minecrafttrialpe_NA": futureIso,
      "com.epicgames.fortnite_NA": futureIso,
      "undefined_NA": futureIso,
      "_NA": futureIso
    };
    localStorage.setItem("rewardedPremiumExpiryTimestamp", JSON.stringify(rwdData));
    sessionStorage.setItem("rewardedPremiumExpiryTimestamp", JSON.stringify(rwdData));

    var _origGetItem = Storage.prototype.getItem;
    Storage.prototype.getItem = function(k) {
      if (k === "rewardedPremiumExpiryTimestamp") {
        var fIso = new Date(Date.now() + 7 * 86400 * 1000).toISOString();
        var obj = {
          "com.aptoide.partners.nowgg.store_NA": fIso,
          "com.roblox.client_NA": fIso,
          "com.mojang.minecrafttrialpe_NA": fIso,
          "com.epicgames.fortnite_NA": fIso,
          "undefined_NA": fIso,
          "_NA": fIso
        };
        try {
          var raw = _origGetItem.call(this, k);
          if (raw) {
            var p = JSON.parse(raw);
            for (var key in p) obj[key] = fIso;
          }
        } catch(e) {}
        return JSON.stringify(obj);
      }
      return _origGetItem.apply(this, arguments);
    };

    var _origParse = JSON.parse;
    JSON.parse = function(text, reviver) {
      var res = _origParse.apply(this, arguments);
      if (typeof text === 'string' && text.indexOf('rewardedPremiumExpiryTimestamp') !== -1 && res && typeof res === 'object') {
        return new Proxy(res, {
          get: function(target, prop) {
            if (typeof prop === 'string') {
              return new Date(Date.now() + 7 * 86400 * 1000).toISOString();
            }
            return target[prop];
          }
        });
      }
      return res;
    };

    // Tag and maintain the real WebRTC stream video, silence and hide all fake teaser videos without blinking
    function syncStreamVideos() {
      try {
        var gameVideo = document.getElementById('js-game-video');
        if (gameVideo) {
          gameVideo.classList.add('athyx-real-stream');
        }
        var vids = document.querySelectorAll('video');
        for (var i = 0; i < vids.length; i++) {
          var v = vids[i];
          var isClapboard = v.classList.contains('transition-video') || (v.src && v.src.indexOf('clapboard') !== -1) || (v.className && typeof v.className === 'string' && v.className.indexOf('transition-video') !== -1);
          if (isClapboard) {
            v.pause();
            v.currentTime = 0;
            v.src = "";
            v.style.setProperty('display', 'none', 'important');
            v.style.setProperty('visibility', 'hidden', 'important');
            v.style.setProperty('pointer-events', 'none', 'important');
            v.style.setProperty('opacity', '0', 'important');
            v.style.setProperty('z-index', '-9999999', 'important');
            if (v.parentNode) {
              try { v.parentNode.removeChild(v); } catch(e) {}
            }
            continue;
          }
          if (v.id === 'js-game-video' || v.srcObject) {
            if (!v.classList.contains('athyx-real-stream')) {
              v.classList.add('athyx-real-stream');
            }
          }
        }
        var skips = document.querySelectorAll('[class*="skip" i], [class*="Skip"], [aria-label*="skip" i], [aria-label*="close" i], .videoAdUiSkipButton');
        for (var j = 0; j < skips.length; j++) {
          skips[j].click();
        }
      } catch(e) {}
    }
    syncStreamVideos();
    setInterval(syncStreamVideos, 500);
    window.addEventListener('DOMContentLoaded', syncStreamVideos);
    window.addEventListener('load', syncStreamVideos);
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
  try {
    window.nggVersionMismatch = false;
    Object.defineProperty(window, 'nggVersionMismatch', {
      get: function() { return false; },
      set: function() {},
      configurable: true
    });
  } catch(e) {}
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
          url = parsed.pathname + parsed.search + parsed.hash;
        }
      }
      url = url.replace(/\/oapi\/\d+\/play\/v1\//, '/oapi/1/play/v1/');
      if (url.startsWith('/play/v1/')) {
        url = '/oapi/1' + url;
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
    // Auto-populate auth token if missing on play API calls
    var urlStr = typeof input === 'string' ? input : (input && input.url ? input.url : '');
    if (urlStr.includes('/play/v1/') || urlStr.includes('/startSession') || urlStr.includes('/oapi/')) {
      init = init || {};
      var at = window.__SEED_TOKEN__ || localStorage.getItem('ng_token_v2') || sessionStorage.getItem('ng_token_v2') || '';
      var pt = window.__SEED_PLAY_USER_TOKEN__ || localStorage.getItem('playUserToken') || sessionStorage.getItem('playUserToken') || '';
      if (init.headers instanceof Headers) {
        if (at) init.headers.set('authorization', 'NowV2 ' + at);
        if (pt) init.headers.set('x-ngg-playuser-token', pt);
      } else if (typeof init.headers === 'object' && init.headers !== null) {
        if (at) {
          init.headers['authorization'] = 'NowV2 ' + at;
          init.headers['Authorization'] = 'NowV2 ' + at;
        }
        if (pt) {
          init.headers['x-ngg-playuser-token'] = pt;
        }
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
  var origSend = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.send = function(body) {
    return origSend.call(this, body);
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
      if (v.classList.contains('BgVideo') || v.classList.contains('preloader-video') || (v.src && (v.src.endsWith('.mp4') || v.src.includes('gcdn.co') || v.src.includes('launch-video') || v.src.includes('clapboard')))) {
        try {
          v.pause();
          v.style.setProperty('display', 'none', 'important');
          v.style.setProperty('visibility', 'hidden', 'important');
          v.style.setProperty('pointer-events', 'none', 'important');
        } catch(e) {}
      } else if (v.srcObject || v.readyState >= 2) {
        if (v.paused) {
          try {
            var p = v.play();
            if (p && p.catch) p.catch(function() {});
          } catch(e) {}
        }
        v.style.setProperty('display', 'block', 'important');
        v.style.setProperty('visibility', 'visible', 'important');
        v.style.setProperty('opacity', '1', 'important');
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
    var btn = document.getElementById('ng-play-browser-btn') || document.querySelector('button.Button:not(.loading)');
    if (btn && !btn._athyxClicked) {
      btn._athyxClicked = true;
      try {
        btn.click();
        btn.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
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
        pp['isMultiSubscriptionFlow'] = False
        pp['isMultiPanelAdsEnabled'] = False
        pp['showNewAdsLayout'] = False
        pp['isServerSideDesktopAdsEnabled'] = False
        pp['requireHomepageLaunch'] = False
        pp['serviceStatus'] = None
        pp['error'] = None
        pp['errorStatus'] = None
        pp['errorStatusCode'] = None

        app_info = pp.get('appInfo', {})
        app_info['isMultiSubscriptionFlow'] = False
        app_info['showNewAdsLayout'] = False
        app_info['isServerSideDesktopAdsEnabled'] = False
        app_info['requireRewardedAdsOrPremium'] = False
        app_info['requireHomepageLaunch'] = False
        app_info['enablePlayModeWithPd'] = False
        app_info['status'] = 'Success'
        app_info['state'] = 'active'
        app_info['redirectProxyTrafficPlayDomain'] = ''
        client_config = pp.get('clientConfig', {})
        if client_config:
            client_config['redirectProxyTrafficPlayDomain'] = ''
            client_config['enableCouponGenerator'] = False
        pff = app_info.get('playFeFeatures', {})
        pff['enableCouponGenerator'] = False
        pff['tryAndDownload'] = {'isEnabled': False, 'cumulativeTimeLimitSecs': 0, 'clientLink': '1'}
        pff['partnerSessionEndInfo'] = {'enable': False}
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

    base_url = NOW_GG_BASE_URL
    if "startSession" in path:
        base_url = "https://now.gg"
        path = re.sub(r"^/oapi/\d+/play/v1/", "/oapi/7/play/v1/", path)
    target = f"{base_url}{path}"
    if query:
        target = f"{target}?{query}"

    host_name = "now.gg" if base_url == "https://now.gg" else "doctoraux.com"
    request_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "Referer": f"https://{host_name}/",
        "Origin": f"https://{host_name}",
        "Accept": "*/*",
    }
    if headers:
        for k, v in headers.items():
            k_low = k.lower()
            if k_low not in {"host", "origin", "referer", "accept-encoding"}:
                request_headers[k] = v

    # Enforce matching frontend version so now.gg backend does not return 205 Version Mismatch
    global CURRENT_FE_VERSION
    incoming_ver = None
    if headers:
        for k, v in headers.items():
            if k.lower() in {"x-ngg-fe-version", "x-ng-app-ver"} and v:
                incoming_ver = v
                break
    ver_to_use = incoming_ver or CURRENT_FE_VERSION
    request_headers["x-ngg-fe-version"] = ver_to_use
    request_headers["x-ng-app-ver"] = ver_to_use

    # Ensure Authorization is ALWAYS matched and active
    token = get_guest_token()
    if token:
        # Clear any stale Authorization header
        for k in list(request_headers.keys()):
            if k.lower() == "authorization":
                del request_headers[k]
        request_headers["Authorization"] = f"NowV2 {token}"
        SESSION_COOKIES["ng_token_v2"] = token

    # For any play API, ALWAYS ensure x-ngg-playuser-token matches the active guest token's authUserId
    if ("/play/v1/" in path or "startSession" in path) and "createPlayUser" not in path and "getAppPlayFeatures" not in path:
        target_app = "7074"
        if query:
            m_qid = re.search(r'appId=([^&]+)', query)
            if m_qid:
                target_app = m_qid.group(1)
        if body and b'appId' in body:
            try:
                b_data = json.loads(body.decode('utf-8', errors='ignore'))
                if b_data.get('appId'):
                    target_app = str(b_data['appId'])
            except Exception:
                pass
        play_tok = get_play_user_token(target_app)
        if play_tok:
            for k in list(request_headers.keys()):
                if k.lower() == "x-ngg-playuser-token":
                    del request_headers[k]
            request_headers["x-ngg-playuser-token"] = play_tok

    # Inject stored session cookies if present
    cookie_parts = []
    if "Cookie" in request_headers:
        cleaned_ck = request_headers["Cookie"]
        if token:
            cleaned_ck = re.sub(r'ng_token_v2=[^;]+', f'ng_token_v2={token}', cleaned_ck)
        cookie_parts.append(cleaned_ck)
    if SESSION_COOKIES:
        for ck, cv in SESSION_COOKIES.items():
            if ck not in ("ng_token_v2", "playUserToken"):
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
            resp_bytes = response.read()
            if response.status == 205:
                v_text = resp_bytes.decode("utf-8", errors="ignore").strip()
                if v_text.startswith("berlin-v") and v_text != request_headers.get("x-ngg-fe-version"):
                    CURRENT_FE_VERSION = v_text
                    request_headers["x-ngg-fe-version"] = CURRENT_FE_VERSION
                    request_headers["x-ng-app-ver"] = CURRENT_FE_VERSION
                    req_retry = Request(target, data=body, headers=request_headers, method=method)
                    try:
                        with urlopen(req_retry, timeout=30) as retry_resp:
                            return (retry_resp.status, list(retry_resp.headers.items()), retry_resp.read())
                    except HTTPError as retry_err:
                        return (retry_err.code, list(retry_err.headers.items()), retry_err.read())
            raw_headers = list(response.headers.items())
            # Parse Set-Cookie into SESSION_COOKIES
            for k, v in raw_headers:
                if k.lower() == "set-cookie":
                    name_val = v.split(";")[0].strip()
                    if "=" in name_val:
                        ck, cv = name_val.split("=", 1)
                        SESSION_COOKIES[ck] = cv
            return (response.status, raw_headers, resp_bytes)
    except HTTPError as error:
        raw_headers = list(error.headers.items())
        err_body = error.read()
        if error.code == 205:
            v_text = err_body.decode("utf-8", errors="ignore").strip()
            if v_text.startswith("berlin-v") and v_text != request_headers.get("x-ngg-fe-version"):
                CURRENT_FE_VERSION = v_text
                request_headers["x-ngg-fe-version"] = CURRENT_FE_VERSION
                req_retry = Request(target, data=body, headers=request_headers, method=method)
                try:
                    with urlopen(req_retry, timeout=30) as retry_resp:
                        return (retry_resp.status, list(retry_resp.headers.items()), retry_resp.read())
                except HTTPError as retry_err:
                    return (retry_err.code, list(retry_err.headers.items()), retry_err.read())
        if error.code == 401:
            fresh_guest_tok = get_guest_token(force_refresh=True)
            if fresh_guest_tok:
                request_headers["Authorization"] = f"NowV2 {fresh_guest_tok}"
                SESSION_COOKIES["ng_token_v2"] = fresh_guest_tok
                target_app = "7074"
                if query:
                    m_qid = re.search(r'appId=([^&]+)', query)
                    if m_qid:
                        target_app = m_qid.group(1)
                fresh_play_tok = get_play_user_token(target_app, force_refresh=True)
                if fresh_play_tok:
                    request_headers["x-ngg-playuser-token"] = fresh_play_tok
                req_retry = Request(target, data=body, headers=request_headers, method=method)
                try:
                    with urlopen(req_retry, timeout=30) as retry_resp:
                        return (retry_resp.status, list(retry_resp.headers.items()), retry_resp.read())
                except HTTPError as retry_err:
                    return (retry_err.code, list(retry_err.headers.items()), retry_err.read())
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

        # Neutralize any request for teaser / preloader mp4 videos (returns empty 204 so client never downloads clapperboard)
        if parsed.path.endswith(".mp4") or "launch-video" in parsed.path or "aptoide.mp4" in parsed.path or "Launch_1920" in parsed.path:
            self._send_response(204, [
                ("Content-Type", "video/mp4"),
                ("Access-Control-Allow-Origin", "*"),
                ("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS"),
                ("Content-Length", "0"),
            ], b"")
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

        # Direct handler for createPlayUser to guarantee genuine HMAC playUserToken per appId
        if "createPlayUser" in parsed.path:
            content_length = int(self.headers.get("Content-Length", "0"))
            body_bytes = self.rfile.read(content_length) if content_length else b"{}"
            target_app = "7074"
            if body_bytes:
                try:
                    b_json = json.loads(body_bytes.decode("utf-8", errors="ignore"))
                    if b_json.get("appId"):
                        target_app = str(b_json["appId"])
                except Exception:
                    pass
            play_tok = get_play_user_token(target_app)
            resp_data = {
                "status": "SuccessUserCreated",
                "playUserToken": play_tok,
                "nowbuxCreditLimitExceeded": False,
            }
            body = json.dumps(resp_data).encode("utf-8")
            self._send_response(200, [
                ("Content-Type", "application/json; charset=utf-8"),
                ("Access-Control-Allow-Origin", "*"),
                ("Access-Control-Allow-Methods", "GET, POST, OPTIONS"),
                ("Access-Control-Allow-Headers", "*"),
                ("Access-Control-Allow-Credentials", "true"),
                ("Set-Cookie", f"playUserToken={play_tok}; Path=/; Max-Age=86400; SameSite=Lax"),
            ], body)
            return

        # Direct handler for getAppPlayFeatures
        if "getAppPlayFeatures" in parsed.path:
            resp_data = {
                "status": "Success",
                "enableLiveChat": False,
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
            resp_data = {
                "status": "Success",
                "clientIpInfo": {
                    "browserCode": "desktop",
                    "isBot": False,
                    "isDataCenter": False,
                    "isVpn": False,
                    "country": "US",
                    "countryCode": "US"
                }
            }
            body = json.dumps(resp_data).encode("utf-8")
            self._send_response(200, [
                ("Content-Type", "application/json; charset=utf-8"),
                ("Access-Control-Allow-Origin", "*"),
                ("Access-Control-Allow-Methods", "GET, POST, OPTIONS"),
                ("Access-Control-Allow-Headers", "*"),
            ], body)
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

        # Route ALL play/v1 API calls from ANY prefix (e.g. /oapi/6/, /oapi/7/) to /oapi/1/ to match doctoraux upstream backend
        path = re.sub(r"^/oapi/\d+/play/v1/", "/oapi/1/play/v1/", path)
        if path.startswith("/play/v1/"):
            path = f"/oapi/1{path}"

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
        # Update CURRENT_FE_VERSION if 205 Version Mismatch occurs
        if status == 205:
            global CURRENT_FE_VERSION
            v_text = resp_body.decode("utf-8", errors="ignore").strip()
            if v_text.startswith("berlin-v"):
                CURRENT_FE_VERSION = v_text

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
            resp_body = re.sub(rb'205\s*===\s*[a-zA-Z0-9_\.]+\.status', rb'false', resp_body)
            resp_body = re.sub(rb'[a-zA-Z0-9_\.]+\.status\s*===\s*205', rb'false', resp_body)
            resp_body = resp_body.replace(b'205===E.status', b'false')
            resp_body = resp_body.replace(b'205 === E.status', b'false')
            resp_body = resp_body.replace(b'205===A.status', b'false')
            resp_body = resp_body.replace(b'205 === A.status', b'false')
            resp_body = resp_body.replace(b'window.nggVersionMismatch=!0', b'window.nggVersionMismatch=!1')
            resp_body = resp_body.replace(b'window.nggVersionMismatch = !0', b'window.nggVersionMismatch = !1')
            resp_body = resp_body.replace(b'return f(e),!0', b'return false')
            resp_body = resp_body.replace(b'window.location.href=p(window.location.href)', b'console.warn("Reload blocked")')
            resp_body = re.sub(rb'\(0,\s*[a-zA-Z0-9_]+\.(?:xW|Yi)\)\(["\']StartSession[^"\']*["\']\)', rb'null', resp_body)
            resp_body = resp_body.replace(b'(0,u.xW)("StartSession")', b'null')
            resp_body = resp_body.replace(b'(0,u.Yi)("StartSession")', b'null')
            resp_body = resp_body.replace(b'(0,h.xW)("StartSessionTryAgain")', b'null')
            resp_body = resp_body.replace(b'(0,u.xW)("StartSessionTryAgain")', b'null')
            resp_body = resp_body.replace(b'(0,h.Yi)("StartSessionTryAgain")', b'null')
            resp_body = resp_body.replace(b'(0,u.Yi)("StartSessionTryAgain")', b'null')
            # Auto-launch PlayNow in chunk 3176
            resp_body = resp_body.replace(
                b'playCtaText:i,isFortnite:o}=e,[r,s]=(0,a.useState)(!1)',
                b'playCtaText:i,isFortnite:o}=e,[r,s]=(0,a.useState)(!0);(0,a.useEffect)(()=>{try{t()}catch(e){}},[])'
            )
            # Neutralize clapboard transition video URL in JavaScript bundles
            resp_body = resp_body.replace(b'https://cdn.now.gg/nowgg-static/clapboardVideo.mp4', b'data:,')
            resp_body = resp_body.replace(b'clapboardVideo.mp4', b'data:,')

        # Strip ads and inject shim into HTML responses
        if is_html and resp_body:
            resp_body = strip_ads_from_next_data(resp_body)
            # Neutralize clapboard transition video URL in HTML
            resp_body = resp_body.replace(b'https://cdn.now.gg/nowgg-static/clapboardVideo.mp4', b'data:,')
            resp_body = resp_body.replace(b'clapboardVideo.mp4', b'data:,')
            # Neutralize raw anchor links to external now.gg / doctoraux.com
            resp_body = resp_body.replace(b'href="https://now.gg', b'data-orig-href="https://now.gg')
            resp_body = resp_body.replace(b'href="https://www.now.gg', b'data-orig-href="https://www.now.gg')
            resp_body = resp_body.replace(b'href="https://doctoraux.com', b'data-orig-href="https://doctoraux.com')
            resp_body = resp_body.replace(b'href="http://www.roblox.com"', b'href="javascript:void(0)"')
            resp_body = resp_body.replace(b'mmoculture.com/news', b'')
            resp_body = resp_body.replace(b'mmoculture.com', b'')
            token = get_guest_token()
            m_app = re.search(rb'"appId"\s*:\s*"?(\d+)"?', resp_body)
            app_id = m_app.group(1).decode("utf-8") if m_app else "7074"
            play_tok = get_play_user_token(app_id)
            try:
                expiry = int(float(GUEST_TOKEN_CACHE.get("expiry") or (time.time() + 86400)))
            except (ValueError, TypeError):
                expiry = int(time.time() + 86400)
            seed_script = f'<script>window.__SEED_TOKEN__ = "{token}"; window.__SEED_PLAY_USER_TOKEN__ = "{play_tok}"; window.__SEED_EXPIRY__ = {expiry};</script>'.encode('utf-8')
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
