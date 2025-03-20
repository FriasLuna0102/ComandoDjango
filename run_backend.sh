#!/bin/bash
# Script para clonar con Git LFS, ejecutar el backend de Django y configurar Nginx como proxy inverso

# Instalar Git LFS
sudo apt-get update
sudo apt-get install -y git-lfs
git lfs install

# Clonar repositorio con LFS
git clone https://github.com/RandaeGS/proyecto_tesis
cd proyecto_tesis
git lfs pull

# Instalar Docker
sudo apt-get update
sudo apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
$(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}") stable" | \
sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Navegar al directorio del backend
cd backend_django

# Agregar usuario al grupo docker
sudo usermod -aG docker $USER

# Detener contenedores existentes
sudo docker compose -f docker-compose.local.yml down

# Construir y levantar los contenedores
sudo docker compose -f docker-compose.local.yml build
sudo docker compose -f docker-compose.local.yml up -d

# Esperar a que los servicios estén listos
sleep 10

# Instalar dependencias de OpenCV en el contenedor
sudo docker compose -f docker-compose.local.yml exec -T django apt-get update
sudo docker compose -f docker-compose.local.yml exec -T django apt-get install -y libgl1-mesa-glx libglib2.0-0 libsm6 libxext6 libxrender-dev

# Ejecutar migraciones y recolectar estáticos
sudo docker compose -f docker-compose.local.yml exec -T django python manage.py migrate
sudo docker compose -f docker-compose.local.yml exec -T django python manage.py collectstatic --noinput

# ========================================================
# 🔹 CONFIGURACIÓN DE NGINX COMO PROXY INVERSO
# ========================================================

# Instalar Nginx si no está instalado
sudo apt-get install -y nginx

# Crear configuración de Nginx para Django
NGINX_CONF="/etc/nginx/sites-available/django_proxy"

echo "server {
    listen 80;
    server_name appdjango.friaslunaa.ninja;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    }
}" | sudo tee $NGINX_CONF > /dev/null

# Enlazar la configuración y reiniciar Nginx
sudo ln -sf /etc/nginx/sites-available/django_proxy /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl restart nginx

echo "✅ Nginx configurado correctamente. Ahora puedes acceder a tu aplicación en http://appdjango.friaslunaa.ninja sin necesidad del puerto 8000."

