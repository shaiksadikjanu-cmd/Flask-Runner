import os
import sys
import signal
import subprocess
import time
import threading
import re
import shutil
from flask import Flask, render_template_string, request, jsonify

app = Flask(__name__)

# Global variable to track the running user-process
user_process = None
USER_APP_PORT = 5001

# The IDE Frontend
IDE_HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Julu's Flask Runner</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/lucide@latest"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.44.0/min/vs/loader.min.js"></script>
    <style>
        body { background-color: #0f172a; height: 100vh; overflow: hidden; }
        .terminal { font-family: 'Fira Code', monospace; font-size: 12px; line-height: 1.5; }
        
        /* Sidebar File Items */
        .file-item {
            cursor: pointer;
            border-left: 2px solid transparent;
            transition: all 0.2s;
        }
        .file-item:hover { background-color: #1e293b; }
        .file-item.active {
            background-color: #1e293b;
            border-left-color: #3b82f6;
            color: #fff;
        }

        /* Resizers */
        .resizer-h {
            width: 8px; background-color: #0f172a; cursor: col-resize;
            display: flex; align-items: center; justify-content: center;
            border-left: 1px solid #1e293b; border-right: 1px solid #1e293b;
            z-index: 50;
        }
        .resizer-h:hover, .resizer-h.dragging { background-color: #3b82f6; }
        
        .resizer-v {
            height: 8px; background-color: #0f172a; cursor: row-resize;
            display: flex; align-items: center; justify-content: center;
            border-top: 1px solid #1e293b; border-bottom: 1px solid #1e293b;
            width: 100%; z-index: 50;
        }
        .resizer-v:hover, .resizer-v.dragging { background-color: #3b82f6; }
    </style>
</head>
<body class="text-slate-300 flex flex-col h-screen">

    <!-- Header -->
    <header class="bg-slate-900 border-b border-slate-800 p-4 flex justify-between items-center select-none h-16">
        <div class="flex items-center space-x-3">
            <div class="bg-indigo-600 p-2 rounded-lg"><i data-lucide="zap" class="text-white w-5 h-5"></i></div>
            <h1 class="text-xl font-bold text-white">Flask Runner <span class="text-xs text-emerald-400 font-normal">v6.1 (Install Fix)</span></h1>
        </div>
        <div class="flex items-center space-x-3">
            <button id="runFlaskBtn" onclick="runCode('flask')" class="bg-emerald-600 hover:bg-emerald-500 text-white px-4 py-2 rounded-md font-bold flex items-center transition-all text-sm">
                <i data-lucide="play" class="w-4 h-4 mr-2"></i> Run Flask
            </button>
            <button id="runFrontBtn" onclick="runCode('static')" class="bg-teal-600 hover:bg-teal-500 text-white px-4 py-2 rounded-md font-bold flex items-center transition-all text-sm">
                <i data-lucide="layout" class="w-4 h-4 mr-2"></i> Run Frontend Only
            </button>
            <button id="stopBtn" onclick="stopCode()" class="hidden bg-red-600 hover:bg-red-500 text-white px-6 py-2 rounded-md font-bold flex items-center transition-all text-sm">
                <i data-lucide="square" class="w-4 h-4 mr-2"></i> Stop
            </button>
        </div>
    </header>

    <!-- Main Content -->
    <main class="flex-1 flex overflow-hidden" id="main-container">
        <!-- Left Panel -->
        <div id="left-panel" class="flex" style="width: 50%;">
            <div class="w-48 bg-slate-900 border-r border-slate-800 flex flex-col select-none">
                <div class="p-3 text-xs font-bold uppercase tracking-widest text-slate-500">Explorer</div>
                <div class="flex-1 overflow-y-auto space-y-1 p-2">
                    <div class="file-item active flex items-center p-2 rounded text-sm text-slate-400" onclick="switchFile('app.py')">
                        <i data-lucide="file-code" class="w-4 h-4 mr-2 text-blue-400"></i> app.py
                    </div>
                    <div class="file-item flex items-center p-2 rounded text-sm text-slate-400" onclick="switchFile('templates/index.html')">
                        <i data-lucide="file" class="w-4 h-4 mr-2 text-orange-400"></i> index.html
                    </div>
                    <div class="file-item flex items-center p-2 rounded text-sm text-slate-400" onclick="switchFile('static/style.css')">
                        <i data-lucide="palette" class="w-4 h-4 mr-2 text-blue-300"></i> style.css
                    </div>
                    <div class="file-item flex items-center p-2 rounded text-sm text-slate-400" onclick="switchFile('static/script.js')">
                        <i data-lucide="scroll" class="w-4 h-4 mr-2 text-yellow-400"></i> script.js
                    </div>
                </div>
            </div>
            <div class="flex-1 flex flex-col min-w-0">
                <div class="bg-slate-900 px-4 py-2 text-xs font-bold text-slate-500 border-b border-slate-800 flex justify-between select-none">
                    <span id="current-filename">app.py</span>
                    <span id="status" class="text-slate-600">Idle</span>
                </div>
                <div id="editor-container" class="flex-1"></div>
            </div>
        </div>

        <!-- Horizontal Resizer -->
        <div id="resizer-h" class="resizer-h"></div>

        <!-- Right Panel -->
        <div id="right-panel" class="flex flex-col bg-slate-950" style="width: 50%;">
            <div id="preview-section" class="flex flex-col border-b border-slate-800" style="height: 60%; min-height: 100px;">
                <div class="bg-slate-900 p-2 flex items-center space-x-2 select-none">
                    <div class="flex-1 bg-slate-800 rounded px-3 py-1 text-xs text-slate-400 flex items-center truncate">
                        <i data-lucide="globe" class="w-3 h-3 mr-2"></i> <span id="url-display">http://localhost:5001/</span>
                    </div>
                    <button onclick="refreshIframe()" class="p-1 hover:bg-slate-700 rounded"><i data-lucide="refresh-cw" class="w-3 h-3"></i></button>
                </div>
                <div class="flex-1 bg-white relative h-full">
                    <iframe id="preview" class="w-full h-full border-none"></iframe>
                    <div id="empty-state" class="absolute inset-0 bg-slate-900 flex flex-col items-center justify-center text-center p-10 select-none">
                        <i data-lucide="server" class="w-16 h-16 text-slate-800 mb-4"></i>
                        <h2 class="text-slate-500 text-lg">Server Not Running</h2>
                        <p class="text-slate-600 text-sm">Select a Run Mode above.</p>
                    </div>
                </div>
            </div>

            <!-- Vertical Resizer -->
            <div id="resizer-v" class="resizer-v"></div>

            <!-- Terminal Area -->
            <div class="flex-1 flex flex-col min-h-[100px]">
                <div class="bg-slate-900 p-2 border-b border-slate-800 flex items-center space-x-2">
                    <span class="text-xs font-bold text-slate-500 uppercase px-2 select-none">PIP Install:</span>
                    <input type="text" id="pkgInput" placeholder="library_name" class="flex-1 bg-slate-950 border border-slate-700 rounded px-2 py-1 text-sm text-slate-300 focus:border-indigo-500 outline-none">
                    <button onclick="installPkg()" id="installBtn" class="bg-indigo-600 hover:bg-indigo-500 text-white px-3 py-1 rounded text-xs font-bold transition-colors select-none">Install</button>
                </div>
                <div class="flex-1 bg-black p-4 overflow-y-auto terminal">
                    <div id="terminal-output" class="text-emerald-500 whitespace-pre-wrap"></div>
                </div>
            </div>
        </div>
    </main>

    <script>
        const fileSystem = {
            'app.py': `from flask import Flask, render_template\\n\\napp = Flask(__name__)\\n\\n@app.route("/")\\ndef home():\\n    return render_template("index.html")\\n\\nif __name__ == "__main__":\\n    print("💕 Julie IDE: Flask Backend Started!")\\n    app.run(port=5001, debug=True, use_reloader=False)`,
            'templates/index.html': `<!DOCTYPE html>\\n<html lang="en">\\n<head>\\n    <meta charset="UTF-8">\\n    <title>Julie Flask App</title>\\n    <link rel="stylesheet" href="/static/style.css">\\n</head>\\n<body>\\n    <div class="container">\\n        <h1>Hello from Templates!</h1>\\n        <p>Edit me and hit Run!</p>\\n        <button id="alertBtn">Click Me</button>\\n    </div>\\n    <script src="/static/script.js"><\/script>\\n</body>\\n</html>`,
            'static/style.css': `body { background: #0f172a; color: white; font-family: sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }\\n.container { text-align: center; padding: 2rem; border: 2px dashed #14b8a6; border-radius: 10px; }\\nh1 { color: #2dd4bf; }\\nbutton { padding: 10px 20px; background: #0d9488; border: none; color: white; cursor: pointer; border-radius: 5px; margin-top: 1rem; }\\nbutton:hover { background: #115e59; }`,
            'static/script.js': `console.log("Static JS Loaded");\\ndocument.getElementById('alertBtn').onclick = function() { alert("Frontend JavaScript is working!"); };`
        };

        let currentFile = 'app.py';
        let editor;

        require.config({ paths: { vs: 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.44.0/min/vs' } });
        require(['vs/editor/editor.main'], function () {
            editor = monaco.editor.create(document.getElementById('editor-container'), {
                value: fileSystem[currentFile],
                language: 'python',
                theme: 'vs-dark',
                automaticLayout: true,
                fontSize: 14,
                minimap: { enabled: false }
            });
        });

        function switchFile(filename) {
            fileSystem[currentFile] = editor.getValue();
            document.querySelectorAll('.file-item').forEach(el => {
                el.classList.remove('active');
                if (el.innerText.trim().includes(filename.split('/').pop())) el.classList.add('active');
            });
            currentFile = filename;
            document.getElementById('current-filename').innerText = filename;
            let lang = 'python';
            if (filename.endsWith('.html')) lang = 'html';
            if (filename.endsWith('.css')) lang = 'css';
            if (filename.endsWith('.js')) lang = 'javascript';
            monaco.editor.setModelLanguage(editor.getModel(), lang);
            editor.setValue(fileSystem[filename]);
        }

        const runFlaskBtn = document.getElementById('runFlaskBtn');
        const runFrontBtn = document.getElementById('runFrontBtn');
        const stopBtn = document.getElementById('stopBtn');
        const terminal = document.getElementById('terminal-output');
        const preview = document.getElementById('preview');
        const emptyState = document.getElementById('empty-state');
        const statusText = document.getElementById('status');
        const urlDisplay = document.getElementById('url-display');
        const pkgInput = document.getElementById('pkgInput');
        const installBtn = document.getElementById('installBtn');

        function appendLog(text) {
            if (!text) return;
            // Filter out internal marker
            const cleanText = text.replace('[INSTALL_FINISHED]', '');
            if (cleanText) {
                terminal.innerText += cleanText + "\\n";
                terminal.parentElement.scrollTop = terminal.parentElement.scrollHeight;
            }
        }

        async function runCode(mode) {
            if (editor) fileSystem[currentFile] = editor.getValue();
            terminal.innerText = "";
            appendLog(`> Initializing ${mode === 'flask' ? 'Flask Project' : 'Static Frontend'}...`);
            
            runFlaskBtn.classList.add('hidden');
            runFrontBtn.classList.add('hidden');
            stopBtn.classList.remove('hidden');
            statusText.innerText = mode === 'flask' ? "Running Backend" : "Running Frontend";
            statusText.classList.replace('text-slate-600', 'text-emerald-500');

            try {
                const response = await fetch('/execute', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ files: fileSystem, mode: mode })
                });
                
                const result = await response.json();
                if (result.status === 'started') {
                    if (mode === 'flask') {
                         if (result.auto_fixed) appendLog("> Note: Port 5001 enforced in app.py");
                         appendLog("> Starting Python Flask Server...");
                         urlDisplay.innerText = "http://localhost:5001/";
                         setTimeout(() => {
                            preview.src = "http://localhost:5001/?" + new Date().getTime();
                            emptyState.classList.add('hidden');
                         }, 2000);
                    } else {
                         appendLog("> Starting Static HTTP Server...");
                         const staticUrl = "http://localhost:5001/templates/index.html";
                         urlDisplay.innerText = staticUrl;
                         setTimeout(() => {
                            preview.src = staticUrl + "?" + new Date().getTime();
                            emptyState.classList.add('hidden');
                         }, 1000);
                    }
                    pollLogs();
                } else {
                    appendLog("Error: " + result.message);
                    stopCode();
                }
            } catch (err) {
                appendLog("Network Error: " + err.message);
                stopCode();
            }
        }

        async function stopCode() {
            await fetch('/stop', { method: 'POST' });
            runFlaskBtn.classList.remove('hidden');
            runFrontBtn.classList.remove('hidden');
            stopBtn.classList.add('hidden');
            preview.src = "";
            emptyState.classList.remove('hidden');
            statusText.innerText = "Stopped";
            statusText.classList.replace('text-emerald-500', 'text-red-500');
            appendLog("> Process terminated.");
        }

        let isPolling = false;
        let isInstalling = false; // New flag to track installation state

        async function pollLogs() {
            if (isPolling) return;
            isPolling = true;
            
            // Keep polling if code is running OR if installation is happening
            while (!stopBtn.classList.contains('hidden') || isInstalling) {
                try {
                    const res = await fetch('/logs');
                    const data = await res.json();
                    
                    if (data.logs) {
                        appendLog(data.logs);
                        // Check for the finish marker from backend
                        if (data.logs.includes('[INSTALL_FINISHED]')) {
                            isInstalling = false;
                            installBtn.disabled = false;
                            installBtn.innerText = "Install";
                            installBtn.classList.remove("opacity-50");
                        }
                    }
                } catch(e) {}
                await new Promise(r => setTimeout(r, 500));
            }
            isPolling = false;
        }
        
        async function installPkg() {
            const pkg = pkgInput.value.trim();
            if (!pkg) return;
            
            isInstalling = true; // Set flag
            installBtn.disabled = true;
            installBtn.innerText = "Installing...";
            installBtn.classList.add("opacity-50");
            
            appendLog("\\n> Requesting install: " + pkg + "...");
            pollLogs(); // Ensure polling is active

            try {
                await fetch('/install', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ package: pkg })
                });
                pkgInput.value = "";
                // Note: We do NOT re-enable the button here. 
                // We wait for '[INSTALL_FINISHED]' in pollLogs.
            } catch (err) {
                appendLog("Install Request Failed: " + err.message);
                isInstalling = false;
                installBtn.disabled = false;
                installBtn.innerText = "Install";
                installBtn.classList.remove("opacity-50");
            }
        }

        // Resizers
        const resizerH = document.getElementById('resizer-h');
        const resizerV = document.getElementById('resizer-v');
        const leftPanel = document.getElementById('left-panel');
        const rightPanel = document.getElementById('right-panel');
        const previewSection = document.getElementById('preview-section');
        const mainContainer = document.getElementById('main-container');
        let isResizingH = false, isResizingV = false;

        resizerH.addEventListener('mousedown', (e) => { isResizingH = true; document.body.style.cursor = 'col-resize'; e.preventDefault(); });
        resizerV.addEventListener('mousedown', (e) => { isResizingV = true; document.body.style.cursor = 'row-resize'; e.preventDefault(); });
        
        document.addEventListener('mousemove', (e) => {
            if (isResizingH) {
                const containerRect = mainContainer.getBoundingClientRect();
                let w = ((e.clientX - containerRect.left) / containerRect.width) * 100;
                if (w < 20) w = 20; if (w > 80) w = 80;
                leftPanel.style.width = w + "%"; rightPanel.style.width = (100 - w) + "%";
                if (editor) editor.layout();
            }
            if (isResizingV) {
                const rightRect = rightPanel.getBoundingClientRect();
                let h = ((e.clientY - rightRect.top) / rightRect.height) * 100;
                if (h < 10) h = 10; if (h > 90) h = 90;
                previewSection.style.height = h + "%";
            }
        });
        document.addEventListener('mouseup', () => { isResizingH = false; isResizingV = false; document.body.style.cursor = 'default'; if (editor) editor.layout(); });

        function refreshIframe() { preview.src = preview.src; }
        stopBtn.onclick = stopCode;
        lucide.createIcons();
    </script>
</body>
</html>
'''

log_buffer = []

@app.route("/")
def index():
    return render_template_string(IDE_HTML)

@app.route("/install", methods=["POST"])
def install_package():
    package = request.json.get('package')
    if not package: return jsonify({"status": "error", "message": "No package name"})
    
    def run_install():
        global log_buffer
        log_buffer.append(f"> pip install {package}...")
        try:
            # Added --no-warn-script-location to reduce noise
            process = subprocess.Popen(
                [sys.executable, "-m", "pip", "install", package, "--no-warn-script-location"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
            )
            for line in iter(process.stdout.readline, ""):
                if line: log_buffer.append(line.strip())
            process.wait()
            if process.returncode == 0: log_buffer.append(f"> Success: '{package}' installed!")
            else: log_buffer.append(f"> Failed: pip returned code {process.returncode}")
        except Exception as e:
            log_buffer.append(f"> Install Error: {str(e)}")
        finally:
            # CRITICAL: Signal to frontend that we are done
            log_buffer.append("[INSTALL_FINISHED]")

    threading.Thread(target=run_install, daemon=True).start()
    return jsonify({"status": "installing"})

@app.route("/execute", methods=["POST"])
def execute():
    global user_process, log_buffer
    files_data = request.json.get('files', {})
    mode = request.json.get('mode', 'flask')
    
    stop_existing_process()
    time.sleep(0.5)
    
    log_buffer = []
    auto_fixed = False
    
    if not os.path.exists('templates'): os.makedirs('templates')
    if not os.path.exists('static'): os.makedirs('static')
    
    try:
        for filename, content in files_data.items():
            if mode == 'flask' and filename == 'app.py':
                if re.search(r'port\s*=\s*\d+', content):
                    content = re.sub(r'port\s*=\s*\d+', 'port=5001', content)
                    auto_fixed = True
                elif "app.run(" in content and "port=" not in content:
                    content = content.replace("app.run(", "app.run(port=5001, ")
                    auto_fixed = True
                if "app.run" in content and "use_reloader" not in content:
                    if "port=5001" in content:
                        content = content.replace("port=5001", "port=5001, use_reloader=False")
            
            filepath = os.path.join(os.getcwd(), filename)
            if '..' in filename: continue
            with open(filepath, "w", encoding='utf-8') as f:
                f.write(content)
    except Exception as e:
        return jsonify({"status": "error", "message": f"File Write Error: {e}"})
    
    env = os.environ.copy()
    env.pop("WERKZEUG_RUN_MAIN", None)
    env.pop("WERKZEUG_SERVER_FD", None)
    env["PYTHONIOENCODING"] = "utf-8"
    
    try:
        command = [sys.executable, "-W", "ignore", "app.py"] if mode == 'flask' else [sys.executable, "-u", "-m", "http.server", "5001"]
        user_process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            errors='replace',
            env=env,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
        )
        def reader():
            try:
                for line in iter(user_process.stdout.readline, ""):
                    if line: log_buffer.append(line.strip())
            except: pass
        threading.Thread(target=reader, daemon=True).start()
        return jsonify({"status": "started", "auto_fixed": auto_fixed})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route("/logs")
def get_logs():
    global log_buffer
    if not log_buffer: return jsonify({"logs": ""})
    logs = "\n".join(log_buffer)
    log_buffer = [] 
    return jsonify({"logs": logs})

@app.route("/stop", methods=["POST"])
def stop():
    stop_existing_process()
    return jsonify({"status": "stopped"})

def stop_existing_process():
    global user_process
    if user_process:
        try:
            if os.name == 'nt':
                subprocess.call(['taskkill', '/F', '/T', '/PID', str(user_process.pid)])
            else:
                os.killpg(os.getpgid(user_process.pid), signal.SIGTERM)
        except: pass
        user_process = None

if __name__ == "__main__":
    print("-----------------------------------------")
    print("IDE Platform starting at http://localhost:5000")
    print("-----------------------------------------")
    app.run(port=5000, debug=True, use_reloader=False)