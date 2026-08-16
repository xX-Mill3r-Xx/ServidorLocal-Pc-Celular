#!/usr/bin/env python3
r"""
Servidor local de arquivos.

Permite navegar, baixar e enviar (upload) arquivos entre este computador
e qualquer dispositivo (ex.: celular) conectado à MESMA rede Wi-Fi/LAN,
acessando pelo navegador em: http://<IP_DO_PC>:<PORTA>

Uso:
    python app.py                     # compartilha a pasta atual
    python app.py --dir "C:\Users\eu\Documentos"
    python app.py --port 8080
"""

import argparse
import os
import socket
from pathlib import Path

from flask import (
    Flask,
    abort,
    redirect,
    render_template_string,
    request,
    send_from_directory,
    url_for,
)
from werkzeug.utils import secure_filename

app = Flask(__name__)

# Definido em main() a partir dos argumentos de linha de comando
ROOT_DIR: Path = Path.cwd()


def safe_join(root: Path, relative: str) -> Path:
    """Impede 'path traversal' (ex.: ../../etc/passwd)."""
    target = (root / relative).resolve()
    if root not in target.parents and target != root:
        abort(403)
    return target


TEMPLATE = """
<!doctype html>
<html lang="pt-br">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Compartilhamento local - {{ current_rel or '/' }}</title>
  <style>
    * { box-sizing: border-box; }
    body {
      font-family: -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif;
      background: #0f1115; color: #e6e6e6; margin: 0; padding: 16px;
    }
    h1 { font-size: 1.1rem; word-break: break-all; color: #f5f5f5; }
    .breadcrumb { font-size: 0.85rem; color: #9aa0a6; margin-bottom: 14px; }
    .breadcrumb a { color: #6db3f2; text-decoration: none; }
    .card {
      background: #1a1d24; border: 1px solid #2a2d35; border-radius: 10px;
      padding: 12px; margin-bottom: 16px;
    }
    ul { list-style: none; padding: 0; margin: 0; }
    li {
      display: flex; align-items: center; justify-content: space-between;
      padding: 10px 6px; border-bottom: 1px solid #23262e;
    }
    li:last-child { border-bottom: none; }
    li a.name { color: #e6e6e6; text-decoration: none; flex: 1; }
    li a.name:hover { color: #6db3f2; }
    .icon { margin-right: 8px; }
    .dl { color: #6db3f2; text-decoration: none; font-size: 0.85rem; margin-left: 10px; }
    .empty { color: #8a8f98; padding: 10px; }
    form.upload {
      display: flex; flex-direction: column; gap: 10px;
    }
    input[type=file] {
      background: #12151b; color: #e6e6e6; border: 1px dashed #3a3f4a;
      border-radius: 8px; padding: 12px; width: 100%;
    }
    button {
      background: #3d7be0; color: white; border: none; border-radius: 8px;
      padding: 12px; font-size: 1rem; cursor: pointer;
    }
    button:active { background: #2f63b8; }
    .flash { background: #17321f; border: 1px solid #275b34; color: #b7f0c4;
      padding: 8px 12px; border-radius: 8px; margin-bottom: 14px; font-size: 0.9rem; }
  </style>
</head>
<body>
  <h1>📁 Compartilhamento local</h1>
  <div class="breadcrumb">
    <a href="{{ url_for('browse', subpath='') }}">raiz</a>
    {% for name, path in crumbs %} / <a href="{{ url_for('browse', subpath=path) }}">{{ name }}</a>{% endfor %}
  </div>

  {% if uploaded %}
    <div class="flash">✅ Arquivo "{{ uploaded }}" enviado com sucesso!</div>
  {% endif %}

  <div class="card">
    <form class="upload" method="post" enctype="multipart/form-data"
          action="{{ url_for('upload', subpath=current_rel) }}">
      <input type="file" name="file" multiple required>
      <button type="submit">⬆️ Enviar arquivo(s) para esta pasta</button>
    </form>
  </div>

  <div class="card">
    <ul>
      {% if current_rel %}
        <li><a class="name" href="{{ url_for('browse', subpath=parent_rel) }}">⬅️ .. (voltar)</a></li>
      {% endif %}
      {% for entry in entries %}
        <li>
          {% if entry.is_dir %}
            <a class="name" href="{{ url_for('browse', subpath=entry.rel) }}">📁 {{ entry.name }}</a>
          {% else %}
            <a class="name" href="{{ url_for('browse', subpath=entry.rel) }}">📄 {{ entry.name }}
              <span style="color:#8a8f98; font-size:0.8rem;">({{ entry.size }})</span>
            </a>
            <a class="dl" href="{{ url_for('download', subpath=entry.rel) }}">baixar</a>
          {% endif %}
        </li>
      {% else %}
        <li class="empty">Pasta vazia.</li>
      {% endfor %}
    </ul>
  </div>
</body>
</html>
"""


def human_size(num: float) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if num < 1024:
            return f"{num:.0f} {unit}" if unit == "B" else f"{num:.1f} {unit}"
        num /= 1024
    return f"{num:.1f} PB"


@app.route("/", defaults={"subpath": ""})
@app.route("/browse/<path:subpath>")
def browse(subpath):
    target = safe_join(ROOT_DIR, subpath)
    if not target.exists():
        abort(404)
    if target.is_file():
        # Se o usuário clicar num arquivo, oferece o download
        return redirect(url_for("download", subpath=subpath))

    entries = []
    for item in sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
        rel = str(item.relative_to(ROOT_DIR)).replace(os.sep, "/")
        entries.append({
            "name": item.name,
            "rel": rel,
            "is_dir": item.is_dir(),
            "size": "" if item.is_dir() else human_size(item.stat().st_size),
        })

    current_rel = subpath.strip("/")
    parts = current_rel.split("/") if current_rel else []
    crumbs, acc = [], []
    for p in parts:
        acc.append(p)
        crumbs.append((p, "/".join(acc)))

    parent_rel = "/".join(parts[:-1])

    uploaded = request.args.get("uploaded", "")

    return render_template_string(
        TEMPLATE,
        entries=entries,
        current_rel=current_rel,
        crumbs=crumbs,
        parent_rel=parent_rel,
        uploaded=uploaded,
    )


@app.route("/download/<path:subpath>")
def download(subpath):
    target = safe_join(ROOT_DIR, subpath)
    if not target.exists() or target.is_dir():
        abort(404)
    return send_from_directory(target.parent, target.name, as_attachment=True)


@app.route("/upload/", defaults={"subpath": ""}, methods=["POST"])
@app.route("/upload/<path:subpath>", methods=["POST"])
def upload(subpath):
    target_dir = safe_join(ROOT_DIR, subpath)
    if not target_dir.exists() or not target_dir.is_dir():
        abort(404)

    files = request.files.getlist("file")
    last_name = ""
    for f in files:
        if not f or not f.filename:
            continue
        filename = secure_filename(f.filename)
        if filename:
            f.save(target_dir / filename)
            last_name = filename

    return redirect(url_for("browse", subpath=subpath, uploaded=last_name))


def get_local_ip() -> str:
    """Descobre o IP local (na rede) deste computador."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


def main():
    global ROOT_DIR
    parser = argparse.ArgumentParser(description="Servidor local de arquivos.")
    parser.add_argument("--dir", default=".", help="Pasta a ser compartilhada (padrão: pasta atual)")
    parser.add_argument("--port", type=int, default=5000, help="Porta do servidor (padrão: 5000)")
    args = parser.parse_args()

    ROOT_DIR = Path(args.dir).resolve()
    if not ROOT_DIR.exists():
        raise SystemExit(f"Pasta não encontrada: {ROOT_DIR}")

    ip = get_local_ip()
    print("=" * 60)
    print(" Servidor de arquivos rodando!")
    print(f" Pasta compartilhada: {ROOT_DIR}")
    print(f" No PC:      http://127.0.0.1:{args.port}")
    print(f" No celular: http://{ip}:{args.port}")
    print(" (celular precisa estar na MESMA rede Wi-Fi que este PC)")
    print("=" * 60)

    app.run(host="0.0.0.0", port=args.port, debug=False)


if __name__ == "__main__":
    main()
