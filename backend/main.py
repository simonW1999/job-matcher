import os
import hashlib
import json
import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Job Matcher API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

EXCLUDE = ["senior", "10 años", "8 años", "gerente", "director", "jefe", "lead"]

# ─── Modelos ────────────────────────────────────────────────────────────────

class CVRequest(BaseModel):
    cv_text: str
    area: str = ""
    mode: str = ""

# ─── Scrapers (reutilizados de tu bot) ──────────────────────────────────────

def is_relevant(title, keywords, description=""):
    text = (title + " " + description).lower()
    if any(ex.lower() in text for ex in EXCLUDE):
        return False
    return any(kw.lower() in text for kw in keywords)

def scrape_computrabajo(keywords: list[str]) -> list[dict]:
    jobs = []
    searches = ["sociologo", "analista-de-datos", "investigacion-de-mercado",
                "ux-researcher", "derechos-humanos", "community-manager",
                "marketing-digital", "ciencias-sociales"]
    for term in searches:
        url = f"https://ar.computrabajo.com/trabajo-de-{term}"
        try:
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
            soup = BeautifulSoup(r.text, "html.parser")
            for card in soup.select("article.box_offer")[:10]:
                title_el = card.select_one("h2 a")
                company_el = card.select_one("[class*='company']")
                if title_el and is_relevant(title_el.text.strip(), keywords):
                    jobs.append({
                        "title": title_el.text.strip(),
                        "company": company_el.text.strip() if company_el else "N/A",
                        "url": "https://ar.computrabajo.com" + title_el.get("href", ""),
                        "source": "Computrabajo",
                        "location": "Argentina",
                        "mode": "No especificado"
                    })
        except Exception as e:
            print(f"Computrabajo error ({term}): {e}")
    return jobs

def scrape_indeed(keywords: list[str]) -> list[dict]:
    jobs = []
    searches = ["sociologo", "analista+de+datos+junior", "investigacion+de+mercado",
                "ux+researcher", "derechos+humanos", "community+manager",
                "ciencias+sociales"]
    for term in searches:
        url = f"https://ar.indeed.com/jobs?q={term}&l=Argentina"
        try:
            r = requests.get(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }, timeout=10)
            soup = BeautifulSoup(r.text, "html.parser")
            for card in soup.select("[class*='job_seen_beacon'], [class*='tapItem']")[:10]:
                title_el = card.select_one("h2 span, [class*='jobTitle'] span")
                company_el = card.select_one("[class*='companyName'], [data-testid='company-name']")
                link_el = card.select_one("h2 a, [class*='jobTitle'] a")
                if title_el and link_el and is_relevant(title_el.text.strip(), keywords):
                    jobs.append({
                        "title": title_el.text.strip(),
                        "company": company_el.text.strip() if company_el else "N/A",
                        "url": "https://ar.indeed.com" + link_el.get("href", ""),
                        "source": "Indeed",
                        "location": "Argentina",
                        "mode": "No especificado"
                    })
        except Exception as e:
            print(f"Indeed error ({term}): {e}")
    return jobs

def scrape_trabajando(keywords: list[str]) -> list[dict]:
    jobs = []
    searches = ["sociologo", "analista-datos", "investigacion-mercado",
                "community-manager", "marketing", "derechos-humanos"]
    for term in searches:
        url = f"https://www.trabajando.com.ar/trabajo/{term}"
        try:
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
            soup = BeautifulSoup(r.text, "html.parser")
            for card in soup.select("[class*='offer'], [class*='job-card'], article")[:10]:
                title_el = card.select_one("h2, h3, [class*='title']")
                company_el = card.select_one("[class*='company'], [class*='empresa']")
                link_el = card.select_one("a")
                if title_el and link_el and is_relevant(title_el.text.strip(), keywords):
                    href = link_el.get("href", "")
                    jobs.append({
                        "title": title_el.text.strip(),
                        "company": company_el.text.strip() if company_el else "N/A",
                        "url": href if href.startswith("http") else "https://www.trabajando.com.ar" + href,
                        "source": "Trabajando.com",
                        "location": "Argentina",
                        "mode": "No especificado"
                    })
        except Exception as e:
            print(f"Trabajando error ({term}): {e}")
    return jobs

def deduplicate(jobs: list[dict]) -> list[dict]:
    seen = set()
    unique = []
    for job in jobs:
        jid = hashlib.md5(f"{job['title']}{job['company']}".encode()).hexdigest()
        if jid not in seen:
            seen.add(jid)
            unique.append(job)
    return unique

# ─── Groq: análisis de CV ────────────────────────────────────────────────────

def analyze_cv_with_groq(cv_text: str) -> dict:
    prompt = f"""Analizá el siguiente CV y devolvé SOLO un objeto JSON (sin markdown, sin explicaciones) con esta estructura exacta:
{{
  "profile_tags": ["tag1", "tag2", ...],
  "keywords": ["palabra1", "palabra2", ...],
  "summary": "Una oración describiendo el perfil profesional"
}}

- profile_tags: máximo 8 etiquetas cortas que describan habilidades, formación y áreas del perfil
- keywords: 10-15 palabras clave en español e inglés para buscar empleos relevantes para este perfil
- summary: resumen en una oración del perfil

CV:
{cv_text[:3000]}"""

    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=600
    )
    raw = response.choices[0].message.content.strip()
    # limpiar posibles backticks
    raw = raw.replace("```json", "").replace("```", "").strip()
    return json.loads(raw)

# ─── Groq: ranking de empleos ────────────────────────────────────────────────

def rank_jobs_with_groq(cv_text: str, profile: dict, jobs: list[dict]) -> list[dict]:
    if not jobs:
        return []

    jobs_text = "\n".join([
        f"{i+1}. {j['title']} en {j['company']} ({j['source']})"
        for i, j in enumerate(jobs[:30])
    ])

    prompt = f"""Tenés este perfil profesional:
Resumen: {profile.get('summary', '')}
Tags: {', '.join(profile.get('profile_tags', []))}

Y estas ofertas de empleo:
{jobs_text}

Devolvé SOLO un JSON (sin markdown) con esta estructura:
{{
  "rankings": [
    {{
      "index": 1,
      "score": 85,
      "reason": "Explicación corta de por qué este puesto es un buen match (2-3 oraciones en español)"
    }},
    ...
  ]
}}

- index: número de la oferta (1-based)
- score: de 0 a 100, qué tan bien encaja con el perfil
- reason: explicación honesta del match, mencionando fortalezas y brechas si las hay
- Incluí solo las ofertas con score >= 40
- Ordená de mayor a menor score"""

    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=2000
    )
    raw = response.choices[0].message.content.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()
    rankings = json.loads(raw).get("rankings", [])

    ranked_jobs = []
    for r in rankings:
        idx = r["index"] - 1
        if 0 <= idx < len(jobs):
            job = jobs[idx].copy()
            job["score"] = r["score"]
            job["reason"] = r["reason"]
            ranked_jobs.append(job)

    ranked_jobs.sort(key=lambda x: x["score"], reverse=True)
    return ranked_jobs

# ─── Endpoints ───────────────────────────────────────────────────────────────

@app.post("/analyze")
async def analyze(req: CVRequest):
    if len(req.cv_text.strip()) < 50:
        raise HTTPException(status_code=400, detail="El CV es demasiado corto.")

    # 1. Analizar CV con Groq
    try:
        profile = analyze_cv_with_groq(req.cv_text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error analizando CV: {str(e)}")

    keywords = profile.get("keywords", [])

    # 2. Scrapear empleos
    all_jobs = []
    all_jobs += scrape_computrabajo(keywords)
    all_jobs += scrape_indeed(keywords)
    all_jobs += scrape_trabajando(keywords)
    all_jobs = deduplicate(all_jobs)

    if not all_jobs:
        return {
            "profile": profile,
            "jobs": [],
            "message": "No se encontraron ofertas en este momento. Intentá de nuevo en unos minutos."
        }

    # 3. Rankear con Groq
    try:
        ranked = rank_jobs_with_groq(req.cv_text, profile, all_jobs)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error rankeando resultados: {str(e)}")

    return {
        "profile": profile,
        "jobs": ranked
    }

@app.get("/health")
def health():
    return {"status": "ok"}
