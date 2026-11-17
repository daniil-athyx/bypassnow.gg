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
NOW_GG_BASE_URL = "https://now.gg"

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
                "Origin": "https://now.gg",
                "Referer": "https://now.gg/",
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
  /* Force full viewport and kill scrollbars/backgrounds */
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

  /* Eliminate all ads, sidebars, rating banners, and skeleton placeholders */
  [id*="ad-"], [id*="ad_"], [class*="ad-"], [class*="ad_"], [class*="Ad"],
  [class*="skeleton"], [id*="skeleton"],
  [id*="div-gpt-ad"], [class*="midroll"],
  .jUWcJN, [class*="jUWcJN"],
  [class*="OtherGames"], [class*="GameList"], [class*="GameGrid"],
  [class*="StyledPreview"], [class*="HeroAppInfo"],
  [class*="DesktopPanel"], [class*="desktop-panel-layout"],
  [class*="bKCkYJ"], [class*="RemoveAds"], [class*="remove-ads"],
  [class*="preroll"], [id*="preroll"], [class*="ima-ad"], [id*="ima-ad"],
  [class*="AdPlayer"], [id*="AdPlayer"], [class*="video-ad"], [class*="ad-video"],
  [class*="pip-video-wrapper"], [class*="PipVideo"], [class*="AdOverlay"],
  [class*="app-page-error"], .app-page-error, .abs-overlay, [class*="ErrorModal"], [class*="error-modal"] {
    display: none !important;
    width: 0 !important;
    height: 0 !important;
    visibility: hidden !important;
    pointer-events: none !important;
  }

  /* Specifically hide all ad videos, ad iframes, and placeholders */
  video[src]:not([src=""]),
  video[currentSrc]:not([currentSrc=""]),
  video:has(source),
  video source,
  iframe[src*="ima"], iframe[src*="doubleclick"], iframe[src*="googlesyndication"],
  [class*="ima-"], [id*="ima-"], [class*="AdContainer"], [id*="AdContainer"],
  [class*="video-ad"], [class*="ad-video"], [class*="AdPlayer"], [id*="AdPlayer"],
  [class*="pip-video-wrapper"], [class*="PipVideo"], [class*="AdOverlay"] {
    display: none !important;
    width: 0 !important;
    height: 0 !important;
    visibility: hidden !important;
    pointer-events: none !important;
    opacity: 0 !important;
  }

  /* Eliminate app store landing layout so the stream player occupies top: 0 */
  .StyledLayout, section.StyledLayout, [class*="StyledLayout"],
  .ComponentMainDiv, [class*="ComponentMainDiv"],
  .ciQTX0js5AsOQ5v6, .xES0bjZoI7ksV3Oz,
  .AppContent, [class*="AppContent"],
  .lcpImgWrapper, .lcpDiv,
  [class*="multi-ad-layout"], .iXBWlQ, [class*="iXBWlQ"], main, [class*="page-content"] {
    width: 100vw !important;
    height: 100vh !important;
    max-width: 100vw !important;
    max-height: 100vh !important;
    margin: 0 !important;
    padding: 0 !important;
    border: none !important;
    background: #000 !important;
    display: flex !important;
    flex-direction: column !important;
    justify-content: center !important;
    align-items: center !important;
  }

  /* When game container is present, hide all landing page containers */
  body:has(video) .StyledLayout,
  body:has(video) .ComponentMainDiv,
  body:has(video) [class*="ComponentMainDiv"],
  body:has(video) [class*="StyledLayout"],
  body:has(canvas) .StyledLayout,
  body:has(canvas) .ComponentMainDiv {
    display: none !important;
    height: 0 !important;
    max-height: 0 !important;
    visibility: hidden !important;
    pointer-events: none !important;
  }

  /* Only WebRTC stream video (without src) and canvas should fill the screen */
  canvas, video:not([src]):not(:has(source)) {
    position: absolute !important;
    inset: 0 !important;
    top: 0 !important;
    left: 0 !important;
    width: 100% !important;
    height: 100% !important;
    max-width: 100vw !important;
    max-height: 100vh !important;
    transform: none !important;
    object-fit: contain !important;
    display: block !important;
    margin: 0 !important;
    padding: 0 !important;
    background: #000 !important;
    z-index: 99999 !important;
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

  // 3. TCF API shim to prevent GDPR consent errors
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

  // 4. URL rewrite helper: convert now.gg main origin absolute URLs to local proxy relative path
  function rewriteUrl(url) {
    if (!url || typeof url !== 'string') return url;
    try {
      if (url.startsWith('https://now.gg/') || url.startsWith('http://now.gg/')) {
        return url.replace(/^https?:\/\/now\.gg/, '');
      }
      if (url.startsWith('https://www.now.gg/') || url.startsWith('http://www.now.gg/')) {
        return url.replace(/^https?:\/\/www\.now\.gg/, '');
      }
      if (url.includes('now.gg')) {
        var parsed = new URL(url, window.location.href);
        if (parsed.hostname === 'now.gg' || parsed.hostname === 'www.now.gg') {
          return parsed.pathname + parsed.search + parsed.hash;
        }
      }
    } catch (e) {}
    return url;
  }

  // 5. Intercept fetch
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

  // 6. Intercept XMLHttpRequest
  var origOpen = XMLHttpRequest.prototype.open;
  XMLHttpRequest.prototype.open = function(method, url) {
    var rest = Array.prototype.slice.call(arguments, 2);
    return origOpen.apply(this, [method, rewriteUrl(url)].concat(rest));
  };

  // 7. Intercept sendBeacon
  if (navigator.sendBeacon) {
    var origBeacon = navigator.sendBeacon;
    navigator.sendBeacon = function(url, data) {
      return origBeacon.call(this, rewriteUrl(url), data);
    };
  }

  // 8. Fullscreen & Instant Ad-Bypass Routine
  function cleanAndMaximizeGame() {
    // A. Hide any element mentioning ads or launching after ads
    var walker = document.createTreeWalker(document.body || document.documentElement, NodeFilter.SHOW_TEXT, null, false);
    var node;
    var nodesToHide = [];
    while (node = walker.nextNode()) {
      var val = node.nodeValue;
      if (val && (val.indexOf('will launch after the ad') !== -1 || val.indexOf('Ads help keep now.gg Free') !== -1)) {
        var p = node.parentElement;
        while (p && p !== document.body && !p.querySelector('canvas')) {
          var tag = p.tagName.toLowerCase();
          if (tag === 'div' || tag === 'section' || tag === 'aside' || tag === 'footer') {
            nodesToHide.push(p);
            break;
          }
          p = p.parentElement;
        }
      }
    }
    for (var i = 0; i < nodesToHide.length; i++) {
      nodesToHide[i].style.setProperty('display', 'none', 'important');
    }

    // B. Hide top navbar
    var header = document.querySelector('header, nav, #top-bar-list, [class*="gLZcnl"]');
    if (header) {
      header.style.setProperty('display', 'none', 'important');
    }

    // C. Hide bottom control bar and footers
    var bars = document.querySelectorAll('#ng-control-bar, [id*="control-bar"], footer, .footer, [class*="copyright-footer"], [class*="ControlBar"]');
    for (var k = 0; k < bars.length; k++) {
      bars[k].style.setProperty('display', 'none', 'important');
      bars[k].style.setProperty('height', '0px', 'important');
      bars[k].style.setProperty('visibility', 'hidden', 'important');
      bars[k].style.setProperty('pointer-events', 'none', 'important');
    }

    // D. Instantly auto-click any "Back to Game" or skip ad buttons
    var allClickables = document.querySelectorAll('button, a, div[role="button"], [class*="back"], [class*="Back"]');
    for (var b = 0; b < allClickables.length; b++) {
      var btn = allClickables[b];
      var text = (btn.textContent || btn.innerText || '').trim();
      if (/back to game/i.test(text) || /^skip$/i.test(text) || /^skip ad/i.test(text)) {
        try {
          btn.click();
          btn.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
        } catch(e) {}
      }
    }

    // E. Instantly kill, mute, and eliminate any ad videos
    var videos = document.querySelectorAll('video');
    for (var j = 0; j < videos.length; j++) {
      var v = videos[j];
      var hasSrc = !!(v.src || v.currentSrc || v.querySelector('source'));
      var isStream = !!(v.srcObject && v.srcObject.active !== false);
      if (hasSrc || (!isStream && (v.duration > 0 || v.closest('[id*="ad"], [class*="ad"], [id*="ima"], [class*="ima"], [class*="pip"], [id*="pip"]')))) {
        try {
          v.pause();
          v.muted = true;
          if (v.duration && !v.ended) {
            v.currentTime = v.duration;
          }
          v.dispatchEvent(new Event('ended'));
        } catch(e) {}
        v.style.setProperty('display', 'none', 'important');
        v.style.setProperty('visibility', 'hidden', 'important');
        v.style.setProperty('width', '0px', 'important');
        v.style.setProperty('height', '0px', 'important');
        v.style.setProperty('position', 'absolute', 'important');
        v.style.setProperty('pointer-events', 'none', 'important');
      }
    }

    // Hide any ad iframes
    var adIframes = document.querySelectorAll('iframe:not(#stream-viewport)');
    for (var f = 0; f < adIframes.length; f++) {
      var ifr = adIframes[f];
      var isrc = (ifr.src || '').toLowerCase();
      if (isrc.includes('ima') || isrc.includes('doubleclick') || isrc.includes('google') || ifr.closest('[class*="ad"], [id*="ad"]')) {
        ifr.style.setProperty('display', 'none', 'important');
        ifr.style.setProperty('visibility', 'hidden', 'important');
      }
    }

    // F. Reset Redux/Zustand ad and PiP states
    try {
      if (window.P && window.P.A && typeof window.P.A.getState === 'function') {
        var appState = window.P.A.getState();
        if (appState && appState.play && (appState.play.isAdPlaying || appState.play.isPipVisible)) {
          window.P.A.getState().updatePlayState({ isAdPlaying: false, isPipVisible: false });
        }
      }
    } catch(e) {}

    // G. Locate the REAL game media (Canvas or WebRTC stream video)
    var gameMedia = document.querySelector('canvas');
    if (!gameMedia) {
      for (var k = 0; k < videos.length; k++) {
        if (videos[k].srcObject) {
          gameMedia = videos[k];
          break;
        }
      }
    }
    if (!gameMedia) {
      try {
        var vr = window.P && window.P.A && window.P.A.getState && window.P.A.getState().play && window.P.A.getState().play.videoRef;
        if (vr && vr.current) gameMedia = vr.current;
      } catch(e) {}
    }
    if (!gameMedia) {
      for (var m = 0; m < videos.length; m++) {
        if (!videos[m].src && !videos[m].currentSrc && !videos[m].querySelector('source')) {
          gameMedia = videos[m];
          break;
        }
      }
    }

    if (gameMedia) {
      gameMedia.style.setProperty('display', 'block', 'important');
      gameMedia.style.setProperty('visibility', 'visible', 'important');
      gameMedia.style.setProperty('opacity', '1', 'important');
      gameMedia.style.setProperty('width', '100vw', 'important');
      gameMedia.style.setProperty('height', '100vh', 'important');
      gameMedia.style.setProperty('max-width', '100vw', 'important');
      gameMedia.style.setProperty('max-height', '100vh', 'important');
      gameMedia.style.setProperty('object-fit', 'contain', 'important');
      gameMedia.style.setProperty('position', 'fixed', 'important');
      gameMedia.style.setProperty('transform', 'none', 'important');
      gameMedia.style.setProperty('top', '0', 'important');
      gameMedia.style.setProperty('left', '0', 'important');
      gameMedia.style.setProperty('margin', '0', 'important');
      gameMedia.style.setProperty('padding', '0', 'important');
      gameMedia.style.setProperty('z-index', '99999', 'important');
      gameMedia.style.setProperty('background', '#000', 'important');

      if (gameMedia.tagName === 'VIDEO' && gameMedia.paused) {
        try {
          gameMedia.play().catch(function() {
            gameMedia.muted = true;
            gameMedia.play().catch(function() {});
          });
        } catch(e) {}
      }

      var parent = gameMedia.parentElement;
      while (parent && parent !== document.body) {
        parent.style.setProperty('width', '100vw', 'important');
        parent.style.setProperty('height', '100vh', 'important');
        parent.style.setProperty('position', 'fixed', 'important');
        parent.style.setProperty('top', '0', 'important');
        parent.style.setProperty('left', '0', 'important');
        parent.style.setProperty('margin', '0', 'important');
        parent.style.setProperty('padding', '0', 'important');
        parent.style.setProperty('border', 'none', 'important');
        parent.style.setProperty('background', '#000', 'important');
        parent.style.setProperty('z-index', '9999', 'important');
        parent = parent.parentElement;
        if (parent && parent.id === '__next') {
          var siblings = parent.children;
          for (var s = 0; s < siblings.length; s++) {
            if (!siblings[s].contains(gameMedia)) {
              siblings[s].style.setProperty('display', 'none', 'important');
              siblings[s].style.setProperty('height', '0', 'important');
            }
          }
          break;
        }
      }
    }
  }

  setInterval(cleanAndMaximizeGame, 80);
  if (window.MutationObserver) {
    var obs = new MutationObserver(cleanAndMaximizeGame);
    document.addEventListener('DOMContentLoaded', function() {
      obs.observe(document.body, { childList: true, subtree: true });
    });
  }

  // 10. Provide dummy elements for ad containers if missing
  document.addEventListener('DOMContentLoaded', function() {
    if (!document.getElementById('google-funding-choices')) {
      var d = document.createElement('div');
      d.id = 'google-funding-choices';
      d.style.display = 'none';
      document.body.appendChild(d);
    }
  });
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
        "Referer": "https://now.gg/",
        "Origin": "https://now.gg",
        "Host": "now.gg",
        "Accept": "*/*",
    }
    if headers:
        for k, v in headers.items():
            k_low = k.lower()
            if k_low not in {"host", "origin", "referer", "accept-encoding"}:
                request_headers[k] = v

    # Ensure Authorization header is ALWAYS populated for now.gg session requests
    token = get_guest_token()
    if token:
        auth_keys = [k for k in request_headers if k.lower() == "authorization"]
        if not auth_keys:
            request_headers["Authorization"] = f"NowV2 {token}"
        elif not request_headers[auth_keys[0]].strip() or request_headers[auth_keys[0]].strip() in {"NowV2", "Bearer"}:
            request_headers[auth_keys[0]] = f"NowV2 {token}"
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

        if parsed.path.startswith("/stream/play/"):
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

        forwarded_headers = {
            key: value
            for key, value in self.headers.items()
            if key.lower() not in {"host", "content-length", "connection", "accept-encoding"}
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

        for key, value in raw_headers:
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

        # Strip ads and inject shim into HTML responses
        if is_html and resp_body:
            resp_body = strip_ads_from_next_data(resp_body)
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
