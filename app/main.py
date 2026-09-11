import sys
import os
import shutil
import socket
import logging
import argparse
from html import escape
from urllib.parse import quote
from pathlib import Path
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

# كتم سجلات Uvicorn
logging.getLogger("uvicorn").setLevel(logging.CRITICAL)
logging.getLogger("uvicorn.access").setLevel(logging.CRITICAL)
logging.getLogger("uvicorn.error").setLevel(logging.CRITICAL)

RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
CYAN = "\033[36m"
RESET = "\033[0m"
CYAN_1 = "\033[1;36m"

# ASCII Art Header للتيرمينال عند البدء
TERMINAL_HEADER = r"""
 __   ______  _   _    _____           _ 
 \ \ / / __ \| \ | |  |_   _|__   ___ | |
  \ V /|  _ \|  \| |    | |/ _ \ / _ \| |
   | | | |_) | |\  |    | | (_) | (_) | |
   |_| |____/|_| \_|    |_|\___/ \___/|_|

    YBN QuickShare - Local File Sharing Tool
"""

app = FastAPI()

# تهيئة المسارات للتوافق مع PyInstaller
if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys._MEIPASS)
    EXE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).resolve().parent
    EXE_DIR = BASE_DIR

STATIC_FILES = EXE_DIR / "shared_files"
README_FILE = EXE_DIR / "README.txt"
os.makedirs(STATIC_FILES, exist_ok=True)

app.mount("/assets", StaticFiles(directory=BASE_DIR / "static_files"), name="assets")


def shared_path(relative_path: str) -> Path:
    target = (STATIC_FILES / relative_path).resolve()
    if not target.is_relative_to(STATIC_FILES.resolve()):
        raise HTTPException(status_code=403, detail="غير مسموح بالوصول لهذا المسار")
    return target

# ربط shared_files
app.mount("/shared", StaticFiles(directory=STATIC_FILES), name="shared")


@app.post("/upload")
async def upload_file(file: UploadFile = File(...), current_path: str = Form("")):
    try:
        target_dir = shared_path(current_path)
        if not target_dir.is_dir():
            raise HTTPException(status_code=404, detail="المجلد غير موجود")
        filename = file.filename or ""
        if not filename or filename in (".", "..") or any(c in filename for c in '/\\:'):
            raise HTTPException(status_code=400, detail="اسم الملف غير صالح")
        file_path = shared_path(str((target_dir / filename).relative_to(STATIC_FILES.resolve())))

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        redirect_url = f"/files/{quote(current_path)}" if current_path else "/"
        return RedirectResponse(url=redirect_url, status_code=303)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"فشل رفع الملف: {str(e)}")


@app.get("/", response_class=HTMLResponse)
@app.get("/files/{req_path:path}", response_class=HTMLResponse)
def list_files(req_path: str = ""):
    target_dir = shared_path(req_path)

    if not target_dir.exists():
        raise HTTPException(status_code=404, detail="المسار غير موجود")

    if target_dir.is_file():
        return FileResponse(
            path=target_dir,
            filename=target_dir.name,
            media_type="application/octet-stream"
        )

    try:
        items = os.listdir(target_dir)
        file_list_html = ""

        if req_path.strip("/"):
            parent_path = Path(req_path).parent
            parent_link = f"/files/{quote(parent_path.as_posix())}" if str(parent_path) != "." else "/"
            file_list_html += f"""
            <li class="item folder parent-folder">
                <a href="{parent_link}">
                    <span class="icon">⬅️</span>
                    <span class="name">.. (المجلد الأعلى)</span>
                </a>
            </li>
            """

        directories = [i for i in items if (target_dir / i).is_dir()]
        files = [i for i in items if (target_dir / i).is_file()]

        for d in sorted(directories):
            sub_path = f"{req_path}/{d}".strip("/")
            file_list_html += f"""
            <li class="item folder">
                <a href="/files/{quote(sub_path)}">
                    <span class="icon">📁</span>
                    <span class="name">{escape(d)}/</span>
                </a>
            </li>
            """

        for f in sorted(files):
            rel_path = f"{req_path}/{f}".strip("/")
            file_list_html += f"""
            <li class="item file">
                <a href="/shared/{quote(rel_path)}" download="{escape(f)}">
                    <span class="icon">📄</span>
                    <span class="name">{escape(f)}</span>
                    <span class="download-badge">تنزيل 📥</span>
                </a>
            </li>
            """

        html_content = f"""
        <!DOCTYPE html>
        <html dir="rtl" lang="ar">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>YBN QuickShare </title>
            <link rel="icon" type="image/png" href="/assets/logo.png">
            <style>
                :root {{
                    --bg-color: #0d1117;
                    --card-bg: #161b22;
                    --text-color: #c9d1d9;
                    --accent-yellow: #e3b341;
                    --primary: #38edf8;
                    --border: #30363d;
                }}
                body {{
                    font-family: system-ui, -apple-system, sans-serif;
                    background-color: var(--bg-color);
                    color: var(--text-color);
                    margin: 0;
                    padding: 20px;
                    display: flex;
                    justify-content: center;
                }}
                .container {{
                    width: 100%;
                    max-width: 800px;
                }}
                .brand-header {{
                    background: var(--card-bg);
                    padding: 18px 24px;
                    border-radius: 16px;
                    border: 1px solid var(--border);
                    margin-bottom: 16px;
                    display: flex;
                    align-items: center;
                    direction: ltr;
                    gap: 20px;
                }}
                .logo-img {{
                    width: 55px;
                    height: 55px;
                    border-radius: 12px;
                    object-fit: cover;
                    border: 2px solid var(--accent-yellow);
                    flex-shrink: 0;
                }}
                .brand-text h1 {{
                    margin: 0;
                    font-size: 1.4rem;
                    color: #ffffff;
                }}
                .brand-text h1 span {{ color: var(--accent-yellow); }}
                .brand-text p {{ margin: 2px 0 0 0; font-size: 0.85rem; color: #8b949e; }}
                
                .upload-card {{
                    background: var(--card-bg);
                    padding: 16px 20px;
                    border-radius: 12px;
                    border: 1px dashed var(--accent-yellow);
                    margin-bottom: 16px;
                }}
                .upload-form {{
                    display: flex;
                    gap: 10px;
                    align-items: center;
                    flex-wrap: wrap;
                }}
                .file-input {{
                    flex-grow: 1;
                    color: var(--text-color);
                    font-size: 0.9rem;
                }}
                .upload-btn {{
                    background: var(--accent-yellow);
                    color: #000;
                    border: none;
                    padding: 8px 18px;
                    border-radius: 8px;
                    font-weight: bold;
                    cursor: pointer;
                    transition: 0.2s;
                }}
                .upload-btn:hover {{
                    opacity: 0.9;
                }}

                .path-bar {{
                    background: var(--card-bg);
                    padding: 12px 18px;
                    border-radius: 10px;
                    border: 1px solid var(--border);
                    margin-bottom: 16px;
                    font-size: 0.95rem;
                    color: #8b949e;
                }}
                .path-text {{ color: var(--primary); font-weight: bold; }}
                ul {{ list-style: none; padding: 0; margin: 0; }}
                .item {{
                    background: var(--card-bg);
                    margin-bottom: 8px;
                    border-radius: 10px;
                    border: 1px solid var(--border);
                }}
                .item a {{
                    display: flex;
                    align-items: center;
                    padding: 14px 18px;
                    text-decoration: none;
                    color: var(--text-color);
                    gap: 12px;
                }}
                .icon {{ font-size: 1.25rem; }}
                .name {{ font-weight: 500; flex-grow: 1; word-break: break-all; }}
                .download-badge {{
                    font-size: 0.85rem;
                    background-color: rgba(227, 179, 65, 0.1);
                    color: var(--accent-yellow);
                    padding: 6px 12px;
                    border-radius: 8px;
                    font-weight: 600;
                    border: 1px solid rgba(227, 179, 65, 0.3);
                }}
                .parent-folder {{ background: #21262d; }}
            </style>
        </head>
        <body>
            <div class="container">
                <!-- الهيدر (تم تعديل المسارات إلى /shared/) -->
                <div class="brand-header">
                    <img src="/assets/logo.png" alt="YBN Logo" class="logo-img">
                    <div class="brand-text">
                        <h1>YBN <span>QuickShare</span></h1>
                        <p>الطريقة الأسرع لمشاركة الملفات</p>
                    </div>
                </div>

                <!-- رفع الملفات -->
                <div class="upload-card">
                    <form class="upload-form" action="/upload" method="post" enctype="multipart/form-data">
                        <input type="hidden" name="current_path" value="{escape(req_path)}">
                        <input type="file" name="file" class="file-input" required>
                        <button type="submit" class="upload-btn">رفع الملف 📤</button>
                    </form>
                </div>

                <!-- المسار الحالي -->
                <div class="path-bar">
                    <span>📂 المسار الحالي:</span>
                    <span class="path-text">/{escape(req_path)}</span>
                </div>

                <!-- القائمة -->
                <ul>
                    {file_list_html}
                </ul>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(content=html_content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

def handle_readme(ip, port):
    README_CONTENT = f"""YBN QuickShare - Local File Sharing Tool
----------------------------------------
افتح المتصفح على الرابط التالي على أي جهاز للوصول إلى واجهة التطبيق:

http://{ip}:{port}
----------------------------------------
- لا تقم بتشغيل VPN على نفس الجهاز الذي يعمل عليه التطبيق، وإلا فلن تتمكن الأجهزة الأخرى من الوصول إليه.
- تأكد من أن الجهازين على نفس الشبكة المحلية (Wi-Fi أو LAN).
"""
    README_FILE.write_text(README_CONTENT, encoding="utf-8")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="YBN QuickShare")
    parser.add_argument("--port", type=int, default=8050)
    args = parser.parse_args()
    ip = get_ip()
    port = args.port
    handle_readme(ip, port)
    print(f'{CYAN_1}{TERMINAL_HEADER}{RESET}')
    print(f"{YELLOW}Access the app at: {CYAN}http://{ip}:{port}{RESET}")
    print(50 * "-")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="critical", access_log=False)
