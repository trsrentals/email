#!/usr/bin/env python3
"""
TRS Email Validator — Local Backend
Unlocks MX validation and Odoo integration.

Install: pip install flask flask-cors dnspython openpyxl
Run:     python backend.py
"""

import subprocess, sys, io, re, threading, os
from concurrent.futures import ThreadPoolExecutor, as_completed

REQUIRED = ["flask", "flask-cors", "dnspython", "openpyxl"]

def install_deps():
    missing = []
    for pkg in REQUIRED:
        try: __import__(pkg.replace("-","_"))
        except ImportError: missing.append(pkg)
    if not missing: return
    print(f"Installing: {', '.join(missing)}...")
    try:
        subprocess.check_call([sys.executable,"-m","pip","install"]+missing,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except:
        subprocess.check_call([sys.executable,"-m","pip","install",
            "--break-system-packages"]+missing,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("Done.")

install_deps()

from flask import Flask, request, jsonify
from flask_cors import CORS
import requests

try:
    import dns.resolver, dns.exception
    DNS_OK = True
except ImportError:
    DNS_OK = False

try:
    import openpyxl
    XLSX_OK = True
except ImportError:
    XLSX_OK = False

app = Flask(__name__)
CORS(app, origins="*")

EMAIL_RE = re.compile(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$')

DISPOSABLE = {
    "mailinator.com","guerrillamail.com","tempmail.com","throwam.com","yopmail.com",
    "sharklasers.com","10minutemail.com","trashmail.com","fakeinbox.com","maildrop.cc",
    "dispostable.com","spamgourmet.com","trashmail.net","mailnull.com","spam4.me",
    "getairmail.com","discard.email","tempr.email","temp-mail.org","tempinbox.com",
    "tempail.com","temporary-mail.net","tmailinator.com","mailscrap.com","mailzilla.com",
    "meltmail.com","mintemail.com","binkmail.com","guerrillamail.biz","guerrillamail.de",
    "guerrillamail.info","guerrillamail.net","guerrillamail.org","guerrillamailblock.com",
    "ieatspam.eu","ieatspam.info","jetable.com","jetable.net","jetable.org",
    "killmail.com","killmail.net","nowmymail.com","nospamfor.us","trashmail.at",
    "trashmail.io","trashmail.me","trashmail.xyz","spamhereplease.com","spaml.de",
    "teleworm.us","tempalias.com","wegwerfmail.de","wegwerfmail.net","wegwerfmail.org",
    "filzmail.com","frapmail.com","mt2009.com","mt2014.com","myspamless.com",
    "obobbo.com","oneoffemail.com","owlpic.com","pepbot.com","pjjkp.com",
    "powered.name","povertymail.com","zehnminuten.de","zehnminutenmail.de",
    "zippymail.info","zoemail.net","zomg.info","objectmail.com","pookmail.com",
}

TYPO_MAP = {
    "gmial.com":"gmail.com","gmal.com":"gmail.com","gamil.com":"gmail.com",
    "gnail.com":"gmail.com","gmail.co":"gmail.com","gmail.cm":"gmail.com",
    "gmail.ocm":"gmail.com","gmaill.com":"gmail.com","gmali.com":"gmail.com",
    "yaho.com":"yahoo.com","yahooo.com":"yahoo.com","yhoo.com":"yahoo.com",
    "yahoo.co":"yahoo.com","hotmial.com":"hotmail.com","hotmai.com":"hotmail.com",
    "hotmil.com":"hotmail.com","hotmal.com":"hotmail.com","hotnail.com":"hotmail.com",
    "hotmaill.com":"hotmail.com","outlok.com":"outlook.com","outllook.com":"outlook.com",
    "outloook.com":"outlook.com","otulook.com":"outlook.com",
    "iclod.com":"icloud.com","icoud.com":"icloud.com","icloud.co":"icloud.com",
    "protonmial.com":"protonmail.com","protonmai.com":"protonmail.com",
    "aoll.com":"aol.com","aol.co":"aol.com",
}

_mx_cache = {}
_mx_lock  = threading.Lock()

def check_mx(domain):
    with _mx_lock:
        if domain in _mx_cache: return _mx_cache[domain]
    if not DNS_OK: return None
    try:
        answers  = dns.resolver.resolve(domain,'MX',lifetime=6)
        valid_mx = [r for r in answers if str(r.exchange) not in ('.','')]
        result   = len(valid_mx) > 0
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer,
            dns.exception.Timeout, dns.resolver.NoNameservers):
        result = False
    except Exception:
        result = None
    with _mx_lock: _mx_cache[domain] = result
    return result

def validate_one(email):
    email = email.strip().lower()
    out = {"email":email,"valid":False,"no_typo":True,"not_disposable":True,
           "has_mx":False,"fail_reason":"","typo_suggestion":None,"mx_checked":DNS_OK}
    if not email or len(email) > 254:
        out["fail_reason"] = "Empty or too long"; return out
    if not EMAIL_RE.match(email):
        out["fail_reason"] = "Invalid syntax"; return out
    local, domain = email.split("@",1)
    if len(local) > 64:
        out["fail_reason"] = "Local part too long"; return out
    if domain in TYPO_MAP:
        sug = f"{local}@{TYPO_MAP[domain]}"
        out["no_typo"] = False; out["typo_suggestion"] = sug
        out["fail_reason"] = f"Possible typo — did you mean {sug}?"; return out
    if domain in DISPOSABLE:
        out["not_disposable"] = False
        out["fail_reason"] = "Disposable/temporary email provider"; return out
    has_mx = check_mx(domain)
    if has_mx is False:
        out["fail_reason"] = "No MX records — domain cannot receive email"; return out
    if has_mx is None:
        out["valid"] = True; out["fail_reason"] = "MX unverified (DNS unavailable)"; return out
    out["has_mx"] = True; out["valid"] = True
    return out

def extract_emails(text):
    found = re.findall(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', text)
    return list(dict.fromkeys(e.lower().strip() for e in found))

def parse_upload(filename, content_bytes):
    name = filename.lower()
    if name.endswith(('.txt','.csv')):
        try:    text = content_bytes.decode('utf-8-sig')
        except: text = content_bytes.decode('latin-1', errors='replace')
        return extract_emails(text), None
    if name.endswith(('.xlsx','.xls')):
        if not XLSX_OK:
            return None, "openpyxl not installed — run: pip install openpyxl"
        try:
            wb = openpyxl.load_workbook(io.BytesIO(content_bytes),read_only=True,data_only=True)
            parts = []
            for sheet in wb.worksheets:
                for row in sheet.iter_rows(values_only=True):
                    for cell in row:
                        if cell and isinstance(cell, str): parts.append(cell)
            wb.close()
            return extract_emails(' '.join(parts)), None
        except Exception as e:
            return None, f"XLSX error: {e}"
    return None, "Unsupported file type. Use .csv, .xlsx, or .txt"

# ── ROUTES ────────────────────────────────────────────────────────────────────
@app.route('/ping')
def ping():
    return jsonify({"status":"ok","dns":DNS_OK,"xlsx":XLSX_OK,"version":"2.0"})

@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify({"error":"No file received"}), 400
    f = request.files['file']
    emails, err = parse_upload(f.filename, f.read())
    if err:    return jsonify({"error":err}), 400
    if not emails: return jsonify({"error":"No email addresses found in file"}), 400
    return jsonify({"emails":emails,"count":len(emails)})

@app.route('/validate', methods=['POST'])
def validate():
    data   = request.get_json(silent=True) or {}
    emails = [str(e).strip() for e in data.get('emails',[]) if e]
    if not emails: return jsonify({"results":[]})
    order   = {e:i for i,e in enumerate(emails)}
    results = []
    with ThreadPoolExecutor(max_workers=10) as ex:
        futures = {ex.submit(validate_one,e):e for e in emails}
        for f in as_completed(futures): results.append(f.result())
    results.sort(key=lambda r: order.get(r['email'],9999))
    return jsonify({"results":results})

# ── ODOO PROXY ────────────────────────────────────────────────────────────────
@app.route('/odoo/<path:path>', methods=['GET','POST','PUT','DELETE','OPTIONS'])
def odoo_proxy(path):
    odoo_url = request.headers.get('X-Odoo-URL','').rstrip('/')
    if not odoo_url:
        return jsonify({"error":"Missing X-Odoo-URL header"}), 400
    target = f"{odoo_url}/{path}"
    if request.query_string:
        target += '?' + request.query_string.decode()
    skip = {'host','content-length','transfer-encoding','connection','x-odoo-url','origin'}
    headers = {k:v for k,v in request.headers if k.lower() not in skip}
    try:
        resp = requests.request(
            method=request.method, url=target,
            headers=headers, data=request.get_data(),
            cookies=request.cookies, allow_redirects=True, timeout=30)
    except requests.exceptions.ConnectionError as e:
        return jsonify({"error":f"Cannot reach Odoo: {e}"}), 502
    except requests.exceptions.Timeout:
        return jsonify({"error":"Odoo request timed out"}), 504
    skip_resp = {'content-encoding','content-length','transfer-encoding','connection'}
    out_headers = {k:v for k,v in resp.headers.items() if k.lower() not in skip_resp}
    out_headers['Access-Control-Allow-Origin'] = '*'
    out_headers['Access-Control-Allow-Headers'] = '*'
    from flask import Response
    return Response(resp.content, status=resp.status_code, headers=out_headers)

if __name__ == '__main__':
    PORT = 7842
    print(f"""
╔══════════════════════════════════════════════════════╗
║      TRS Email Validator — Local Backend v2          ║
╠══════════════════════════════════════════════════════╣
║  DNS/MX : {'✓ active' if DNS_OK else '✗ install dnspython'}
║  XLSX   : {'✓ active' if XLSX_OK else '✗ install openpyxl'}
╠══════════════════════════════════════════════════════╣
║  Running on http://localhost:{PORT}
║  Keep this window open while using the tool
╚══════════════════════════════════════════════════════╝
""")
    app.run(host='127.0.0.1', port=PORT, debug=False, threaded=True)
