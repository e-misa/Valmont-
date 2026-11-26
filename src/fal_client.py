"""Cliente mínimo da fila do fal.ai (via curl, pelo proxy do ambiente).

A chave NÃO fica no código nem em variável: o proxy da sessão injeta o
cabeçalho Authorization nas requisições para queue.fal.run.

Uso típico:
    from fal_client import run, data_uri, download
    res = run("fal-ai/nano-banana/edit", {"prompt": "...", "image_urls": [data_uri(path)]})
    download(res["images"][0]["url"], "build/gerados/take.png")

Cada chamada fica registrada em build/gerados/registro.jsonl (modelo,
parâmetros sem as imagens, id do pedido e URLs de saída), para auditoria.
"""
from __future__ import annotations

import base64
import json
import mimetypes
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "build/gerados/registro.jsonl"
QUEUE = "https://queue.fal.run"


def _curl(args, data=None, timeout=120):
    cmd = ["curl", "-sS", "--max-time", str(timeout), "-H", "Authorization: Key proxy-injected",
           "-w", "\n%{http_code}"] + args
    r = subprocess.run(cmd, input=data, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"curl falhou: {r.stderr.strip()}")
    body, _, code = r.stdout.rpartition("\n")
    return int(code), body


def data_uri(path, max_side=None):
    p = Path(path)
    raw = p.read_bytes()
    if max_side:
        from io import BytesIO
        from PIL import Image
        im = Image.open(p).convert("RGB")
        im.thumbnail((max_side, max_side), Image.LANCZOS)
        buf = BytesIO()
        im.save(buf, "JPEG", quality=94)
        raw = buf.getvalue()
        mime = "image/jpeg"
    else:
        mime = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
    return f"data:{mime};base64," + base64.b64encode(raw).decode()


def _strip(obj):
    """Remove data URIs do registro (só metadados)."""
    if isinstance(obj, dict):
        return {k: _strip(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_strip(v) for v in obj]
    if isinstance(obj, str) and obj.startswith("data:"):
        return obj[:30] + "...(imagem)"
    return obj


def submit(model, payload):
    code, body = _curl(["-X", "POST", "-H", "Content-Type: application/json",
                        "--data-binary", "@-", f"{QUEUE}/{model}"], data=json.dumps(payload))
    if code >= 300:
        raise RuntimeError(f"envio {model}: HTTP {code}: {body[:500]}")
    return json.loads(body)


def wait(job, poll=4.0, timeout=1800):
    t0 = time.time()
    while True:
        code, body = _curl([job["status_url"]], timeout=60)
        if code >= 300 and code != 202:
            raise RuntimeError(f"status: HTTP {code}: {body[:300]}")
        st = json.loads(body).get("status")
        if st == "COMPLETED":
            break
        if time.time() - t0 > timeout:
            raise TimeoutError(f"pedido {job.get('request_id')} demorou demais")
        time.sleep(poll)
    code, body = _curl([job["response_url"]], timeout=120)
    if code >= 300:
        raise RuntimeError(f"resultado: HTTP {code}: {body[:500]}")
    return json.loads(body)


def run(model, payload, tag=""):
    job = submit(model, payload)
    res = wait(job)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a") as f:
        f.write(json.dumps({"t": time.strftime("%Y-%m-%d %H:%M:%S"), "tag": tag, "model": model,
                            "request_id": job.get("request_id"), "payload": _strip(payload),
                            "result": _strip(res)}, ensure_ascii=False) + "\n")
    return res


def download(url, dest):
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["curl", "-sS", "-L", "--max-time", "300", "-o", str(dest), "-w", "%{http_code}", url],
                       capture_output=True, text=True)
    if r.returncode != 0 or not r.stdout.startswith("2"):
        raise RuntimeError(f"download falhou ({r.stdout}): {r.stderr.strip()}")
    return dest
