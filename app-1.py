import os, re, shutil, tempfile, threading
from flask import Flask, request, send_file, jsonify, after_this_request, Response
import yt_dlp

app = Flask(__name__)
SLOTS = threading.Semaphore(int(os.environ.get("MAX_JOBS", "3")))
URL_RE = re.compile(r"^https?://([\w-]+\.)?(youtube\.com|youtu\.be)/", re.I)
FMT = ("bv*[height<=720][ext=mp4]+ba[ext=m4a]/b[height<=720][ext=mp4]"
       "/bv*[height<=720]+ba/b[height<=720]")

@app.get("/")
def home():
    return Response(PAGE, mimetype="text/html")

@app.get("/api/download")
def download():
    url = (request.args.get("url") or "").strip()
    if not URL_RE.match(url):
        return jsonify(error="الرابط غير صحيح، تأكد أنه رابط يوتيوب"), 400
    if not SLOTS.acquire(blocking=False):
        return jsonify(error="السيرفر مشغول، حاول بعد لحظات"), 503
    tmp = tempfile.mkdtemp(prefix="yt_")
    opts = {
        "format": FMT,
        "merge_output_format": "mp4",
        "outtmpl": os.path.join(tmp, "%(title).120B.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "concurrent_fragment_downloads": 8,
        "http_chunk_size": 10 * 1024 * 1024,
        "retries": 5,
    }
    opts["js_runtimes"] = {"node": {}}
    ck = "/etc/secrets/cookies.txt"
    if os.path.exists(ck):
        shutil.copy(ck, os.path.join(tmp, "cookies.txt"))
        opts["cookiefile"] = os.path.join(tmp, "cookies.txt")
    if shutil.which("aria2c"):
        opts["external_downloader"] = "aria2c"
        opts["external_downloader_args"] = {"default": ["-x16", "-s16", "-k1M"]}
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            path = os.path.splitext(ydl.prepare_filename(info))[0] + ".mp4"
    except Exception as e:
        shutil.rmtree(tmp, ignore_errors=True)
        SLOTS.release()
        return jsonify(error="تعذر تحميل الفيديو: " + str(e)[:160]), 500
    SLOTS.release()

    @after_this_request
    def cleanup(resp):
        resp.call_on_close(lambda: shutil.rmtree(tmp, ignore_errors=True))
        return resp
    return send_file(path, as_attachment=True,
                     download_name=os.path.basename(path), mimetype="video/mp4")

PAGE = """<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>تحميل 720</title>
<style>
:root{--bg:#eef2f6;--ink:#14213d;--mute:#5b6b85;--acc:#1f5eff;--card:#fff}
@media(prefers-color-scheme:dark){:root{--bg:#0e1522;--ink:#e8eefc;--mute:#8d9bb5;--acc:#5b8cff;--card:#17213a}}
*{box-sizing:border-box}
body{margin:0;min-height:100vh;display:grid;place-items:center;padding:20px;background:var(--bg);color:var(--ink);font-family:"Segoe UI",Tahoma,sans-serif}
main{width:100%;max-width:460px}
h1{font-size:2.2rem;margin:0 0 6px}
p{color:var(--mute);margin:0 0 22px;line-height:1.7}
.box{background:var(--card);padding:16px;border-radius:14px}
input{width:100%;padding:14px;font-size:1rem;border:2px solid transparent;border-radius:10px;background:var(--bg);color:var(--ink);direction:ltr;text-align:left}
input:focus{outline:none;border-color:var(--acc)}
button{width:100%;margin-top:12px;padding:14px;font-size:1.05rem;font-weight:700;border:0;border-radius:10px;background:var(--acc);color:#fff;cursor:pointer}
button:disabled{opacity:.6}
#msg{min-height:1.6em;margin-top:12px;font-size:.95rem}
.err{color:#d93a3a}.ok{color:var(--mute)}
</style></head><body><main>
<h1>تحميل 720p</h1>
<p>الصق رابط فيديو يوتيوب، ويبدأ التحميل بصيغة MP4 مباشرة.</p>
<div class="box">
<input id="u" type="url" placeholder="https://youtu.be/..." autocomplete="off">
<button id="b">حمّل الفيديو</button>
<div id="msg"></div></div></main>
<script>
const u=document.getElementById('u'),b=document.getElementById('b'),m=document.getElementById('msg');
async function go(){
  const url=u.value.trim(); if(!url)return;
  b.disabled=true; m.className='ok'; m.textContent='جاري تجهيز الفيديو... لا تغلق الصفحة';
  try{
    const r=await fetch('/api/download?url='+encodeURIComponent(url));
    if(!r.ok){const j=await r.json();throw new Error(j.error)}
    const blob=await r.blob();
    const cd=r.headers.get('Content-Disposition')||'';
    const n=(cd.match(/filename\\*=UTF-8''([^;]+)/)||[])[1];
    const a=document.createElement('a');
    a.href=URL.createObjectURL(blob);
    a.download=n?decodeURIComponent(n):'video.mp4';
    a.click(); m.textContent='تم التحميل ✓';
  }catch(e){m.className='err';m.textContent=e.message||'حدث خطأ'}
  b.disabled=false;
}
b.onclick=go; u.addEventListener('keydown',e=>{if(e.key==='Enter')go()});
u.addEventListener('paste',()=>setTimeout(go,50));
</script></body></html>"""

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), threaded=True)
