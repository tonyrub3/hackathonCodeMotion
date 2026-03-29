# Truth Engine – Quick Start

## Requisiti

- Python 3.11+
- Node.js 18+
- npm

## 1. Installazione

```bash
cd /Users/antonio/Desktop/hackathonCodeMotion
python3 -m venv .venv
source .venv/bin/activate
pip install -r apps/backend/requirements.txt
cd apps/frontend && npm install && cd ../..
cp .env.example .env
```

## 2. Configurazione `.env`

Variabili minime:

```env
REGOLO_API_KEY=your_regolo_key
REGOLO_BASE_URL=https://api.regolo.ai/v1
REGOLO_MODEL=Llama-3.3-70B-Instruct
REGOLO_QUERY_MODEL=Llama-3.3-70B-Instruct
REGOLO_CLAIM_MODEL=Llama-3.3-70B-Instruct
REGOLO_CROSSCHECK_MODEL=gpt-oss-120b
REGOLO_SCORING_MODEL=gpt-oss-120b
TAVILY_API_KEY=your_tavily_key
TE_TIMEOUT=0
```

`TE_TIMEOUT=0` significa nessun timeout lato client.

## 3. Avvio del progetto

Backend:

```bash
source .venv/bin/activate
cd apps/backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Frontend:

```bash
cd apps/frontend
npm run dev
```

Indirizzi utili:
- API: `http://localhost:8000`
- Docs: `http://localhost:8000/docs`
- Frontend: `http://localhost:3000`

## 4. Test rapido delle API

```bash
curl http://localhost:8000/api/health
```

```bash
curl -X POST http://localhost:8000/api/verify \
  -H "Content-Type: application/json" \
  -d '{
    "input_type": "text",
    "content": "donald trump è stato ucciso l'\"'\"'anno scorso",
    "language": "it"
  }'
```

```bash
curl -X POST http://localhost:8000/api/verify \
  -H "Content-Type: application/json" \
  -d '{
    "input_type": "url",
    "content": "https://example.com/article",
    "language": "it"
  }'
```

## 5. Test del backend

```bash
source .venv/bin/activate
./.venv/bin/pytest apps/backend/app/tests -q
```

## 6. Documentazione utile

- [README.md](README.md)
- [docs/system_architecture_overview.md](docs/system_architecture_overview.md)
