#!/bin/bash

echo "=============================================="
echo "      YT Downloader Pro - Instalador"
echo "=============================================="


DIR="/opt/yt-downloader"

cd "$DIR" || exit 1


echo "Criando ambiente virtual..."

if [ ! -d "venv" ]; then

    python3 -m venv venv

else

    echo "venv já existe."

fi


echo "Atualizando pip..."

venv/bin/python -m pip install --upgrade pip setuptools wheel


echo "Instalando bibliotecas..."

venv/bin/pip install -r requirements.txt


echo "Atualizando yt-dlp..."

venv/bin/pip install --upgrade yt-dlp curl_cffi


echo "Criando pastas..."

mkdir -p downloads
mkdir -p cache
mkdir -p logs


chmod +x run.sh


echo "=============================================="
echo "Instalação concluída!"
echo "=============================================="