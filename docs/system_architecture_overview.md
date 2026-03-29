# Truth Engine: Panoramica dell'Architettura

## Sintesi Esecutiva

Truth Engine e un sistema di fact-checking retrieval-first per statement brevi e URL di articoli. Combina:
- orchestrazione deterministica e tracciabile
- retrieval web reale tramite Tavily
- layer LLM specializzati per query planning, claim decomposition, cross-checking e explanation scoring
- output API strutturato con verdetto, evidenze, analisi delle fonti, timing e trace di pipeline

L'obiettivo e semplice: recuperare evidenze rilevanti, ragionare sulle fonti trovate e restituire una decisione leggibile che resti ancorata ai contenuti reali.

## Flusso ad Alto Livello

```text
Client / Frontend
    -> POST /api/verify
    -> Orchestrator
        -> InputNormalizerAgent
        -> ClaimDecompositionAgent (URL only)
        -> TavilyFirstEngine
            -> QueryPlanningAgent
            -> TavilySearchProfileBuilder
            -> Tavily Search + Extract
            -> SourceScoringLayer
            -> CrossCheckAnalysisLayer
            -> ExplanationScoringLayer
            -> Guardrails + Final Assembly
    -> VerifyResponse
```

## Fasi della Pipeline

### 1. Normalizzazione dell'input
- testo: pulizia e language detection
- URL: fetch della pagina, estrazione di corpo, titolo, autore, data e link citati

Output:
- `normalized_text`
- `article_title`
- `article_author`
- `article_date`
- `source_url`
- `cited_links`

### 2. Claim decomposition
Solo per input URL.

Un LLM estrae claim verificabili e query seed dal corpo dell'articolo. Questi claim guidano il retrieval, soprattutto sugli articoli lunghi o molto densi.

Output:
- `state.claims`

### 3. Query planning
Un LLM trasforma il testo o i claim estratti in query di retrieval. Le date relative come `l'anno scorso` vengono risolte usando la data corrente o la data dell'articolo.

Output:
- `state.generated_queries`

### 4. Costruzione del search profile
Il backend sceglie dinamicamente i parametri di Tavily:
- `topic`: `general`, `news`, `finance`
- `country`
- filtri temporali come `time_range`, `start_date`, `end_date`

Questo rende il retrieval contestuale invece che uniforme.

### 5. Retrieval Tavily ed enrichment
Il motore esegue un cascade retrieval:
- tier 1 su domini piu forti o trusted
- tier 2 piu ampio se necessario

Se un risultato e troppo povero, Tavily extract viene usato per arricchire il contenuto.

Salvato nello state:
- `all_tavily_results`
- `tavily_answer_hints`
- `tavily_search_profile`

### 6. Source pre-scoring
Le fonti vengono ordinate prima dell'analisi semantica usando:
- `domain_trust`
- `content_trust`
- `local_relevance`
- `source_reliability`

Questo non e il verdetto finale: serve a preparare evidenze migliori per il judge LLM.

### 7. Cross-check analysis
Il cross-check LLM riceve:
- il testo da verificare
- i claim estratti
- le fonti web selezionate con il loro contenuto

Restituisce:
- `judgment_basis`
- `explanation`
- `per_source`
- segnali iniziali legati al verdetto

Se il primo output del modello non e JSON utilizzabile, il sistema esegue un repair pass LLM-only per recuperare JSON strutturato invece di degradare silenziosamente.

### 8. Explanation scoring
Un secondo LLM legge l'explanation e deriva:
- `truth_score`
- `confidence_score`
- `verdict`

Questo mantiene lo scoring numerico allineato con il reasoning mostrato all'utente.

### 9. Guardrail e assembly finale
L'ultimo layer del motore:
- costruisce `sources_used`, `evidence` e `contradictions`
- applica gli ultimi guardrail su confidence e coerenza del verdetto
- preserva explanation e trace per il frontend

## Stato Condiviso

La pipeline e coordinata tramite `PipelineState`, un oggetto di stato mutabile condiviso che contiene:
- input normalizzato
- metadati dell'articolo
- claim estratti
- query generate
- risultati Tavily e hint
- fonti selezionate ed evidenze
- explanation, score, confidence e verdict
- timing ed errori

Questo design mantiene il sistema lineare e debuggabile.

## Punti di Forza

- funziona sia su testo sia su URL
- retrieval web in tempo reale
- ricerca guidata dai claim sugli articoli lunghi
- explanation finale in italiano
- payload ricco per demo e debugging
- separazione chiara tra retrieval, scoring e reasoning

## Limiti Attuali

- il verdetto finale e ancora soprattutto document-level, non pienamente claim-by-claim
- la qualita del retrieval resta un collo di bottiglia importante
- source independence e source forensics sono ancora leggere

## Modelli Attualmente Consigliati

- `REGOLO_QUERY_MODEL=Llama-3.3-70B-Instruct`
- `REGOLO_CLAIM_MODEL=Llama-3.3-70B-Instruct`
- `REGOLO_CROSSCHECK_MODEL=gpt-oss-120b`
- `REGOLO_SCORING_MODEL=gpt-oss-120b`

## Mini Roadmap

1. esporre `judgment_basis` nel frontend
2. passare da un verdetto document-level a una vera aggregazione claim-level
3. migliorare source independence e source forensics
4. calibrare la confidence su set di valutazione reali
