#!/bin/bash

echo "=============================================="
echo "        Iniciando YT Downloader Pro"
echo "=============================================="

# Pasta onde está este script
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR" || exit 1

# Verifica Python
if ! command -v python3 >/dev/null 2>&1; then
    echo "ERRO: Python 3 não encontrado."
    exit 1
fi

# Cria a venv caso não exista
if [ ! -d "venv" ]; then

    echo "Ambiente virtual não encontrado."
    echo "Criando ambiente virtual..."

    python3 -m venv venv

    venv/bin/python -m pip install --upgrade pip setuptools wheel

    venv/bin/python -m pip install -r requirements.txt

    venv/bin/python -m pip install --upgrade yt-dlp curl_cffi

fi

echo "Iniciando programa..."

exec venv/bin/python yt_downloader.py
