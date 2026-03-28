# Truth Engine – Quick Start

## Prerequisites

- Python 3.11+
- Node.js 18+
- npm

---

## 1. Setup

```bash
# Clone and enter the project
cd /home/nicola/Documents/truthengine/hackathonCodeMotion

# Create virtual environment and install Python dependencies
python3 -m venv .venv
source .venv/bin/activate
cd apps/backend
pip install -r requirements.txt
cd ../..

# Install frontend dependencies
cd apps/frontend
npm install
cd ../..

# Create .env from template
cp .env.example .env
# Edit .env and add your API keys
```

---

## 2. Configure API Keys

Edit `.env` in the project root:

```env
REGOLO_API_KEY=your_regolo_key_here
REGOLO_MODEL=meta-llama/Meta-Llama-3.1-70B-Instruct
REGOLO_EMBEDDING_API_KEY=your_embedding_key_here
REGOLO_EMBEDDING_MODEL=Qwen/Qwen3-Embedding-8B
GOOGLE_FACTCHECK_API_KEY=your_google_key_here   # optional
```

---

## 3. Run

### Backend (Terminal 1)

```bash
cd /home/nicola/Documents/truthengine/hackathonCodeMotion/apps/backend
source ../../.venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Backend runs at: **http://localhost:8000**
API docs at: **http://localhost:8000/docs**

### Frontend (Terminal 2)

```bash
cd /home/nicola/Documents/truthengine/hackathonCodeMotion/apps/frontend
npm run dev
```

Frontend runs at: **http://localhost:3000**

---

## 4. Test via Frontend

1. Open **http://localhost:3000**
2. Select **Text** or **URL** mode
3. Enter content to verify
4. Click **Verify**

### Demo mode (no backend needed)

Check **"Use mock data (demo)"** to see the full UI with sample data.

---

## 5. Test via API (curl)

### Health check

```bash
curl http://localhost:8000/api/health
```

### Verify text (Italian)

```bash
curl -X POST http://localhost:8000/api/verify \
  -H "Content-Type: application/json" \
  -d '{
    "input_type": "text",
    "content": "Il tasso di inflazione in Italia ha raggiunto il 2% nel febbraio 2026, secondo le stime ISTAT.",
    "language": "it",
    "country": "IT",
    "topic": "economy"
  }'
```

### Verify text (English)

```bash
curl -X POST http://localhost:8000/api/verify \
  -H "Content-Type: application/json" \
  -d '{
    "input_type": "text",
    "content": "The European Central Bank raised interest rates three times in 2025, causing a 15% drop in retail sales across Southern Europe.",
    "language": "en",
    "topic": "economy"
  }'
```

### Verify URL

```bash
curl -X POST http://localhost:8000/api/verify \
  -H "Content-Type: application/json" \
  -d '{
    "input_type": "url",
    "content": "https://www.ansa.it/sito/notizie/economia/2026/03/28/example.html",
    "language": "it",
    "country": "IT"
  }'
```

### Verify with topic hint

```bash
curl -X POST http://localhost:8000/api/verify \
  -H "Content-Type: application/json" \
  -d '{
    "input_type": "text",
    "content": "NATO announced a new defense spending target of 3.5% of GDP for all member states.",
    "language": "en",
    "topic": "defense"
  }'
```

### Verify a causal claim

```bash
curl -X POST http://localhost:8000/api/verify \
  -H "Content-Type: application/json" \
  -d '{
    "input_type": "text",
    "content": "Consumer spending declined sharply because the ECB raised interest rates. This caused unemployment to rise to 8% in Spain.",
    "language": "en",
    "topic": "economy"
  }'
```

### Verify a multi-claim article

```bash
curl -X POST http://localhost:8000/api/verify \
  -H "Content-Type: application/json" \
  -d '{
    "input_type": "text",
    "content": "The Italian government approved a new budget of 40 billion euros for 2026. The Ministry of Finance confirmed the allocation includes 5 billion for defense and 8 billion for healthcare. According to ISTAT, GDP growth is expected to reach 1.2% this year. Critics argue the budget does not adequately address the housing crisis.",
    "language": "en",
    "country": "IT",
    "topic": "economy"
  }'
```

---

## 6. Run Tests

```bash
cd /home/nicola/Documents/truthengine/hackathonCodeMotion/apps/backend
source ../../.venv/bin/activate
python -m pytest app/tests/ -v
```

---

## 7. Pretty-print API response

```bash
curl -s -X POST http://localhost:8000/api/verify \
  -H "Content-Type: application/json" \
  -d '{"input_type": "text", "content": "The pope died yesterday."}' \
  | python3 -m json.tool
```

---

## 8. Run local verify script (no server needed)

```bash
cd /home/nicola/Documents/truthengine/hackathonCodeMotion/apps/backend
source ../../.venv/bin/activate
python scripts/run_local_verify.py
```
