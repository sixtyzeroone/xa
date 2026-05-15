#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, sys, shlex, importlib.util, re, platform, time, random, itertools, threading, shutil, textwrap
import socket
import select
import json
import requests
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime  # Tambah ini!
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box
from rich.markup import escape


from prompt_toolkit import prompt
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.styles import Style
from prompt_toolkit.formatted_text import ANSI  # Tambahkan ini
from prompt_toolkit.completion import WordCompleter
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from core import Search, get_random_banner, load_banners_from_folder, is_terminal_environment
os.environ['TERM'] = 'xterm-256color'
os.environ['COLORTERM'] = 'truecolor'
console = Console()
import builtins
builtins.console = console

BASE_DIR = Path(__file__).parent.parent 
MODULE_DIR, BANNER_DIR = BASE_DIR / "modules", BASE_DIR / "banner"
METADATA_READ_LINES = 120

# ─── Smart Filter (sama dengan ai_assistant.py) ────────────────────────────────
_INJECT_SCORE_THRESHOLD = 2
_INJECT_MIN_LEN         = 30

_INJECT_PATTERNS = [
    (re.compile(r'\b(\d{1,5})/tcp\b',                                    re.I), 3),
    (re.compile(r'\b(\d{1,5})/udp\b',                                    re.I), 3),
    (re.compile(r'\bopen\b',                                              re.I), 1),
    (re.compile(r'\bnmap\b',                                              re.I), 2),
    (re.compile(r'\b(apache|nginx|iis|tomcat|openssh|vsftpd|samba)\b',   re.I), 3),
    (re.compile(r'\b(http|https|ftp|ssh|rdp|smb|ldap|mysql|mssql|redis)\b', re.I), 2),
    (re.compile(r'\bCVE-\d{4}-\d+\b',                                    re.I), 5),
    (re.compile(r'\b(vuln|exploit|vulnerability|rce|lfi|sqli|xss)\b',    re.I), 4),
    (re.compile(r'\b(gobuster|nikto|enum4linux|smbmap|hydra|sqlmap|ffuf)\b', re.I), 3),
    (re.compile(r'\b(found|discovered|detected)\b',                       re.I), 2),
    (re.compile(r'\bStatus:\s*\d{3}\b',                                   re.I), 2),
    (re.compile(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b',              re.I), 2),
    (re.compile(r'\b(username|password|hash|ntlm|kerberos|token)\b',     re.I), 3),
    (re.compile(r'\b(shell|session|meterpreter|reverse.?shell)\b',       re.I), 4),
    (re.compile(r'\b(windows|linux|ubuntu|debian|centos|kali)\b',        re.I), 2),
    (re.compile(r'\b(kernel|uname|systeminfo)\b',                        re.I), 2),
    (re.compile(r'\b(error|warning|failed|exception)\b',                 re.I), 1),
]

_NOISE_PATTERNS = [
    re.compile(r'^\s*$'),
    re.compile(r'^starting\s+\w+\s+v[\d.]+',  re.I),
    re.compile(r'^#'),
    re.compile(r'^\[[\*\+\-!]\]\s*$'),
]

def _smart_filter(text: str) -> str:
    if not text or len(text.strip()) < _INJECT_MIN_LEN:
        return ""
    lines = []
    for line in text.splitlines():
        if any(p.match(line) for p in _NOISE_PATTERNS):
            continue
        score = sum(w for p, w in _INJECT_PATTERNS if p.search(line))
        if score >= _INJECT_SCORE_THRESHOLD:
            lines.append(line)
    return "\n".join(lines)


# ─── CLI AI Assistant ──────────────────────────────────────────────────────────
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

CLI_SYSTEM_PROMPT = """You are LazyAI, a penetration testing assistant embedded in the Lazy Framework CLI.

Your role:
- Analyze scan and enumeration output, explain findings clearly
- Suggest next enumeration steps based on discovered information
- Explain CVEs, vulnerabilities, and attack vectors
- Interpret tool output: nmap, smbmap, enum4linux, nikto, gobuster, etc.
- Recommend which Nexus modules to use next

Rules:
- Be concise and actionable
- Use plain text without markdown headers or bullet symbols
- Always remind that any action requires explicit written authorization
"""

class CLIAssistant:
    """
    AI Assistant untuk mode CLI.
    Pakai: ai <pertanyaan>   → tanya langsung
           ai ctx            → lihat context yang terkumpul
           ai clear          → hapus context
           ai key <sk-or-..> → set API key
           ai model <name>   → ganti model
    """

    DEFAULT_MODEL = "meta-llama/llama-3.3-8b-instruct:free"

    def __init__(self):
        self._context_lines: list[str] = []   # baris relevan dari output modul
        self._history:       list[dict] = []   # chat history
        self._api_key:       str        = os.environ.get("OPENROUTER_API_KEY", "")
        self._model:         str        = self.DEFAULT_MODEL
        self._smart:         bool       = True  # smart filter ON by default
        self._context_max:   int        = 8000  # karakter maks context

    # ── Public ──────────────────────────────────────────────────────────────────

    # Regex strip ANSI escape codes
    _ANSI_RE = re.compile(r'\x1b\[[0-9;]*[mGKHF]|\x1b\[[0-9]*[A-Z]')

    def inject(self, text: str):
        """Dipanggil setiap ada output dari modul/tool."""
        # Bersihkan ANSI escape codes dulu supaya context terbaca AI
        text = self._ANSI_RE.sub('', text)

        if self._smart:
            filtered = _smart_filter(text)
            if not filtered:
                return
            new_lines = filtered.splitlines()
        else:
            new_lines = [l for l in text.splitlines() if l.strip()]

        # Deduplikasi — normalisasi whitespace lalu cek apakah sudah ada di context
        existing = set(
            re.sub(r'\s+', ' ', l).strip()
            for l in self._context_lines
        )
        deduped = []
        for line in new_lines:
            normalized = re.sub(r'\s+', ' ', line).strip()
            if normalized and normalized not in existing:
                deduped.append(line)
                existing.add(normalized)

        if not deduped:
            return

        self._context_lines.extend(deduped)

        # Trim supaya tidak melebihi batas karakter
        joined = "\n".join(self._context_lines)
        if len(joined) > self._context_max:
            trimmed = joined[-self._context_max:]
            self._context_lines = trimmed.splitlines()

    # Quick prompts — shortcut ke pertanyaan yang paling sering dipakai saat pentest
    QUICK_PROMPTS = {
        "next":    "Berdasarkan output di context, rekomendasikan langkah enumerasi atau eksploitasi selanjutnya secara spesifik.",
        "vulns":   "Identifikasi semua potensi vulnerability dari output ini. Sebutkan service, versi, dan alasan kenapa rentan.",
        "explain": "Jelaskan temuan dari output ini dengan bahasa sederhana. Apa artinya bagi keamanan target?",
        "modules": "Modul Lazy Framework mana yang paling cocok digunakan selanjutnya berdasarkan output ini? Jelaskan alasannya.",
        "cve":     "Cek apakah ada CVE yang relevan dengan service dan versi yang ditemukan di output. Sebutkan CVE ID dan dampaknya.",
        "summary": "Buat ringkasan singkat: port yang terbuka, service yang berjalan, dan OS target berdasarkan output ini.",
        "privesc": "Dari output ini, apakah ada indikasi potensi privilege escalation? Sebutkan vektor yang mungkin.",
        "creds":   "Apakah ada credential, hash, token, atau informasi autentikasi yang bocor dalam output ini?",
        "os":      "Identifikasi OS, versi kernel, dan arsitektur target dari output ini. Seberapa yakin kamu?",
        "report":  "Buat draft laporan singkat (temuan, risiko, rekomendasi) berdasarkan semua output yang ada di context.",
    }

    def handle(self, args: list[str]) -> bool:
        """
        Handle perintah 'ai ...' dari REPL.
        Return True jika ditangani, False jika syntax salah.
        """
        if not args:
            self._show_help()
            return True

        sub = args[0].lower()

        # ── Utility commands ──
        if sub == "key":
            return self._cmd_key(args[1:])
        if sub == "model":
            return self._cmd_model(args[1:])
        if sub == "ctx":
            return self._cmd_ctx()
        if sub == "clear":
            return self._cmd_clear()
        if sub == "smart":
            return self._cmd_smart(args[1:])
        if sub == "history":
            return self._cmd_history()
        if sub == "prompts":
            return self._cmd_prompts()

        # ── Quick prompts ──
        if sub in self.QUICK_PROMPTS:
            self._ask(self.QUICK_PROMPTS[sub])
            return True

        # Semua selain subcommand di atas → dianggap pertanyaan bebas
        question = " ".join(args)
        self._ask(question)
        return True

    # ── Subcommands ─────────────────────────────────────────────────────────────

    def _cmd_key(self, args):
        if not args:
            masked = ("*" * (len(self._api_key) - 6) + self._api_key[-6:]) if len(self._api_key) > 6 else "belum diset"
            console.print(f"[cyan]API Key:[/cyan] {masked}")
            return True
        self._api_key = args[0].strip()
        console.print("[green]✓ API key disimpan.[/green]")
        return True

    def _cmd_model(self, args):
        if not args:
            console.print(f"[cyan]Model aktif:[/cyan] {self._model}")
            return True
        self._model = args[0].strip()
        console.print(f"[green]✓ Model → {self._model}[/green]")
        return True

    def _cmd_ctx(self):
        if not self._context_lines:
            console.print("[yellow]Context kosong. Jalankan modul dulu.[/yellow]")
            return True
        ctx = "\n".join(self._context_lines)
        console.print(f"[dim]─── Context ({len(ctx)} chars) ───[/dim]")
        console.print(ctx)
        console.print(f"[dim]─── End context ───[/dim]")
        return True

    def _cmd_clear(self):
        self._context_lines.clear()
        self._history.clear()
        console.print("[green]✓ Context dan history dihapus.[/green]")
        return True

    def _cmd_smart(self, args):
        if args and args[0].lower() in ("off", "0", "false"):
            self._smart = False
            console.print("[yellow]Smart filter OFF — semua output masuk context.[/yellow]")
        else:
            self._smart = True
            console.print("[green]Smart filter ON — hanya output relevan masuk context.[/green]")
        return True

    def _cmd_history(self):
        if not self._history:
            console.print("[yellow]History kosong.[/yellow]")
            return True
        for msg in self._history:
            role  = msg["role"].upper()
            color = "cyan" if role == "USER" else "green"
            console.print(f"[bold {color}][{role}][/bold {color}] {msg['content'][:200]}")
        return True

    def _cmd_prompts(self):
        table = Table(box=box.SIMPLE, show_header=True, header_style="bold white")
        table.add_column("Shortcut",    style="bold cyan",  width=12)
        table.add_column("Pertanyaan",  style="white",      min_width=50)
        for key, prompt_text in self.QUICK_PROMPTS.items():
            table.add_row(f"ai {key}", prompt_text[:80] + ("…" if len(prompt_text) > 80 else ""))
        console.print(Panel(table, title="Quick Prompts", border_style="cyan", expand=False))
        return True

    def _show_help(self):
        console.print(
            "[bold white]ai[/bold white] — LazyAI CLI\n\n"
            "[bold yellow]── Utility ──[/bold yellow]\n"
            "  [cyan]ai <pertanyaan>[/cyan]       tanya AI bebas (context otomatis disertakan)\n"
            "  [cyan]ai ctx[/cyan]                lihat context yang terkumpul dari output modul\n"
            "  [cyan]ai clear[/cyan]              hapus context & history\n"
            "  [cyan]ai key [sk-or-...][/cyan]    set / lihat API key\n"
            "  [cyan]ai model [name][/cyan]        set / lihat model\n"
            "  [cyan]ai smart off|on[/cyan]        toggle smart filter\n"
            "  [cyan]ai history[/cyan]             lihat riwayat chat\n"
            "  [cyan]ai prompts[/cyan]             tampilkan semua quick prompts\n\n"
            "[bold yellow]── Quick Prompts ──[/bold yellow]\n"
            "  [cyan]ai next[/cyan]       langkah selanjutnya yang disarankan\n"
            "  [cyan]ai vulns[/cyan]      identifikasi vulnerability dari output\n"
            "  [cyan]ai explain[/cyan]    jelaskan temuan dengan bahasa sederhana\n"
            "  [cyan]ai modules[/cyan]    sarankan modul Lazy Framework berikutnya\n"
            "  [cyan]ai cve[/cyan]        cek CVE relevan dari service/versi\n"
            "  [cyan]ai summary[/cyan]    ringkasan port, service, dan OS\n"
            "  [cyan]ai privesc[/cyan]    cek potensi privilege escalation\n"
            "  [cyan]ai creds[/cyan]      cek credential/hash yang bocor\n"
            "  [cyan]ai os[/cyan]         identifikasi OS dan versi target\n"
            "  [cyan]ai report[/cyan]     draft laporan dari semua temuan\n"
        )

    # ── Core: kirim ke OpenRouter ────────────────────────────────────────────────

    def _ask(self, question: str):
        if not self._api_key:
            console.print("[red]API key belum diset. Gunakan: ai key <sk-or-...>[/red]")
            return

        # Susun pesan — sertakan context jika ada
        user_content = question
        if self._context_lines:
            ctx_text = "\n".join(self._context_lines)
            user_content = f"Context dari output terminal:\n{ctx_text}\n\nPertanyaan: {question}"

        self._history.append({"role": "user", "content": user_content})

        messages = [{"role": "system", "content": CLI_SYSTEM_PROMPT}] + self._history

        console.print(f"[dim]LazyAI ({self._model}) ...[/dim]")

        try:
            response = requests.post(
                OPENROUTER_URL,
                headers={
                    "Authorization":  f"Bearer {self._api_key}",
                    "Content-Type":   "application/json",
                    "HTTP-Referer":   "https://lazyframework.local",
                    "X-Title":        "Lazy Framework CLI",
                },
                json={
                    "model":    self._model,
                    "messages": messages,
                    "stream":   True,
                },
                stream=True,
                timeout=120,
            )
            response.raise_for_status()

            console.print("[bold green][LazyAI][/bold green] ", end="")
            full_reply = ""
            for line in response.iter_lines():
                if not line or line == b"data: [DONE]":
                    continue
                raw = line.decode().removeprefix("data: ")
                try:
                    data  = json.loads(raw)
                    token = data["choices"][0]["delta"].get("content", "")
                    if token:
                        print(token, end="", flush=True)
                        full_reply += token
                except Exception:
                    pass
            print()  # newline setelah streaming selesai

            if full_reply:
                self._history.append({"role": "assistant", "content": full_reply})

        except requests.exceptions.ConnectionError:
            console.print("[red]Tidak bisa terhubung ke OpenRouter. Cek koneksi.[/red]")
        except requests.exceptions.HTTPError as e:
            code = e.response.status_code if e.response else "?"
            msgs = {401: "API key tidak valid (401).",
                    402: "Kredit habis (402). Top up di openrouter.ai.",
                    429: "Rate limit (429). Tunggu sebentar."}
            console.print(f"[red]{msgs.get(code, f'HTTP error {code}: {e}')}[/red]")
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")

@dataclass
class ModuleInstance:
    name: str
    module: Any
    options: Dict[str, Any] = field(default_factory=dict)
    
    def set_option(self, key, value):
        if key not in self.module.OPTIONS: raise KeyError(f"Unknown option '{key}'")
        self.options[key] = value
    def get_options(self):
        if hasattr(self.module, "OPTIONS"):
            return {k: {"value": self.options.get(k, v.get("default")), **v} for k, v in self.module.OPTIONS.items()}
        return {}

    def run(self, session): return self.module.run(session, self.options)

# Style untuk mengatur warna saran (abu-abu/putih redup)
lzf_style = Style.from_dict({
    'auto-suggestion': '#888888',
})

class LazyFramework:
    def __init__(self):
        self.modules, self.metadata = {}, {}
        self.loaded_module: Optional[ModuleInstance] = None
        self.session = {"user": os.getenv("USER", "unknown")}
        self.ai = CLIAssistant()          # ← AI CLI assistant
        self.scan_modules()
        self.auto_cleanup()
        self.external_tools = self._scan_external_tools()

    def _scan_external_tools(self):
        tools = {
            'nmap': shutil.which('nmap'),
            'metasploit': shutil.which('msfconsole'),
            'sqlmap': shutil.which('sqlmap'),
            'nikto': shutil.which('nikto'),
            'gobuster': shutil.which('gobuster'),
            'hydra': shutil.which('hydra'),
            'john': shutil.which('john'),
        }
        return {k: v for k, v in tools.items() if v}

    def scan_modules(self):
        self.modules.clear()
        self.metadata.clear()
        self.auto_run_modules()
        valid_extensions = [".py", ".cpp", ".c", ".rb", ".php"]
        for folder, prefix in ((MODULE_DIR, "modules"),):
            for p in folder.rglob("*"):
                if p.is_dir(): continue
                if p.suffix not in valid_extensions: continue
                if p.name == "__init__.py": continue
                if "__pycache__" in p.parts or p.suffix in ['.pyc', '.pyo']: continue
                rel = str(p.relative_to(folder)).replace(os.sep, "/")
                key = f"{prefix}/{rel[:-len(p.suffix)]}" if p.suffix else f"{prefix}/{rel}"
                if key.endswith('.py'): key = key[:-3]
                self.modules[key] = p
                self.metadata[key] = self._read_meta(p)
        self.auto_run_modules()
     
    def auto_run_modules(self):
        if not self.modules:
            console.print("No modules found.")
            return
        console.print(f"[bold green][*][/bold green] Scanning module tree... {len(self.modules)} module(s)")
        for key, path in sorted(self.modules.items()):
            rel = path.relative_to(BASE_DIR)
            if path.suffix == ".py":
                try:
                    compile(path.read_bytes(), str(path), 'exec')
                    console.print(f"  OK  {rel}")
                except Exception as e:
                    console.print(f"[bold red][!][/bold red] No modules found during scan {rel}  {e}")
            else:
                console.print(f"  FILE {rel}")

    def _read_meta(self, path):
        data = {"description": "(No description available)", "options": [], "dependencies": [], "rank": "Normal"}
        try:
            text = "".join(path.open("r", encoding="utf-8", errors="ignore").readlines()[:METADATA_READ_LINES])
            if (m_info := re.search(r"MODULE_INFO\s*=\s*{([^}]+)}", text, re.DOTALL)):
                content = m_info.group(1)
                if (m_desc := re.search(r"(?:'description'|\"description\")\s*:\s*['\"]([^'\"]+)['\"]", content)):
                    data["description"] = m_desc.group(1).strip()
                if (m_rank := re.search(r"(?:'rank'|\"rank\")\s*:\s*['\"]([^'\"]+)['\"]", content)):
                    data["rank"] = m_rank.group(1).strip()
                if (m_deps := re.search(r"(?:'dependencies'|\"dependencies\")\s*:\s*\[([^\]]+)\]", content)):
                    deps_str = m_deps.group(1)
                    dependencies = re.findall(r"['\"]([^'\"]+)['\"]", deps_str)
                    data["dependencies"] = [dep.strip() for dep in dependencies if dep.strip()]
            if (mo := re.search(r"OPTIONS\s*=\s*{([^}]*)}", text, re.DOTALL)):
                data["options"] = re.findall(r"['\"]([A-Za-z0-9_]+)['\"]\s*:", mo.group(1))
        except Exception:
            pass
        return data

    def _check_dependencies(self, dependencies: List[str]) -> Dict[str, bool]:
        results = {}
        for dep in dependencies:
            clean_dep = re.split(r'[><=!]', dep)[0].strip().lower()
            if clean_dep == "pyinstaller":
                results[dep] = shutil.which("pyinstaller") is not None
                continue
            import_names = self._generate_import_names(clean_dep)
            success = False
            for name in import_names:
                if importlib.util.find_spec(name) is not None:
                    results[dep] = True
                    success = True
                    break
            if not success:
                results[dep] = False
        return results

    def _generate_import_names(self, package_name: str) -> List[str]:
        names = [package_name]
        if '-' in package_name: names.append(package_name.replace('-', '_'))
        if '.' in package_name: names.append(package_name.replace('.', '_'))
        mappings = {
            'beautifulsoup4': ['bs4'], 'pillow': ['PIL'], 'pyyaml': ['yaml'], 'opencv-python': ['cv2'],
            'requests': ['requests'], 'scapy': ['scapy'], 'cryptography': ['cryptography']
        }
        if package_name in mappings: names.extend(mappings[package_name])
        return list(dict.fromkeys(names))

    def cmd_use(self, args):
        if not args:
            console.print("Usage: use <module>", style="bold red")
            return
        user_key = args[0].strip()
        if user_key.lower().endswith('.py'): user_key = user_key[:-3]
        variations = [user_key, f"modules/{user_key}"]
        if user_key.startswith('modules/'): variations.insert(0, user_key); variations.append(user_key[8:])
        key = next((v for v in variations if v in self.modules), None)
        if not key:
            frag = user_key.split('/')[-1].lower()
            candidates = [k for k in self.modules.keys() if frag in k.lower() or k.lower().endswith('/' + frag)]
            if candidates:
                console.print(f"Module '{user_key}' not found. Did you mean:", style="yellow")
                for c in candidates[:8]: console.print("  " + c)
            else:
                console.print(f"Module '{user_key}' not found.", style="red")
            return

        path = self.modules[key]
        try:
            module_dir = path.parent
            pycache_path = module_dir / "__pycache__"
            self._delete_pycache_folder(pycache_path, "Pre-cleanup")

            spec = importlib.util.spec_from_file_location(key.replace('/', '_'), path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)

            self._delete_pycache_folder(pycache_path, "Post-cleanup")

            meta = getattr(mod, "MODULE_INFO", {})
            dependencies = meta.get("dependencies", [])
            if dependencies:
                dep_results = self._check_dependencies(dependencies)
                missing_deps = [dep for dep, available in dep_results.items() if not available]
                if missing_deps:
                    console.print(f"[yellow]Warning: Missing dependencies for module '{key}':[/yellow]")
                    for dep in missing_deps:
                        console.print(f"  [red]{dep}[/red] - not installed")
                    console.print(f"\n[yellow]Install missing dependencies with: pip install {' '.join(missing_deps)}[/yellow]")

            inst = ModuleInstance(key, mod)
            for k, meta_opt in getattr(mod, "OPTIONS", {}).items():
                if "default" in meta_opt:
                    inst.options[k] = meta_opt["default"]
            self.loaded_module = inst
            console.print(Panel(f"[*] Reloading modules from all [*][bold]{key}[/bold]", style="green"))
        except Exception as e:
            console.print(f"[*] Reloading Error modules from all [*] {escape(str(e))}", style="bold red")

    def auto_cleanup(self):
        cleaned_count = 0
        CORE_DIRS = [BASE_DIR / "bin", BASE_DIR / "core"]
        for d in CORE_DIRS:
            pycache_path = d / "__pycache__"
            if self._delete_pycache_folder(pycache_path, "Manual Cleanup"):
                cleaned_count += 1
        for p in MODULE_DIR.rglob("__pycache__"):
            if self._delete_pycache_folder(p, "Manual Cleanup"):
                 cleaned_count += 1

    def _delete_pycache_folder(self, pycache_path: Path, action_name: str):
        if pycache_path.is_dir():
            try:
                for item in pycache_path.iterdir():
                    if item.is_file(): os.unlink(item)
                os.rmdir(pycache_path)
                return True
            except Exception:
                return False
        return False

    def cmd_run(self, args):
        if not self.loaded_module:
            console.print("No module loaded.", style="red")
            return
        
        # === PERBAIKAN: Deklarasi di luar try block ===
        history_entry = None
        
        try:
            # TAMBAH INI: Simpan entry history sebelum run
            self.session.setdefault("modules_history", [])
            history_entry = {
                "name": self.loaded_module.name,
                "time": datetime.now().strftime("%H:%M:%S"),
                "options": dict(self.loaded_module.options),
                "status": "executing",
                "results": ""  # Akan diupdate setelah run
            }
            self.session["modules_history"].append(history_entry)
            
            # Check dependencies terlebih dahulu
            mod = self.loaded_module.module
            meta = getattr(mod, "MODULE_INFO", {})
            dependencies = meta.get("dependencies", [])
            if dependencies:
                dep_results = self._check_dependencies(dependencies)
                missing_deps = [dep for dep, available in dep_results.items() if not available]
                if missing_deps:
                    console.print(f"[red]Error: Missing dependencies: {', '.join(missing_deps)}[/red]")
                    console.print(f"[yellow]Install with: pip install {' '.join(missing_deps)}[/yellow]")
                    # Update history entry
                    if history_entry:
                        history_entry["status"] = "failed"
                        history_entry["results"] = f"Missing dependencies: {', '.join(missing_deps)}"
                    return
            
            # Jalankan module — output terminal tetap normal,
            # sambil capture teks bersih untuk AI context via tee
            import io, builtins, sys
            from rich.console import Console as RichConsole

            # Buffer untuk AI (tanpa ANSI/markup)
            ai_buf = io.StringIO()

            # Tee stdout: tulis ke terminal asli DAN ke ai_buf
            class _TeeStdout:
                """Intercept print() biasa — teruskan ke sys.__stdout__ dan ai_buf."""
                def write(self, s):
                    sys.__stdout__.write(s)
                    ai_buf.write(s)
                def flush(self):
                    sys.__stdout__.flush()

            # Tee console: intercept console.print() → terminal + ai_buf
            _orig_console = getattr(builtins, 'console', None)

            class _TeeConsole:
                """Intercept console.print() — teruskan ke console asli dan ai_buf."""
                def print(self, *args, **kwargs):
                    if _orig_console:
                        _orig_console.print(*args, **kwargs)
                    plain = " ".join(str(a) for a in args) + "\n"
                    ai_buf.write(plain)

                def __getattr__(self, name):
                    return getattr(_orig_console, name)

            tee = _TeeConsole()

            # Pasang tee ke builtins dan stdout
            _orig_stdout     = sys.stdout
            sys.stdout       = _TeeStdout()
            builtins.console = tee

            # Patch console lokal di dalam modul itu sendiri
            # (menangani modul seperti wpscan.py yang punya `console = Console()` sendiri)
            mod_obj = self.loaded_module.module
            _mod_orig_console = getattr(mod_obj, 'console', None)
            if _mod_orig_console is not None:
                # Buat tee khusus yang tetap teruskan ke console lokal modul (warna tetap jalan)
                class _ModTeeConsole:
                    def print(self, *args, **kwargs):
                        _mod_orig_console.print(*args, **kwargs)  # tampil di terminal dengan warna
                        plain = " ".join(str(a) for a in args) + "\n"
                        ai_buf.write(plain)                        # plain text ke AI
                    def __getattr__(self, name):
                        return getattr(_mod_orig_console, name)
                mod_obj.console = _ModTeeConsole()

            try:
                result = self.loaded_module.run(self.session)
            finally:
                sys.stdout       = _orig_stdout
                builtins.console = _orig_console
                # Kembalikan console lokal modul
                if _mod_orig_console is not None:
                    mod_obj.console = _mod_orig_console

            # Gabungkan: teks dari tee + return value (jika ada)
            captured = "\n".join(filter(None, [
                ai_buf.getvalue(),
                str(result) if result else "",
            ])).strip()

            # Inject ke AI context (smart filter otomatis strip noise)
            if captured:
                self.ai.inject(captured)

            # Update history entry setelah run selesai
            if history_entry:
                history_entry["results"] = captured if captured else "No output"
                history_entry["status"] = "executed"
                
            console.print("Module executed successfully.", style="green")
            
        except Exception as e:
            console.print(f"Error running module: {e}", style="red")
            
            # PERBAIKAN: Cek history_entry sebelum mengakses
            if history_entry:
                history_entry["status"] = "failed"
                history_entry["results"] = str(e)

    def cmd_help(self, args):
        commands = [
            ("show modules", "Show all available modules"),
            #("show recon", "Show reconnaissance modules"),
            #("show strike", "Show strike/exploitation modules"),
            #("show hold", "Show hold/persistence modules"),
            #("show ops", "Show operations modules"),
            ("show payloads", "Show available payload modules"),
            ("use <module>", "Load a module by name"),
            ("info", "Show information about the current module"),
            ("options", "Show options for current module"),
            ("set <option> <value>", "Set module option"),
            ("run", "Run current module"),
            ("back", "Unload module"),
            ("search <keyword>", "Search modules"),
            ("scan", "Rescan modules"),
            ("banner reload|list", "Reload/list banner files"),
            ("cd <dir>", "Change working directory"),
            ("ls", "List current directory"),
            ("clear", "Clear terminal screen"),
            ("ai <question>", "Ask LazyAI (uses captured output as context)"),
            ("ai key <sk-or->", "Set OpenRouter API key"),
            ("ai model <name>", "Switch AI model"),
            ("ai ctx", "Show current AI context"),
            ("ai clear", "Clear AI context & history"),
            ("exit / quit", "Exit the program"),
        ]
        table = Table(title="Core Commands", box=box.SIMPLE_HEAVY)
        table.add_column("Command", style="bold white")
        table.add_column("Description", style="white")
        for cmd, desc in commands:
            table.add_row(cmd, desc)
        panel = Panel(table, title="", border_style="white", expand=True)
        console.print(panel)

    def cmd_payloads(self, args):
        payload_modules = {}
        for key, path in self.modules.items():
            if not key.startswith("modules/"): continue
            parts = key.split('/')
            if not (("payload" in parts) or ("payloads" in parts)): continue
            payload_modules[key] = self.metadata.get(key, {})
        if not payload_modules:
            console.print("No payload modules found under 'modules/'.", style="yellow")
            return
        table = Table(title="Available Payloads", box=box.SIMPLE_HEAVY, expand=True)
        table.add_column("Payload", style="bold cyan", width=30)
        table.add_column("Type", style="yellow", width=15)
        table.add_column("Platform", style="green", width=12)
        table.add_column("Arch", style="magenta", width=10)
        table.add_column("Rank", style="red", width=8)
        table.add_column("Description", style="white", min_width=20)
        for key, meta in sorted(payload_modules.items()):
            display_name = key[len("modules/"):]
            kl = key.lower()
            payload_type = "unknown"
            if "meterpreter" in kl: payload_type = "meterpreter"
            elif "shell" in kl: payload_type = "shell"
            elif "reverse" in kl: payload_type = "reverse"
            elif "bind" in kl: payload_type = "bind"
            elif "staged" in kl: payload_type = "staged"
            elif "stageless" in kl: payload_type = "stageless"
            platform_info = meta.get("platform", "multi")
            if isinstance(platform_info, str): platform_info = platform_info.capitalize()
            arch = meta.get("arch", "multi")
            rank = meta.get("rank", "Normal")
            description = meta.get("description", "No description available")
            table.add_row(display_name, payload_type, str(platform_info), str(arch), str(rank), description)
        total_payloads = len(payload_modules)
        payload_types = {}
        platforms = {}
        for key in payload_modules.keys():
            kl = key.lower()
            if "/windows/" in kl: platforms["Windows"] = platforms.get("Windows", 0) + 1
            elif "/linux/" in kl: platforms["Linux"] = platforms.get("Linux", 0) + 1
            elif "/android/" in kl: platforms["Android"] = platforms.get("Android", 0) + 1
            elif "/mac" in kl or "/osx" in kl: platforms["macOS"] = platforms.get("macOS", 0) + 1
            else: platforms["Multi"] = platforms.get("Multi", 0) + 1
            if "reverse" in kl: payload_types["Reverse"] = payload_types.get("Reverse", 0) + 1
            elif "bind" in kl: payload_types["Bind"] = payload_types.get("Bind", 0) + 1
            elif "meterpreter" in kl: payload_types["Meterpreter"] = payload_types.get("Meterpreter", 0) + 1
            elif "shell" in kl: payload_types["Shell"] = payload_types.get("Shell", 0) + 1
        console.print(table)
        console.print(f"\n[bold]Payload Statistics:[/bold]")
        console.print(f"  • Total Payloads: [cyan]{total_payloads}[/cyan]")
        if payload_types:
            type_stats = " | ".join([f"{k}: {v}" for k, v in payload_types.items()])
            console.print(f"  • Types: {type_stats}")
        if platforms:
            platform_stats = " | ".join([f"{k}: {v}" for k, v in platforms.items()])
            console.print(f"  • Platforms: {platform_stats}")

    # === TAMPILAN SAMA PERSIS DENGAN FRAMEWORK1.PY ===
    def _show_modules_by_type(self, module_type):
        """Menampilkan modul berdasarkan type (recon, strike, hold, ops) dengan tampilan seperti Metasploit"""
        type_modules = {}
        type_lower = module_type.lower()
        
        for key, path in self.modules.items():
            if not key.startswith("modules/"): 
                continue
                
            meta = self.metadata.get(key, {})
            if not meta.get("options"):
                continue
            
            # Hanya 4 tipe tetap seperti framework1.py
            if f"/{type_lower}/" in key.lower():
                type_modules[key] = meta
        
        if not type_modules:
            console.print(f"No {module_type} modules found.", style="yellow")
            return
        
        type_descriptions = {
            'recon': 'Reconnaissance Modules',
            'strike': 'Strike/Exploitation Modules', 
            'hold': 'Hold/Persistence Modules',
            'ops': 'Operations Modules'
        }
        
        description = type_descriptions.get(module_type.lower(), f"{module_type.capitalize()} Modules")
        
        table = Table(
            title=f"{description}",
            box=box.SIMPLE,
            show_header=True,
            header_style="bold white",
            title_style="bold white"
        )
        
        table.add_column("Name", style="green", width=40, overflow="fold")
        table.add_column("Category", style="yellow", width=30)
        table.add_column("Rank", style="red", width=30)
        table.add_column("Description", style="white", min_width=30)
        
        for key, meta in sorted(type_modules.items()):
            display_name = key[len("modules/"):]
            category = "general"
            parts = key.split('/')
            if len(parts) > 2:
                category = parts[2]
            
            rank = meta.get("rank", "normal")
            description = meta.get("description", "No description available")
            
            rank_color = {
                "excellent": "bold green",
                "great": "green", 
                "good": "yellow",
                "normal": "white",
                "average": "white",
                "low": "red",
                "manual": "bold red"
            }.get(rank.lower(), "white")
            
            table.add_row(
                display_name,
                category,
                f"[{rank_color}]{rank.capitalize()}[/{rank_color}]",
                description
            )
        
        console.print(table)
        console.print(f"\n[i]{len(type_modules)} modules[/i]")

    def _show_available_types(self):
        available_types = self._get_available_types()
        if not available_types:
            console.print("No module types found.", style="yellow")
            return
        
        table = Table(title="Available Module Types", box=box.SIMPLE_HEAVY)
        table.add_column("Type", style="bold cyan")
        table.add_column("Count", style="green")
        table.add_column("Description", style="white")
        
        type_descriptions = {
            'recon': 'Intelligence gathering & reconnaissance',
            'strike': 'Offensive operations & exploitation', 
            'hold': 'Position maintenance & persistence',
            'ops': 'Ongoing operations & payload execution',
            'exploit': 'Exploitation modules for vulnerabilities' # <-- Tambahkan ini
        }
        
        for type_name, count in sorted(available_types.items()):
            desc = type_descriptions.get(type_name, 'No description')
            table.add_row(type_name.upper(), str(count), desc)
        
        console.print(table)
        console.print(f"\n[yellow]Usage: show {', '.join(available_types.keys())}[/yellow]")

    def _get_available_types(self):
        types_count = {
            'recon': 0,
            'strike': 0,
            'hold': 0,
            'ops': 0,
            'exploit': 0
        }
        
        for key in self.modules.keys():
            if not key.startswith("modules/"):
                continue
            if "/recon/" in key.lower():
                types_count['recon'] += 1
            if "/strike/" in key.lower():
                types_count['strike'] += 1
            if "/hold/" in key.lower():
                types_count['hold'] += 1
            if "/ops/" in key.lower():
                types_count['ops'] += 1
            if "/exploit/" in kl:
                types_count['exploit'] += 1
        return {k: v for k, v in types_count.items() if v > 0}

    def cmd_show(self, args):
        if not args:
            console.print("[bold red][!][/bold red] Argument Failed")
            console.print("[bold green][✓][/bold green] Valid parameters: show modules|recon|strike|hold|ops|payloads")
            return
        
        subcommand = args[0].lower()
        
        if subcommand == "modules":
            self._show_all_modules()
        elif subcommand == "payloads":
            self.cmd_payloads([])
        elif subcommand == "types":
            self._show_available_types()
        elif subcommand in ['recon', 'strike', 'hold', 'ops', 'exploit']:
            self._show_modules_by_type(subcommand)
        elif subcommand.startswith("modules/"):
            category = subcommand[8:]
            self._show_modules_by_category(category)
        else:
            console.print(f"Unknown show subcommand: {subcommand}", style="red")
            console.print("Usage: show modules|recon|strike|hold|ops|payloads", style="yellow")

    def _show_all_modules(self):
        terminal_width = shutil.get_terminal_size((80, 20)).columns
        MAX_MODULE_WIDTH = terminal_width // 4
        MAX_RANK_WIDTH = terminal_width // 6
        MAX_DESC_WIDTH = terminal_width // 4
        table = Table(box=box.SIMPLE_HEAVY, expand=True)
        table.add_column("Module", style="bold white", width=MAX_MODULE_WIDTH, overflow="fold", justify="left")
        table.add_column("Rank", style="bold yellow", width=MAX_RANK_WIDTH, justify="center")
        table.add_column("Description", style="white", min_width=10, overflow="fold", justify="left")
        for k, v in sorted(self.metadata.items()):
            meta = self.metadata.get(k, {}) or {}
            if not meta.get("options"):
               continue
            display_key = k.replace("modules/", "", 1)
            if "__pycache__" in display_key:
                display_key = re.sub(r"\/__pycache__\/.*$", "", display_key)
                display_key = re.sub(r"(\.cpython-\d+)?$", "", display_key)
            if display_key.endswith('.py'):
                display_key = display_key[:-3]
            rank = meta.get("rank", "Normal")
            desc = v.get("description", "(no description)")
            table.add_row(display_key, rank, desc)
        panel = Panel(table, title="All Modules", border_style="white", expand=True)
        console.print(panel)

    def _show_modules_by_category(self, category):
        category_modules = {}
        for key, path in self.modules.items():
            meta = self.metadata.get(key, {})
            if not meta.get("options"):
               continue
            if not key.startswith("modules/"): continue
            if key.startswith(f"modules/{category}"):
                category_modules[key] = self.metadata.get(key, {})
        if not category_modules:
            console.print(f"No modules found in category: {category}", style="yellow")
            available_categories = self._get_available_categories()
            if available_categories:
                console.print("Available categories:", style="yellow")
                for cat in sorted(available_categories):
                    console.print(f"  • {cat}", style="dim")
            return
        table = Table(title=f"Modules in {category}", box=box.SIMPLE_HEAVY, expand=True)
        table.add_column("Module", style="bold cyan", width=35)
        table.add_column("Type", style="yellow", width=15)
        table.add_column("Platform", style="green", width=12)
        table.add_column("Rank", style="red", width=8)
        table.add_column("Description", style="white", min_width=25)
        for key, meta in sorted(category_modules.items()):
            display_name = key[len("modules/"):]
            kl = key.lower()
            module_type = "unknown"
            if "exploit" in kl: module_type = "exploit"
            elif "scanner" in kl or "discovery" in kl: module_type = "scanner"
            elif "auxiliary" in kl: module_type = "auxiliary"
            elif "post" in kl: module_type = "post"
            elif "payload" in kl: module_type = "payload"
            elif "encoder" in kl: module_type = "encoder"
            platform_info = meta.get("platform", "multi")
            if isinstance(platform_info, str): platform_info = platform_info.capitalize()
            rank = meta.get("rank", "Normal")
            description = meta.get("description", "No description available")
            table.add_row(display_name, module_type, str(platform_info), str(rank), description)
        total_modules = len(category_modules)
        module_types = {}
        platforms = {}
        for key in category_modules.keys():
            kl = key.lower()
            if "/windows/" in kl: platforms["Windows"] = platforms.get("Windows", 0) + 1
            elif "/linux/" in kl: platforms["Linux"] = platforms.get("Linux", 0) + 1
            elif "/android/" in kl: platforms["Android"] = platforms.get("Android", 0) + 1
            elif "/mac" in kl or "/osx" in kl: platforms["macOS"] = platforms.get("macOS", 0) + 1
            else: platforms["Multi"] = platforms.get("Multi", 0) + 1
            if "exploit" in kl: module_types["Exploit"] = module_types.get("Exploit", 0) + 1
            elif "scanner" in kl or "discovery" in kl: module_types["Scanner"] = module_types.get("Scanner", 0) + 1
            elif "auxiliary" in kl: module_types["Auxiliary"] = module_types.get("Auxiliary", 0) + 1
            elif "payload" in kl: module_types["Payload"] = module_types.get("Payload", 0) + 1
        console.print(table)
        console.print(f"\n[bold]Category Statistics:[/bold]")
        console.print(f"  • Total Modules: [cyan]{total_modules}[/cyan]")
        if module_types:
            type_stats = " | ".join([f"{k}: {v}" for k, v in module_types.items()])
            console.print(f"  • Types: {type_stats}")
        if platforms:
            platform_stats = " | ".join([f"{k}: {v}" for k, v in platforms.items()])
            console.print(f"  • Platforms: {platform_stats}")

    def _get_available_categories(self):
        categories = set()
        for key in self.modules.keys():
            if key.startswith("modules/"):
                rel_path = key[8:]
                if '/' in rel_path:
                    category = rel_path.split('/')[0]
                    categories.add(category)
        return categories

    def cmd_info(self, args):
        if not self.loaded_module:
            console.print("No module loaded. Use 'use <module>' first.", style="red")
            return
        # --- BAGIAN PEMBERSIHAN PATH ---
        full_module_path = self.loaded_module.name
        # 1. Hapus "modules/" dari awal string jika ada
        display_path = full_module_path
        if display_path.startswith("modules/"):
            display_path = display_path.replace("modules/", "", 1)
        # 2. Hapus ".py" dari akhir string jika ada
        if display_path.endswith(".py"):
            display_path = display_path[:-3]
        # -------------------------------
        path_parts = full_module_path.split('/')
        mod_type = "UNKNOWN"
        # Mengambil kategori (exploit, recon, dll) untuk baris 'Type'
        if len(path_parts) > 1:
        # Jika path: modules/exploit/xss/file.py -> path_parts[1] adalah 'exploit'
            mod_type = path_parts[1].upper()
        mod = self.loaded_module.module
        meta = getattr(mod, "MODULE_INFO", {}) or {}
        name = meta.get("name", self.loaded_module.name.split('/')[-1])
        authors = meta.get("author", meta.get("authors", "Unknown"))
        description = meta.get("description", "No description provided.")
        rank = meta.get ('rank', 'Normal')
        rank_color = {
            "excellent": "bold green",
            "great": "green",
            "good": "yellow",
            "normal": "white",
            "goodtier": "red"
        }.get(rank.lower(), "white")
        license_ = meta.get("license", "Unknown")
        references = meta.get("references", [])
        dependencies = meta.get("dependencies", [])
        dep_status = {}
        if dependencies:
            dep_status = self._check_dependencies(dependencies)
        console.print(f"\n[bold white]       Name: [/bold white][bold cyan]{name}[/bold cyan]")
        console.print(f"[bold white]     Module: [/bold white]{display_path}")
        console.print(f"[bold white]       Type: [/bold white]{mod_type}")
        console.print(f"[bold white]   Platform: [/bold white]{meta.get('platform', 'All')}")
        console.print(f"[bold white]       Arch: [/bold white]{meta.get('arch', 'All')}")
        console.print(f"[bold white]     Author: [/bold white]{authors}")
        console.print(f"[bold white]    License: [/bold white]{license_}")
        console.print(f"[bold white]       Rank: [/bold white][{rank_color}]{rank.capitalize()}[/{rank_color}]")

        console.print(f"\n[bold white]Description:[/bold white]")
        desc_lines = textwrap.fill(description, width=80)
        console.print(Panel(desc_lines, border_style="blue", box=box.SQUARE))
        if dependencies:
            console.print(f"\n[bold white]Dependencies:[/bold white]")
            deps_table = Table(show_header=True, header_style="bold white", box=box.SIMPLE, show_edge=False)
            deps_table.add_column("Package", style="white", width=25)
            deps_table.add_column("Status", style="white", width=15)
            deps_table.add_column("Action", style="white", width=30)
            for dep in dependencies:
                status = dep_status.get(dep, False)
                status_text = "[green]Available[/green]" if status else "[red]Missing[/red]"
                action_text = "[green]Ready[/green]" if status else f"[yellow]pip install {dep}[/yellow]"
                deps_table.add_row(dep, status_text, action_text)
            console.print(deps_table)
        if references:
            console.print(f"\n[bold white]References:[/bold white]")
            for i, ref in enumerate(references, 1):
                console.print(f"  [bold white]{i}.[/bold white] {ref}")
        if hasattr(mod, "OPTIONS") and isinstance(getattr(mod, "OPTIONS"), dict):
            opts = self.loaded_module.get_options()
            if opts:
                console.print(f"\n[bold yellow]Module options ({self.loaded_module.name}):[/bold yellow]")
                console.print("")
                table = Table(show_header=True, header_style="bold yellow", box=box.SIMPLE, show_edge=False)
                table.add_column("Name", style="white", width=25, no_wrap=True)
                table.add_column("Current", style="cyan", width=25, no_wrap=True)
                table.add_column("Required", style="white", width=25, justify="center")
                table.add_column("Description", style="white", width=30)
                for name, info in opts.items():
                    current = str(info.get('value', '')).strip()
                    if not current: current = info.get('default', '')
                    if not current: current = ""
                    required = "yes" if info.get('required') else "no"
                    desc = info.get('description', 'No description')
                    table.add_row(name, current, required, desc)
                console.print(table)
            else:
                console.print(f"\n[bold yellow]This module has no options.[/bold yellow]")
        else:
            console.print(f"\n[bold yellow]This module has no options.[/bold yellow]")
        console.print("")

    def cmd_options(self, args):
        if not self.loaded_module:
            console.print("No module loaded.", style="red")
            return
        if hasattr(self.loaded_module.module, "OPTIONS"):
            table = Table(show_header=True, header_style="bold white", box=box.SIMPLE)
            table.add_column("Name", width=30, no_wrap=True)
            table.add_column("Current", justify="center", width=30)
            table.add_column("Required", justify="center", width=15)
            table.add_column("Description", width=50)
            for k, v in self.loaded_module.get_options().items():
                current_setting = str(v['value']) if 'value' in v else "Not Set"
                required = "Yes" if v.get('required') else "No"
                description = v.get('description', "No description available.")
                table.add_row(k, current_setting, required, description)
            panel = Panel(table, title="Module Options", border_style="white", expand=False)
            console.print(panel)
        else:
            console.print(f"Module '{self.loaded_module.name}' has no configurable options.", style="yellow")

    def cmd_set(self, args):
        if not self.loaded_module: 
            console.print("No module loaded.", style="red")
            return
        if len(args) < 2: 
            console.print("Usage: set <option> <value>", style="red")
            return
        opt, val = args[0], " ".join(args[1:])
        try:
            self.loaded_module.set_option(opt, val)
            console.print(f"{opt} => {val}", style="green")
        except Exception as e:
            console.print(str(e), style="red")

    def cmd_back(self, args):
        if self.loaded_module: 
            console.print(f"Unloaded {self.loaded_module.name}", style="yellow")
            self.loaded_module = None
        else: 
            console.print("No module loaded.", style="red")

    def cmd_scan(self, args):
        self.scan_modules()
        console.print(f"Scanned {len(self.modules)} modules.", style="green")

    def cmd_search(self, args):
        if not args:
            return console.print("Usage: search <keyword>", style="red")
        keyword = " ".join(args).strip().lower()
        results = []
        for key, meta in self.metadata.items():
            if keyword in key.lower() or keyword in meta.get("description","").lower():
                if meta.get("options"):
                    results.append((key, meta.get("description", "(no description)")))
        if not results:
            return console.print(f"No modules matching '{keyword}'", style="yellow")
        table = Table(box=box.SIMPLE)
        table.add_column("Module", style="bold red", overflow="fold")
        table.add_column("Description")
        for key, desc in sorted(results):
            display_key = key.replace("modules/", "", 1)
            table.add_row(display_key, desc or "(no description)")
        panel = Panel(table, title=f"Module for: {keyword}", border_style="white", expand=True)
        console.print(panel)

    def cmd_banner(self, args):
        console.print(get_random_banner())

    def cmd_cd(self, args):
        if not args: return
        try: 
            os.chdir(args[0])
            console.print("Changed Directory to: " + os.getcwd())
        except Exception as e: 
            console.print("Error: " + str(e), style="red")

    def cmd_pwd(self, args):
           try:
               console.print(f"[bold cyan]Current Directory:[/bold cyan] [white]{os.getcwd()}[/white]")
           except Exception as e:
               console.print(f"[red]Error:[/red] {e}", style="red")

    def cmd_ls(self, args):
        try:
            for f in os.listdir(): 
                console.print(f)
        except Exception as e: 
            console.print("Error: " + str(e), style="red")

    def cmd_clear(self, args): 
        os.system("cls" if platform.system().lower() == "windows" else "clear")

    def cmd_ai(self, args):
        self.ai.handle(args)

    def repl(self):
        # Gunakan banner yang sesuai dengan environment
        banner_output = get_random_banner()
        
        if is_terminal_environment():
            # Terminal - gunakan rich formatting
            console.print(
                "[bold cyan]=[ Lazy Framework v2.0 ]=[/]\n"
                "[dim]Advanced Penetration Testing Platform • Type 'help' for commands[/]\n"
            )
            console.print(banner_output)
        else:
            # Non-terminal - output clean
            print("Lazy Framework v2.0")
            print("Advanced Penetration Testing Platform • Type 'help' for commands")
            print("")
            print(banner_output)
        # Ini akan menyarankan perintah dasar dan semua nama modul yang ada
        module_list = [k.replace("modules/", "", 1) for k in self.modules.keys()]
        commands = ['use', 'set', 'run', 'show', 'info', 'search', 'back', 'help', 'exit',
                    'ai', 'ai key', 'ai model', 'ai ctx', 'ai clear', 'ai smart', 'ai history',
                    'ai prompts',
                    'ai next', 'ai vulns', 'ai explain', 'ai modules', 'ai cve',
                    'ai summary', 'ai privesc', 'ai creds', 'ai os', 'ai report']
        lzf_completer = WordCompleter(commands + module_list, ignore_case=True)
 
        while True:
            try:
                if self.loaded_module:
                    full_path = self.loaded_module.name.replace("modules/", "", 1)
                    parts = full_path.split('/')
                    
                    if len(parts) >= 2:
                        category = parts[0]                  # misal: recon
                        module_name = '/'.join(parts[1:])    # cms/wpscan (semua sisa path)
                    else:
                        category = ""
                        module_name = full_path
                    
                    if is_terminal_environment():
                        # Prompt dengan multi-warna yang diperbaiki
                        if category and module_name:
                            prompt_text = f"\033[1;31mlzf\033[0m \033[1;33m[\033[0m\033[1;31m{category}\033[0m\033[1;33m]\033[0m (\033[1;37m{module_name}\033[0m\033[1;33m)\033[0m > "
                        elif category:
                            prompt_text = f"\033[1;31mlzf\033[0m \033[1;33m[\033[0m\033[1;31m{category}\033[0m\033[1;33m]\033[0m > "
                        elif module_name:
                            prompt_text = f"\033[1;31mlzf\033[0m (\033[1;37m{module_name}\033[0m\033[1;33m)\033[0m > "
                        else:
                            prompt_text = f"\033[1;31mlzf\033[0m > "
                    else:
                        prompt_text = f"lzf [{category}] ({module_name}) > "
                else:
                    prompt_text = "\033[1;36mlzf > \033[0m" if is_terminal_environment() else "lzf > "
                    
                line = prompt(
                ANSI(prompt_text), 
                auto_suggest=AutoSuggestFromHistory(),
                completer=lzf_completer,
                style=lzf_style
                )
            except (EOFError, KeyboardInterrupt):
                break
            if not line.strip(): 
                continue
            parts = shlex.split(line)
            cmd, args = parts[0], parts[1:]
            if cmd in ("exit", "quit"): 
                break
            getattr(self, f"cmd_{cmd}", lambda a: print("Unknown command"))(args)
