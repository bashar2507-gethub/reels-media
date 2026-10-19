"""Render an Instagram carousel (1080x1350 JPG slides) and a vertical slideshow video for YouTube.

    python scripts/render_carousel.py --id c001

Reads content/carousels/<id>.json and the images in images/<id>/, writes carousels/<id>/
slide-XX.jpg and carousels/<id>/<id>-slides.mp4. Text is laid out in Chromium (correct Arabic
shaping and right-to-left order) with the Cairo fonts in assets/fonts (OFL).
"""
from __future__ import annotations

import argparse
import base64
import html
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
W, H = 1080, 1350
LEVEL = {"strong": "#3DDC97", "mid": "#FFC14D", "limited": "#FF8A7A", "depends": "#7AD2F2", "plan": "#FFC14D"}
RANK_COLOR = {"دليل قوي": "#3DDC97", "دليل متوسط": "#FFC14D", "دليل محدود": "#FF8A7A", "يعتمد على الحالة": "#7AD2F2"}


def font_face(name: str, file: str) -> str:
    data = base64.b64encode((ROOT / "assets/fonts" / file).read_bytes()).decode()
    return f"@font-face{{font-family:'{name}';src:url(data:font/ttf;base64,{data}) format('truetype');}}"


def img_uri(path: Path) -> str:
    return "data:image/jpeg;base64," + base64.b64encode(path.read_bytes()).decode()


CSS = """
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:1080px;height:1350px;overflow:hidden;background:#071E23}
body{font-family:'CairoSB';color:#fff;direction:rtl}
.slide{position:relative;width:1080px;height:1350px;overflow:hidden;background:#071E23}
.photo{position:absolute;inset:0 0 auto 0;height:700px;background-size:cover;background-position:center}
.photo:after{content:'';position:absolute;inset:0;background:linear-gradient(180deg,rgba(7,30,35,.15) 0%,rgba(7,30,35,.25) 45%,#071E23 100%)}
.num{position:absolute;top:44px;left:48px;font-family:'CairoXB';font-size:28px;letter-spacing:1px;direction:ltr;
     background:rgba(7,30,35,.72);padding:6px 20px;border-radius:40px;border:2px solid rgba(255,255,255,.25)}
.badge{position:absolute;top:44px;right:48px;font-family:'CairoXB';font-size:30px;padding:6px 26px;border-radius:40px;color:#071E23}
.body{position:absolute;left:64px;right:64px;top:560px;bottom:118px;display:flex;flex-direction:column;justify-content:flex-start}
h1{font-family:'CairoBlack';font-size:64px;line-height:1.25;margin-bottom:22px}
.fig{display:flex;align-items:baseline;gap:22px;margin-bottom:18px}
.fig b{font-family:'CairoBlack';font-size:88px;color:#FFC14D;direction:ltr;unicode-bidi:isolate;line-height:1}
.fig span{font-size:30px;color:#D6E9EC;line-height:1.35}
ul{list-style:none}
li{position:relative;padding-right:40px;font-size:var(--fs,35px);line-height:1.5;margin-bottom:14px}
li:before{content:'';position:absolute;right:4px;top:.62em;width:16px;height:16px;border-radius:50%;background:#FFC14D}
.src{position:absolute;left:64px;right:64px;bottom:44px;font-size:22px;color:#9CC3CA;line-height:1.4;
     border-top:2px solid rgba(255,255,255,.12);padding-top:14px}
.src i{font-style:normal;direction:ltr;unicode-bidi:isolate}
.cover .photo{height:1350px}
.cover .photo:after{background:linear-gradient(180deg,rgba(7,30,35,.05) 0%,rgba(7,30,35,.2) 40%,rgba(7,30,35,.92) 72%,#071E23 100%)}
.cover .body{top:auto;bottom:150px}
.kicker{display:inline-block;align-self:flex-start;font-family:'CairoXB';font-size:32px;color:#071E23;background:#FFC14D;padding:6px 24px;border-radius:40px;margin-bottom:22px}
.cover h1{font-size:84px;line-height:1.22}
.sub{font-size:34px;color:#D6E9EC;line-height:1.45}
.swipe{position:absolute;bottom:56px;left:64px;font-family:'CairoXB';font-size:32px;color:#FFC14D}
.plan .photo{height:560px}
.plan .body{top:440px}
.steps{display:flex;flex-direction:column;gap:18px}
.step{background:rgba(255,255,255,.06);border-right:8px solid #FFC14D;border-radius:18px;padding:16px 26px}
.step b{display:block;font-family:'CairoXB';font-size:32px;color:#FFC14D}
.step span{font-size:var(--fs,32px);line-height:1.45}
.dim .photo{height:1350px;opacity:.28}
.dim .photo:after{background:linear-gradient(180deg,rgba(7,30,35,.4),#071E23)}
.dim .body{top:130px}
.rank{counter-reset:r}
.rank div{display:flex;justify-content:space-between;align-items:center;font-size:var(--fs,33px);padding:9px 0;border-bottom:2px solid rgba(255,255,255,.08)}
.rank div:before{counter-increment:r;content:counter(r);font-family:'CairoBlack';color:#FFC14D;width:52px}
.rank div span{flex:1}
.rank div em{font-style:normal;font-family:'CairoXB';font-size:24px;padding:3px 16px;border-radius:30px;color:#071E23}
.myths{margin-top:26px;background:rgba(255,138,122,.1);border:2px solid rgba(255,138,122,.5);border-radius:20px;padding:18px 26px}
.myths h2{font-family:'CairoXB';font-size:32px;color:#FF8A7A;margin-bottom:6px}
.myths p{font-size:var(--fs,31px);line-height:1.5}
.refs .body{top:130px;bottom:60px}
.refs ol{direction:ltr;padding-left:38px;font-family:'CairoSB';line-height:1.38;color:#D6E9EC}
.refs li{padding:0;margin-bottom:10px;font-size:var(--fs,25px)}
.refs li:before{display:none}
.refs .note{font-size:26px;color:#9CC3CA;margin-top:14px;line-height:1.5}
"""

FIT_JS = """
() => {
  const body = document.querySelector('.body'); if (!body) return 0;
  const lim = body.getBoundingClientRect().bottom;
  let fs = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--fs')) || 0;
  const last = () => { const k = body.lastElementChild; return k ? k.getBoundingClientRect().bottom : 0; };
  let n = 0;
  while (last() > lim && n < 40) { fs = (fs || 35) - 1; document.documentElement.style.setProperty('--fs', fs + 'px'); n++; }
  return last() > lim ? -1 : n;
}
"""


def esc(t: str) -> str:
    return html.escape(t)


def slide_html(s: dict, total: int, images: Path, fonts: str) -> str:
    kind = s.get("kind", "points")
    photo = f"<div class='photo' style=\"background-image:url('{img_uri(images / (s['image'] + '.jpg'))}')\"></div>" if s.get("image") else ""
    num = f"<div class='num'>{s['n']}/{total}</div>"
    badge = (f"<div class='badge' style='background:{LEVEL.get(s.get('level'), '#FFC14D')}'>{esc(s['badge'])}</div>"
             if s.get("badge") else "")
    src = f"<div class='src'>المصدر: <i>{esc(s['src'])}</i></div>" if s.get("src") else ""
    if kind == "cover":
        inner = (f"<div class='body'><div class='kicker'>{esc(s['kicker'])}</div><h1>{esc(s['title'])}</h1>"
                 f"<p class='sub'>{esc(s['sub'])}</p></div><div class='swipe'>← {esc(s['swipe'])}</div>")
        cls = "cover"
    elif kind == "plan":
        steps = "".join(f"<div class='step'><b>{esc(a)}</b><span>{esc(b)}</span></div>" for a, b in s["steps"])
        inner = f"<div class='body'><h1>{esc(s['title'])}</h1><div class='steps'>{steps}</div></div>"
        cls = "plan"
    elif kind == "summary":
        rows = "".join(f"<div><span>{esc(a)}</span><em style='background:{RANK_COLOR.get(b, '#FFC14D')}'>{esc(b)}</em></div>"
                       for a, b in s["ranking"])
        myths = "".join(f"<p>✗ {esc(m)}: غير صحيح</p>" for m in s["myths"])
        inner = (f"<div class='body'><h1>{esc(s['title'])}</h1><div class='rank'>{rows}</div>"
                 f"<div class='myths'><h2>3 خرافات شائعة</h2>{myths}</div></div>")
        cls = "dim"
    elif kind == "refs":
        refs = "".join(f"<li>{esc(r)}</li>" for r in s["refs"])
        inner = (f"<div class='body'><h1>{esc(s['title'])}</h1><ol>{refs}</ol>"
                 f"<p class='note'>معلومات عامة للتثقيف، ولا تغني عن استشارة مختص. الصور مولّدة بالذكاء الاصطناعي.</p></div>")
        cls = "refs"
    else:
        fig = (f"<div class='fig'><b>{esc(s['figure'])}</b><span>{esc(s['figure_sub'])}</span></div>"
               if s.get("figure") else "")
        pts = "".join(f"<li>{esc(p)}</li>" for p in s["points"])
        inner = f"<div class='body'><h1>{esc(s['title'])}</h1>{fig}<ul>{pts}</ul></div>"
        cls = ""
    return (f"<!doctype html><html lang='ar' dir='rtl'><head><meta charset='utf-8'><style>{fonts}{CSS}</style></head>"
            f"<body><div class='slide {cls}'>{photo}{num}{badge}{inner}{src}</div></body></html>")


def render(cid: str) -> list[Path]:
    from playwright.sync_api import sync_playwright
    spec = json.loads((ROOT / f"content/carousels/{cid}.json").read_text(encoding="utf-8"))
    images, out = ROOT / spec["images"], ROOT / "carousels" / cid
    out.mkdir(parents=True, exist_ok=True)
    fonts = font_face("CairoBlack", "Cairo-Black.ttf") + font_face("CairoXB", "Cairo-ExtraBold.ttf") + \
        font_face("CairoSB", "Cairo-SemiBold.ttf")
    total, paths, report = len(spec["slides"]), [], {}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": W, "height": H})
        for s in spec["slides"]:
            page.set_content(slide_html(s, total, images, fonts))
            page.evaluate("document.fonts.ready")
            report[s["n"]] = page.evaluate(FIT_JS)
            png = out / f"slide-{s['n']:02d}.png"
            page.screenshot(path=str(png))
            jpg = png.with_suffix(".jpg")
            subprocess.run(["python3", "-c", f"from PIL import Image; Image.open('{png}').convert('RGB').save('{jpg}', quality=92)"], check=True)
            png.unlink()
            paths.append(jpg)
        browser.close()
    bad = [n for n, v in report.items() if v == -1]
    if bad:
        raise SystemExit(f"text does not fit on slides {bad}")
    print("font shrink steps per slide:", report)
    return paths


def video(cid: str, slides: list[Path], seconds: float = 6.0, last: float = 9.0) -> Path:
    """1080x1920 slideshow: each 4:5 slide centred over a blurred copy of itself, 0.5 s crossfades."""
    out = ROOT / "carousels" / cid / f"{cid}-slides.mp4"
    inputs, filters, n = [], [], len(slides)
    durs = [seconds] * (n - 1) + [last]
    for i, (s, d) in enumerate(zip(slides, durs)):
        inputs += ["-loop", "1", "-t", f"{d + 0.5}", "-i", str(s)]
        filters.append(f"[{i}:v]split[a{i}][b{i}];[a{i}]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
                       f"gblur=sigma=40,eq=brightness=-0.25[bg{i}];[bg{i}][b{i}]overlay=0:(H-h)/2,fps=30,format=yuv420p,setsar=1[v{i}]")
    prev, t = "v0", durs[0]
    for i in range(1, n):
        filters.append(f"[{prev}][v{i}]xfade=transition=fade:duration=0.5:offset={t:.2f}[x{i}]")
        prev, t = f"x{i}", t + durs[i]
    cmd = ["ffmpeg", "-y", "-v", "error", *inputs, "-f", "lavfi", "-t", f"{t + 0.5:.2f}", "-i", "anullsrc=r=48000:cl=stereo",
           "-filter_complex", ";".join(filters), "-map", f"[{prev}]", "-map", f"{n}:a", "-c:v", "libx264", "-preset", "medium",
           "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart", str(out)]
    subprocess.run(cmd, check=True)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True)
    ap.add_argument("--no-video", action="store_true")
    a = ap.parse_args()
    paths = render(a.id)
    if not a.no_video:
        print(video(a.id, paths))
