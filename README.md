# LocalDrop — PC para celular

Aplicativo Windows para compartilhar arquivos entre o PC e dispositivos na mesma rede Wi-Fi.

## Uso

```powershell
py -m pip install -r requirements.txt
py app.py
```

A interface usa a pasta `img` ao lado de `app.py` para os arquivos enviados e recebidos. Inicie o servidor e abra, no celular conectado à mesma rede Wi-Fi, o endereço exibido.

Para apenas o servidor: `py app.py --no-gui`.

## Aplicativo Windows

Execute `build_windows.bat` depois de instalar as dependências. O executável ficará em `dist\LocalDrop\LocalDrop.exe` e usará `dist\LocalDrop\img`.
