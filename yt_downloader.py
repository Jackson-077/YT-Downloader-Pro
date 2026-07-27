#!/usr/bin/env python3
# ==========================================================
# YT Downloader Pro
# Versão: 1.7 (Universal Edition - Linux/Windows)
#
# Autor: Jackson Q. 
#
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
import customtkinter as ctk
from tkinter import filedialog, messagebox
from PIL import Image
from io import BytesIO
from yt_dlp import YoutubeDL

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
def add_browser_cookies(opts):

    browsers = [

        "edge",
        "chrome",
        "firefox",
        "brave",
        "opera",
        "vivaldi"

    ]


    for browser in browsers:

        try:

            teste = opts.copy()

            teste["cookiesfrombrowser"] = (
                browser,
            )


            with YoutubeDL(teste):
                pass


            opts["cookiesfrombrowser"] = (
                browser,
            )


            print(
                f"[YT Downloader] Cookie encontrado: {browser}"
            )

            return True


        except Exception as e:

            print(
                f"Falhou {browser}: {e}"
            )

            continue


    print(
        "[YT Downloader] Nenhum navegador com cookies válido."
    )

    return False
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
        
        self.load_config()
        self.create_widgets()
        
        # Verifica binários na inicialização
        self.check_local_binaries()
        
        self.window.mainloop()

    def check_local_binaries(self):
        """Verifica binários locais (Windows) ou do sistema (Linux)."""
        msg = []
        
        # Windows: Verifica binários locais na pasta do EXE
        if sys.platform == "win32":
            ffmpeg_local = os.path.join(BASE_PATH, "ffmpeg.exe")
            deno_local = os.path.join(BASE_PATH, "deno.exe")
            if os.path.exists(ffmpeg_local): msg.append("FFmpeg Local")
            if os.path.exists(deno_local): msg.append("Deno Local")
        
        # Linux: Verifica binários do sistema (importante para .deb)
        else:
            if shutil.which("ffmpeg"): msg.append("FFmpeg Sistema")
            if shutil.which("deno"): msg.append("Deno Sistema")
            
        if msg:
            status_text = f"Pronto. ({' + '.join(msg)})"
            self.window.after(1000, lambda: self.status_label.configure(text=status_text))

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
        self.quality_combo = ctk.CTkComboBox(self.main_frame, width=200, values=["Melhor", "1080p", "720p", "480p", "360p"])
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
        self.download_btn.pack(pady=20)

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
            "logger": UTF8Logger(),
        }


        opts["http_headers"] = {

            "User-Agent":
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/138 Safari/537.36"

        }


        opts["remote_components"] = [
            "ejs:github"
        ]


        opts["extractor_args"] = {

            "youtube": {

                "player_client": [
                    "web",
                    "android"
                ]

            }

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
        
        self.search_btn.configure(state="disabled")
        self.status_label.configure(text="Buscando informações...")
        threading.Thread(target=self.get_info, args=(url,), daemon=True).start()

    def get_info(self, url):
        try:
            ydl_opts_fast = self.get_common_opts()
            ydl_opts_fast.update({
                "skip_download": True,
                "extract_flat": True,
                "playlistend": 100,
            })

            with YoutubeDL(ydl_opts_fast) as ydl:
                info_raw = ydl.extract_info(url, download=False)

            entries = info_raw.get("entries", [])
            is_real_playlist = (info_raw.get("_type") == "playlist" or len(entries) > 1)

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
                        self.window.after(0, lambda: self.format_var.set("mp3"))
                    else:
                        self.window.after(0, lambda: self.format_var.set("mp4"))
                    
                    self.update_ui_playlist(info_raw)
                    return
                
                else: # Escolheu "video"
                    self.tipo_download = "video"
                    if entries:
                        first_video = entries[0]
                        self.video_url = first_video.get("url") or first_video.get("webpage_url") or url
                    else:
                        self.video_url = url
            else:
                self.tipo_download = "video"
                self.video_url = url

            self.fetch_video_details(self.video_url)

        except Exception as e:
            self.window.after(0, lambda: messagebox.showerror("Erro", f"Erro ao obter informações: {str(e)}"))
            self.window.after(0, lambda: self.status_label.configure(text="Erro ao carregar."))
        finally:
            self.window.after(0, lambda: self.search_btn.configure(state="normal"))

    def fetch_video_details(self, url):

        try:

            ydl_opts = self.get_common_opts()

            ydl_opts.update({
                "skip_download": True,
                "noplaylist": True,
            })


            try:

                # Primeira tentativa: sem cookies

                ydl_opts.pop(
                    "cookiesfrombrowser",
                    None
                )

                with YoutubeDL(ydl_opts) as ydl:

                    self.info = ydl.extract_info(
                        url,
                        download=False
                    )


            except Exception as primeiro_erro:


                print(
                    "[YT Downloader] Falhou sem cookies. Testando navegadores..."
                )


                # Segunda tentativa: cookies automáticos

                if add_browser_cookies(ydl_opts):

                    with YoutubeDL(ydl_opts) as ydl:

                        self.info = ydl.extract_info(
                            url,
                            download=False
                        )

                else:

                    raise primeiro_erro



            self.window.after(
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
        entries = info.get("entries", [])
        count = len(entries)

        self.title_label.configure(text=f"Playlist: {title}")
        self.channel_label.configure(text=f"Vídeos encontrados: {count} (Limite de 100)")
        self.duration_label.configure(text="Pronto para baixar a playlist.")
        self.status_label.configure(text="Playlist carregada.")
        self.thumb_label.configure(image="", text="📚", font=("Arial", 50))

    def load_thumbnail(self, url):
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
            response = requests.get(url, timeout=10, headers=headers)
            img_data = Image.open(BytesIO(response.content)).convert("RGB")
            img_data.thumbnail((400, 225))
            
            self.thumbnail = ctk.CTkImage(light_image=img_data, dark_image=img_data, size=(400, 225))
            self.window.after(0, lambda: self.thumb_label.configure(image=self.thumbnail, text=""))
        except:
            self.window.after(0, lambda: self.thumb_label.configure(image="", text="🖼️", font=("Arial", 50)))

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
            count = len(self.playlist_info.get("entries", []))

            ctk.CTkLabel(dialog, text=" Playlist detectada", font=("Arial", 22, "bold")).pack(pady=(20, 10))
            ctk.CTkLabel(dialog, text=f"Título: {title}", wraplength=400, font=("Arial", 14)).pack(pady=5)
            ctk.CTkLabel(dialog, text=f"Vídeos: {count} (Máximo 100 processados)", text_color="orange").pack(pady=5)

            ctk.CTkButton(dialog, text="Baixar Playlist Completa (MP4)", width=320, height=45, fg_color="#1f538d", font=("Arial", 14, "bold"), command=lambda: set_result("playlist_mp4")).pack(pady=10)
            ctk.CTkButton(dialog, text="Baixar Playlist Completa (MP3)", width=320, height=45, fg_color="#2c6e49", font=("Arial", 14, "bold"), command=lambda: set_result("playlist_mp3")).pack(pady=5)
            ctk.CTkButton(dialog, text="Baixar apenas este vídeo", width=320, height=40, command=lambda: set_result("video")).pack(pady=10)
            ctk.CTkButton(dialog, text="Cancelar", width=320, height=40, fg_color="gray40", command=on_close).pack(pady=10)

        self.window.after(0, create_dialog)
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

        self.download_btn.configure(state="disabled")
        self.progress_bar.set(0)
        self.status_label.configure(text="Iniciando download...")
        
        threading.Thread(target=self.run_download, daemon=True).start()

    def run_download(self):
        try:
            formato = self.format_var.get()
            qualidade = self.quality_combo.get()
            url = self.playlist_url if self.tipo_download == "playlist" else self.video_url
            
            opts = self.get_common_opts()
            opts.update({
                "progress_hooks": [self.update_progress_hook],
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
                res_map = {
                    "1080p": "1080",
                    "720p": "720",
                    "480p": "480",
                    "360p": "360"
                }

                res = res_map.get(qualidade)

                if res:
                    opts["format"] = (
                        f"bestvideo*[height<={res}]+bestaudio/"
                        f"best[height<={res}]/"
                        f"best"
                    )
                else:
                    opts["format"] = (
                        "bestvideo*+bestaudio/"
                        "best"
                    )

                opts["merge_output_format"] = "mp4"

            # Caminho de Saída
            if self.tipo_download == "playlist":
                opts.update({
                    "outtmpl": os.path.join(self.download_folder, "%(playlist_title)s", "%(playlist_index)s - %(title)s.%(ext)s"),
                    "noplaylist": False,
                    "playlistend": 100,
                })
            else:
                opts.update({
                    "outtmpl": os.path.join(self.download_folder, "%(title).100s [%(id)s].%(ext)s"),
                    "noplaylist": True,
                })

            
            with YoutubeDL(opts) as ydl:
                ydl.download([url])

            self.window.after(0, lambda: self.status_label.configure(text="Download concluído!"))
            self.window.after(0, lambda: messagebox.showinfo("Sucesso", "Download finalizado com sucesso."))
            
            if self.tipo_download == "video":
                self.save_history(self.info.get("title", "Vídeo"))

        except Exception as e:
            erro = str(e).encode("utf-8", "replace").decode("utf-8")

            self.window.after(
                0,
                lambda: self.status_label.configure(text="Erro no download.")
            )

            self.window.after(
                0,
                lambda erro=erro: messagebox.showerror(
                    "Erro",
                    f"Erro no download:\n\n{erro}"
                )
            )

        finally:
            self.window.after(
                0,
                lambda: self.download_btn.configure(state="normal")
            )

    def update_progress_hook(self, d):
        if d["status"] == "downloading":
            try:
                downloaded = d.get("downloaded_bytes", 0)
                total = d.get("total_bytes") or d.get("total_bytes_estimate")
                
                if total:
                    percent = downloaded / total
                    self.window.after(0, lambda: self.progress_bar.set(percent))
                else:
                    p_str = d.get("_percent_str", "0%").replace("%", "")
                    if "\x1b" in p_str:
                        p_str = re.sub(r"\x1b\[[0-9;]*m", "", p_str)
                    self.window.after(0, lambda: self.progress_bar.set(float(p_str.strip())/100))

                speed = d.get("_speed_str", "N/A")
                if "\x1b" in speed:
                    speed = re.sub(r"\x1b\[[0-9;]*m", "", speed)
                
                self.window.after(0, lambda: self.status_label.configure(text=f"Baixando... {speed}"))
            except: pass
        elif d["status"] == "finished":
            self.window.after(0, lambda: self.progress_bar.set(1))
            self.window.after(0, lambda: self.status_label.configure(text="Processando..."))

    # -----------------------------------------
    # Utilitários
    # -----------------------------------------
    def check_ffmpeg(self):
        # Verifica local primeiro, depois system path
        ffmpeg_local = os.path.join(BASE_PATH, "ffmpeg.exe")
        if os.path.exists(ffmpeg_local) or shutil.which("ffmpeg"):
            return True
        messagebox.showwarning("FFmpeg", "FFmpeg não encontrado. Coloque o ffmpeg.exe na pasta do programa ou instale-o no sistema.")
        return False

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
    Baixa vídeo + áudio.

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
