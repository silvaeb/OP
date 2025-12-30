# Set environment variables for this session and start the app
# Uso recomendado: desenvolvimento local apenas. Para produção, defina variáveis em um serviço/host seguro,
# mantenha FLASK_DEBUG="false", SECRET_KEY forte, SESSION_COOKIE_SECURE="true" sob HTTPS e sirva via gunicorn/Nginx.
# Update SECRET_KEY to a strong, random value before using

$env:SECRET_KEY = "mude-esta-chave-para-uma-bem-grande-e-aleatoria"
$env:FLASK_DEBUG = "false"
$env:FLASK_HOST = "0.0.0.0"
$env:FLASK_PORT = "8000"
$env:SESSION_COOKIE_SECURE = "false"  # set true only when serving over HTTPS
$env:SESSION_COOKIE_SAMESITE = "Lax"
$env:MAX_CONTENT_MB = "16"

# Activate venv if present
$venvActivate = Join-Path $PSScriptRoot ".venv/Scripts/Activate.ps1"
if (Test-Path $venvActivate) { . $venvActivate }

# Run the app
python app.py
