#!/usr/bin/env python3
"""LocalDrop: servidor local e interface Windows."""
import argparse, os, queue, socket, sys, threading, webbrowser
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import BOTH, END, LEFT, X, filedialog, messagebox, ttk
from flask import Flask, abort, jsonify, redirect, render_template_string, request, send_from_directory, url_for
from werkzeug.serving import make_server
from werkzeug.utils import secure_filename

app = Flask(__name__); ROOT_DIR = Path.cwd(); EVENTS = queue.Queue()
def safe_join(root, rel):
    p=(root/rel).resolve()
    if root not in p.parents and p != root: abort(403)
    return p
def human_size(n):
    for u in ('B','KB','MB','GB','TB'):
        if n<1024:return f'{n:.0f} {u}' if u=='B' else f'{n:.1f} {u}'
        n/=1024
    return f'{n:.1f} PB'

PAGE='''<!doctype html><html lang="pt-br"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>LocalDrop</title><style>*{box-sizing:border-box}body{margin:0;background:#101827;color:#eaf0ff;font:16px Segoe UI,Arial}.w{max-width:800px;margin:auto;padding:24px}.muted{color:#aab9d3}.card{background:#192338;border:1px solid #2c3b59;border-radius:16px;padding:18px;margin-top:18px}.upload{border:2px dashed #526b9f;text-align:center;padding:25px;border-radius:12px}button,a.dl{border:0;border-radius:9px;background:#5086ff;color:#fff;padding:11px 16px;font-weight:600;text-decoration:none;margin-top:12px}.bar{height:9px;border-radius:9px;background:#2a3853;margin-top:14px;overflow:hidden}.bar i{display:block;height:100%;width:0;background:#5de0a5}ul{list-style:none;margin:0;padding:0}li{padding:13px 4px;border-bottom:1px solid #293750;display:flex;gap:12px;align-items:center}.name{color:#edf3ff;text-decoration:none;flex:1;word-break:break-all}.size{color:#9cabc7;font-size:.85em}.crumb a{color:#8bb4ff;text-decoration:none}</style><main class="w"><h1>📡 LocalDrop</h1><div class="muted">Compartilhamento na rede local</div><div class="card crumb"><a href="{{url_for('browse',subpath='')}}">Arquivos</a>{%for n,p in crumbs%} / <a href="{{url_for('browse',subpath=p)}}">{{n}}</a>{%endfor%}</div><div class="card"><form id="upload" class="upload" action="{{url_for('upload',subpath=current)}}" method="post" enctype="multipart/form-data">Solte arquivos aqui ou escolha abaixo<br><input type="file" name="file" multiple required><br><button>Enviar para o PC</button><div class="bar"><i id="p"></i></div><div id="s" class="muted"></div></form></div><div class="card"><ul>{%if current%}<li><a class="name" href="{{url_for('browse',subpath=parent)}}">← Voltar</a></li>{%endif%}{%for e in entries%}<li>{%if e.dir%}<a class="name" href="{{url_for('browse',subpath=e.rel)}}">📁 {{e.name}}</a>{%else%}<span class="name">📄 {{e.name}}</span><span class="size">{{e.size}}</span><a class="dl" href="{{url_for('download',subpath=e.rel)}}">Baixar</a>{%endif%}</li>{%else%}<li class="muted">A pasta está vazia.</li>{%endfor%}</ul></div></main><script>upload.onsubmit=e=>{e.preventDefault();let x=new XMLHttpRequest;x.open('POST',upload.action);x.upload.onprogress=e=>{if(e.lengthComputable){let n=Math.round(e.loaded/e.total*100);p.style.width=n+'%';s.textContent='Enviando: '+n+'%'}};x.onload=()=>{s.textContent=x.status<300?'Concluído!':'Falha no envio.';if(x.status<300)setTimeout(()=>location.reload(),500)};x.send(new FormData(upload))}</script>'''
@app.route('/',defaults={'subpath':''})
@app.route('/browse/<path:subpath>')
def browse(subpath):
    d=safe_join(ROOT_DIR,subpath)
    if not d.exists():abort(404)
    if d.is_file():return redirect(url_for('download',subpath=subpath))
    es=[{'name':p.name,'rel':str(p.relative_to(ROOT_DIR)).replace(os.sep,'/'),'dir':p.is_dir(),'size':'' if p.is_dir() else human_size(p.stat().st_size)} for p in sorted(d.iterdir(),key=lambda p:(p.is_file(),p.name.lower()))]
    cur=subpath.strip('/'); parts=cur.split('/') if cur else []; acc=[]; crumbs=[]
    for part in parts: acc.append(part);crumbs.append((part,'/'.join(acc)))
    return render_template_string(PAGE,entries=es,current=cur,parent='/'.join(parts[:-1]),crumbs=crumbs)
@app.route('/download/<path:subpath>')
def download(subpath):
    p=safe_join(ROOT_DIR,subpath)
    if not p.exists() or p.is_dir():abort(404)
    EVENTS.put('Download iniciado: '+p.name); return send_from_directory(p.parent,p.name,as_attachment=True)
@app.route('/upload/',defaults={'subpath':''},methods=['POST'])
@app.route('/upload/<path:subpath>',methods=['POST'])
def upload(subpath):
    d=safe_join(ROOT_DIR,subpath); saved=[]
    if not d.is_dir():abort(404)
    for f in request.files.getlist('file'):
        n=secure_filename(f.filename or '')
        if n:f.save(d/n);saved.append(n)
    if saved:EVENTS.put('Recebido: '+', '.join(saved))
    return jsonify(ok=True,files=saved)
def local_ip():
    s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    try:s.connect(('8.8.8.8',80));return s.getsockname()[0]
    except OSError:return '127.0.0.1'
    finally:s.close()
class Server:
    def __init__(self,folder,port):self.folder,self.port,self.httpd=folder,port,None
    def start(self):
        global ROOT_DIR
        ROOT_DIR=self.folder.resolve();self.httpd=make_server('0.0.0.0',self.port,app,threaded=True);threading.Thread(target=self.httpd.serve_forever,daemon=True).start()
    def stop(self):
        if self.httpd:self.httpd.shutdown();self.httpd.server_close();self.httpd=None
class GUI(tk.Tk):
    def __init__(self,folder,port):
        super().__init__();self.folder,self.port,self.server=folder,port,None;self.title('LocalDrop — Compartilhamento local');self.geometry('680x530');self.minsize(580,450);self.configure(bg='#101827')
        st=ttk.Style(self);st.theme_use('clam');st.configure('TFrame',background='#101827');st.configure('TLabel',background='#101827',foreground='#eaf0ff',font=('Segoe UI',10));st.configure('Title.TLabel',font=('Segoe UI Semibold',22));st.configure('TButton',font=('Segoe UI Semibold',10),padding=9);st.configure('Horizontal.TProgressbar',troughcolor='#263650',background='#59dca1')
        b=ttk.Frame(self,padding=24);b.pack(fill=BOTH,expand=True);ttk.Label(b,text='📡  LocalDrop',style='Title.TLabel').pack(anchor='w');ttk.Label(b,text='Envie arquivos para o celular ou receba-os pela rede Wi-Fi.',foreground='#aab9d3').pack(anchor='w',pady=(2,20));c=ttk.Frame(b);c.pack(fill=X);self.btn=ttk.Button(c,text='▶  Iniciar servidor',command=self.toggle);self.btn.pack(side=LEFT);ttk.Button(c,text='Abrir no navegador',command=self.open).pack(side=LEFT,padx=8);self.status=ttk.Label(b,text='Servidor parado',foreground='#f0b35e');self.status.pack(anchor='w',pady=(14,4));self.url=ttk.Label(b,text='',foreground='#8bb4ff',font=('Segoe UI',11,'bold'));self.url.pack(anchor='w');ttk.Separator(b).pack(fill=X,pady=18);ttk.Label(b,text=f'Pasta compartilhada: {folder}',foreground='#aab9d3',wraplength=620).pack(anchor='w');ttk.Button(b,text='＋  Adicionar arquivos para envio',command=self.add).pack(anchor='w',pady=(10,5));self.prog=ttk.Progressbar(b,mode='determinate');self.prog.pack(fill=X);self.copy=ttk.Label(b,text='Os arquivos adicionados ficam disponíveis para download.',foreground='#aab9d3');self.copy.pack(anchor='w',pady=(4,10));ttk.Label(b,text='Atividade',font=('Segoe UI Semibold',11)).pack(anchor='w');self.log=tk.Text(b,height=8,bg='#192338',fg='#eaf0ff',relief='flat',padx=10,pady=9,state='disabled',font=('Consolas',9));self.log.pack(fill=BOTH,expand=True,pady=(5,0));self.protocol('WM_DELETE_WINDOW',self.close);self.after(400,self.poll)
    def toggle(self):
        if self.server:self.server.stop();self.server=None;self.btn.config(text='▶  Iniciar servidor');self.status.config(text='Servidor parado',foreground='#f0b35e');self.url.config(text='');self.write('Servidor interrompido.');return
        try:self.server=Server(self.folder,self.port);self.server.start()
        except OSError as e:self.server=None;messagebox.showerror('Não foi possível iniciar',f'A porta {self.port} está ocupada.\n\n{e}');return
        u=f'http://{local_ip()}:{self.port}';self.btn.config(text='■  Parar servidor');self.status.config(text='Servidor em execução — conecte o celular na mesma rede Wi-Fi',foreground='#5de0a5');self.url.config(text=u);self.write('Servidor iniciado em '+u)
    def open(self):
        if not self.server:self.toggle()
        if self.server:webbrowser.open(f'http://127.0.0.1:{self.port}')
    def add(self):
        ps=filedialog.askopenfilenames(title='Escolha os arquivos para compartilhar')
        if ps:threading.Thread(target=self.copy_files,args=(ps,),daemon=True).start()
    def copy_files(self,ps):
        total=sum(Path(p).stat().st_size for p in ps);done=0
        for x in ps:
            src,dst=Path(x),self.folder/Path(x).name
            with src.open('rb') as a,dst.open('wb') as z:
                while chunk:=a.read(1024*1024):z.write(chunk);done+=len(chunk);self.after(0,self.update_copy,done,total,src.name)
            self.after(0,self.write,'Arquivo adicionado: '+src.name)
        self.after(0,lambda:self.copy.config(text='Arquivos disponíveis para download.'))
    def update_copy(self,d,t,n):self.prog['value']=d/t*100 if t else 100;self.copy.config(text=f'Preparando {n}: {human_size(d)} de {human_size(t)}')
    def poll(self):
        while not EVENTS.empty():self.write(EVENTS.get_nowait())
        self.after(400,self.poll)
    def write(self,s):self.log.config(state='normal');self.log.insert(END,f'[{datetime.now():%H:%M:%S}] {s}\n');self.log.see(END);self.log.config(state='disabled')
    def close(self):
        if self.server:self.server.stop()
        self.destroy()
def default_folder():
    p=(Path(sys.executable).parent if getattr(sys,'frozen',False) else Path(__file__).parent)/'img';p.mkdir(exist_ok=True);return p
def main():
    p=argparse.ArgumentParser();p.add_argument('--dir',type=Path);p.add_argument('--port',type=int,default=5000);p.add_argument('--no-gui',action='store_true');a=p.parse_args();folder=(a.dir or default_folder()).resolve();folder.mkdir(parents=True,exist_ok=True)
    if not a.no_gui:GUI(folder,a.port).mainloop();return
    s=Server(folder,a.port);s.start();print(f'Servidor em http://{local_ip()}:{a.port} — pasta: {folder}')
    try:threading.Event().wait()
    except KeyboardInterrupt:s.stop()
if __name__=='__main__':main()
