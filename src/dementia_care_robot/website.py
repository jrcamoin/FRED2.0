"""Public Human Frame Robotics website, separate from the resident interface.

The customer entry currently links directly to /app. Future customer accounts
need their own purchase/device authorization; caregiver sessions are separate.
"""


def fred_page() -> bytes:
    """Render the public website without reading resident data."""
    return '''<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Human Frame Robotics — Meet FRED</title>
<link rel="stylesheet" href="/static/site/fred.css"><style>
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:#f7f5ef;color:#203b36;font:18px/1.6 system-ui,sans-serif}
a{color:inherit}header,main,footer{max-width:1160px;margin:auto;padding:28px}header{display:flex;align-items:center;justify-content:space-between;gap:24px}
.brand{font-weight:800;text-decoration:none;letter-spacing:-.04em;font-size:23px}nav{display:flex;align-items:center;gap:24px;flex-wrap:wrap}nav a{text-decoration:none;font-size:15px}
.button{display:inline-block;background:#254f43;color:white;border-radius:100px;padding:14px 25px;text-decoration:none;font-weight:650}.secondary{background:transparent;color:#254f43;border:1px solid #254f43}
.hero{display:grid;grid-template-columns:1.2fr 1fr;align-items:center;gap:60px;padding:70px 0 90px}.eyebrow{text-transform:uppercase;letter-spacing:.16em;font-size:12px;font-weight:750;color:#587167}h1{font-size:clamp(42px,6vw,72px);line-height:1.07;letter-spacing:-.06em;margin:20px 0}h2{font-size:36px;line-height:1.2;letter-spacing:-.04em}h3{font-size:22px;margin-top:0}p{max-width:620px}.muted{color:#5b7068}.actions{display:flex;gap:14px;flex-wrap:wrap;margin-top:28px}
.portrait{background:#dbe7db;border-radius:140px 140px 32px 32px;min-height:400px;display:grid;place-content:center;text-align:center;padding:35px}.face{background:#254f43;border-radius:55px;padding:55px 65px;display:flex;gap:45px;box-shadow:0 24px 45px #203b3620}.eye{display:block;background:#eff7d5;width:24px;height:45px;border-radius:20px}.portrait p{margin-bottom:0;font-weight:650}.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:20px;margin:32px 0 70px}.card{background:white;padding:30px;border-radius:24px;border:1px solid #e0e5dc}.access{background:#254f43;color:white;padding:45px;border-radius:30px}.access .button{background:#edf3cf;color:#203b36}footer{font-size:14px;color:#5b7068;padding-top:45px;padding-bottom:45px}a:focus-visible{outline:3px solid #c16d32;outline-offset:5px}
@media(max-width:760px){header{align-items:flex-start;flex-direction:column}.hero{grid-template-columns:1fr;padding:30px 0;gap:30px}.portrait{min-height:300px}.cards{grid-template-columns:1fr}.access{padding:28px}nav{gap:16px}}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
</style></head><body>
<a class="skip-link" href="#main">Skip to content</a><header><a class="brand" href="/">Human Frame <span>Robotics</span></a><nav aria-label="Main navigation"><a href="/">The framework</a><a href="/fred" aria-current="page">Meet FRED</a><a href="/caregiver">Caregiver tools</a><a class="button" href="/app">Open your robot ↗</a></nav></header>
<main id="main"><div class="breadcrumb"><a href="/">Human Frame Robotics</a><span>/</span> Meet FRED</div><section class="hero" id="meet-fred"><div><span class="eyebrow">A Human Frame Robotics project · In development</span><h1>A familiar presence.<br>A little everyday help.</h1><p class="muted">Meet FRED, our robot companion project for people living with dementia and the people who care for them. Conversation, familiar photos, and gentle reminders come together in one place.</p><div class="actions"><a class="button" href="/app">Open your robot</a><a class="button secondary" href="#everyday">Explore FRED</a></div></div><div class="portrait"><div class="face" aria-hidden="true"><span class="eye"></span><span class="eye"></span></div><p>Hello. I’m FRED.</p><span class="muted">Your robot companion</span><span class="portrait-caption">A simple interface. A familiar place to return.</span></div></section>
<section id="everyday"><span class="eyebrow">Built around everyday moments</span><h2>Support that feels familiar.</h2><div class="cards"><article class="card"><span class="card-number">01 / CONNECT</span><h3>A space to talk</h3><p>Type to FRED or use voice when speech services are available. Keep the conversation within easy reach.</p></article><article class="card"><span class="card-number">02 / ROUTINE</span><h3>Gentle reminders</h3><p>Caregivers can schedule everyday tasks, choose repeat times, and attach a familiar voice note.</p></article><article class="card"><span class="card-number">03 / BELONGING</span><h3>Familiar faces</h3><p>Add family photos and recordings to bring a personal touch to the resident’s screen.</p></article></div></section>
<section class="journey"><div><span class="eyebrow">One companion. Two thoughtful spaces.</span><h2>For the everyday.<br>And the people behind it.</h2></div><div class="journey-options"><a href="/app"><span>FOR TIME WITH FRED</span><h3>Your companion space ↗</h3><p>Talk, see familiar photos, and respond to reminders in a calm, easy-to-read space.</p></a><a href="/caregiver"><span>FOR CAREGIVERS</span><h3>A little preparation. More connection. ↗</h3><p>Add reminders and family media, manage contacts, and review FRED’s responses.</p></a></div></section><section class="access"><span class="eyebrow" style="color:#dbe7db">Your FRED experience</span><h2>Ready to spend time with FRED?</h2><p>Open the robot app to start a conversation. You can also find reminders and familiar media in the caregiver dashboard.</p><p>Preview access is open for now. Customer sign-in for robot and software owners is planned.</p><div class="actions"><a class="button" href="/app">Open your robot ↗</a><a class="caregiver-link" href="/caregiver">Set up the caregiver space →</a></div></section>
</main><footer><div class="footer-links"><a href="/">Human Frame Robotics ↗</a><a href="/fred">Meet FRED</a><a href="/app">Companion app</a><a href="/caregiver">Caregiver tools</a></div>FRED prototype · FRED supports everyday interaction and does not replace caregivers or emergency services.</footer>
</body></html>'''.encode()


from pathlib import Path

SITE_DIR = Path(__file__).parent / "static" / "site"

def landing_page() -> bytes:
    """Serve the imported brand site without accessing private resident data."""
    return (SITE_DIR / "index.html").read_bytes()

def public_asset(path: str):
    """Only explicitly packaged public assets can be served."""
    assets = {
        "/static/site/" + name: SITE_DIR / name
        for name in ("styles.css", "conversion.css", "script.js", "fred.css",
                     "app.css", "assets/hero-robot.png")
    }
    asset = assets.get(path)
    return asset.read_bytes() if asset else None
