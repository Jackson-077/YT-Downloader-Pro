#!/usr/bin/env python3
# ==========================================================
# YT Downloader Pro
# Versão: 1.0
#
# Autor: Jackson Q.
#
# Downloader gráfico utilizando yt-dlp
#
# Linux / Windows
#
# ==========================================================
import json
import datetime
import shutil
import os
import sys
import threading
import subprocess
import customtkinter as ctk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
import requests
from io import BytesIO
from yt_dlp import YoutubeDL

# -----------------------------
# Configuração da Interface
# -----------------------------

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class Downloader:

    def __init__(self):

        self.window = ctk.CTk()

        self.window.title("YT Downloader Pro")

        self.window.geometry("900x760")
        self.window.resizable(True, True)

        self.download_folder = os.path.join(
            os.path.expanduser("~"),
            "Downloads"
        )

        self.config_file = "config.json"

        self.history_file = "history.json"

        self.load_config()

        self.thumbnail = None

        self.info = None

        self.create_widgets()

        self.window.mainloop()

    # -----------------------------------------

    def create_widgets(self):

        title = ctk.CTkLabel(
            self.window,
            text="YT Downloader Pro",
            font=("Arial", 28, "bold")
        )

        title.pack(pady=10)


        # Área com rolagem
        self.main_frame = ctk.CTkScrollableFrame(
            self.window,
            width=850,
            height=680
        )

        self.main_frame.pack(
            padx=10,
            pady=10,
            fill="both",
            expand=True
        )


        self.url = ctk.CTkEntry(
            self.main_frame,
            width=700,
            placeholder_text="Cole aqui a URL do vídeo..."
        )

        self.url.pack(pady=10)
         
        self.search_btn = ctk.CTkButton(
            self.main_frame,
            text="Buscar informações",
            command=self.start_info_thread
        )

        self.search_btn.pack(pady=5)
        # -----------------------------
        # Botões auxiliares
        # -----------------------------

        frame_botoes = ctk.CTkFrame(
            self.main_frame
        )

        frame_botoes.pack(
            pady=10
        )


        self.clear_btn = ctk.CTkButton(
            frame_botoes,
            text="Limpar URL",
            width=150,
            command=self.clear_url
        )

        self.clear_btn.grid(
            row=0,
            column=0,
            padx=10
        )



        self.open_folder_btn = ctk.CTkButton(
            frame_botoes,
            text="Abrir Pasta",
            width=150,
            command=self.open_download_folder
        )

        self.open_folder_btn.grid(
            row=0,
            column=1,
            padx=10
        )

        self.help_btn = ctk.CTkButton(
            frame_botoes,
            text="Ajuda",
            width=150,
            command=self.show_help
        )

        self.help_btn.grid(
            row=0,
            column=2,
            padx=10
        )

        self.thumb_label = ctk.CTkLabel(
            self.main_frame,
            text=""
        )

        self.thumb_label.pack(pady=10)


        self.title_video = ctk.CTkLabel(
            self.main_frame,
            text="Título:",
            wraplength=760,
            justify="left"
        )

        self.title_video.pack()


        self.channel = ctk.CTkLabel(
            self.main_frame,
            text="Canal:"
        )

        self.channel.pack()


        self.duration = ctk.CTkLabel(
            self.main_frame,
            text="Duração:"
        )

        self.duration.pack()


        ctk.CTkLabel(
            self.main_frame,
            text=""
        ).pack()


        self.format_var = ctk.StringVar(
            value="mp4"
        )


        ctk.CTkRadioButton(
            self.main_frame,
            text="Vídeo MP4",
            variable=self.format_var,
            value="mp4"
        ).pack(pady=5)


        ctk.CTkRadioButton(
            self.main_frame,
            text="Áudio MP3",
            variable=self.format_var,
            value="mp3"
        ).pack(pady=5)


        ctk.CTkLabel(
            self.main_frame,
            text="Qualidade"
        ).pack(pady=5)


        self.quality = ctk.CTkComboBox(
            self.main_frame,
            width=200,
            values=[
                "Melhor",
                "1080p",
                "720p",
                "480p",
                "360p"
            ]
        )

        self.quality.set("Melhor")

        self.quality.pack(pady=5)


        ctk.CTkButton(
            self.main_frame,
            text="Escolher Pasta",
            command=self.choose_folder
        ).pack(pady=10)


        self.folder_label = ctk.CTkLabel(
            self.main_frame,
            text=self.download_folder,
            wraplength=700
        )

        self.folder_label.pack()


        self.progress = ctk.CTkProgressBar(
            self.main_frame,
            width=600
        )

        self.progress.pack(
            pady=20
        )

        self.progress.set(0)


        self.status = ctk.CTkLabel(
            self.main_frame,
            text="Pronto."
        )

        self.status.pack()


        self.download_btn = ctk.CTkButton(
            self.main_frame,
            text="BAIXAR",
            width=250,
            height=40,
            command=self.start_download
        )

        self.download_btn.pack(
            pady=20
        )


#------------------------------------------
    def show_help(self):

        janela = ctk.CTkToplevel(self.window)

        janela.title("Ajuda")

        janela.geometry("700x650")

        janela.grab_set()


        texto = ctk.CTkTextbox(
            janela,
            wrap="word",
            font=("Arial", 15)
        )

        texto.pack(
            fill="both",
            expand=True,
            padx=10,
            pady=10
        )


        texto.insert(
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

    6) Clique em BAIXAR.

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

    • Em playlists do YouTube apenas o
    vídeo atual é baixado.

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

        texto.configure(state="disabled")
    # -----------------------------------------

 

    def start_info_thread(self):

        thread = threading.Thread(
            target=self.get_info
        )

        thread.daemon = True

        thread.start()


    # -----------------------------------------

    def choose_folder(self):

        folder = filedialog.askdirectory()

        if folder:

            self.download_folder = folder

            self.folder_label.configure(
                text=folder
            )

            self.save_config()
    # -----------------------------------------

    # -----------------------------------------
    # LIMPAR CAMPO URL
    # -----------------------------------------

    def clear_url(self):

        self.url.delete(
            0,
            "end"
        )

        self.info = None

        self.title_video.configure(
            text="Título:"
        )

        self.channel.configure(
            text="Canal:"
        )

        self.duration.configure(
            text="Duração:"
        )

        self.thumb_label.configure(
            image="",
            text=""
        )

        self.status.configure(
            text="Campo limpo."
        )


    # -----------------------------------------
    # ABRIR PASTA DOWNLOAD
    # -----------------------------------------

    def open_download_folder(self):

        pasta = self.download_folder


        if not os.path.exists(pasta):

            os.makedirs(
                pasta
            )


        if sys.platform.startswith("linux"):

            subprocess.Popen(
                [
                    "xdg-open",
                    pasta
                ]
            )


        elif sys.platform.startswith("win"):

            os.startfile(
                pasta
            )


        elif sys.platform.startswith("darwin"):

            subprocess.Popen(
                [
                    "open",
                    pasta
                ]
            )

      # -----------------------------------------

    def start_download(self):

        if self.info is None:

            messagebox.showwarning(
                "Aviso",
                "Primeiro clique em Buscar informações."
            )

            return


        thread = threading.Thread(
            target=self.download_video
        )

        thread.daemon = True

        thread.start()


    # -----------------------------------------

    def get_info(self):

        url = self.url.get().strip()

        if not url:

            messagebox.showwarning(
                "Aviso",
                "Informe uma URL."
            )

            return

        self.status.configure(
            text="Buscando informações..."
        )

        self.window.after(
            0,
            lambda: self.status.configure(
                text="Buscando informações..."
            )
        )

        try:

            ydl_opts = {

                "quiet": True,

                "skip_download": True,

                "noplaylist": True,

                "socket_timeout": 20,

                "js_runtimes": {
                    "deno": {}
                }

            }

            with YoutubeDL(ydl_opts) as ydl:

                self.info = ydl.extract_info(
                    url,
                    download=False
                )

            title = self.info.get("title", "Desconhecido")

            uploader = self.info.get(
                "uploader",
                "Desconhecido"
            )

            duration = self.info.get(
                "duration",
                0
            )

            thumb = self.info.get(
                "thumbnail",
                None
            )

            horas = duration // 3600

            minutos = (duration % 3600) // 60

            segundos = duration % 60

            if horas:

                tempo = f"{horas:02}:{minutos:02}:{segundos:02}"

            else:

                tempo = f"{minutos:02}:{segundos:02}"

            self.title_video.configure(
                text=f"Título: {title}"
            )

            self.channel.configure(
                text=f"Canal: {uploader}"
            )

            self.duration.configure(
                text=f"Duração: {tempo}"
            )

            if thumb:

                resposta = requests.get(
                    thumb,
                    timeout=15
                )

                resposta.raise_for_status()

                imagem = Image.open(
                    BytesIO(resposta.content)
                )

                imagem = imagem.convert("RGB")

                imagem.thumbnail(
                    (400, 225),
                    Image.Resampling.LANCZOS
                )

                self.thumbnail = ctk.CTkImage(
                    light_image=imagem,
                    dark_image=imagem,
                    size=(400, 225)
                )

                self.thumb_label.configure(
                    image=self.thumbnail,
                    text=""
                )

            else:

                self.thumb_label.configure(
                    image=None,
                    text="Sem miniatura disponível."
                )

            self.status.configure(
                text="Informações carregadas."
            )

        except Exception as erro:

            messagebox.showerror(
                "Erro",
                str(erro)
            )

            self.status.configure(
                text="Erro ao obter informações."
            )
            
    # -----------------------------------------

    def update_progress(self, data):

        if data["status"] == "downloading":

            total = data.get(
                "total_bytes"
            ) or data.get(
                "total_bytes_estimate"
            )

            baixado = data.get(
                "downloaded_bytes",
                0
            )

            if total:

                porcentagem = baixado / total

                self.progress.set(
                    porcentagem
                )

            velocidade = data.get(
                "speed"
            )

            if velocidade:

                mb = velocidade / 1024 / 1024

                texto = (
                    f"Baixando... "
                    f"{mb:.2f} MB/s"
                )

                self.status.configure(
                    text=texto
                )


        elif data["status"] == "finished":

            self.progress.set(1)

            self.status.configure(
                text="Processando arquivo..."
            )


        # -----------------------------------------

    def download_video(self):

        if not self.check_ffmpeg():
            return


        try:

            url = self.url.get().strip()

            formato = self.format_var.get()

            qualidade = self.quality.get()


            if not url:

                messagebox.showwarning(
                    "Aviso",
                    "Nenhuma URL informada."
                )

                return


            if not os.path.exists(
                self.download_folder
            ):

                os.makedirs(
                    self.download_folder
                )


            self.progress.set(0)


            # ==========================
            # DOWNLOAD MP3
            # ==========================

            if formato == "mp3":


                opcoes = {


                    "format":
                    "bestaudio/best",


                    "outtmpl":
                    os.path.join(
                        self.download_folder,
                        "%(title).100B [%(id)s].%(ext)s"
                    ),


                    "noplaylist":
                    True,


                    "progress_hooks":
                    [
                        self.update_progress
                    ],


                    "postprocessors":
                    [

                        {

                            "key":
                            "FFmpegExtractAudio",

                            "preferredcodec":
                            "mp3",

                            "preferredquality":
                            "192"

                        }

                    ],


                    "js_runtimes":
                    {
                        "deno": {}
                    }


                }



            # ==========================
            # DOWNLOAD MP4
            # ==========================

            else:

                if "youtube.com" in url or "youtu.be" in url:

                    if qualidade == "1080p":

                        formato_video = (
                            "bestvideo[height<=1080]+bestaudio/best"
                        )

                    elif qualidade == "720p":

                        formato_video = (
                            "bestvideo[height<=720]+bestaudio/best"
                        )

                    elif qualidade == "480p":

                        formato_video = (
                            "bestvideo[height<=480]+bestaudio/best"
                        )

                    elif qualidade == "360p":

                        formato_video = (
                            "bestvideo[height<=360]+bestaudio/best"
                        )

                    else:

                        formato_video = (
                            "bestvideo+bestaudio/best"
                        )

                else:

                    # TikTok, Facebook, Instagram, Dailymotion...

                    if qualidade == "1080p":

                        formato_video = "bestvideo[height<=1080]+bestaudio/best"

                    elif qualidade == "720p":

                        formato_video = "bestvideo[height<=720]+bestaudio/best"

                    elif qualidade == "480p":

                        formato_video = "bestvideo[height<=480]+bestaudio/best"

                    elif qualidade == "360p":

                        formato_video = "bestvideo[height<=360]+bestaudio/best"

                    else:

                        formato_video = "bestvideo+bestaudio/best"


                opcoes = {

                    "format": formato_video,

                    "merge_output_format": "mp4",

                    "outtmpl": os.path.join(
                        self.download_folder,
                        "%(title).100B [%(id)s].%(ext)s"
                    ),

                    "trim_file_name": 120,

                    "noplaylist": True,

                    "progress_hooks": [
                        self.update_progress
                    ],

                    "js_runtimes": {
                        "deno": {}
                    }

                }
                self.status.configure(
                text="Iniciando download..."
            )


            self.window.update()



            with YoutubeDL(opcoes) as ydl:


                ydl.download(
                    [
                        url
                    ]
                )



            self.save_history(

                self.info.get(
                    "title",
                    "Sem título"
                )

            )



            self.progress.set(1)


            self.status.configure(
                text="Download concluído!"
            )


            messagebox.showinfo(
                "Concluído",
                "Download finalizado com sucesso."
            )



        except Exception as erro:


            self.status.configure(
                text="Erro no download."
            )


            messagebox.showerror(
                "Erro",
                str(erro)
            )

    def check_ffmpeg(self):

        if shutil.which(
            "ffmpeg"
        ):

            return True

        else:

            messagebox.showwarning(
                "FFmpeg",
                "FFmpeg não encontrado. Instale para usar MP4 e MP3."
            )

            return False


    # -----------------------------------------
    # CONFIGURAÇÕES
    # -----------------------------------------

    def load_config(self):

        if os.path.exists(self.config_file):

            try:

                with open(
                    self.config_file,
                    "r",
                    encoding="utf-8"
                ) as arquivo:

                    config = json.load(arquivo)

                    self.download_folder = config.get(
                        "download_folder",
                        self.download_folder
                    )

            except:

                pass
    # -----------------------------------------

    def save_config(self):

        config = {

            "download_folder":
            self.download_folder

        }


        with open(
            self.config_file,
            "w",
            encoding="utf-8"
        ) as arquivo:


            json.dump(
                config,
                arquivo,
                indent=4
            )


    # -----------------------------------------
    # HISTÓRICO
    # -----------------------------------------

    def save_history(self, titulo):

        registro = {

            "titulo":
            titulo,

            "data":
            datetime.datetime.now()
            .strftime(
                "%d/%m/%Y %H:%M"
            ),

            "pasta":
            self.download_folder

        }


        historico = []


        if os.path.exists(
            self.history_file
        ):

            try:

                with open(
                    self.history_file,
                    "r",
                    encoding="utf-8"
                ) as arquivo:

                    historico = json.load(
                        arquivo
                    )

            except:

                historico = []


        historico.append(
            registro
        )


        with open(
            self.history_file,
            "w",
            encoding="utf-8"
        ) as arquivo:

            json.dump(
                historico,
                arquivo,
                indent=4,
                ensure_ascii=False
            )







Downloader()
