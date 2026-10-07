#!/bin/bash

# ==========================================================
# YT Downloader Pro
# Gerador DEB Ubuntu/Debian
#
# Autor: Jackson Q.
#
# Compatível:
# Ubuntu 22.04 / 24.04 / Debian
#
# Inclui:
# - yt-dlp embutido
# - FFmpeg
# - Cookies navegador
# - Firefox/Chrome
# ==========================================================


set -e


# ==============================
# CONFIGURAÇÃO
# ==============================

NOME_PACOTE="yt-downloader"

VERSAO="1.8.0"

EXECUTAVEL="yt-downloader"

PASTA_DEB="${NOME_PACOTE}_${VERSAO}"


echo ""
echo "===================================="
echo " YT Downloader Pro - Build DEB"
echo "===================================="
echo ""


# ==============================
# LIMPEZA
# ==============================

echo "🧹 Limpando builds antigos..."

rm -rf build
rm -rf dist
rm -rf "$PASTA_DEB"
rm -f "${PASTA_DEB}.deb"



# ==============================
# VERIFICA VENV
# ==============================

if [ ! -d "venv" ]; then

    echo "❌ ERRO: venv não encontrada"

    exit 1

fi



# ==============================
# DEPENDÊNCIAS PYTHON
# ==============================


echo ""
# ==============================
# INSTALA DEPENDÊNCIAS PYTHON
# ==============================

echo "🐍 Atualizando dependências Python..."

venv/bin/pip install -U \
yt-dlp \
curl_cffi \
bgutil-ytdlp-pot-provider \
customtkinter \
pillow \
requests \
keyring \
secretstorage \
browser-cookie3

# ==============================
# PYINSTALLER
# ==============================


echo ""
echo "⚙️ Gerando executável..."


# Usa o .spec (inclui yt_dlp completo, curl_cffi, ícone etc.)
venv/bin/pip install -U pyinstaller
venv/bin/pyinstaller --clean --noconfirm yt-downloader.spec



if [ ! -f "dist/$EXECUTAVEL" ]; then

    echo "❌ Executável não criado"

    exit 1

fi



# ==============================
# ESTRUTURA DE PACOTE
# ==============================


echo ""
echo "📁 Criando estrutura DEB..."


mkdir -p "$PASTA_DEB/DEBIAN"

mkdir -p "$PASTA_DEB/opt/$EXECUTAVEL"

mkdir -p "$PASTA_DEB/usr/bin"

mkdir -p "$PASTA_DEB/usr/share/applications"

mkdir -p "$PASTA_DEB/usr/share/icons/hicolor/256x256/apps"



# ==============================
# COPIAR EXECUTÁVEL
# ==============================


echo "📦 Copiando programa..."


cp \
dist/$EXECUTAVEL \
"$PASTA_DEB/opt/$EXECUTAVEL/$EXECUTAVEL"



chmod +x \
"$PASTA_DEB/opt/$EXECUTAVEL/$EXECUTAVEL"



# ==============================
# COMANDO GLOBAL
# ==============================


echo "🔧 Criando comando..."


cat > "$PASTA_DEB/usr/bin/$EXECUTAVEL" <<EOF
#!/bin/bash

/opt/$EXECUTAVEL/$EXECUTAVEL

EOF


chmod +x \
"$PASTA_DEB/usr/bin/$EXECUTAVEL"



# ==============================
# ICONE
# ==============================

if [ -f "icone.png" ]; then

    echo "🖼️ Instalando ícone..."

    cp icone.png \
    "$PASTA_DEB/usr/share/icons/hicolor/256x256/apps/${EXECUTAVEL}.png"

else

    echo "⚠️ icone.png não encontrado"

fi



# ==============================
# MENU APLICATIVO
# ==============================


echo "🖥️ Criando atalho..."


cat > "$PASTA_DEB/usr/share/applications/$EXECUTAVEL.desktop" <<EOF
[Desktop Entry]
Name=YT Downloader Pro
Comment=Downloader de vídeos usando yt-dlp
Exec=$EXECUTAVEL
Icon=$EXECUTAVEL
Terminal=false
Type=Application
Categories=Utility;Network;
StartupNotify=true
EOF



# ==============================
# CONTROL
# ==============================


echo "📄 Criando controle DEBIAN..."


cat > "$PASTA_DEB/DEBIAN/control" <<EOF
Package: $NOME_PACOTE
Version: $VERSAO
Architecture: amd64
Maintainer: Jackson Quequi
Depends: ffmpeg, curl, gnome-keyring
Section: utils
Priority: optional
Description: YT Downloader Pro - Downloader gráfico usando yt-dlp com suporte a múltiplas plataformas
EOF



# ==============================
# PÓS INSTALAÇÃO
# ==============================


echo "🔐 Criando pós-instalação..."


cat > "$PASTA_DEB/DEBIAN/postinst" <<'EOF'
#!/bin/bash

set -e


# =====================================
# Instala Deno para yt-dlp (EJS)
# =====================================

if ! command -v deno >/dev/null 2>&1; then

    echo "Instalando Deno..."

    curl -fsSL https://deno.land/install.sh | DENO_INSTALL=/usr/local sh

fi



# =====================================
# Atualiza atalhos do aplicativo
# =====================================

if command -v update-desktop-database >/dev/null 2>&1; then

    update-desktop-database \
    /usr/share/applications \
    >/dev/null 2>&1 || true

fi



# =====================================
# Atualiza cache dos ícones
# =====================================

if command -v gtk-update-icon-cache >/dev/null 2>&1; then

    gtk-update-icon-cache \
    -f -t \
    /usr/share/icons/hicolor \
    >/dev/null 2>&1 || true

fi


exit 0

EOF


chmod 755 "$PASTA_DEB/DEBIAN/postinst"



# ==============================
# GERAR DEB
# ==============================


echo ""
echo "📦 Gerando pacote DEB..."


dpkg-deb --build "$PASTA_DEB"



if [ -f "${PASTA_DEB}.deb" ]; then


echo ""
echo "===================================="
echo "✅ DEB criado com sucesso"
echo ""
echo "${PASTA_DEB}.deb"
echo "===================================="


else


echo "❌ Erro ao criar pacote"

exit 1


fi