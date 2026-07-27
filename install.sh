#!/bin/bash

echo "=============================================="
echo "      YT Downloader Pro - Instalador"
echo "=============================================="

# Vai para a pasta onde está este script
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR" || exit 1

echo "Pasta do projeto:"
echo "$DIR"
echo

# Verifica Python
if ! command -v python3 >/dev/null 2>&1; then
    echo "ERRO: Python 3 não encontrado."
    exit 1
fi

echo "Criando ambiente virtual..."

if [ ! -d "venv" ]; then
    python3 -m venv venv
else
    echo "Ambiente virtual já existe."
fi

echo
echo "Atualizando pip..."

venv/bin/python -m pip install --upgrade pip setuptools wheel

echo
echo "Instalando dependências..."

venv/bin/python -m pip install -r requirements.txt

echo
echo "Atualizando yt-dlp..."

venv/bin/python -m pip install --upgrade yt-dlp curl_cffi

echo
echo "Criando pastas..."

mkdir -p downloads
mkdir -p cache
mkdir -p logs

chmod +x run.sh
chmod +x yt_downloader.py

echo
echo "=============================================="
echo "Instalação concluída com sucesso!"
echo "=============================================="
echo
echo "Para executar:"
echo
echo "    ./run.sh"
echo
