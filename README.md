# Truth Engine

Truth Engine e un sistema di fact-checking spiegabile per testo e URL di articoli. Combina retrieval web reale, query planning con LLM, claim decomposition, cross-checking e scoring guidato dalle fonti per produrre un verdetto finale con evidenze, fonti, tempi e trace di pipeline.

Flusso principale:
`input -> normalizzazione -> claim/query planning -> retrieval Tavily -> source scoring -> cross-check LLM -> scoring dall'explanation -> response`

Funzionalita chiave:
- supporta statement brevi e URL lunghi
- ricerca web contestualizzata con filtri temporali
- explanation finale in italiano
- evidenze, contraddizioni e analisi delle fonti visibili
- backend FastAPI modulare + frontend Next.js

Il progetto e pensato per demo rapide e trasparenti di fact-checking: il retrieval e osservabile, i ruoli dei modelli sono separati e ogni risultato e accompagnato da reasoning strutturato.

Documentazione utile:
- [QUICKSTART.md](QUICKSTART.md)
- [docs/system_architecture_overview.md](docs/system_architecture_overview.md)
