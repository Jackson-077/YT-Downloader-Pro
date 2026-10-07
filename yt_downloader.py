#!/usr/bin/env python3
# ==========================================================
# YT Downloader Pro
# Versão: 1.8 (Universal Edition - Linux/Windows)
#
# Autor: Jackson Q.
# Downloader gráfico utilizando yt-dlp
# Suporte: Local Binaries (FFmpeg, Deno) para Windows EXE
# ==========================================================

import json
import datetime
import shutil
import os
import sys
import threading
import subprocess
import requests
import re
import io
import hashlib
import queue
import customtkinter as ctk
from tkinter import filedialog, messagebox
from PIL import Image
from io import BytesIO
from yt_dlp import YoutubeDL
from yt_dlp.networking.impersonate import ImpersonateTarget
from yt_dlp.postprocessor.common import PostProcessor
from urllib.parse import urlparse, parse_qs


# -----------------------------
# EXE sem console (--windowed): stdout/stderr podem ser None
# -----------------------------
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

# No Windows, evita que uma janela preta de console pisque a cada chamada
# do ffmpeg/ffprobe/tasklist quando o programa roda como .exe.
SUBPROCESS_FLAGS = (
    getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0
)


# -----------------------------
# UTF-8 Windows
# -----------------------------
class UTF8Logger:

    def debug(self, msg):
        self.safe_print(msg)

    def warning(self, msg):
        self.safe_print(msg)

    def error(self, msg):
        self.safe_print(msg)

    def safe_print(self, msg):
        try:
            print(str(msg).encode(
                "utf-8",
                "replace"
            ).decode("utf-8"))
        except:
            pass
# -----------------------------
# Configuração de Caminhos para EXE
# -----------------------------
def get_base_path():
    """Retorna o caminho base, seja rodando script ou executável compilado."""
    if getattr(sys, 'frozen', False):
        # Se for um executável compilado (.exe)
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

BASE_PATH = get_base_path()


def recurso(nome):
    """Caminho de um arquivo empacotado (ícone etc.), no script ou no EXE."""
    candidatos = []
    if getattr(sys, "_MEIPASS", None):
        candidatos.append(os.path.join(sys._MEIPASS, nome))
    candidatos.append(os.path.join(BASE_PATH, nome))
    candidatos.append(os.path.join(BASE_PATH, "icon", nome))
    for c in candidatos:
        if os.path.isfile(c):
            return c
    return None


def preparar_ambiente():
    """Coloca no PATH as pastas onde ffmpeg/ffprobe/deno podem estar.

    No Windows os binários ficam ao lado do .exe; no Linux o deno instalado
    pelo postinst do .deb fica em /usr/local/bin (ou ~/.deno/bin). Assim o
    yt-dlp os encontra mesmo quando o app é aberto pelo menu (PATH reduzido).
    """
    extras = [BASE_PATH]
    if getattr(sys, "_MEIPASS", None):
        extras.append(sys._MEIPASS)
    if sys.platform != "win32":
        extras += ["/usr/local/bin", os.path.expanduser("~/.deno/bin")]
    atual = os.environ.get("PATH", "")
    partes = atual.split(os.pathsep) if atual else []
    novos = [d for d in extras if os.path.isdir(d) and d not in partes]
    os.environ["PATH"] = os.pathsep.join(novos + partes)


preparar_ambiente()


# -----------------------------
# Correção para bug do yt-dlp (ok.ru e similares)
# -----------------------------
def aplicar_patches_yt_dlp():
    """Corrige "the JSON object must be str, bytes or bytearray, not dict".

    Alguns sites (ex.: ok.ru) passaram a enviar certos campos já como objeto
    JSON (dict/list) e não como texto. O extrator do yt-dlp ainda chama
    _parse_json() nesse valor e quebra. Aqui tornamos o _parse_json tolerante:
    se o valor já é dict/list, devolvemos como está. Para qualquer outro
    caso o comportamento original é mantido.
    """
    try:
        from yt_dlp.extractor.common import InfoExtractor

        original = InfoExtractor._parse_json
        if getattr(original, "_yt_patch_tolerante", False):
            return

        def _parse_json_tolerante(self, json_string, video_id, *args, **kwargs):
            if isinstance(json_string, (dict, list)):
                return json_string
            return original(self, json_string, video_id, *args, **kwargs)

        _parse_json_tolerante._yt_patch_tolerante = True
        InfoExtractor._parse_json = _parse_json_tolerante
    except Exception:
        pass


aplicar_patches_yt_dlp()


try:
    # O yt-dlp re-lança DownloadCancelled mesmo com "ignoreerrors": True.
    # Com uma Exception comum, ele engolia o cancelamento e seguia para o
    # próximo item da playlist.
    from yt_dlp.utils import DownloadCancelled as _YDLDownloadCancelled
except Exception:  # versões muito antigas do yt-dlp
    _YDLDownloadCancelled = Exception


class DownloadCancelado(_YDLDownloadCancelled):
    pass


def rodar_cancelavel(cmd, cancel_event=None, **kwargs):
    """Igual a subprocess.run(check=True, capture_output=True), mas encerra
    o processo (ex.: ffmpeg) assim que o usuário cancelar."""
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, **kwargs
    )
    while True:
        try:
            saida, erro = proc.communicate(timeout=0.5)
            break
        except subprocess.TimeoutExpired:
            if cancel_event is not None and cancel_event.is_set():
                proc.kill()
                try:
                    proc.communicate(timeout=5)
                except Exception:
                    pass
                raise DownloadCancelado("Download cancelado pelo usuário.")
    if proc.returncode != 0:
        raise subprocess.CalledProcessError(proc.returncode, cmd, saida, erro)
    return subprocess.CompletedProcess(cmd, proc.returncode, saida, erro)


def curl_cffi_disponivel():
    try:
        import curl_cffi  # noqa: F401
        return True
    except Exception:
        return False


def erro_pede_login(msg):
    """True se o erro indica login/anti-bot (aí vale tentar cookies)."""
    msg = str(msg).lower()
    termos = (
        "sign in", "confirm you", "not a bot", "cookies",
        "login required", "private video", "age-restricted",
        "confirm your age", "age verification", "inappropriate for some users",
    )
    return any(t in msg for t in termos)


def mensagem_amigavel(erro):
    """Converte erros técnicos do yt-dlp em explicações claras em português."""
    texto = re.sub(r"\x1b\[[0-9;]*m", "", str(erro)).strip()
    texto = re.sub(r"^(ERROR:\s*)+", "", texto)
    baixo = texto.lower()

    dicas = [
        (("json object must be",),
         "O site mudou o formato dos dados e o extrator do yt-dlp falhou. "
         "Atualize o app/yt-dlp para a versão mais recente."),
        (("unsupported url",),
         "Este link não é suportado. Confira se é o link direto do vídeo."),
        (("getaddrinfo", "name or service not known", "network is unreachable",
          "temporary failure in name resolution", "timed out", "connection refused"),
         "Sem conexão com a internet ou o site está fora do ar."),
        (("http error 403", "403: forbidden"),
         "O site recusou o acesso (403). Tente novamente em instantes ou atualize o yt-dlp."),
        (("http error 404", "video unavailable", "this video is not available",
          "has been removed", "does not exist"),
         "O vídeo não está mais disponível (removido ou link incorreto)."),
        (("private video",),
         "Este vídeo é privado."),
        (("not available in your country", "geo"),
         "Este vídeo é bloqueado na sua região."),
        (("sign in", "not a bot", "confirm you"),
         "O site pediu login/confirmação anti-robô. Entre na sua conta no navegador "
         "(Chrome/Firefox/Edge) e tente de novo."),
        (("ffmpeg", "ffprobe"),
         "Problema com o FFmpeg. Verifique se ele está instalado / ao lado do programa."),
        (("no space left", "disk full"),
         "Sem espaço em disco na pasta de destino."),
        (("permission denied",),
         "Sem permissão para gravar na pasta escolhida. Escolha outra pasta."),
    ]
    for termos, dica in dicas:
        if any(t in baixo for t in termos):
            return f"{dica}\n\nDetalhes técnicos:\n{texto[:500]}"
    return texto[:800]

LOCK_DIR = os.path.join(os.path.expanduser("~"), ".yt-downloader", "locks")


def _pid_ativo(pid):
    """Verifica se um processo com esse PID ainda está rodando (Windows/Linux/Mac)."""
    if sys.platform == "win32":
        try:
            saida = subprocess.check_output(
                ["tasklist", "/FI", f"PID eq {pid}"],
                text=True, stderr=subprocess.DEVNULL,
                creationflags=SUBPROCESS_FLAGS,
            )
            return str(pid) in saida
        except Exception:
            return False
    else:
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        return True


def reservar_download(url, formato, qualidade, download_folder):
    """Evita que duas instâncias do programa, baixando o MESMO vídeo ao
    mesmo tempo, escrevam por cima do mesmo arquivo (o que corrompe o
    resultado). Retorna (sufixo_arquivo, caminho_do_lock):
      - sufixo_arquivo: "" normalmente, ou " (copia)" se outra instância
        já estiver baixando exatamente este vídeo agora.
      - caminho_do_lock: deve ser removido no finally do download.
    """
    try:
        os.makedirs(LOCK_DIR, exist_ok=True)

        chave = hashlib.md5(
            f"{url}|{formato}|{qualidade}|{download_folder}".encode("utf-8")
        ).hexdigest()
        lock_path = os.path.join(LOCK_DIR, chave + ".lock")

        outra_instancia_ativa = False
        if os.path.exists(lock_path):
            try:
                with open(lock_path, "r", encoding="utf-8") as f:
                    pid_antigo = int(f.read().strip())
                if pid_antigo != os.getpid() and _pid_ativo(pid_antigo):
                    outra_instancia_ativa = True
            except Exception:
                pass

        with open(lock_path, "w", encoding="utf-8") as f:
            f.write(str(os.getpid()))

        return (" (copia)" if outra_instancia_ativa else ""), lock_path

    except Exception:
        # Se o sistema de trava falhar por qualquer motivo, não deve
        # impedir o download normal — só perdemos a proteção extra.
        return "", None


def liberar_download(lock_path):
    if lock_path and os.path.exists(lock_path):
        try:
            os.remove(lock_path)
        except OSError:
            pass


def get_video_only_url(url):
    """Remove parâmetros de playlist de links do YouTube para vídeo único."""
    parsed = urlparse(url)
    query = parse_qs(parsed.query)

    if ("youtube.com" in parsed.netloc or "youtu.be" in parsed.netloc) and query.get("v"):
        return f"https://www.youtube.com/watch?v={query['v'][0]}"

    return url


def add_browser_cookies(opts):
    """Procura, em silêncio, um navegador com cookies de sessão utilizáveis.

    Testa cada navegador suportado tentando de fato extrair cookies (não
    apenas instanciar o YoutubeDL). Nenhuma mensagem de erro é exibida ao
    usuário e nada é impresso no console caso nenhum navegador seja
    encontrado — isso é esperado (nem todo mundo tem esses navegadores
    instalados) e não deve parecer uma falha do programa.
    """

    browsers = [
        "chrome",
        "edge",
        "brave",
        "vivaldi",
        "opera",
        "firefox",
    ]

    for browser in browsers:
        try:
            teste = opts.copy()
            teste["cookiesfrombrowser"] = (browser,)
            teste["quiet"] = True
            teste["no_warnings"] = True

            with YoutubeDL(teste) as ydl:
                # Força a extração real dos cookies (e não só a criação do
                # objeto), que é onde erros de perfil/DB bloqueado aparecem.
                ydl.cookiejar

            opts["cookiesfrombrowser"] = (browser,)
            return True

        except Exception:
            # Silencioso de propósito: navegador ausente, perfil bloqueado
            # ou sem cookies são todos motivos legítimos de não usar esse
            # navegador — não é um erro para mostrar ao usuário.
            continue

    return False


def extrair_info_com_fallback(ydl_opts, url, **extract_kwargs):
    """Chama ydl.extract_info tentando primeiro sem cookies e, se o site
    pedir login/confirmação (ex.: "Sign in to confirm you're not a bot"
    do YouTube), tenta de novo automaticamente com cookies de algum
    navegador instalado — sem nunca expor esse processo como erro.

    Usado tanto na busca rápida (extract_flat) quanto na busca detalhada,
    para que o mesmo problema não precise ser corrigido em dois lugares.
    """

    opts = ydl_opts.copy()
    opts.pop("cookiesfrombrowser", None)

    try:
        with YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, **extract_kwargs)

    except Exception as primeiro_erro:
        # Só vale a pena tentar cookies se o erro for de autenticação/
        # bloqueio anti-bot. Para outros erros (URL inválida, vídeo
        # removido, etc.) tentar cookies não resolveria nada.
        precisa_login = erro_pede_login(primeiro_erro)

        if not precisa_login:
            raise

        cookies_ok = add_browser_cookies(opts)

        if cookies_ok:
            try:
                with YoutubeDL(opts) as ydl:
                    return ydl.extract_info(url, **extract_kwargs)
            except Exception:
                pass  # tenta a próxima estratégia abaixo

        # Cookies não resolveram (ou não havia navegador com cookies
        # válidos). Alguns vídeos são bloqueados especificamente no
        # cliente "mweb"/"tv"/"web_safari" que fixamos em get_common_opts;
        # como último recurso, deixamos o yt-dlp escolher livremente entre
        # TODOS os clientes que ele suporta (o comportamento padrão dele
        # às vezes contorna esse bloqueio quando um cliente fixo não
        # consegue).
        if "extractor_args" in opts:
            opts_sem_restricao = opts.copy()
            opts_sem_restricao.pop("extractor_args", None)
            try:
                with YoutubeDL(opts_sem_restricao) as ydl:
                    return ydl.extract_info(url, **extract_kwargs)
            except Exception:
                pass

        # Nada funcionou: relata o erro original (mais claro para o
        # usuário do que os erros das tentativas intermediárias).
        raise primeiro_erro


# -----------------------------
# Garantia de Compatibilidade (H.264 + AAC)
# -----------------------------
class EnsureH264AACPP(PostProcessor):
    """Garante que o arquivo .mp4 final seja H.264 (vídeo) + AAC (áudio).

    O YouTube frequentemente só oferece os streams separados em VP9/AV1
    (vídeo) e Opus (áudio). Quando isso acontece, o "merge_output_format":
    "mp4" do yt-dlp apenas troca o CONTÊINER (remux) para .mp4, mas mantém
    os codecs originais dentro dele — resultando em um arquivo .mp4 que
    muitos players/TVs/celulares não conseguem reproduzir.

    Este pós-processador roda depois do download/merge e:
      1) Verifica os codecs reais do arquivo final via ffprobe.
      2) Se já estiverem em H.264 + AAC, não faz nada (0 custo).
      3) Caso contrário, recodifica apenas a trilha necessária (vídeo e/ou
         áudio) com ffmpeg, mantendo a outra em "copy" sempre que possível
         para economizar tempo e preservar qualidade.
    """

    # Cache no nível da classe: a detecção de hardware só precisa
    # rodar uma vez por execução do programa, não a cada vídeo.
    _encoder_cache = None

    def __init__(self, downloader=None, ffmpeg_path="ffmpeg", ffprobe_path="ffprobe",
                 cancel_event=None):
        super().__init__(downloader)
        self.ffmpeg_path = ffmpeg_path
        self.ffprobe_path = ffprobe_path
        self.cancel_event = cancel_event

    def _detectar_encoder_video(self):
        """Detecta o melhor codificador H.264 disponível: hardware primeiro
        (muito mais rápido que CPU), com fallback para libx264 por software.

        Retorna uma lista de argumentos ffmpeg (ex.: ["-c:v", "h264_nvenc", ...]).
        """

        if EnsureH264AACPP._encoder_cache is not None:
            return EnsureH264AACPP._encoder_cache

        # (encoder, args extras, nome amigável)
        candidatos = [
            ("h264_nvenc", ["-preset", "p4", "-tune", "hq", "-rc", "vbr", "-cq", "20", "-b:v", "0"], "NVIDIA NVENC"),
            ("h264_qsv", ["-preset", "faster", "-global_quality", "20"], "Intel Quick Sync"),
            ("h264_videotoolbox", ["-q:v", "55"], "Apple VideoToolbox"),
            ("h264_amf", ["-quality", "speed", "-rc", "cqp", "-qp_i", "20", "-qp_p", "20"], "AMD AMF"),
        ]

        try:
            encoders_disponiveis = subprocess.run(
                [self.ffmpeg_path, "-hide_banner", "-encoders"],
                capture_output=True, text=True, timeout=15,
                creationflags=SUBPROCESS_FLAGS,
            ).stdout.lower()
        except Exception:
            encoders_disponiveis = ""

        for nome_encoder, args_extra, label in candidatos:
            if nome_encoder not in encoders_disponiveis:
                continue

            # Confirma que o encoder realmente funciona nesta máquina
            # (listado no ffmpeg não significa necessariamente que há
            # GPU/driver compatível disponível em tempo de execução).
            teste = subprocess.run(
                [
                    self.ffmpeg_path, "-hide_banner", "-loglevel", "error",
                    "-f", "lavfi", "-i", "color=black:s=64x64:d=0.1",
                    "-c:v", nome_encoder, "-frames:v", "1", "-f", "null", "-",
                ],
                capture_output=True, text=True, timeout=15,
                creationflags=SUBPROCESS_FLAGS,
            )

            if teste.returncode == 0:
                resultado = ["-c:v", nome_encoder] + args_extra
                EnsureH264AACPP._encoder_cache = (resultado, label)
                return EnsureH264AACPP._encoder_cache

        # Nenhuma GPU utilizável: usa libx264 por software, mas com preset
        # rápido e todos os threads da CPU (em vez do "medium" original,
        # que em vídeos longos de 1h+ demorava demais).
        resultado = [
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "21",
            "-pix_fmt", "yuv420p",
            "-threads", "0",
        ]
        EnsureH264AACPP._encoder_cache = (resultado, "CPU (libx264 veryfast)")
        return EnsureH264AACPP._encoder_cache

    def _probe_codec(self, filepath, stream_select):
        cmd = [
            self.ffprobe_path,
            "-v", "error",
            "-select_streams", stream_select,
            "-show_entries", "stream=codec_name",
            "-of", "csv=p=0",
            filepath,
        ]
        resultado = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            creationflags=SUBPROCESS_FLAGS,
        )
        return resultado.stdout.strip().lower()

    def run(self, info, _forcar_software=False):
        if self.cancel_event is not None and self.cancel_event.is_set():
            raise DownloadCancelado("Download cancelado pelo usuário.")

        filepath = info.get("filepath")

        if not filepath or not os.path.exists(filepath):
            return [], info

        # Só nos interessa o resultado final em .mp4 (fluxo de vídeo).
        if not filepath.lower().endswith(".mp4"):
            return [], info

        try:
            vcodec = self._probe_codec(filepath, "v:0")
            acodec = self._probe_codec(filepath, "a:0")
        except Exception as e:
            self.report_warning(
                f"[H.264/AAC] Não foi possível verificar os codecs ({e}). "
                "Mantendo o arquivo como está."
            )
            return [], info

        precisa_video = bool(vcodec) and not vcodec.startswith(("h264", "avc1"))
        precisa_audio = bool(acodec) and not acodec.startswith("aac")

        if not precisa_video and not precisa_audio:
            # Já está no padrão desejado (H.264 + AAC). Nada a fazer.
            return [], info

        self.to_screen(
            f"[H.264/AAC] Ajustando compatibilidade "
            f"(vídeo: {vcodec or '?'} -> "
            f"{'h264' if precisa_video else 'mantido'}, "
            f"áudio: {acodec or '?'} -> "
            f"{'aac' if precisa_audio else 'mantido'})..."
        )

        tmp_path = filepath + ".h264aac.tmp.mp4"

        cmd = [self.ffmpeg_path, "-y", "-i", filepath]

        if precisa_video:
            if _forcar_software:
                args_encoder, label_encoder = [
                    "-c:v", "libx264", "-preset", "veryfast",
                    "-crf", "21", "-pix_fmt", "yuv420p", "-threads", "0",
                ], "CPU (libx264 veryfast)"
            else:
                args_encoder, label_encoder = self._detectar_encoder_video()
            self.to_screen(f"[H.264/AAC] Codificando com: {label_encoder}")
            cmd += args_encoder
        else:
            cmd += ["-c:v", "copy"]

        if precisa_audio:
            cmd += ["-c:a", "aac", "-b:a", "192k"]
        else:
            cmd += ["-c:a", "copy"]

        # +faststart move os metadados para o início do arquivo, permitindo
        # início de reprodução mais rápido (importante em navegadores/TVs).
        cmd += ["-movflags", "+faststart", tmp_path]

        try:
            rodar_cancelavel(
                cmd, self.cancel_event,
                creationflags=SUBPROCESS_FLAGS,
            )
        except DownloadCancelado:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
            raise
        except subprocess.CalledProcessError as e:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

            # Se o encoder de hardware falhou nesta execução real (driver
            # desatualizado, VRAM insuficiente, etc.), força libx264 por
            # software numa única nova tentativa antes de desistir do vídeo.
            if precisa_video and not _forcar_software:
                EnsureH264AACPP._encoder_cache = None
                self.to_screen(
                    "[H.264/AAC] Encoder de hardware falhou, tentando por software..."
                )
                return self.run(info, _forcar_software=True)

            self.report_warning(
                f"[H.264/AAC] Falha ao converter, mantendo arquivo original: {e.stderr}"
            )
            return [], info

        os.replace(tmp_path, filepath)
        info["filepath"] = filepath

        return [], info


# -----------------------------
# Configuração da Interface
# -----------------------------
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class Downloader:
    def __init__(self):
        self.window = ctk.CTk()
        self.window.title("YT Downloader Pro")
        self.window.geometry("900x850")
        self.window.resizable(True, True)

        # Caminhos e Configurações
        self.download_folder = os.path.join(os.path.expanduser("~"), "Downloads")
        app_dir = os.path.join(os.path.expanduser("~"), ".yt-downloader")
        os.makedirs(app_dir, exist_ok=True)
        
        self.config_file = os.path.join(app_dir, "config.json")
        self.history_file = os.path.join(app_dir, "history.json")

        # Variáveis de Estado
        self.info = None
        self.playlist_info = None
        self.thumbnail = None
        self.tipo_download = "video"  # "video" ou "playlist"
        self.video_url = None
        self.playlist_url = None
        
        self.cancel_event = threading.Event()
        self._ui_queue = queue.Queue()

        self.load_config()
        self.create_widgets()
        self.definir_icone()
        self.window.after(50, self._drenar_fila_ui)
        
        # Verifica binários na inicialização
        self.check_local_binaries()
        
        self.window.mainloop()

    # -----------------------------------------
    # Atualizações de UI vindas de threads (thread-safe)
    # -----------------------------------------
    def ui_after(self, ms, fn):
        """Agenda fn na thread principal do Tk. Chamado de threads de
        trabalho, passa por uma fila (o Tkinter não é thread-safe)."""
        if threading.current_thread() is threading.main_thread():
            return self.window.after(ms, fn)
        self._ui_queue.put(fn)

    def _drenar_fila_ui(self):
        try:
            while True:
                fn = self._ui_queue.get_nowait()
                try:
                    fn()
                except Exception:
                    pass
        except queue.Empty:
            pass
        self.window.after(50, self._drenar_fila_ui)

    def definir_icone(self):
        try:
            caminho = recurso("icone.png") or recurso("ytdown_icon_192x192.png")
            if caminho:
                from tkinter import PhotoImage
                self._icone = PhotoImage(file=caminho)
                self.window.iconphoto(True, self._icone)
        except Exception:
            pass

    def check_local_binaries(self):
        """Verifica binários locais (Windows) ou do sistema (Linux)."""
        msg = []
        
        # O PATH já inclui a pasta do programa (ver preparar_ambiente), então
        # shutil.which encontra tanto binários locais (EXE) quanto do sistema.
        if shutil.which("ffmpeg"): msg.append("FFmpeg")
        if shutil.which("deno"): msg.append("Deno")
        if not curl_cffi_disponivel(): msg.append("sem curl_cffi")
            
        if msg:
            status_text = f"Pronto. ({' + '.join(msg)})"
            self.ui_after(1000, lambda: self.status_label.configure(text=status_text))

    def create_widgets(self):
        # Título Principal
        title = ctk.CTkLabel(self.window, text="YT Downloader Pro", font=("Arial", 28, "bold"))
        title.pack(pady=10)

        # Área com rolagem
        self.main_frame = ctk.CTkScrollableFrame(self.window, width=850, height=750)
        self.main_frame.pack(padx=10, pady=10, fill="both", expand=True)

        # Campo de URL
        self.url_entry = ctk.CTkEntry(self.main_frame, width=700, placeholder_text="Cole aqui a URL do vídeo ou playlist...")
        self.url_entry.pack(pady=10)
         
        self.search_btn = ctk.CTkButton(self.main_frame, text="Buscar informações", command=self.start_info_thread)
        self.search_btn.pack(pady=5)

        # Botões auxiliares
        frame_botoes = ctk.CTkFrame(self.main_frame)
        frame_botoes.pack(pady=10)

        self.clear_btn = ctk.CTkButton(frame_botoes, text="Limpar URL", width=150, command=self.clear_url)
        self.clear_btn.grid(row=0, column=0, padx=10)

        self.open_folder_btn = ctk.CTkButton(frame_botoes, text="Abrir Pasta", width=150, command=self.open_download_folder)
        self.open_folder_btn.grid(row=0, column=1, padx=10)

        self.help_btn = ctk.CTkButton(frame_botoes, text="Ajuda", width=150, command=self.show_help)
        self.help_btn.grid(row=0, column=2, padx=10)

        # Exibição de Informações
        self.thumb_label = ctk.CTkLabel(self.main_frame, text="")
        self.thumb_label.pack(pady=10)

        self.title_label = ctk.CTkLabel(self.main_frame, text="Título:", wraplength=760, justify="left", font=("Arial", 14, "bold"))
        self.title_label.pack()

        self.channel_label = ctk.CTkLabel(self.main_frame, text="Canal:")
        self.channel_label.pack()

        self.duration_label = ctk.CTkLabel(self.main_frame, text="Duração:")
        self.duration_label.pack()

        # Opções de Formato e Qualidade
        self.format_var = ctk.StringVar(value="mp4")
        
        frame_opcoes = ctk.CTkFrame(self.main_frame)
        frame_opcoes.pack(pady=15)

        ctk.CTkRadioButton(frame_opcoes, text="Vídeo MP4", variable=self.format_var, value="mp4").grid(row=0, column=0, padx=20)
        ctk.CTkRadioButton(frame_opcoes, text="Áudio MP3", variable=self.format_var, value="mp3").grid(row=0, column=1, padx=20)

        ctk.CTkLabel(self.main_frame, text="Qualidade").pack(pady=(10, 0))
        self.quality_combo = ctk.CTkComboBox(self.main_frame, width=200, values=["Melhor", "2160p (4K)", "1440p", "1080p", "720p", "480p", "360p"])
        self.quality_combo.set("Melhor")
        self.quality_combo.pack(pady=5)

        # Pasta de Destino
        ctk.CTkButton(self.main_frame, text="Escolher Pasta", command=self.choose_folder).pack(pady=10)
        self.folder_label = ctk.CTkLabel(self.main_frame, text=self.download_folder, wraplength=700, text_color="gray")
        self.folder_label.pack()

        # Progresso e Status
        self.progress_bar = ctk.CTkProgressBar(self.main_frame, width=600)
        self.progress_bar.pack(pady=20)
        self.progress_bar.set(0)

        self.status_label = ctk.CTkLabel(self.main_frame, text="Pronto.")
        self.status_label.pack()

        # Botão de Download
        self.download_btn = ctk.CTkButton(self.main_frame, text="BAIXAR", width=250, height=45, font=("Arial", 16, "bold"), command=self.start_download)
        self.download_btn.pack(pady=(20, 5))

        self.cancel_btn = ctk.CTkButton(
            self.main_frame, text="Cancelar download", width=250, height=32,
            fg_color="gray40", hover_color="#8b2d2d", state="disabled",
            command=self.cancel_download,
        )
        self.cancel_btn.pack(pady=(0, 20))

    # -----------------------------------------
    # Lógica de Informações
    # -----------------------------------------
    def get_common_opts(self):

        opts = {

            "quiet": True,
            "no_warnings": True,
            "socket_timeout": 60,
            "nocolor": True,
            "retries": 10,
            "fragment_retries": 10,
            # Links de mídia do YouTube expiram rapidamente. Arquivos .part
            # antigos não devem ser retomados, pois o servidor responde 403
            # ao receber a requisição Range com a URL expirada.
            "continuedl": False,
            "nopart": True,
            # O YouTube pode recusar a conexão IPv6 de alguns provedores,
            # mesmo quando a página e os metadados são carregados normalmente.
            "force_ipv4": True,
            # Usa uma impressão digital real de navegador (curl_cffi), em vez
            # de apenas alterar o texto do User-Agent. Isso reduz erros 403
            # causados pela validação anti-bot do YouTube.
            "logger": UTF8Logger(),
        }

        # Só usa impersonate se o curl_cffi estiver disponível (no EXE/.deb
        # empacotado ele precisa ter sido incluído). Sem ele, o yt-dlp
        # falharia com "Impersonate target not available".
        if curl_cffi_disponivel():
            opts["impersonate"] = ImpersonateTarget.from_str("chrome-133:macos-15")

        # Nomes de arquivo seguros no Windows (remove : ? " etc.).
        if sys.platform == "win32":
            opts["windowsfilenames"] = True


        opts["remote_components"] = [
            "ejs:github"
        ]

        # Provedor de PO Token. O YouTube passou a exigir esse token para
        # liberar algumas URLs de áudio/vídeo; sem ele o servidor retorna 403.
        # O caminho é relativo ao aplicativo para não depender de ~/. 
        pot_server_home = os.path.join(
            BASE_PATH,
            ".tools",
            "bgutil-ytdlp-pot-provider",
            "server",
        )
        # A implementação Deno do provedor é TypeScript.
        if os.path.isfile(os.path.join(pot_server_home, "src", "generate_once.ts")):
            opts["extractor_args"] = {
                "youtube": {
                    # "mweb" primeiro (usa o PO Token do provedor local),
                    # mas com "tv" e "web_safari" como alternativas — esses
                    # dois raramente são bloqueados pelo "confirm you're
                    # not a bot" mesmo sem PO Token/cookies.
                    "player_client": ["mweb", "tv", "web_safari"],
                },
                "youtubepot-bgutilscript": {
                    "server_home": [pot_server_home],
                },
            }


        if sys.platform == "win32":

            ffmpeg = os.path.join(
                BASE_PATH,
                "ffmpeg.exe"
            )

            if os.path.exists(ffmpeg):

                opts["ffmpeg_location"] = ffmpeg


        # NÃO coloca cookie aqui direto
        # tenta primeiro sem cookie


        return opts



    def start_info_thread(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("Aviso", "Informe uma URL.")
            return
        
        # Descarta resultados antigos para não baixar o vídeo errado caso
        # esta nova busca falhe.
        self.reset_ui_state()
        self.search_btn.configure(state="disabled")
        self.status_label.configure(text="Buscando informações...")
        threading.Thread(target=self.get_info, args=(url,), daemon=True).start()

    def get_info(self, url):
        try:
            ydl_opts_fast = self.get_common_opts()
            ydl_opts_fast.update({
                "skip_download": True,
                "extract_flat": True,
                # Para identificar uma playlist basta ler o primeiro item.
                # Consultar os 100 itens de um Mix antes de o usuário decidir
                # baixar apenas o vídeo dispara muitas chamadas ao YouTube e
                # pode provocar bloqueio HTTP 403 na mídia logo em seguida.
                "playlistend": 1,
            })

            info_raw = extrair_info_com_fallback(
                ydl_opts_fast, url, download=False
            )

            query = parse_qs(urlparse(url).query)

            # A URL possui parâmetro list=
            is_playlist_url = "list" in query

            entries = info_raw.get("entries") or []

            # Alguns tipos de playlist do YouTube retornam entries vazio.
            # Nesse caso consultamos diretamente a playlist.
            if is_playlist_url and not entries:
                playlist_url = f"https://www.youtube.com/playlist?list={query['list'][0]}"

                playlist_info = extrair_info_com_fallback(
                    ydl_opts_fast, playlist_url, download=False
                )

                if playlist_info:
                    info_raw = playlist_info
                    entries = info_raw.get("entries") or []

            # Quantidade total (limitada a 100). Dá prioridade ao total que
            # o YouTube informa, pois acima só carregamos o primeiro item.
            total_videos = (
                info_raw.get("playlist_count")
                or info_raw.get("n_entries")
                or len(entries)
                or 0
            )

            total_videos = min(total_videos, 100)

            # Salva para a interface
            info_raw["video_count"] = total_videos

            is_real_playlist = (
                is_playlist_url
                or info_raw.get("_type") == "playlist"
                or total_videos > 1
            )

            if is_real_playlist:

                self.playlist_info = info_raw
                self.playlist_url = url

                escolha = self.show_playlist_dialog()

                if escolha == "cancelar":
                    self.reset_ui_state()
                    return

                if escolha.startswith("playlist"):

                    self.tipo_download = "playlist"

                    if "mp3" in escolha:
                        self.ui_after(
                            0,
                            lambda: self.format_var.set("mp3")
                        )
                    else:
                        self.ui_after(
                            0,
                            lambda: self.format_var.set("mp4")
                        )

                    self.update_ui_playlist(info_raw)
                    return

                else:
                    # Usuário escolheu baixar apenas o vídeo atual
                    self.tipo_download = "video"
                    self.video_url = get_video_only_url(url)

            else:

                self.tipo_download = "video"
                self.video_url = get_video_only_url(url)

                # Vídeo único já extraído por completo na busca rápida:
                # reaproveita e evita uma segunda requisição ao site.
                if (info_raw.get("formats") and info_raw.get("title")
                        and info_raw.get("_type", "video") == "video"
                        and self.video_url == url):
                    self.info = info_raw
                    self.ui_after(0, lambda: self.update_ui_video(self.info))
                    return

            self.fetch_video_details(self.video_url)

        except Exception as e:
            # Captura a mensagem agora: a variável "e" deixa de existir ao
            # sair do except e a lambda roda depois, na thread principal.
            erro = mensagem_amigavel(e)
            self.ui_after(
                0,
                lambda erro=erro: messagebox.showerror(
                    "Erro",
                    f"Erro ao obter informações:\n\n{erro}"
                )
            )

            self.ui_after(
                0,
                lambda: self.status_label.configure(
                    text="Erro ao carregar."
                )
            )

        finally:
            self.ui_after(
                0,
                lambda: self.search_btn.configure(
                    state="normal"
                )
            )
    
    def fetch_video_details(self, url):

        try:

            ydl_opts = self.get_common_opts()

            ydl_opts.update({
                "skip_download": True,
                "noplaylist": True,
            })

            self.info = extrair_info_com_fallback(
                ydl_opts, url, download=False
            )

            self.ui_after(
                0,
                lambda: self.update_ui_video(self.info)
            )


        except Exception as e:

            raise e

    def update_ui_video(self, info):
        title = info.get("title", "Desconhecido")
        uploader = info.get("uploader") or info.get("uploader_id") or "Desconhecido"
        duration = info.get("duration", 0)
        thumb_url = info.get("thumbnail")

        if duration:
            try:
                duration = int(float(duration))
                m, s = divmod(duration, 60)
                h, m = divmod(m, 60)
                tempo = f"{h:02d}:{m:02d}:{s:02d}" if h > 0 else f"{m:02d}:{s:02d}"
            except:
                tempo = "N/A"
        else:
            tempo = "N/A"

        self.title_label.configure(text=f"Título: {title}")
        self.channel_label.configure(text=f"Canal: {uploader}")
        self.duration_label.configure(text=f"Duração: {tempo}")
        self.status_label.configure(text="Vídeo carregado.")
        
        if thumb_url:
            threading.Thread(target=self.load_thumbnail, args=(thumb_url,), daemon=True).start()
        else:
            self.thumb_label.configure(image="", text="🎥", font=("Arial", 50))

    def update_ui_playlist(self, info):
        title = info.get("title", "Playlist")

        # Usa a quantidade calculada em get_info()
        count = info.get(
            "video_count",
            len(info.get("entries", []))
        )

        self.title_label.configure(
            text=f"Playlist: {title}"
        )

        self.channel_label.configure(
            text=f"Vídeos encontrados: {count} (Máximo de 100 processados)"
        )

        self.duration_label.configure(
            text="Pronto para baixar a playlist."
        )

        self.status_label.configure(
            text="Playlist carregada."
        )

        self.thumb_label.configure(
            image="",
            text="📚",
            font=("Arial", 50)
        )
    
    def load_thumbnail(self, url):
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
            response = requests.get(url, timeout=10, headers=headers)
            img_data = Image.open(BytesIO(response.content)).convert("RGB")
            img_data.thumbnail((400, 225))
            
            self.thumbnail = ctk.CTkImage(light_image=img_data, dark_image=img_data, size=(400, 225))
            self.ui_after(0, lambda: self.thumb_label.configure(image=self.thumbnail, text=""))
        except:
            self.ui_after(0, lambda: self.thumb_label.configure(image="", text="🖼️", font=("Arial", 50)))

    def show_playlist_dialog(self):
        resultado = "cancelar"
        dialog_done = threading.Event()
        dialog = None

        def set_result(res):
            nonlocal resultado
            resultado = res
            if dialog:
                dialog.destroy()
            dialog_done.set()

        def on_close():
            set_result("cancelar")

        def create_dialog():
            nonlocal dialog
            dialog = ctk.CTkToplevel(self.window)
            dialog.title("Playlist detectada")
            dialog.geometry("450x420")
            dialog.resizable(False, False)
            dialog.transient(self.window)
            dialog.grab_set()
            dialog.protocol("WM_DELETE_WINDOW", on_close)

            title = self.playlist_info.get("title", "Sem título")
            count = (
                self.playlist_info.get("video_count")
                or len(self.playlist_info.get("entries") or [])
            )

            ctk.CTkLabel(dialog, text=" Playlist detectada", font=("Arial", 22, "bold")).pack(pady=(20, 10))
            ctk.CTkLabel(dialog, text=f"Título: {title}", wraplength=400, font=("Arial", 14)).pack(pady=5)
            ctk.CTkLabel(dialog, text=f"Vídeos: {count} (Máximo 100 processados)", text_color="orange").pack(pady=5)

            ctk.CTkButton(dialog, text="Baixar Playlist Completa (MP4)", width=320, height=45, fg_color="#1f538d", font=("Arial", 14, "bold"), command=lambda: set_result("playlist_mp4")).pack(pady=10)
            ctk.CTkButton(dialog, text="Baixar Playlist Completa (MP3)", width=320, height=45, fg_color="#2c6e49", font=("Arial", 14, "bold"), command=lambda: set_result("playlist_mp3")).pack(pady=5)
            ctk.CTkButton(dialog, text="Baixar apenas este vídeo", width=320, height=40, command=lambda: set_result("video")).pack(pady=10)
            ctk.CTkButton(dialog, text="Cancelar", width=320, height=40, fg_color="gray40", command=on_close).pack(pady=10)

        self.ui_after(0, create_dialog)
        dialog_done.wait()
        return resultado

    # -----------------------------------------
    # Lógica de Download
    # -----------------------------------------
    def start_download(self):
        if self.tipo_download == "video" and not self.info:
            messagebox.showwarning("Aviso", "Busque as informações primeiro.")
            return
        if self.tipo_download == "playlist" and not self.playlist_info:
            messagebox.showwarning("Aviso", "Busque as informações primeiro.")
            return

        if not self.check_ffmpeg():
            return

        self.cancel_event.clear()
        self.download_btn.configure(state="disabled")
        self.cancel_btn.configure(state="normal")
        self.progress_bar.set(0)
        self.status_label.configure(text="Iniciando download...")
        
        threading.Thread(target=self.run_download, daemon=True).start()

    def cancel_download(self):
        self.cancel_event.set()
        self.cancel_btn.configure(state="disabled")
        self.status_label.configure(text="Cancelando...")

    def _baixar_youtube_dl(self, opts, url, formato):
        """Baixa com yt-dlp tentando primeiro SEM cookies (mais rápido e
        não mexe nos navegadores). Só busca cookies de sessão se o próprio
        site pedir login/confirmação de que não é um robô — e, mesmo
        assim, em silêncio, sem mostrar isso como erro."""

        def _run(o):
            with YoutubeDL(o) as ydl:
                if formato == "mp4":
                    ydl.add_post_processor(
                        EnsureH264AACPP(
                            downloader=ydl,
                            ffmpeg_path=self.get_ffmpeg_binary(),
                            ffprobe_path=self.get_ffprobe_binary(),
                            cancel_event=self.cancel_event,
                        ),
                        when="after_move",
                    )
                ydl.download([url])

        opts_sem_cookie = opts.copy()
        opts_sem_cookie.pop("cookiesfrombrowser", None)

        try:
            _run(opts_sem_cookie)
            return
        except Exception as primeiro_erro:
            if self.cancel_event.is_set():
                raise
            precisa_login = erro_pede_login(primeiro_erro)
            if not precisa_login:
                raise

            opts_cookie = opts.copy()
            if not add_browser_cookies(opts_cookie):
                raise primeiro_erro

            try:
                _run(opts_cookie)
                return
            except Exception:
                # Última tentativa: deixa o yt-dlp escolher livremente
                # entre todos os clientes, sem restringir a mweb/tv.
                if "extractor_args" in opts_cookie:
                    opts_livre = opts_cookie.copy()
                    opts_livre.pop("extractor_args", None)
                    _run(opts_livre)
                    return
                raise

    def run_download(self):
        lock_path = None
        try:
            formato = self.format_var.get()
            qualidade = self.quality_combo.get()
            url = self.playlist_url if self.tipo_download == "playlist" else self.video_url
           
            # Protege contra a mesma URL sendo baixada ao mesmo tempo por
            # duas instâncias do programa (o que corromperia o arquivo).
            sufixo_duplicata, lock_path = reservar_download(
                url, formato, qualidade, self.download_folder
            )

            if sufixo_duplicata:
                self.ui_after(
                    0,
                    lambda: self.status_label.configure(
                        text="Este vídeo já está sendo baixado em outra janela. Salvando como cópia..."
                    )
                )

            opts = self.get_common_opts()
            self._arquivo_em_andamento = None
            opts.update({
                "progress_hooks": [self.update_progress_hook],
                # Garantem o cancelamento também entre itens da playlist
                # e entre etapas de conversão (ex.: ffmpeg do MP3).
                "postprocessor_hooks": [self._checar_cancelamento_hook],
                "match_filter": self._match_filter_cancelavel,
            })

            # Configurações de Formato
            if formato == "mp3":
                opts.update({
                    "format": "bestaudio/best",
                    "postprocessors": [{
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }],
                })
            else:  # mp4
                m_res = re.match(r"(\d+)p", qualidade)
                res = m_res.group(1) if m_res else None

                # Prioriza vídeo H.264 (avc1) + áudio AAC (mp4a) nativos do
                # YouTube sempre que existirem para essa resolução — assim
                # evitamos recodificação desnecessária. Se não existirem
                # (comum em 1440p/4K, que costuma vir apenas em VP9/AV1),
                # caímos para o melhor disponível; o EnsureH264AACPP cuida
                # de recodificar apenas quando for realmente preciso.
                if res:
                    opts["format"] = (
                        f"bestvideo[vcodec^=avc1][height<={res}]+bestaudio[acodec^=mp4a]/"
                        f"bestvideo[height<={res}]+bestaudio/"
                        f"best[height<={res}]/"
                        f"best"
                    )
                else:
                    opts["format"] = (
                        "bestvideo[vcodec^=avc1]+bestaudio[acodec^=mp4a]/"
                        "bestvideo*+bestaudio/"
                        "best"
                    )

                opts["merge_output_format"] = "mp4"

            # Caminho de Saída
            if self.tipo_download == "playlist":
                opts.update({
                    "outtmpl": os.path.join(
                        self.download_folder, "%(playlist_title)s",
                        f"%(playlist_index)s - %(title)s{sufixo_duplicata}.%(ext)s",
                    ),
                    "noplaylist": False,
                    "playlistend": 100,
                    # Evita que o YouTube bloqueie a sequência de 100
                    # downloads como tráfego automatizado. A pequena pausa é
                    # aplicada somente em playlists, não em vídeo único.
                    "sleep_interval_requests": 1,
                    "sleep_interval": 2,
                    "max_sleep_interval": 4,
                    # Se o YouTube recusar temporariamente um item, segue
                    # com os próximos da playlist em vez de abortar tudo.
                    "ignoreerrors":  True,
                })
            else:
                opts.update({
                    "outtmpl": os.path.join(
                        self.download_folder,
                        f"%(title).100s [%(id)s]{sufixo_duplicata}.%(ext)s",
                    ),
                    "noplaylist": True,
                })

            
            try:
                self._baixar_youtube_dl(opts, url, formato)
            except Exception as erro_download:
                if self.cancel_event.is_set():
                    raise
                # Alguns fluxos separados do YouTube (vídeo + áudio) exigem
                # um PO Token e podem devolver 403. Para vídeo individual,
                # tentamos então um MP4 progressivo, que já contém áudio e
                # vídeo no mesmo arquivo; assim nunca concluímos com vídeo
                # mudo por causa da falha do fluxo de áudio.
                is_youtube = "youtube.com" in url or "youtu.be" in url
                if (self.tipo_download != "video" or formato != "mp4"
                        or not is_youtube):
                    raise erro_download

                self.ui_after(
                    0,
                    lambda: self.status_label.configure(
                        text="YouTube recusou alta qualidade. Tentando MP4 com áudio..."
                    )
                )

                opts_fallback = opts.copy()
                opts_fallback.update({
                    # Formatos progressivos têm vídeo e áudio juntos. No
                    # YouTube, normalmente a melhor alternativa é 360p.
                    "format": (
                        "best[ext=mp4][vcodec!=none][acodec!=none]/"
                        "best[vcodec!=none][acodec!=none]"
                    ),
                    "merge_output_format": "mp4",
                    "overwrites": True,
                    "retries": 3,
                })

                self._baixar_youtube_dl(opts_fallback, url, formato)

            # Rede de segurança: se o cancelamento foi engolido em algum
            # ponto, não mostra "concluído".
            if self.cancel_event.is_set():
                raise DownloadCancelado("Download cancelado pelo usuário.")

            self.ui_after(0, lambda: self.cancel_btn.configure(state="disabled"))
            self.ui_after(0, lambda: self.status_label.configure(text="Download concluído!"))
            self.ui_after(0, lambda: messagebox.showinfo("Sucesso", "Download finalizado com sucesso."))
            
            if self.tipo_download == "video":
                self.save_history(self.info.get("title", "Vídeo"))

        except Exception as e:
            if self.cancel_event.is_set():
                self._remover_arquivo_incompleto()
                self.ui_after(0, lambda: self.status_label.configure(text="Download cancelado."))
                self.ui_after(0, lambda: self.progress_bar.set(0))
            else:
                erro = mensagem_amigavel(e).encode("utf-8", "replace").decode("utf-8")

                self.ui_after(
                    0,
                    lambda: self.status_label.configure(text="Erro no download.")
                )

                self.ui_after(
                    0,
                    lambda erro=erro: messagebox.showerror(
                        "Erro",
                        f"Erro no download:\n\n{erro}"
                    )
                )

        finally:
            liberar_download(lock_path)
            self.ui_after(
                0,
                lambda: self.download_btn.configure(state="normal")
            )
            self.ui_after(
                0,
                lambda: self.cancel_btn.configure(state="disabled")
            )

    def _checar_cancelamento_hook(self, d):
        if self.cancel_event.is_set():
            raise DownloadCancelado("Download cancelado pelo usuário.")

    def _match_filter_cancelavel(self, info_dict, *args, **kwargs):
        # Chamado pelo yt-dlp antes de cada item; nunca filtra nada.
        if self.cancel_event.is_set():
            raise DownloadCancelado("Download cancelado pelo usuário.")
        return None

    def _remover_arquivo_incompleto(self):
        """Com "nopart", o arquivo em andamento fica com o nome final e
        incompleto. Remove só ele ao cancelar."""
        caminho = getattr(self, "_arquivo_em_andamento", None)
        self._arquivo_em_andamento = None
        if caminho and os.path.isfile(caminho):
            try:
                os.remove(caminho)
            except OSError:
                pass

    def update_progress_hook(self, d):
        if self.cancel_event.is_set():
            raise DownloadCancelado("Download cancelado pelo usuário.")
        if d.get("status") == "downloading":
            self._arquivo_em_andamento = d.get("filename") or d.get("tmpfilename")
        elif d.get("status") == "finished":
            self._arquivo_em_andamento = None
        if d["status"] == "downloading":
            try:
                downloaded = d.get("downloaded_bytes", 0)
                total = d.get("total_bytes") or d.get("total_bytes_estimate")
                
                if total:
                    percent = downloaded / total
                    self.ui_after(0, lambda p=percent: self.progress_bar.set(min(max(p, 0), 1)))
                else:
                    p_str = d.get("_percent_str", "0%").replace("%", "")
                    if "\x1b" in p_str:
                        p_str = re.sub(r"\x1b\[[0-9;]*m", "", p_str)
                    pct = float(p_str.strip()) / 100
                    self.ui_after(0, lambda p=pct: self.progress_bar.set(min(max(p, 0), 1)))

                speed = d.get("_speed_str", "N/A")
                if "\x1b" in speed:
                    speed = re.sub(r"\x1b\[[0-9;]*m", "", speed)
                
                eta = re.sub(r"\x1b\[[0-9;]*m", "", str(d.get("_eta_str", "") or "")).strip()
                texto = f"Baixando... {speed}" + (f"  •  restam {eta}" if eta and eta != "N/A" else "")
                self.ui_after(0, lambda t=texto: self.status_label.configure(text=t))
            except: pass
        elif d["status"] == "finished":
            self.ui_after(0, lambda: self.progress_bar.set(1))
            self.ui_after(0, lambda: self.status_label.configure(text="Processando..."))

    # -----------------------------------------
    # Utilitários
    # -----------------------------------------
    def check_ffmpeg(self):
        # Verifica local primeiro, depois system path
        ffmpeg_local = os.path.join(BASE_PATH, "ffmpeg.exe")
        if os.path.exists(ffmpeg_local) or shutil.which("ffmpeg"):
            return True
        messagebox.showwarning(
            "FFmpeg",
            "FFmpeg não encontrado.\n\n"
            "Windows: coloque ffmpeg.exe e ffprobe.exe na pasta do programa.\n"
            "Linux: sudo apt install ffmpeg"
        )
        return False

    def get_ffmpeg_binary(self):
        """Retorna o caminho do ffmpeg: local (Windows/EXE) ou do sistema (PATH)."""
        if sys.platform == "win32":
            local = os.path.join(BASE_PATH, "ffmpeg.exe")
            if os.path.exists(local):
                return local
        found = shutil.which("ffmpeg")
        return found or "ffmpeg"

    def get_ffprobe_binary(self):
        """Retorna o caminho do ffprobe: local (Windows/EXE) ou do sistema (PATH)."""
        if sys.platform == "win32":
            local = os.path.join(BASE_PATH, "ffprobe.exe")
            if os.path.exists(local):
                return local
        found = shutil.which("ffprobe")
        return found or "ffprobe"

    def clear_url(self):
        self.url_entry.delete(0, "end")
        self.reset_ui_state()
        self.status_label.configure(text="Campos limpos.")

    def reset_ui_state(self):
        self.info = None
        self.playlist_info = None
        self.tipo_download = "video"
        self.video_url = None
        self.playlist_url = None
        self.title_label.configure(text="Título:")
        self.channel_label.configure(text="Canal:")
        self.duration_label.configure(text="Duração:")
        self.thumb_label.configure(image="", text="")
        self.progress_bar.set(0)

    def choose_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.download_folder = folder
            self.folder_label.configure(text=folder)
            self.save_config()

    def open_download_folder(self):
        if not os.path.exists(self.download_folder):
            os.makedirs(self.download_folder)
        
        if sys.platform == "win32": os.startfile(self.download_folder)
        elif sys.platform == "darwin": subprocess.Popen(["open", self.download_folder])
        else: subprocess.Popen(["xdg-open", self.download_folder])

    def load_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    self.download_folder = config.get("download_folder", self.download_folder)
            except: pass

    def save_config(self):
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump({"download_folder": self.download_folder}, f, indent=4)

    def save_history(self, titulo):
        registro = {
            "titulo": titulo,
            "data": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
            "pasta": self.download_folder
        }
        historico = []
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, "r", encoding="utf-8") as f: historico = json.load(f)
            except: pass
        historico.append(registro)
        with open(self.history_file, "w", encoding="utf-8") as f:
            json.dump(historico, f, indent=4, ensure_ascii=False)

    def show_help(self):
        help_win = ctk.CTkToplevel(self.window)
        help_win.title("Ajuda")
        help_win.geometry("600x600")
        help_text = ctk.CTkTextbox(help_win, wrap="word", font=("Arial", 14))
        help_text.pack(fill="both", expand=True, padx=10, pady=10)
        help_text.insert(
            "1.0",
    """
    ==============================
        YT Downloader Pro
    ==============================

    COMO USAR

    1) Copie o link do vídeo.

    Atalhos:

    Ctrl + C = Copiar
    Ctrl + V = Colar

    ----------------------------------------

    2) Cole o link na caixa de texto.

    ----------------------------------------

    3) Clique em:

    Buscar informações

    ----------------------------------------

    4) Escolha:

    • Vídeo MP4

    ou

    • Áudio MP3

    ----------------------------------------

    5) Escolha a qualidade desejada.

    ----------------------------------------

    6) Escolha uma das opções:

    • BAIXAR
    Baixa apenas o vídeo informado.

    • Baixar Playlist (MP4)
    Baixa todos os vídeos da playlist do YouTube
    em formato MP4.

    • Baixar Playlist (MP3)
    Baixa todos os vídeos da playlist do YouTube
    convertidos para MP3.

    ----------------------------------------

    OBSERVAÇÃO

    • As opções de Playlist funcionam apenas
    com playlists do YouTube.

    • Caso seja informado o link de um vídeo
    comum, apenas esse vídeo será baixado.

    • Cada playlist será salva automaticamente
    em uma pasta com o nome da playlist.

    ----------------------------------------

    SITES SUPORTADOS
    (podem variar conforme o yt-dlp)

    • YouTube
    • TikTok
    • Facebook
    • Instagram
    • Dailymotion
    • X (Twitter)
    • Vimeo
    • Twitch
    • SoundCloud
    • Bilibili
    • Reddit
    • Pinterest
    • e centenas de outros.

    ----------------------------------------

    TELA PRETA APENAS NO VLC

    Se o vídeo abrir normalmente em outros
    reprodutores (MPV, Celluloid, Videos,
    Windows Media Player etc.), mas ficar
    preto apenas no VLC, o arquivo NÃO está
    com defeito.

    Algumas versões do VLC possuem problemas
    com a aceleração por hardware.

    No VLC faça:

    Ferramentas

    → Preferências

    → Entrada / Codecs

    → Decodificação acelerada por hardware

    Altere para:

    • Desativar

    ou

    • Automático

    Feche o VLC e abra novamente.

    ----------------------------------------

    OBSERVAÇÕES

    • Nem todos os sites oferecem todas as
    qualidades.

    • Alguns vídeos existem apenas em
    360p, 480p ou 720p.

    • O YouTube normalmente possui
    1080p, 1440p e 4K.

    • O programa suporta download de vídeos
    individuais e de playlists completas
    do YouTube.

    • As playlists podem ser baixadas em
    MP4 ou convertidas automaticamente
    para MP3.

    • A velocidade do download depende da
    sua conexão com a Internet e do
    servidor do YouTube.

    • Alguns sites podem bloquear vídeos
    privados ou protegidos.

    • Caso algum site pare de funcionar,
    atualize o yt-dlp:

    pip install -U yt-dlp

    ----------------------------------------

    BOTÕES

    Buscar informações
    Obtém título, duração, canal e miniatura.

    Escolher Pasta
    Seleciona onde salvar os downloads.

    Abrir Pasta
    Abre a pasta dos downloads.

    Limpar URL
    Limpa todas as informações da tela.

    ----------------------------------------

    FORMATOS

    MP4
    Baixa vídeo + áudio em H.264 + AAC,
    o padrão mais compatível com
    celulares, TVs, players e navegadores.
    Se o YouTube só oferecer o vídeo em
    VP9/AV1 ou o áudio em Opus (comum em
    1440p/4K), o programa converte
    automaticamente para H.264 + AAC.

    MP3
    Extrai somente o áudio.

    ----------------------------------------

    PROBLEMAS COMUNS

    Erro de download:
    Atualize o yt-dlp.

    Erro no TikTok:
    Alguns vídeos são protegidos.

    Erro no Facebook:
    Alguns vídeos possuem títulos muito
    grandes ou restrições do próprio site.

    ----------------------------------------

    Autor

    Jackson Q.

    YT Downloader Pro
    """
        )
        help_text.configure(state="disabled")

if __name__ == "__main__":
    Downloader()
