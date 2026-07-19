#!/bin/bash

echo "Iniciando YT Downloader Pro..."

DIR="/opt/yt-downloader"

cd "$DIR" || exit 1


if [ ! -d "venv" ]; then

    echo "Criando ambiente virtual..."

    python3 -m venv venv

    venv/bin/pip install --upgrade pip

    venv/bin/pip install -r requirements.txt

    venv/bin/pip install --upgrade yt-dlp curl_cffi

fi


venv/bin/python yt_downloader.py