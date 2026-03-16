# Job Matcher

Encontrá los empleos que realmente te encajan — análisis de CV con IA + scraping de Computrabajo, Indeed y Trabajando.com.

---

## Requisitos

- Python 3.10 o superior
- Cuenta en [Groq](https://console.groq.com) (gratis, sin tarjeta)

---

## Setup paso a paso

### 1. Conseguí tu API key de Groq

1. Entrá a https://console.groq.com
2. Creá una cuenta gratuita
3. Menú izquierdo → **API Keys** → **Create API Key**
4. Copiá la key

### 2. Configurá el archivo .env

Abrí el archivo `backend/.env` y reemplazá el placeholder:

```
GROQ_API_KEY=tu_api_key_acá
```

### 3. Instalá las dependencias

Abrí una terminal en la carpeta `backend/` y ejecutá:

```bash
pip install -r requirements.txt
```

### 4. Corré el backend

Desde la carpeta `backend/`:

```bash
uvicorn main:app --reload
```

Deberías ver:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
```

### 5. Abrí el frontend

Abrí el archivo `frontend/index.html` directamente en tu navegador (doble click).

---

## Uso

1. Pegá el texto de tu CV en el campo de texto
2. Seleccioná filtros opcionales (área, modalidad)
3. Hacé click en **Analizar mi perfil y buscar matches**
4. Esperá ~30-60 segundos mientras scrapeamos y analizamos
5. Revisá los resultados rankeados por compatibilidad

---

## Estructura del proyecto

```
job-matcher/
├── backend/
│   ├── main.py          # FastAPI + scrapers + integración Groq
│   ├── requirements.txt
│   └── .env             # Tu API key de Groq (no subir a GitHub)
└── frontend/
    └── index.html       # Interfaz web completa
```

---

## Notas

- El scraping puede tardar 20-60 segundos dependiendo de la velocidad de los sitios
- Indeed y Computrabajo a veces bloquean requests; si no aparecen resultados de una fuente, es normal
- El tier gratuito de Groq tiene límite de ~14.400 tokens/minuto — más que suficiente para uso personal
