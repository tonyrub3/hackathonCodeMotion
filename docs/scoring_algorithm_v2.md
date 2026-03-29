# Scoring Algorithm v2 — Proposta di Design

## A) Diagnosi dei limiti attuali

### A.1 Bug critico: i claim estratti vengono distrutti

In `tavily_first.py:589`, `_build_state()` esegue `state.claims = []`.
Questo distrugge i claim estratti da `ClaimDecompositionAgent`, rendendo impossibile qualsiasi scoring claim-level.
I claim guidano il retrieval (via `QueryPlanningAgent`) ma poi spariscono.

### A.2 Il verdict è interamente delegato all'LLM

`CrossCheckAnalysisLayer` chiede al modello di produrre `truth_score`, `confidence_score` e `verdict` in un singolo JSON.
Non esiste nessun post-processor deterministico che validi la coerenza tra questi valori.

Conseguenze:
- il modello può emettere `verdict=verified` con `truth_score=45`
- il modello può dire "non ci sono fonti sufficienti" nell'explanation ma emettere `mostly_verified`
- nessun segnale strutturato (contraddizioni, copertura, diversity) viene usato per governare il verdict
- il fallback deterministico usa `avg(tavily_score) * 80 + 10`, che non ha alcun valore informativo reale

### A.3 source_reliability mescola dominio e contenuto senza separazione

```python
source_reliability = 0.58 * domain_trust + 0.42 * content_trust
```

Questo score viene poi usato sia nel pre-score che nell'evidence_score.
`content_trust` misura la qualità editoriale della pagina (lunghezza, attribution, struttura), **non** la pertinenza al claim.
Ma viene combinato con `domain_trust` in un singolo valore che poi conta come "affidabilità della fonte", creando double counting con `local_relevance`.

### A.4 evidence_score non distingue tipo di evidenza

```python
evidence_score = 0.45 * claim_relevance + 0.35 * source_reliability + 0.20 * tavily_score
```

Problemi:
- `claim_relevance = 0.65 * llm_relevance + 0.35 * local_relevance`: mescola un segnale model-based con un overlap tokenico
- `stance` è usato solo come label (supporting/contradicting/neutral), non come peso
- non c'è distinzione tra evidenza diretta ("il ministro ha detto X il 15 marzo") e evidenza indiretta ("il ministero ha pubblicato un comunicato")
- non c'è `directness` score
- non c'è `specificity` score (la fonte parla dello stesso predicato, o solo dello stesso soggetto?)

### A.5 Nessun claim-level scoring

Per gli URL, i claim vengono estratti con `type` e `checkability_score` ma:
- non vengono linkati all'evidenza
- non hanno `partial_verdict` calcolato (resta sempre `insufficient_evidence`)
- non hanno `partial_score` calcolato (resta sempre `0.0`)
- l'`EvidenceScoringLayer` non sa quale claim ciascuna evidenza supporta

### A.6 Confidence non governata da segnali strutturali

La confidence attuale arriva direttamente dall'LLM (con cap per tier).
Non tiene conto di:
- quanti claim sono coperti
- quanta evidenza diretta esiste
- quante fonti indipendenti confermano
- se ci sono contraddizioni forti non risolte

### A.7 Double counting specifici

| Signal A | Signal B | Dove si sovrappongono |
|---|---|---|
| `domain_trust` dentro `source_reliability` | `source_reliability` dentro `evidence_score` | Il dominio conta due volte nell'evidence |
| `content_trust` dentro `source_reliability` | `content_trust` nel `pre_score` (peso 0.15) | Content trust conta sia via reliability che direttamente |
| `local_relevance` nel `pre_score` | `local_relevance` dentro `claim_relevance` | L'overlap tokenico conta in entrambi |
| `tavily_score` nel `pre_score` | `tavily_score` nell'`evidence_score` | Tavily score usato due volte |
| `llm_relevance` in `claim_relevance` | LLM truth_score/verdict che include il proprio giudizio di rilevanza | Il modello valuta rilevanza sia per-source che globalmente |

### A.8 Mancanza di source independence

Se 3 fonti riportano lo stesso testo di agenzia (es. lancio ANSA ripreso da Corriere, Repubblica, Il Sole), il sistema le conta come 3 conferme indipendenti. In realtà sono una singola fonte originale.

### A.9 Il fallback deterministico è inaffidabile

```python
truth_score = max(0, min(100, int(average_score * 80 + 10)))
```

`average_score` è la media dei `tavily_score`, che misura la rilevanza della query, non la veridicità del contenuto.
Un claim falso su un argomento popolare avrà fonti ad alta rilevanza che lo contraddicono, ma il fallback lo leggerà come "alta verità".

---

## B) Nuovo design di scoring

### Principio fondamentale

**Il verdict non deve essere prodotto dall'LLM.**

L'LLM viene usato per:
1. Estrarre claim atomici (già fatto)
2. Generare query (già fatto)
3. **Estrarre segnali strutturati** per-source e per-claim (nuovo ruolo del CrossCheck)

Il verdict viene **calcolato deterministicamente** da uno scoring probabilistico basato sui segnali estratti.

### Architettura a 4 livelli

```
Layer A: Source Trust Score       (deterministico, pre cross-check)
Layer B: Evidence Quality Score   (ibrido: LLM estrae segnali, scoring deterministico)
Layer C: Claim-Level Score        (deterministico, aggrega evidenze per claim)
Layer D: Document-Level Score     (deterministico, aggrega claim in verdict finale)
```

### Flusso dati nella pipeline modificata

```
SourceScoringLayer        → source_trust_score per fonte
                            (invariato nella posizione, migliorato nei segnali)

CrossCheckAnalysisLayer   → estrae SEGNALI STRUTTURATI, non verdict
                            per ogni (source, claim):
                              stance, directness, specificity, excerpt
                            NON produce truth_score/verdict

EvidenceScoringLayer      → evidence_quality_score per (source, claim)
  [rinominato:               combina source_trust + segnali cross-check
   EvidenceAggregator]       deterministico

ClaimScoringLayer [NUOVO] → claim_support, claim_contradiction,
                             claim_confidence per claim

VerdictAssemblyLayer      → document_truth_score, document_confidence,
  [NUOVO]                    verdict, consistency checks, overrides
                             INTERAMENTE DETERMINISTICO
```

---

## C) Feature set per livello

### C.1 Source Trust Score (Layer A)

Calcolato da `SourceScoringLayer` PRIMA del cross-check. Non cambia con il claim.

| Feature | Tipo | Formula/Logica | Range |
|---|---|---|---|
| `domain_institutional_trust` | deterministic | Lookup per TLD/dominio noto | 0.0-1.0 |
| `editorial_quality` | deterministic | Lunghezza + attribution markers + struttura | 0.0-1.0 |
| `spam_penalty` | deterministic | Spam markers + punctuation abuse | 0.0-1.0 |
| `source_trust_score` | deterministic | Combinazione pesata (vedi formula) | 0.0-1.0 |

**Cosa cambia rispetto a oggi:**
- `domain_trust` → `domain_institutional_trust` (stesso calcolo, nome più chiaro)
- `content_trust` → `editorial_quality` (enfatizza che misura qualità editoriale, NON pertinenza)
- `source_reliability` → `source_trust_score` (stop: non include più content_trust mescolato)
- Rimosso `local_relevance` da questo layer (va nel Layer B)
- Rimosso `pre_score` (non serve più come ranking monodimensionale)

### C.2 Evidence Quality Score (Layer B)

Calcolato da `EvidenceAggregator` DOPO il cross-check, per coppia (source, claim).

| Feature | Tipo | Provenienza | Range |
|---|---|---|---|
| `passage_relevance` | model-based | LLM nel cross-check | 0.0-1.0 |
| `stance` | model-based | LLM nel cross-check | supporting/contradicting/neutral/irrelevant |
| `stance_confidence` | model-based | LLM nel cross-check | 0.0-1.0 |
| `directness` | model-based | LLM nel cross-check | direct/indirect/contextual |
| `specificity` | model-based | LLM nel cross-check | predicate_match/subject_only/topic_only |
| `temporal_alignment` | deterministic | Confronto date articolo vs fonte | 0.0-1.0 |
| `token_overlap` | deterministic | Overlap tokenico (già esistente) | 0.0-1.0 |
| `evidence_quality_score` | deterministic | Formula di combinazione | 0.0-1.0 |

**Segnali estratti dall'LLM (nuovo formato per_source nel cross-check):**

```json
{
  "source_index": 0,
  "claims_addressed": ["c1", "c3"],
  "per_claim": [
    {
      "claim_id": "c1",
      "stance": "supporting",
      "stance_confidence": 0.85,
      "directness": "direct",
      "specificity": "predicate_match",
      "passage_relevance": 0.90,
      "key_excerpt": "Il ministro Rossi ha confermato il 15 marzo..."
    }
  ]
}
```

L'LLM estrae questi segnali strutturati. Lo scoring è deterministico.

### C.3 Claim-Level Score (Layer C)

Calcolato dal nuovo `ClaimScoringLayer`, aggrega le evidenze per claim.

| Feature | Tipo | Formula | Range |
|---|---|---|---|
| `claim_support_score` | deterministic | Aggregazione evidenze supporting | 0.0-1.0 |
| `claim_contradiction_score` | deterministic | Aggregazione evidenze contradicting | 0.0-1.0 |
| `claim_coverage` | deterministic | Numero fonti che addressano il claim | 0-N |
| `source_diversity` | deterministic | Numero domini distinti | 0-N |
| `source_independence` | deterministic | Cluster analysis su domini | 0.0-1.0 |
| `max_directness` | deterministic | Massima directness tra le evidenze | enum |
| `claim_confidence` | deterministic | Funzione di copertura e qualità | 0.0-1.0 |
| `claim_verdict` | deterministic | Regole threshold-based | enum |

### C.4 Document-Level Score (Layer D)

Calcolato dal nuovo `VerdictAssemblyLayer`, aggrega claim in verdict.

| Feature | Tipo | Formula | Range |
|---|---|---|---|
| `document_truth_score` | deterministic | Aggregazione pesata dei claim | 0-100 |
| `document_confidence` | deterministic | Funzione di copertura e agreement | 0.0-1.0 |
| `verdict` | deterministic | Mapping da truth_score + overrides | enum |
| `mixedness` | deterministic | Varianza dei claim verdicts | 0.0-1.0 |
| `coverage_ratio` | deterministic | Claim coperti / claim totali | 0.0-1.0 |

---

## D) Formule e pseudocodice

### D.1 source_trust_score

```python
def source_trust_score(domain_institutional_trust: float,
                       editorial_quality: float,
                       spam_penalty: float) -> float:
    """
    Puro segnale sulla fonte. Non include rilevanza al claim.

    Pesi:
    - domain_institutional_trust: 0.60 (il dominio è il segnale più stabile)
    - editorial_quality: 0.30 (qualità editoriale della pagina)
    - spam_penalty: applicata come moltiplicatore (non come addendo)

    Perché questi pesi:
    - Il dominio è verificabile e stabile nel tempo
    - La qualità editoriale è un proxy per il rigore della fonte
    - Lo spam è un segnale di esclusione, non di gradazione
    """
    base = 0.60 * domain_institutional_trust + 0.40 * editorial_quality
    return round(max(0.05, base * (1.0 - 0.7 * spam_penalty)), 3)
```

### D.2 evidence_quality_score

```python
def evidence_quality_score(
    passage_relevance: float,       # model-based, 0-1
    stance: str,                    # model-based
    stance_confidence: float,       # model-based, 0-1
    directness: str,                # model-based: direct/indirect/contextual
    specificity: str,               # model-based: predicate_match/subject_only/topic_only
    temporal_alignment: float,      # deterministic, 0-1
    source_trust: float,            # from Layer A
) -> float:
    """
    Score di qualità dell'evidenza per una coppia (source, claim).

    Principio: la qualità dipende da quanto l'evidenza è
    rilevante, diretta, specifica e da una fonte affidabile.

    NON include la stance (supporting/contradicting) nel punteggio.
    La stance determina la DIREZIONE, non la QUALITÀ dell'evidenza.
    Un'evidenza contradittoria di alta qualità è preziosa.
    """
    # Directness multiplier
    directness_mult = {
        "direct": 1.0,      # La fonte afferma esplicitamente il fatto
        "indirect": 0.65,   # La fonte implica il fatto
        "contextual": 0.35, # La fonte parla del contesto ma non del fatto
    }.get(directness, 0.35)

    # Specificity multiplier
    specificity_mult = {
        "predicate_match": 1.0,   # Stesso soggetto E stesso predicato
        "subject_only": 0.55,     # Stesso soggetto, predicato diverso
        "topic_only": 0.25,       # Stesso argomento, soggetto/predicato diversi
    }.get(specificity, 0.25)

    quality = (
        0.30 * passage_relevance
        + 0.25 * (directness_mult * specificity_mult)
        + 0.15 * stance_confidence
        + 0.15 * source_trust
        + 0.15 * temporal_alignment
    )

    return round(max(0.0, min(1.0, quality)), 3)
```

### D.3 temporal_alignment (deterministico)

```python
def temporal_alignment(article_date: str | None,
                       source_date: str | None,
                       claim_type: str) -> float:
    """
    Misura quanto la fonte è temporalmente allineata con il claim.

    Se non ci sono date, restituisce un valore neutro (0.5).
    Per claim di tipo event/institutional, la prossimità temporale conta di più.
    Per claim statistical/policy, la finestra è più ampia.
    """
    if not article_date or not source_date:
        return 0.5  # Neutro: non penalizza né premia

    try:
        art_dt = parse_date(article_date)
        src_dt = parse_date(source_date)
        delta_days = abs((art_dt - src_dt).days)
    except Exception:
        return 0.5

    # Finestra dipende dal tipo di claim
    if claim_type in ("event", "institutional", "biographical"):
        # Eventi: la prossimità è fondamentale
        if delta_days <= 3:
            return 1.0
        elif delta_days <= 14:
            return 0.75
        elif delta_days <= 45:
            return 0.50
        else:
            return 0.25
    else:
        # Statistical/policy: finestra più ampia
        if delta_days <= 30:
            return 1.0
        elif delta_days <= 90:
            return 0.75
        elif delta_days <= 365:
            return 0.50
        else:
            return 0.30
```

### D.4 source_independence (deterministico)

```python
# Cluster noti di fonti che condividono wire/contenuti
WIRE_CLUSTERS = {
    "ansa_wire": {"ansa.it", "corriere.it", "repubblica.it", "ilsole24ore.com",
                  "lastampa.it", "ilmessaggero.it"},
    "ap_wire": {"apnews.com", "nytimes.com", "washingtonpost.com"},
    "reuters_wire": {"reuters.com", "bbc.com", "theguardian.com"},
}

def source_independence(domains: list[str]) -> float:
    """
    Penalizza fonti che appartengono allo stesso wire cluster.

    Logica: se tutte le fonti sono nello stesso cluster,
    l'indipendenza è bassa (contano come ~1 fonte).

    Restituisce il rapporto tra cluster distinti e fonti totali.
    """
    if len(domains) <= 1:
        return 1.0  # Una sola fonte, nessun problema di clustering

    # Assegna ogni dominio al suo cluster (o a se stesso se non in nessun cluster)
    cluster_ids = set()
    for domain in domains:
        d = domain.lower()
        assigned = False
        for cluster_name, cluster_members in WIRE_CLUSTERS.items():
            if any(member in d for member in cluster_members):
                cluster_ids.add(cluster_name)
                assigned = True
                break
        if not assigned:
            cluster_ids.add(d)  # Dominio indipendente = cluster di 1

    # Indipendenza = cluster distinti / fonti totali
    # 3 fonti in 3 cluster = 1.0
    # 3 fonti in 1 cluster = 0.33
    return round(min(1.0, len(cluster_ids) / len(domains)), 3)
```

### D.5 claim_support_score e claim_contradiction_score

```python
def claim_support_score(evidences: list[EvidenceRecord]) -> float:
    """
    Aggrega le evidenze supporting per un singolo claim.

    Usa weighted sum con saturazione: più evidenze forti confermano,
    ma il guadagno marginale decresce (curva logaritmica).

    Solo le evidenze con stance=supporting vengono considerate.
    """
    supporting = [e for e in evidences if e.stance == "supporting"]
    if not supporting:
        return 0.0

    # Ordina per evidence_quality_score decrescente
    supporting.sort(key=lambda e: e.evidence_quality_score, reverse=True)

    # Primo contributo pieno, successivi con decadimento
    total = 0.0
    for i, ev in enumerate(supporting):
        weight = 1.0 / (1.0 + 0.5 * i)  # 1.0, 0.67, 0.50, 0.40, ...
        total += ev.evidence_quality_score * weight

    # Normalizza con saturazione logaritmica
    # 1 evidenza forte (0.9) → ~0.62
    # 2 evidenze forti (0.9, 0.8) → ~0.79
    # 3 evidenze forti (0.9, 0.8, 0.7) → ~0.87
    import math
    return round(min(1.0, 0.7 * math.log1p(total)), 3)


def claim_contradiction_score(evidences: list[EvidenceRecord]) -> float:
    """
    Stessa logica di claim_support_score ma per evidenze contradicting.

    Nota: una singola contraddizione forte da fonte autorevole
    è più significativa di molte deboli.
    """
    contradicting = [e for e in evidences if e.stance == "contradicting"]
    if not contradicting:
        return 0.0

    contradicting.sort(key=lambda e: e.evidence_quality_score, reverse=True)

    # Per le contraddizioni, il peso del primo elemento è ancora più alto
    total = 0.0
    for i, ev in enumerate(contradicting):
        weight = 1.0 / (1.0 + 0.7 * i)  # 1.0, 0.59, 0.42, ...
        total += ev.evidence_quality_score * weight

    import math
    return round(min(1.0, 0.7 * math.log1p(total)), 3)
```

### D.6 claim_confidence_score

```python
def claim_confidence_score(
    support: float,             # claim_support_score
    contradiction: float,       # claim_contradiction_score
    coverage: int,              # numero fonti che addressano il claim
    diversity: float,           # source_independence
    max_directness: str,        # massima directness tra le evidenze
    checkability: float,        # dal ClaimDecompositionAgent
) -> float:
    """
    Quanto siamo sicuri del giudizio su questo claim.

    La confidence è ALTA quando:
    - ci sono molte fonti indipendenti (alto coverage * diversity)
    - le evidenze sono dirette (alto directness)
    - il claim è verificabile (alto checkability)
    - c'è accordo chiaro (support alto XOR contradiction alta)

    La confidence è BASSA quando:
    - poche fonti
    - fonti non indipendenti
    - evidenza solo indiretta
    - support e contradiction entrambi medi (situazione ambigua)
    """
    # Coverage factor: satura a 5 fonti
    coverage_factor = min(1.0, coverage / 5.0)

    # Directness factor
    directness_factor = {
        "direct": 1.0,
        "indirect": 0.60,
        "contextual": 0.30,
    }.get(max_directness, 0.20)

    # Agreement clarity: alta quando una delle due prevale nettamente
    # Se support=0.8, contradiction=0.1 → clarity=0.7 (chiaro)
    # Se support=0.5, contradiction=0.4 → clarity=0.1 (ambiguo)
    agreement_clarity = abs(support - contradiction)

    # Composizione
    raw_confidence = (
        0.25 * coverage_factor * diversity
        + 0.30 * directness_factor
        + 0.25 * agreement_clarity
        + 0.10 * checkability
        + 0.10 * max(support, contradiction)  # Forza del segnale prevalente
    )

    return round(max(0.0, min(1.0, raw_confidence)), 3)
```

### D.7 claim_verdict (deterministico, threshold-based)

```python
def claim_verdict(
    support: float,
    contradiction: float,
    confidence: float,
    max_directness: str,
    coverage: int,
) -> str:
    """
    Determina il verdict per un singolo claim.

    Regole (applicate in ordine di priorità):

    1. Se coverage=0 → insufficient_evidence
    2. Se nessuna evidenza diretta E support < 0.3 → insufficient_evidence
    3. Se contradiction > support + 0.25 → false/mostly_false
    4. Se support > contradiction + 0.25 → verified/mostly_verified
    5. Altrimenti → mixed/misleading

    La confidence modula la forza del verdict:
    - confidence < 0.3 → al massimo "mixed"
    """
    # Regola 1: nessuna copertura
    if coverage == 0:
        return "insufficient_evidence"

    # Regola 2: nessuna evidenza diretta e poco supporto
    if max_directness not in ("direct", "indirect") and support < 0.30:
        return "insufficient_evidence"

    net_score = support - contradiction

    # Regola 3: contraddizione prevalente
    if contradiction > support + 0.25:
        if contradiction > 0.70 and confidence > 0.40:
            return "false"
        return "mostly_false"

    # Regola 4: supporto prevalente
    if support > contradiction + 0.25:
        # Gate di confidence
        if confidence < 0.30:
            return "mixed"
        # Gate di directness
        if max_directness == "direct" and support > 0.60 and confidence > 0.50:
            return "verified"
        if support > 0.50:
            return "mostly_verified"
        return "mixed"

    # Regola 5: situazione mista
    if net_score > 0.10:
        return "mixed"  # Leggero vantaggio al supporto
    if net_score < -0.10:
        return "misleading"  # Leggero vantaggio alla contraddizione
    return "mixed"
```

### D.8 document_truth_score

```python
def document_truth_score(
    claims: list[ClaimRecord],
    input_type: str,
) -> float:
    """
    Per URL: media pesata dei claim_support_score, con peso = checkability * importance.
    Per text: usa il claim sintetico unico (il testo intero come claim c0).

    Restituisce un punteggio 0-100.
    """
    if not claims:
        return 0.0

    if input_type == "text":
        # Per testo breve: il claim è unico, usa direttamente il suo score
        c = claims[0]
        raw = c.support - 0.8 * c.contradiction
        return round(max(0, min(100, raw * 100)), 1)

    # Per URL: aggregazione pesata
    total_weight = 0.0
    weighted_score = 0.0

    for c in claims:
        # Peso del claim: checkability * posizione (i primi claim sono più importanti)
        weight = c.checkability * c.importance_weight
        raw = c.support - 0.8 * c.contradiction
        weighted_score += raw * weight
        total_weight += weight

    if total_weight == 0:
        return 0.0

    normalized = weighted_score / total_weight
    return round(max(0, min(100, normalized * 100)), 1)
```

### D.9 document_confidence_score

```python
def document_confidence_score(
    claims: list[ClaimRecord],
    coverage_ratio: float,      # claim coperti / claim totali
    search_tier: str,            # tier1/mixed/tier2
    has_contradictions: bool,
    mixedness: float,            # varianza dei claim verdicts
) -> float:
    """
    Confidence complessiva del documento.

    Componenti:
    1. Media delle claim_confidence pesata per checkability
    2. Penalità per claim non coperti
    3. Cap per tier di ricerca
    4. Penalità per contraddizioni non risolte
    5. Penalità per alta mixedness (claim con verdetti molto diversi)
    """
    if not claims:
        return 0.0

    # 1. Media pesata delle claim confidence
    total_w = 0.0
    weighted_conf = 0.0
    for c in claims:
        w = c.checkability
        weighted_conf += c.confidence * w
        total_w += w
    avg_confidence = weighted_conf / total_w if total_w > 0 else 0.0

    # 2. Penalità copertura
    coverage_factor = 0.5 + 0.5 * coverage_ratio  # range: 0.5-1.0

    # 3. Cap per tier
    tier_cap = {"tier1": 1.0, "mixed": 0.80, "tier2": 0.65}.get(search_tier, 1.0)

    # 4. Penalità contraddizioni
    contradiction_penalty = 0.85 if has_contradictions else 1.0

    # 5. Penalità mixedness (alta varianza tra i verdict dei claim)
    mixedness_penalty = 1.0 - 0.3 * mixedness

    raw = avg_confidence * coverage_factor * contradiction_penalty * mixedness_penalty
    return round(max(0.0, min(tier_cap, raw)), 3)
```

### D.10 document_verdict (deterministico)

```python
def document_verdict(truth_score: float, confidence: float) -> str:
    """
    Mapping deterministico da truth_score e confidence a verdict.

    La confidence modula il massimo verdict raggiungibile.
    """
    # Gate di confidence
    if confidence < 0.15:
        return "insufficient_evidence"

    max_verdict_by_confidence = {
        # confidence < 0.30: massimo "mixed"
        0.30: "mixed",
        # confidence < 0.45: massimo "mostly_verified" o "mostly_false"
        0.45: "mostly_verified",
        # confidence >= 0.45: tutti i verdict possibili
    }

    # Mapping base da truth_score
    if truth_score >= 80:
        base_verdict = "verified"
    elif truth_score >= 65:
        base_verdict = "mostly_verified"
    elif truth_score >= 45:
        base_verdict = "mixed"
    elif truth_score >= 30:
        base_verdict = "misleading"
    elif truth_score >= 15:
        base_verdict = "mostly_false"
    else:
        base_verdict = "false"

    # Applica cap di confidence
    VERDICT_ORDER = [
        "false", "mostly_false", "misleading", "mixed",
        "mostly_verified", "verified"
    ]

    if confidence < 0.30:
        max_idx = VERDICT_ORDER.index("mixed")
    elif confidence < 0.45:
        max_idx = VERDICT_ORDER.index("mostly_verified")
    else:
        max_idx = len(VERDICT_ORDER) - 1

    base_idx = VERDICT_ORDER.index(base_verdict)
    final_idx = min(base_idx, max_idx)

    return VERDICT_ORDER[final_idx]
```

---

## E) Mapping Layer → Responsabilità di scoring

### E.1 SourceScoringLayer (esistente, modificato)

**Input:** risultati Tavily grezzi + testo da verificare
**Output per fonte:**
- `domain_institutional_trust` (deterministic)
- `editorial_quality` (deterministic)
- `spam_penalty` (deterministic)
- `source_trust_score` (deterministic)

**Cosa cambia:**
- Rimosso `local_relevance` da questo layer (va nel Layer B)
- Rimosso `_pre_score` (il ranking si fa per `source_trust_score`)
- Rimosso `_source_reliability` (sostituito da `source_trust_score`)
- `_content_trust` rinominato `_editorial_quality`

**Cosa resta invariato:**
- `domain_reliability()` → rinominato `domain_institutional_trust()`
- Stesse euristiche per TLD e domini noti
- `content_trust_score()` → rinominato `editorial_quality_score()`
- Stessi segnali: lunghezza, attribution, struttura, spam

### E.2 CrossCheckAnalysisLayer (esistente, ruolo ridefinito)

**Input:** testo + fonti scored + claim estratti (per URL)
**Output:** segnali strutturati per coppia (source, claim)

**Ruolo NUOVO:** l'LLM NON produce più truth_score, confidence_score, verdict.
Produce solo segnali strutturati:

```json
{
  "per_source": [
    {
      "source_index": 0,
      "claims_addressed": ["c1", "c3"],
      "per_claim": [
        {
          "claim_id": "c1",
          "stance": "supporting",
          "stance_confidence": 0.85,
          "directness": "direct",
          "specificity": "predicate_match",
          "passage_relevance": 0.90,
          "key_excerpt": "..."
        }
      ]
    }
  ]
}
```

Per input di tipo `text` (senza claim estratti):
- Si crea un claim sintetico `c0` che rappresenta il testo intero
- L'LLM valuta ogni fonte contro `c0`

**Fallback deterministico:**
- Se l'LLM fallisce, `stance=neutral`, `directness=contextual`, `specificity=topic_only`
- `passage_relevance` calcolato da token overlap
- `stance_confidence = 0.0`
- Risultato: il sistema produrrà `insufficient_evidence` con bassa confidence

### E.3 EvidenceAggregator (rinominato da EvidenceScoringLayer)

**Input:** risultati scored + segnali cross-check + claim
**Output per coppia (source, claim):**
- `evidence_quality_score` (deterministic, combina Layer A + segnali Layer B)
- `temporal_alignment` (deterministic)
- Record strutturati per API

**Cosa cambia:**
- Non calcola più un singolo `evidence_score` globale
- Calcola `evidence_quality_score` per coppia (source, claim)
- Il `claim_relevance` attuale viene sostituito da `passage_relevance` + `specificity` + `directness`
- Niente più double counting con `source_reliability`

### E.4 ClaimScoringLayer (NUOVO)

**Input:** evidenze aggregate per claim + informazioni fonte
**Output per claim:**
- `claim_support_score`
- `claim_contradiction_score`
- `claim_coverage` (int)
- `source_diversity` (int)
- `source_independence` (float)
- `max_directness` (enum)
- `claim_confidence` (float)
- `claim_verdict` (enum)

**Posizione nella pipeline:** dopo EvidenceAggregator, prima di VerdictAssembly.

### E.5 VerdictAssemblyLayer (NUOVO)

**Input:** claim scores + metadata pipeline
**Output:**
- `document_truth_score` (0-100)
- `document_confidence` (0.0-1.0)
- `verdict` (enum)
- `mixedness` (float)
- `coverage_ratio` (float)
- Override applicate (lista per auditability)

**Posizione nella pipeline:** ultimo layer, sostituisce la logica in `_build_state`.

---

## F) Regole di override deterministiche

Queste regole vengono applicate DOPO il calcolo degli score, PRIMA dell'emissione del verdict.
Ogni override che si attiva viene registrato in `state.verdict_overrides` per auditability.

### F.1 No direct evidence → no verified

```python
if max_directness_across_claims not in ("direct",) and verdict in ("verified",):
    verdict = "mostly_verified"
    overrides.append("OVERRIDE_F1: no direct evidence, downgraded from verified")
```

**Perché:** un verdict "verified" richiede che almeno un claim centrale abbia evidenza diretta.

### F.2 No direct/indirect evidence → no mostly_verified

```python
if max_directness_across_claims not in ("direct", "indirect") and verdict in ("verified", "mostly_verified"):
    verdict = "mixed"
    overrides.append("OVERRIDE_F2: no direct/indirect evidence, capped at mixed")
```

### F.3 Strong contradiction → confidence cap

```python
if any(c.contradiction_score > 0.65 and c.checkability > 0.70 for c in claims):
    confidence = min(confidence, 0.55)
    overrides.append("OVERRIDE_F3: strong contradiction on checkable claim, confidence capped at 0.55")
```

**Perché:** una forte contraddizione su un claim verificabile indica incertezza irrisolta.

### F.4 Zero coverage → insufficient evidence

```python
if coverage_ratio == 0.0:
    verdict = "insufficient_evidence"
    confidence = 0.0
    overrides.append("OVERRIDE_F4: no claims covered, insufficient evidence")
```

### F.5 Low source independence → confidence penalty

```python
avg_independence = mean(c.source_independence for c in claims if c.coverage > 0)
if avg_independence < 0.40:
    confidence = min(confidence, confidence * 0.70)
    overrides.append(f"OVERRIDE_F5: low source independence ({avg_independence:.2f}), confidence reduced")
```

**Perché:** fonti non indipendenti (stesso wire cluster) non aggiungono vera diversità.

### F.6 Recent claim without corroboration → insufficient evidence cap

```python
for c in claims:
    if c.claim_type in ("event", "institutional") and c.coverage <= 1 and search_tier != "tier1":
        if c.claim_verdict in ("verified", "mostly_verified"):
            c.claim_verdict = "mixed"
            overrides.append(f"OVERRIDE_F6: recent claim {c.id} with single non-primary source, capped at mixed")
```

**Perché:** un singolo report da fonte non primaria non è sufficiente per verificare un evento.

### F.7 Unresolved central claim penalty

```python
central_claims = [c for c in claims if c.checkability >= 0.75]
unresolved = [c for c in central_claims if c.claim_verdict == "insufficient_evidence"]
if len(unresolved) > 0 and len(central_claims) > 0:
    unresolved_ratio = len(unresolved) / len(central_claims)
    if unresolved_ratio > 0.5:
        confidence = min(confidence, 0.40)
        if verdict in ("verified", "mostly_verified"):
            verdict = "mixed"
        overrides.append(f"OVERRIDE_F7: {len(unresolved)}/{len(central_claims)} central claims unresolved")
```

### F.8 Conservative mode per ambienti high-risk

```python
if mode == "conservative":
    # In modalità conservativa:
    # - nessun verdict "verified" possibile
    # - confidence massima 0.80
    # - richiede almeno 2 fonti indipendenti per "mostly_verified"
    if verdict == "verified":
        verdict = "mostly_verified"
    confidence = min(confidence, 0.80)

    for c in claims:
        if c.claim_verdict in ("verified", "mostly_verified") and c.source_diversity < 2:
            c.claim_verdict = "mixed"

    overrides.append("OVERRIDE_F8: conservative mode active")
```

---

## G) Strategia di calibration

### G.1 Principio

Le soglie proposte (0.25, 0.30, 0.45, 0.65, ecc.) sono **valori iniziali ragionati** ma devono essere calibrati su dati reali.

### G.2 Dataset di calibrazione

1. **Gold standard manuale**: annotare 50-100 esempi con verdict atteso, per tipologia:
   - 15-20 claim veri e ben documentati
   - 15-20 claim falsi e ben documentati
   - 10-15 claim parzialmente veri
   - 10-15 claim non verificabili
   - 5-10 claim ambigui/misti

2. **Per ogni esempio**, annotare anche:
   - Evidenza diretta attesa
   - Fonti autorevoli attese
   - Contraddizioni attese

### G.3 Processo di calibrazione

```
Step 1: Eseguire la pipeline sui 50-100 esempi
Step 2: Per ogni esempio, registrare tutti gli score intermedi
Step 3: Analizzare la distribuzione degli score per classe di verdict
Step 4: Trovare le soglie che massimizzano la separazione tra classi
Step 5: Verificare che le soglie producano pochi falsi positivi (priority: evitare "verified" su claim falsi)
```

### G.4 Metriche di calibrazione

- **Separation score**: la differenza media tra score di claim veri e claim falsi
- **False verification rate**: percentuale di claim falsi classificati come verified/mostly_verified
- **Abstention rate**: percentuale di claim su cui il sistema produce insufficient_evidence
- **Confidence calibration**: la confidence deve correlare con la probabilità di verdict corretto

### G.5 Cosa calibrare

| Parametro | Dove | Valore iniziale | Come calibrare |
|---|---|---|---|
| Soglie verdict in `claim_verdict()` | D.7 | 0.25, 0.30, 0.60, 0.70 | Grid search su gold standard |
| Soglie truth_score in `document_verdict()` | D.10 | 15, 30, 45, 65, 80 | ROC analysis |
| Pesi in `evidence_quality_score()` | D.2 | 0.30, 0.25, 0.15, 0.15, 0.15 | Sensitivity analysis |
| Soglie confidence gate | D.7 | 0.30, 0.50 | Precision-recall tradeoff |
| Saturazione logaritmica in support/contradiction | D.5 | 0.7 * log1p | Curve fitting su dati reali |
| Override thresholds | F.1-F.8 | Vari | Analisi errori su gold standard |

### G.6 Signal source classification

| Segnale | Tipo | Note per calibrazione |
|---|---|---|
| `domain_institutional_trust` | deterministic heuristic | Richiede manutenzione della lookup table |
| `editorial_quality` | deterministic heuristic | Pesi interni calibrabili su corpus |
| `spam_penalty` | deterministic heuristic | Marker list espandibile |
| `passage_relevance` | model-based | Dipende dalla qualità del modello LLM |
| `stance` | model-based | Accuracy misurabile su gold standard |
| `stance_confidence` | model-based | Richiede validation che correli con accuracy |
| `directness` | model-based | Classificazione 3-class, misurabile |
| `specificity` | model-based | Classificazione 3-class, misurabile |
| `temporal_alignment` | deterministic | Calibrabile su delta date reali |
| `source_independence` | deterministic | Cluster table da mantenere |
| Tutti gli score aggregati | deterministic | Calibrated: soglie derivate da dati |

---

## H) Piano di implementazione incrementale

### Fase 1 — Quick Wins (1-2 giorni)

**H.1.1** Fix bug critico: rimuovere `state.claims = []` da `_build_state()`.
Preservare i claim estratti dal `ClaimDecompositionAgent`.

**H.1.2** Rinominare feature per chiarezza:
- `domain_trust` → `domain_institutional_trust`
- `content_trust` → `editorial_quality`
- `source_reliability` → `source_trust_score`

**H.1.3** Rimuovere double counting da `source_trust_score`:
- Rimuovere `content_trust` dal `pre_score` (già dentro `source_trust_score`)
- Semplificare: `source_trust_score = 0.60 * domain + 0.40 * editorial * (1 - 0.7 * spam)`

**H.1.4** Popolare `partial_verdict` e `partial_score` nei claim della response.
Anche con logica semplificata, i campi devono avere valori reali, non default.

### Fase 2 — Nuovo CrossCheck prompt (2-3 giorni)

**H.2.1** Modificare il prompt di `CrossCheckAnalysisLayer` per chiedere segnali strutturati claim-aware:
- Se ci sono claim, includerli nel prompt
- Chiedere `per_claim` con stance, directness, specificity per ogni (source, claim)
- NON chiedere più truth_score/verdict all'LLM

**H.2.2** Per input `text`: creare claim sintetico `c0` = testo intero.

**H.2.3** Aggiornare fallback deterministico per il nuovo formato.

### Fase 3 — Evidence Quality Score (1-2 giorni)

**H.3.1** Implementare `evidence_quality_score()` in `EvidenceAggregator`.
Combina `source_trust_score` + segnali cross-check deterministicamente.

**H.3.2** Implementare `temporal_alignment()`.

**H.3.3** Aggiornare i record `scored_evidence` con il nuovo schema.

### Fase 4 — Claim-Level Scoring (2-3 giorni)

**H.4.1** Creare `ClaimScoringLayer` come nuovo file in `services/scoring/`.
**H.4.2** Implementare `claim_support_score`, `claim_contradiction_score`.
**H.4.3** Implementare `source_independence`.
**H.4.4** Implementare `claim_confidence` e `claim_verdict`.
**H.4.5** Aggiornare `PipelineState` con nuovi campi claim-level.

### Fase 5 — Verdict Assembly deterministico (2-3 giorni)

**H.5.1** Creare `VerdictAssemblyLayer` come nuovo file.
**H.5.2** Implementare `document_truth_score`, `document_confidence`, `document_verdict`.
**H.5.3** Implementare override rules F.1-F.8.
**H.5.4** Sostituire la logica in `_build_state` con VerdictAssemblyLayer.
**H.5.5** Aggiornare response models per esporre override e nuovi campi.

### Fase 6 — Calibration e testing (2-4 giorni)

**H.6.1** Costruire gold standard di 50-100 esempi.
**H.6.2** Eseguire pipeline e registrare tutti gli score intermedi.
**H.6.3** Calibrare soglie.
**H.6.4** Test di regressione su edge cases.

### Fase 7 — Hardening (ongoing)

**H.7.1** Espandere `WIRE_CLUSTERS` con dati reali.
**H.7.2** Aggiungere content hash deduplication per evidenze identiche.
**H.7.3** Modalità conservative.
**H.7.4** Logging dettagliato per ogni override.

---

## I) Metriche di valutazione

### I.1 Metriche primarie

| Metrica | Definizione | Target |
|---|---|---|
| **Verdict accuracy** | % di verdict corretti su gold standard | > 75% |
| **False verification rate** | % di claim falsi marcati verified/mostly_verified | < 5% |
| **False alarm rate** | % di claim veri marcati false/mostly_false | < 10% |
| **Abstention rate** | % di insufficient_evidence | 15-30% (troppo basso = overconfident, troppo alto = inutile) |

### I.2 Metriche secondarie

| Metrica | Definizione |
|---|---|
| **Confidence calibration** | Correlazione tra confidence e % verdict corretti |
| **Claim coverage** | % di claim per cui esiste almeno 1 evidenza diretta/indiretta |
| **Override frequency** | % di verdicts modificati da override (deve stabilizzarsi, non crescere) |
| **Explanation coherence** | % di casi in cui explanation e verdict sono coerenti (audit manuale) |

### I.3 Metriche di robustezza

| Metrica | Definizione |
|---|---|
| **Tier sensitivity** | Differenza media di truth_score tra tier1 e tier2 per stessi claim |
| **LLM failure resilience** | Accuracy del fallback quando l'LLM è unavailable |
| **Adversarial robustness** | Accuracy su claim costruiti per ingannare (true claim + false context) |

---

## J) Rischi residui e mitigazioni

### J.1 Rischio: l'LLM non estrae segnali strutturati in modo affidabile

**Impatto:** Se `directness`, `specificity`, `stance_confidence` sono rumorosi, il claim-level scoring sarà impreciso.
**Mitigazione:**
- Fallback conservativo: se il parsing fallisce, `directness=contextual`, `specificity=topic_only`
- Il sistema degraderà verso `insufficient_evidence`, non verso falsi verdetti
- Validation continua: confrontare i segnali LLM con annotazioni umane

### J.2 Rischio: soglie non calibrate producono bias sistematici

**Impatto:** Soglie troppo alte → tutto è insufficient_evidence. Soglie troppo basse → falsi verified.
**Mitigazione:**
- Fase 6 (calibrazione) è obbligatoria prima di produzione
- Modalità conservative come safety net
- Logging di tutti gli score intermedi per audit

### J.3 Rischio: WIRE_CLUSTERS incompleti

**Impatto:** Il sistema sovrappesa fonti non indipendenti.
**Mitigazione:**
- Iniziare con cluster noti (ANSA, AP, Reuters)
- Aggiungere content hash similarity: se due fonti hanno > 80% overlap testuale, sono probabilmente lo stesso wire

### J.4 Rischio: claim extraction di bassa qualità

**Impatto:** Se i claim sono rumorosi o non atomici, tutto il claim-level scoring è compromesso.
**Mitigazione:**
- Il claim `c0` (testo intero per `text` input) bypassa il problema
- Per URL: se tutti i claim hanno checkability < 0.50, fallback a modalità whole-text
- Il ClaimDecompositionAgent ha già un fallback sentence-based

### J.5 Rischio: il sistema diventa troppo conservativo

**Impatto:** Troppi `insufficient_evidence`, il sistema perde utilità.
**Mitigazione:**
- Monitorare `abstention_rate` (target: 15-30%)
- Se troppo alto, rilassare soglie di coverage/directness
- La modalità "standard" (non conservative) deve restare bilanciata

### J.6 Rischio: performance/latenza

**Impatto:** Il nuovo prompt cross-check è più complesso (include claim).
**Mitigazione:**
- Il prompt è leggermente più lungo ma chiede output più strutturato, non più iterazioni
- `ClaimScoringLayer` e `VerdictAssemblyLayer` sono pure computazioni, latenza trascurabile
- Il collo di bottiglia resta la chiamata LLM, che è singola come oggi

---

## Appendice: Campi PipelineState da aggiungere/modificare

```python
# Nuovi campi suggeriti per PipelineState

# Dopo Evidence Analysis (estesi)
claim_evidence_matrix: list[dict[str, Any]]  # Per coppia (claim, source): tutti i segnali
# Formato: [{"claim_id": "c1", "source_id": "s1", "stance": ..., "directness": ..., ...}]

# Dopo Claim Scoring (NUOVO)
claim_scores: list[dict[str, Any]]  # Per claim: support, contradiction, confidence, verdict
# Formato: [{"claim_id": "c1", "support": 0.75, "contradiction": 0.1, "confidence": 0.68, "verdict": "mostly_verified", ...}]

# Dopo Verdict Assembly (estesi)
verdict_overrides: list[str]        # Lista di override applicate (per auditability)
coverage_ratio: float               # Claim coperti / totali
mixedness: float                    # Varianza dei claim verdicts
document_scoring_details: dict      # Tutti i calcoli intermedi per debug
```

## Appendice: Strategia per input `text` (senza claim decomposition)

Per input di tipo `text`, il sistema non ha claim estratti.
Strategia:

1. Creare un **claim sintetico** `c0`:
   ```python
   c0 = {
       "id": "c0",
       "claim": normalized_text[:500],
       "type": "other",
       "checkability_score": 0.50,
       "partial_verdict": "insufficient_evidence",
       "partial_score": 0.0,
   }
   ```

2. Il CrossCheck valuta tutte le fonti contro `c0`.

3. Il ClaimScoringLayer produce un singolo claim score.

4. Il VerdictAssemblyLayer funziona identicamente (1 solo claim → aggregazione banale).

Questo unifica il flusso senza bisogno di branch condizionali.

## Appendice: Anti double-counting checklist

| Score | Dipende da | NON dipende da (a differenza di oggi) |
|---|---|---|
| `source_trust_score` | domain_institutional_trust, editorial_quality, spam | ~~local_relevance~~, ~~tavily_score~~ |
| `evidence_quality_score` | passage_relevance, directness, specificity, stance_confidence, source_trust, temporal_alignment | ~~claim_relevance misto~~, ~~tavily_score~~ |
| `claim_support_score` | evidence_quality_score delle evidenze supporting | ~~source_reliability duplicato~~ |
| `claim_confidence` | coverage, diversity, independence, directness, agreement_clarity, checkability | ~~raw LLM confidence~~ |
| `document_truth_score` | claim support/contradiction scores | ~~truth_score LLM~~ |
| `document_confidence` | claim confidences, coverage_ratio, tier, mixedness | ~~confidence_score LLM~~ |
| `verdict` | document_truth_score, document_confidence, overrides | ~~verdict LLM~~ |
