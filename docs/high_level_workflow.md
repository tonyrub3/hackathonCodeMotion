# Truth Engine: Workflow Ad Alto Livello

## Obiettivo del programma

Il backend implementa un sistema di fact-checking retrieval-first.

In pratica:

1. riceve un input testuale o un URL
2. normalizza il contenuto
3. se l'input e un URL, estrae fino a 10 claim atomici centrali dall'articolo
4. per URL: usa ogni claim come query di ricerca; per testo: genera query con LLM
5. interroga Tavily per trovare fonti web (cascade tier1 -> tier2)
6. arricchisce e pre-scora le fonti trovate
7. usa un modello LLM tramite Regolo per estrarre segnali strutturati per-claim per-fonte (stance, relevance, excerpt)
8. calcola score deterministici per ogni claim (supporting vs contradicting weight)
9. aggrega i claim-level score in un verdict documento con scoring probabilistico
10. costruisce una risposta strutturata con verdict, score, fonti ed explanation in italiano

Il sistema verifica gli articoli URL per singolo claim.
Ogni claim viene cercato individualmente, ogni fonte viene valutata per ogni claim che tratta,
e il verdict finale e calcolato deterministicamente dai segnali strutturati (non dall'LLM).

---

## Entry point principali

### Backend HTTP

- `apps/backend/app/main.py`
  - crea l'app FastAPI
  - carica `.env`
  - inizializza logging e settings
  - monta le route API

- `apps/backend/app/api/routes_verify.py`
  - espone `POST /api/verify`
  - costruisce `Orchestrator`
  - esegue la pipeline completa
  - converte il `PipelineState` in `VerifyResponse`

### Orchestrazione

- `apps/backend/app/core/orchestrator.py`
  - crea lo stato iniziale della richiesta
  - esegue i macro-step della pipeline
  - registra timing, errori e log di alto livello

---

## Workflow ad alto livello

```text
Client / Frontend
    -> POST /api/verify
    -> Orchestrator
        -> InputNormalizerAgent
        -> ClaimDecompositionAgent (URL only)
        -> TavilyFirstEngine
            -> QueryPlanningAgent
            -> TavilySearchProfileBuilder
            -> Tavily search cascade
            -> Tavily extract
            -> SourceScoringLayer
            -> CrossCheckAnalysisLayer
            -> EvidenceScoringLayer
            -> state assembly
    -> VerifyResponse
```

---

## Filosofia architetturale attuale

L'architettura corrente segue una logica retrieval-first:

1. prima trova fonti plausibili
2. poi legge e ordina le evidenze
3. infine chiede al layer di analisi LLM di produrre un giudizio complessivo

I principi pratici oggi sono:

- Tavily e il motore di recall principale
- Regolo e il provider LLM principale
- il motore non e piu un file monolitico puro: alcune responsabilita sono state estratte in layer dedicati
- sugli URL il retrieval e ora guidato dai claim estratti dall'articolo, non solo dal testo completo
- lo scoring delle fonti e separato dal cross-check LLM
- la pipeline resta lineare e facilmente debuggabile tramite `PipelineState`

---

## Stato condiviso: `PipelineState`

Il programma usa un oggetto mutabile unico che scorre da uno step al successivo:

- file: `apps/backend/app/core/state.py`

Questo contiene:

- dati input
- testo normalizzato
- metadati articolo
- claim estratti per URL
- query generate
- risultati Tavily grezzi
- answer hints Tavily
- search profile usato
- fonti selezionate
- evidenze e contraddizioni
- verdict, confidence, explanation
- timings ed errori

Questo design rende il workflow lineare:

```text
ogni layer legge alcune chiavi dello state
ogni layer scrive nuove chiavi nello state
nessun layer deve ricostruire tutto da zero
```

---

## Step 1: Input normalization

### Responsabile

- `apps/backend/app/agents/input_normalizer_agent.py`

### Cosa fa

Se l'input e testo:

- pulisce whitespace
- rileva la lingua
- salva `normalized_text`

Se l'input e URL:

- scarica HTML
- estrae corpo articolo
- estrae titolo, autore, data
- estrae metadata e link citati
- rileva la lingua

### Output principali

- `state.normalized_text`
- `state.article_title`
- `state.article_author`
- `state.article_date`
- `state.article_metadata`
- `state.cited_links`
- `state.language`

### Nota importante

Questo step non verifica nulla.

Serve solo a trasformare l'input grezzo in testo usabile dal resto della pipeline.

---

## Step 2: Claim decomposition (solo URL)

### Responsabile

- `apps/backend/app/agents/claim_decomposition_agent.py`

### Cosa fa

Quando l'input e un URL:

- prende il testo dell'articolo gia estratto
- usa Regolo per estrarre fino a 5 claim atomici e verificabili
- salva claim, tipo e `checkability_score`
- se l'LLM fallisce, usa un fallback sentence-based

### Output principali

- `state.claims`

### Nota importante

Questo e il primo layer claim-centric della pipeline.

Serve a migliorare il retrieval, non produce ancora verdict claim-by-claim.

---

## Step 3: Query planning

### Responsabile

- `apps/backend/app/agents/query_planning_agent.py`

### Cosa fa

Usa Regolo per trasformare il testo da verificare in query di ricerca.

Se sono gia presenti claim estratti:

- prioritizza quei claim
- usa i claim come base per costruire query migliori
- in fallback usa direttamente il testo dei claim invece del testo intero

Il prompt chiede di:

- identificare i fatti verificabili piu importanti
- generare fino a 3 query
- produrre query concise e orientate al retrieval

### Perche e un agente AI sensato

Questo e uno dei punti in cui un LLM aiuta davvero:

- comprime un testo lungo in segnali di ricerca
- riformula meglio rispetto a una semplice substring
- migliora recall su input poco strutturati

### Fallback

Se l'LLM fallisce:

- usa i primi 300 caratteri del testo come query singola

### Output principali

- `state.generated_queries`

---

## Step 3: Search profile building

## Step 4: Search profile building

### Responsabile

- `apps/backend/app/services/retrieval/search_profile.py`

### Cosa fa

Decide come interrogare Tavily in base al contesto.

Costruisce un profilo con:

- `topic`
  - `general`
  - `news`
  - `finance`
- `country`
  - usato solo quando ha senso per query generaliste
- `temporal`
  - `time_range`
  - `start_date`
  - `end_date`

### Logica attuale

- se il testo sembra finanziario, usa `finance`
- se il testo sembra di attualita o contiene segnali recenti, usa `news`
- altrimenti usa `general`

Per la finestra temporale:

- se il claim sembra recente, restringe a `week` o `month`
- se c'e una `article_date` recente, costruisce una finestra centrata su quella data

### Output principali

- `state.tavily_search_profile`

---

## Step 5: Retrieval con Tavily

### Responsabile

- `apps/backend/app/pipeline/tavily_first.py`
- connector: `apps/backend/app/connectors/tavily_search.py`

### Strategia attuale

Il retrieval usa una cascade search in due tier.

#### Tier 1

Ricerca su domini considerati forti o istituzionali:

- grandi media
- fonti istituzionali
- alcune fonti di fact-checking
- alcune fonti scientifiche

#### Tier 2

Se il Tier 1 non basta:

- amplia la ricerca
- esclude social, blog generici, marketplace e domini blacklistati

### Come viene chiamato Tavily

Il sistema usa:

- `search_depth="advanced"`
- `auto_parameters=True`
- `include_answer="basic"`
- `include_raw_content="text"`
- filtri di `topic`
- filtri temporali quando disponibili
- `exact_match=True` in alcuni casi specifici
- chiamate in parallelo su piu query

### Output principali

- risultati selezionati per il cross-check
- `state.all_tavily_results`
- `state.tavily_answer_hints`

### Nota importante

`include_answer="basic"` viene trattato come hint ausiliario, non come evidenza finale.

---

## Step 6: Content enrichment

### Responsabile

- `apps/backend/app/pipeline/tavily_first.py`
- connector: `apps/backend/app/connectors/tavily_extract.py`

### Cosa fa

Se un risultato Tavily ha poco testo:

- chiama `tavily_extract`
- prova a recuperare contenuto testuale piu ricco

### Perche serve

Molti errori di fact-checking arrivano da fonti recuperate ma troppo povere di contenuto.

Questo step migliora la qualita del materiale poi inviato al cross-check LLM.

---

## Step 7: Source pre-scoring

### Responsabile

- `apps/backend/app/services/scoring/source_scoring.py`

### Obiettivo

Separare tre concetti:

1. fiducia nel dominio
2. fiducia nel contenuto della pagina
3. rilevanza locale del testo rispetto all'input

### Feature principali

#### `domain_trust`

Basato su euristiche del dominio:

- `.gov`, `.edu`, `.int`
- alcuni brand editoriali o istituzionali riconosciuti
- fallback neutro per domini sconosciuti

#### `content_trust`

Stimato dal contenuto della pagina:

- lunghezza
- presenza di attribution markers
- presenza di struttura informativa
- penalita per spam markers
- penalita per eccessi di punteggiatura

#### `local_relevance`

Misura l'overlap token-based tra:

- testo da verificare
- testo della fonte

### Aggregazione

Il layer calcola:

- `_domain_trust`
- `_content_trust`
- `_local_relevance`
- `_source_reliability`
- `_pre_score`

Poi riordina i risultati in base a `_pre_score`.

### Nota importante

Questo non e ancora il ranking definitivo di verita.

E solo un pre-ranking delle fonti prima del cross-check LLM.

---

## Step 8: Cross-check LLM

### Responsabile

- `apps/backend/app/services/analysis/crosscheck.py`

### Cosa fa

Costruisce un prompt che contiene:

- il testo completo da verificare
- le fonti Tavily selezionate
- per ogni fonte:
  - dominio
  - URL
  - titolo
  - contenuto testuale

Poi chiede al modello Regolo di produrre un JSON con:

- `truth_score`
- `confidence_score`
- `verdict`
- `explanation`
- `per_source`

### Modalita operative

Ci sono due prompt:

- `tier1`
  - quando le fonti sono soprattutto primarie o forti
- `tier2`
  - quando si lavora con fonti piu deboli o locali
  - impone un cap alla confidence
  - aggiunge caveat sulle fonti non corroborate da media maggiori

### Output principali

- analisi complessiva LLM
- stance per sorgente
- excerpt chiave per sorgente

### Fallback

Se il modello fallisce o il parsing JSON fallisce:

- il sistema genera un fallback deterministico
- usa score medi Tavily e numero fonti
- restituisce comunque un output strutturato

---

## Step 9: Evidence scoring e assembly finale

### Responsabile

- `apps/backend/app/services/scoring/evidence_scoring.py`
- parte finale di `apps/backend/app/pipeline/tavily_first.py`

### Cosa fa

Trasforma:

- risultati retrieval
- segnali di source scoring
- output `per_source` del cross-check

in strutture finali per API.

### Output costruiti

#### `sources_used`

Per ogni fonte:

- id interno
- nome dominio
- tipo fonte
- URL
- tier A/B/C
- `source_reliability_score`
- dimensioni:
  - `domain_trust`
  - `content_trust`
  - `claim_relevance`
  - `local_relevance`
  - `tavily_score`
  - `is_primary`

#### `scored_evidence`

Per ogni fonte:

- `stance`
- `evidence_score`
- `excerpt`

#### `contradictions`

Se il cross-check marca una fonte come contraddittoria:

- viene creato un oggetto contraddizione

### Normalizzazione finale

Il motore poi:

- applica cap di confidence in base al tier di ricerca
- costruisce l'explanation finale
- aggiunge caveat sul tier usato
- calcola un piccolo `linguistic_risk`

---

## Step 10: Response API

### Responsabile

- `apps/backend/app/models/response_models.py`

### Cosa restituisce

La API `POST /api/verify` ritorna una risposta con:

- `claims`
  - oggi vuoto o poco usato nel runtime corrente
- `generated_queries`
- `sources_used`
- `all_tavily_results`
- `tavily_answer_hints`
- `tavily_search_profile`
- `evidence`
- `contradictions`
- `truth_score`
- `confidence_score`
- `verdict`
- `explanation`
- `errors`
- `timings`

---

## Logging e osservabilita

### Responsabile

- `apps/backend/app/utils/logger.py`
- `apps/backend/app/utils/pipeline_trace.py`

### Come leggere i log

I log sono differenziati per layer:

- `[PIPELINE]`
- `[INPUT]`
- `[QUERY]`
- `[RETRIEVAL]`
- `[SCORING]`
- `[ANALYSIS]`
- `[ASSEMBLY]`

Questo aiuta a capire subito:

- dove siamo nel workflow
- quanto tempo ha richiesto ogni fase
- dove e avvenuto un eventuale fallimento

---

## Sequenza completa di esecuzione

```text
1. Il client chiama POST /api/verify
2. La route crea Orchestrator
3. Orchestrator inizializza PipelineState
4. InputNormalizerAgent pulisce testo o estrae contenuto da URL
5. Se l'input e un URL, ClaimDecompositionAgent estrae claim atomici
6. TavilyFirstEngine prende il testo normalizzato
7. QueryPlanningAgent genera query con Regolo, usando i claim se disponibili
8. TavilySearchProfileBuilder decide topic/country/temporal filters
9. Tavily search esegue retrieval in parallelo
10. Se necessario, Tavily extract arricchisce i contenuti
11. SourceScoringLayer pre-scora le fonti
12. CrossCheckAnalysisLayer invia testo + fonti a Regolo
13. EvidenceScoringLayer costruisce fonti finali, evidence e contraddizioni
14. TavilyFirstEngine completa verdict, confidence, explanation e linguistic risk
15. build_response_from_state converte tutto nella response pubblica
16. FastAPI restituisce il JSON finale
```

---

## Ruolo degli agenti AI oggi

Gli step che usano davvero Regolo oggi sono:

1. `ClaimDecompositionAgent`
2. `QueryPlanningAgent`
3. `CrossCheckAnalysisLayer`

Scelta architetturale:

- AI dove serve comprensione semantica e riformulazione
- heuristics e scoring deterministico dove servono auditability e controllo

Questo significa che:

- query planning e AI-assisted
- claim decomposition per URL e AI-assisted
- cross-check e AI-assisted
- source scoring non e affidato direttamente al modello
- verdict finale non e interamente delegato a un agente autonomo

---

## Cosa il sistema fa bene oggi

1. gestisce sia testo che URL
2. usa retrieval web reale
3. conserva i risultati Tavily grezzi
4. sugli URL estrae claim prima del retrieval
5. tiene separati search profile, source scoring e cross-check
6. restituisce explanation, fonti e timings
7. ha fallback quando l'LLM fallisce
8. ha log leggibili per layer

---

## Limiti attuali importanti

### 1. Verifica finale ancora whole-text

Il sistema confronta il testo nel suo complesso contro le fonti.

Sugli URL il retrieval e guidato dai claim, ma il verdict finale non e ancora calcolato claim-by-claim.

Questo puo creare errori quando:

- una parte del testo e confermata
- una parte no
- il verdict aggregato non riflette bene il claim principale

### 2. Source scoring ancora euristico

Lo scoring attuale separa bene i segnali, ma non e ancora un forensic system completo.

### 3. Mancanza di source independence modeling forte

Piu fonti simili non vengono ancora de-duplicate in modo robusto per ownership o wire reuse.

### 4. Claim relevance ancora semplificata

Il sistema usa:

- overlap locale
- relevance del cross-check LLM

ma non ha ancora un vero predicate-level evidence linker.

### 5. Verdict finale ancora troppo dipendente dal cross-check globale

La pipeline e piu modulare di prima, ma non e ancora un sistema con consistency layer forte e post-processor deterministico sui claim.

---

## Direzione evolutiva naturale

Se si vuole far evolvere questa architettura senza rompere cio che gia funziona, i prossimi step naturali sono:

1. introdurre `SourceForensicsAgent`
2. introdurre claim-level evidence linking
3. aggiungere verdict parziali per claim
4. aggiungere un consistency layer tra cross-check e verdict finale
5. ridurre ancora il peso residuo di `tavily_first.py`

---

## Sintesi finale

Il programma oggi e un fact-checker retrieval-first con orchestrazione lineare.

Il workflow reale e:

```text
normalize input
-> decompose URL claims
-> plan queries
-> build Tavily search profile
-> retrieve sources
-> enrich sources
-> pre-score sources
-> LLM cross-check
-> build final evidence/response
```

Il punto piu importante da ricordare e questo:

il sistema attuale non verifica claim atomici separati, ma il testo come unita unica.

Questo documento descrive quindi il workflow reale della codebase attuale, non quello ideale futuro.
