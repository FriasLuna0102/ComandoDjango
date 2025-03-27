#!/bin/bash
# Script para clonar con Git LFS, ejecutar el backend de Django y configurar Nginx como proxy inverso

# Función para manejar errores sin cerrar la sesión
error_exit() {
    echo "❌ ERROR: $1"
    # Si el script fue llamado con source, usar return, de lo contrario exit
    if [[ "${BASH_SOURCE[0]}" != "${0}" ]]; then
        return 1
    else
        exit 1
    fi
}

# Verificar si se pasó la clave API_CL como argumento
if [ -z "$1" ]; then
    echo "❌ ERROR: Debes proporcionar la clave API como argumento."
    echo "Uso: ./run_backend.sh \"tu-clave-api\""
    error_exit "Falta argumento"
fi
API_CL="$1"
# Instalar Git LFS
sudo apt-get update
# sudo apt-get install -y git-lfs
# git lfs install
# Clonar repositorio con LFS
# git clone https://github.com/FriasLuna0102/ComandoDjango
cd ComandoDjango
# git lfs pull
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

# Este comando puede requerir que el usuario cierre y vuelva a abrir sesión para tener efecto
echo "ℹ️ Se ha agregado tu usuario al grupo docker. Es posible que necesites cerrar sesión y volver a iniciarla para que los cambios surtan efecto."
echo "ℹ️ Por ahora, seguiremos usando sudo para ejecutar los comandos docker."



# ========================================================
# 🔹 ACTUALIZAR EL VALOR DE API_CL EN EL ARCHIVO DE ENTORNO
# ========================================================
# Comprobar si el archivo .envs/.local/.django existe
if [ -f .envs/.local/.django ]; then
    # Actualizar el valor de API_CL en el archivo
    sed -i "s|^API_CL=.*|API_CL=$API_CL|" .envs/.local/.django
    echo "✅ Actualizado API_CL en .envs/.local/.django"
else
    echo "❌ No se encontró el archivo .envs/.local/.django"
    error_exit "Archivo de entorno no encontrado"
fi

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

# Mostrar el valor configurado para verificación
echo "🔍 API_CL configurado como: $API_CL"
echo "✅ Puedes verificar dentro del contenedor con: docker exec -it backend_django_local_django cat .envs/.local/.django"

