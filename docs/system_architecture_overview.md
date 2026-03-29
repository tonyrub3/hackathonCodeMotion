# Truth Engine: System Architecture Overview

## Executive Summary

Truth Engine e un sistema di fact-checking retrieval-first progettato per verificare sia statement brevi sia contenuti estratti da URL/articoli.

L'architettura combina:
- orchestrazione deterministica e osservabile
- retrieval web reale tramite Tavily
- uso di LLM specializzati per query planning, claim decomposition, cross-check e scoring
- output spiegabili con fonti, evidenze, reasoning e trace di pipeline

Il sistema e pensato per massimizzare tre obiettivi:
1. recuperare evidenza web rilevante e aggiornata
2. produrre un giudizio leggibile e coerente con le fonti trovate
3. mantenere auditability tramite stato condiviso, logging per layer e response ricca

Attualmente il backend e adatto a una demo avanzata di fact-checking assistito da LLM con retrieval web reale, supporto URL, query generation intelligente e scoring basato sull'explanation.

---

## Obiettivo Del Sistema

Il sistema prende in input:
- testo breve
- URL di articolo o pagina web

E produce in output:
- verdict finale
- truth score
- confidence score
- explanation in italiano
- fonti usate
- evidenze e contraddizioni
- query generate
- risultati Tavily grezzi
- metadata di processo e timing

In altre parole, non e solo un classificatore finale: e una pipeline di analisi multi-step, orientata alla spiegabilita.

---

## High-Level Architecture

```text
Client / Frontend
    -> POST /api/verify
    -> Orchestrator
        -> InputNormalizerAgent
        -> ClaimDecompositionAgent (URL only)
        -> TavilyFirstEngine
            -> QueryPlanningAgent
            -> TavilySearchProfileBuilder
            -> Tavily Search Cascade
            -> Tavily Extract
            -> SourceScoringLayer
            -> CrossCheckAnalysisLayer
            -> ExplanationScoringLayer
            -> Guardrails + Final State Assembly
    -> VerifyResponse
```

---

## Entry Points

### Backend API

- `apps/backend/app/main.py`
  - crea l'app FastAPI
  - carica il `.env`
  - inizializza settings, logging e router

- `apps/backend/app/api/routes_verify.py`
  - espone `POST /api/verify`
  - esegue l'orchestrazione completa
  - converte `PipelineState` in `VerifyResponse`

### Core Orchestration

- `apps/backend/app/core/orchestrator.py`
  - crea lo stato iniziale
  - esegue gli step in ordine
  - logga step, timing, verdict e outcome finale

---

## Shared State: `PipelineState`

Il sistema usa un contenitore unico di stato che attraversa tutta la pipeline.

File:
- `apps/backend/app/core/state.py`

Contiene, tra le altre cose:
- input originale
- testo normalizzato
- metadata articolo
- claim estratti
- query generate
- risultati Tavily completi
- answer hints Tavily
- search profile usato
- fonti usate nel giudizio
- evidenze e contraddizioni
- explanation finale
- truth score / confidence / verdict
- timing e errori
- consensus signals e judgment basis

Questo design rende il sistema lineare, osservabile e facile da debuggare.

---

## Workflow Ad Alto Livello

### 1. Input Normalization

Responsabile:
- `apps/backend/app/agents/input_normalizer_agent.py`

Funzione:
- se input = testo: pulizia, normalizzazione, language detection
- se input = URL: fetch pagina, estrazione corpo, titolo, autore, data, metadata, link citati

Output principali:
- `normalized_text`
- `article_title`
- `article_author`
- `article_date`
- `source_url`
- `cited_links`
- `language`

Valore architetturale:
- unifica il downstream: tutto il resto lavora su testo strutturato, non su input grezzo

---

### 2. Claim Decomposition (solo URL)

Responsabile:
- `apps/backend/app/agents/claim_decomposition_agent.py`

Funzione:
- usa un LLM per estrarre claim verificabili da articoli lunghi
- genera anche una `search_query` seed per ogni claim
- risolve meglio il contenuto denso degli URL rispetto a una verifica whole-text pura

Caratteristiche chiave:
- claim atomici e auto-consistenti
- uso del contesto articolo
- fallback euristico se l'LLM fallisce
- grounding temporale tramite current date / article date

Valore architetturale:
- rende il retrieval piu mirato sugli URL
- evita che tutto il contenuto venga compresso in una singola query generica

---

### 3. Query Planning

Responsabile:
- `apps/backend/app/agents/query_planning_agent.py`

Funzione:
- traduce testo o claim in query Tavily ad alta resa
- usa contesto, metadata e date relative
- se l'input contiene espressioni come `l'anno scorso`, usa la data corrente per risolverle

Caratteristiche chiave:
- query claim-aware quando disponibili i claim
- current date grounding
- fallback deterministico in caso di failure
- supporto modelli dedicati via env

Valore architetturale:
- migliora recall e precisione del retrieval
- riduce query sbagliate o temporalmente allucinate

---

### 4. Search Profile Building

Responsabile:
- `apps/backend/app/services/retrieval/search_profile.py`

Funzione:
- decide i parametri di ricerca Tavily in base al contesto

Dimensioni principali:
- `topic`: `general`, `news`, `finance`
- `country`: usato quando ha senso su ricerche generaliste
- `temporal`: `time_range`, `start_date`, `end_date`

Valore architetturale:
- non tutte le query vengono trattate allo stesso modo
- il retrieval diventa contestuale, non uniforme

---

### 5. Tavily Retrieval

Responsabile:
- `apps/backend/app/pipeline/tavily_first.py`
- connector: `apps/backend/app/connectors/tavily_search.py`

Strategia:
- cascade search
- tier 1 su domini piu forti o whitelistati
- tier 2 piu ampio se necessario
- ricerca in parallelo su query multiple
- uso di `auto_parameters`, `include_answer`, `include_raw_content`, filtri topic/temporal

Valore architetturale:
- retrieval web reale e non simulato
- buona combinazione tra precisione iniziale e recall progressivo
- risposta ricca con `all_tavily_results` e `answer_hints`

---

### 6. Content Enrichment

Responsabile:
- `apps/backend/app/connectors/tavily_extract.py`

Funzione:
- arricchisce i risultati con contenuto testuale piu utile quando le pagine recuperate sono povere

Valore architetturale:
- riduce i casi in cui il judge LLM deve lavorare su snippet troppo corti o rumorosi

---

### 7. Source Pre-Scoring

Responsabile:
- `apps/backend/app/services/scoring/source_scoring.py`

Funzione:
- calcola un pre-ranking delle fonti prima del cross-check

Segnali principali:
- `domain_trust`
- `content_trust`
- `local_relevance`
- `source_reliability`

Valore architetturale:
- separa il problema della qualita della fonte dal giudizio finale
- migliora l'ordine con cui le fonti arrivano al layer di analisi

Nota:
- non e il decisore finale del verdict
- serve a preparare meglio il materiale per il judge

---

### 8. Cross-Check Analysis Layer

Responsabile:
- `apps/backend/app/services/analysis/crosscheck.py`

Funzione:
- esegue il fact-check vero e proprio sul testo rispetto alle fonti trovate
- produce un output strutturato con:
  - `judgment_basis`
  - `truth_score`
  - `confidence_score`
  - `verdict`
  - `explanation`
  - `per_source`

Caratteristiche chiave:
- prompt piu rigoroso e piu grounded sulle fonti
- explanation in italiano
- distinzione tra fonti supporting, contradicting, neutral
- richiesta esplicita di basarsi su evidenze reali, non su testo generico
- modelli dedicati piu forti per il cross-check

Valore architetturale:
- e il cuore semantico del sistema
- legge il contenuto, interpreta i claim, valuta la pertinenza delle fonti

---

### 9. Explanation Scoring Layer

Responsabile:
- `apps/backend/app/services/analysis/explanation_scoring.py`

Funzione:
- usa un secondo LLM per trasformare l'explanation strutturata in:
  - `truth_score`
  - `confidence_score`
  - `verdict`

Perche e utile:
- forza coerenza tra cio che il sistema racconta e il punteggio finale
- evita che un punteggio numerico alto passi indisturbato se l'explanation dice il contrario
- riduce la dipendenza da euristiche troppo fragili a keyword

Valore architetturale:
- crea una doppia lettura LLM:
  - un LLM giudica le fonti
  - un LLM valuta la coerenza e la forza dell'explanation

---

### 10. Guardrails E State Assembly

Responsabile:
- `apps/backend/app/pipeline/tavily_first.py`

Funzione:
- applica gli ultimi controlli deterministici di sicurezza
- costruisce `sources_used`, `scored_evidence`, `contradictions`
- conserva trace e explanation finale per il lettore

Guardrail principali:
- niente verdict positivi se manca supporto minimo coerente
- cap di confidence su tier deboli
- downgrade se explanation e segnali non sono coerenti

Valore architetturale:
- il sistema non e completamente lasciato alla generazione libera del modello
- esiste un ultimo livello di controllo operativo

---

## Key Functionalities

### 1. Supporto a testo e URL
Il sistema non si limita a statement brevi: puo analizzare articoli interi, estrarne claim e usare contesto, titolo, data e autore.

### 2. Retrieval web reale
Tavily fornisce un motore di recall concreto, con risultati raw esposti e query osservabili.

### 3. Query generation intelligente
Il planner non si limita a fare keyword extraction. Usa un LLM e grounding temporale per creare query migliori.

### 4. Pipeline explainable
La response contiene fonti, evidenze, contradiction items, query, search profile, timings e trace.

### 5. Scoring LLM-assisted
Lo score finale non e solo un output numerico isolato: oggi viene riletto e calibrato sull'explanation tramite un LLM dedicato.

### 6. Prompt specialization
Diversi task usano modelli e prompt diversi:
- query generation
- claim decomposition
- cross-check
- explanation scoring

### 7. Configurabilita dei modelli
I modelli Regolo possono essere separati per ruolo tramite variabili ambiente.

---

## Current Model Strategy

Configurazione attuale consigliata:
- `REGOLO_QUERY_MODEL=Llama-3.3-70B-Instruct`
- `REGOLO_CLAIM_MODEL=Llama-3.3-70B-Instruct`
- `REGOLO_CROSSCHECK_MODEL=gpt-oss-120b`
- `REGOLO_SCORING_MODEL=gpt-oss-120b`

Razionale:
- query e claim extraction beneficiano di un modello forte ma veloce
- cross-check e scoring richiedono piu profondita semantica e migliore affidabilita

---

## System Evaluation

### Punti Forti

1. Architettura chiara e modulare
- ogni step ha una responsabilita precisa
- il sistema resta leggibile e debuggabile

2. Ottima osservabilita
- logging per layer
- timings completi
- risultati Tavily completi disponibili
- response ricca di segnali

3. Buon compromesso tra controllo e intelligenza
- retrieval e pipeline sono orchestrati deterministicamente
- i task semantici sono delegati agli LLM

4. Supporto URL sopra la media per un MVP
- non verifica solo testo breve
- lavora anche su contenuti lunghi con decomposition e contesto

5. Maggiore coerenza tra reasoning e score
- l'introduzione del layer di explanation scoring migliora la coerenza percepita del sistema

### Limiti Attuali

1. Non e ancora pienamente claim-by-claim nel verdict finale
- i claim esistono e aiutano il retrieval
- ma il giudizio finale resta soprattutto documento-level / whole-text

2. La qualita dipende ancora molto dal retrieval
- se Tavily recupera fonti parzialmente pertinenti, il judge deve lavorare in condizioni peggiori

3. Le fonti irrilevanti possono ancora introdurre rumore
- soprattutto in query rumorose o su fatti ambigui

4. Il sistema non e ancora un forensic analyzer completo delle fonti
- il pre-scoring e utile, ma non e ancora una vera source forensics pipeline profonda

### Valutazione Complessiva

Nel suo stato attuale, Truth Engine e un sistema forte per:
- demo di fact-checking AI-assisted
- analisi explainable di claim web-based
- retrieval + reasoning su testo e URL
- pipeline backend osservabile e modulare

Per un MVP o hackathon avanzato, il sistema e convincente perche:
- mostra retrieval vero
- usa LLM in modo mirato e non banale
- espone trace, fonti ed evidenze
- ha una architettura che puo evolvere senza essere riscritta da zero

---

## Mini Roadmap

### Fase 1: Hardening Immediato
- aggiungere nel frontend la visualizzazione della `judgment_basis`
- mostrare quale modello e stato usato per query / cross-check / scoring
- aggiungere log espliciti sui downgrade di confidence e verdict

### Fase 2: Claim-Centric Upgrade
- collegare ogni evidenza ai claim specifici
- passare da verdict documento-level a claim-level aggregation reale
- distinguere meglio supporto diretto, indiretto e irrilevante

### Fase 3: Source Intelligence
- introdurre SourceForensicsAgent
- valutare ownership, canonical origin, citation quality, site behavior
- modellare meglio l'independence tra fonti

### Fase 4: Calibration & Evaluation
- raccogliere casi reali e sintetici
- calibrare soglie di verdict e confidence
- misurare false-positive high-confidence rate
- aggiungere benchmark IT/EN dedicati

---

## Recommended Positioning For Presentation

Messaggio chiave:

> Truth Engine e una piattaforma di fact-checking explainable che unisce retrieval web reale, decomposizione del contenuto, reasoning LLM multi-step e scoring coerente con l'explanation.

Punti da valorizzare nella presentazione:
- lavora su testo e URL
- genera query intelligenti e temporalmente grounded
- usa fonti web reali, non dataset statici soltanto
- conserva trace completo della pipeline
- produce verdict, score, explanation e source analysis in modo leggibile
- usa modelli diversi per compiti diversi

---

## Technical Status

Verifica backend corrente:
- test backend passing: `32 passed`

Questo indica che la base del sistema e stabile per una demo tecnica e per una presentazione ad alto livello.
