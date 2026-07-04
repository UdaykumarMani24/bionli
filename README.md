# BioNLI: A Retrieval-Grounded Natural Language Interface for Biological Databases

## Project Overview

BioNLI is a natural language interface that answers biological questions by querying live public databases directly, rather than generating text from model parameters. It integrates eight authoritative resources — NCBI Entrez, Ensembl REST, UniProt, STRING, Reactome, DisGeNET, EMBL-EBI Ontology Lookup Service (OLS), and RCSB PDB together with AlphaFold DB — behind a three-stage pipeline: query understanding, Gene Ontology-based semantic enrichment, and multi-source API execution.

Because every answer is built entirely from retrieved database records, with a source URL and retrieval timestamp attached to each statement, BioNLI avoids the hallucination risk associated with purely generative question-answering systems, at the cost of a more constrained answer format.

This repository contains the full source code and the evaluation query set for the BioNLI system.

## Key Features

- **HGNC-anchored entity recognition**: gene mentions are resolved through a four-stage cascade (direct HGNC symbol match, synonym/previous-symbol lookup, a conditional BioBERT fallback, and a regex fallback covering sixteen high-priority symbols).
- **Two-layer intent classification**: a keyword-weighted scorer assigns one of ten broad categories, followed by a fine-grained intent router (regex pattern matching with additive scoring) that selects one of fifteen question types and the data source(s) to query.
- **Gene Ontology enrichment**: biological process and pathway entities are expanded with GO synonyms and parent terms (via `owlready2`) before the relevant APIs are called.
- **Fully traceable answers**: every response section carries a direct source URL and retrieval timestamp back to the primary database record.
- **Proof-of-concept evaluation**: 90% accuracy on a curated set of 30 gene-centric queries spanning six question categories (gene function, homology, chromosomal location, disease association, pathway membership, concept definition).

This is a research prototype evaluated on a small, developer-constructed query set. It has not yet been benchmarked against an independent dataset or evaluated in a user study; see the accompanying manuscript's Limitations section for details.

## Architecture and Structure

The system is a Flask application with the core logic organized as a `core` package:

```
bionli/
├── app.py                      # Flask application: /, /api/ask, /api/stats, /api/health
├── core/
│   ├── hgnc_loader.py          # Loads and indexes HGNC-approved gene symbols
│   ├── semantic_parser.py      # Entity recognition cascade + first-layer intent classifier
│   ├── intent_router.py        # Fine-grained intent classification and data-source routing
│   ├── structured_query.py     # Shared data classes for entities, intents, structured queries
│   ├── ontology_integration.py # Gene Ontology loading and enrichment
│   ├── data_sources.py         # NCBI, Ensembl, STRING, Reactome, DisGeNET, OLS, UniProt integrations
│   ├── pdb_source.py           # Structure queries (RCSB PDB / AlphaFold DB)
│   └── qa_engine.py            # Orchestration: routing, parallel API calls, caching, formatting
├── templates/
│   └── index.html              # Query submission interface
├── requirements.txt
└── README.md
```

## Getting Started

### Prerequisites

- Python 3.9+
- pip

### 1. Clone the repository

```
git clone https://github.com/UdaykumarMani24/bionli.git
cd bionli
```

### 2. Install dependencies

```
pip install -r requirements.txt
```

### 3. Configure environment variables

```
export NCBI_EMAIL=your_email@example.com
export USE_GPU=False
export PORT=5000
```

### 4. Run the application

```
python app.py
```

The web interface will be available at `http://localhost:5000`.

## API

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | Query submission interface |
| `/api/ask` | POST | Submit a natural language question; returns a formatted, source-attributed answer |
| `/api/stats` | GET | System statistics (indexed gene symbols, GO terms, data sources) |
| `/api/health` | GET | Health check |

## Known Limitations

- The evaluation set (30 queries) was constructed by the developers and covers only canonical, unambiguous gene symbols; it should be read as a functional proof of concept rather than a statistically powered benchmark.
- The BioBERT fallback carries an untrained classification head and currently functions only as a contextual encoder; it did not contribute any entities to the evaluation set.
- Multi-gene comparison queries are intended to be resolved independently per gene and merged; this path is under active verification against the current codebase.

See the accompanying manuscript for a full discussion of limitations and planned extensions.

## Contributing

Contributions are welcome. Please open an issue or submit a pull request for bug fixes, additional data-source integrations, or evaluation improvements.

## Contact

Udayakumar Mani: uthay@bioinfo.sastra.edu
