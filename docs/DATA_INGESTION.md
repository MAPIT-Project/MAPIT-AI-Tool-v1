# Research data ingestion

These commands are based on the supplied operational notes and checked against the
retained scripts. Run them against your new databases. They write data and can be
expensive; they were not executed during repository preparation.

## Dependencies and source files

Activate the root `.venv`, then from the repository root:

```bash
python -m pip install -r scripts/requirements.txt
python -m pip install -r scripts/requirements_scraper.txt
```

Scraping uses Selenium plus Chrome and webdriver-manager; install Chrome.
The root `.env` supplies database credentials. Do not copy old credentials into Git.

Place semicolon-delimited CORDIS exports under `scripts/csv/`:
`project.csv`, `organization.csv`, `projectPublications.csv`,
`projectDeliverables.csv`, `topics.csv`, `legalBasis.csv`, `euroSciVoc.csv`,
`policyPriorities.csv`, `reportSummaries.csv`, `webItem.csv`, `webLink.csv`.
The importer also reads `scripts/csv/projects-xml/`, `scripts/Manuals/` (capital M)
and `scripts/pdfs/`. Supply authorized copies of the source datasets yourself.
The source notes' informal directory descriptions have been replaced here with the
paths actually used by `ingest_data.py`.

## CORDIS and documents

Run from the repository root:

```bash
python scripts/ingest_data.py --targets neo4j qdrant elasticsearch --batch-size 500 --immediate-embedding --enable-chunking --chunk-size 500 --chunk-overlap 100
```

This populates project/document stores including `cordis_projects`, `manuals` and
`pdfs`. Start with a small input dataset before processing a large PDF archive.
The importer has a destructive `--delete` option; it is intentionally absent above.

## Funding calls

Run these commands from `scripts/`:

```bash
cd scripts
python get_all_call_links.py -o calls_links.json
python scrape_call_details.py calls_links.json calls_details.json
python save_call_htmls.py calls_links.json calls_htmls
python ingest_calls_to_neo4j.py calls_details.json
python ingest_html_to_qdrant.py --html-dir calls_htmls
python ingest_html_to_elasticsearch.py --html-dir calls_htmls
cd ..
```

Scrapers depend on the external portal's current page structure. Check downloaded
records before ingestion; a successful browser run does not guarantee completeness.
Generated JSON, HTML and extraction logs are not source files and are ignored.

## Authors, semantic text and indexes

From the root, extract publication authors:

```bash
python test_scripts/neo4j_extract_authors2.py
```

In Neo4j Browser, execute the statements in `docs/neo4j-setup.cypher` on your new
graph. They label domain nodes, populate `NodeType` and `EmbeddingText`, and create
the full-text and 384-dimensional sentence-vector indexes used by the backend.
Then run:

```bash
python test_scripts/add_embedding2.py
```

The utility fills missing `SentenceTransformerEmbedding` values using
`all-MiniLM-L6-v2`. Existing embeddings are not refreshed automatically after text
changes. Verify index state with `SHOW INDEXES` and a known project search.

## Optional graph embeddings and communities

`train_graph_nn_semantic_ultra_safe_improved.py` and
`community_labels_calculation.py` are retained operational tools, not required for
basic chat. Install `scripts/requirements_graph.txt` in a separate environment if
using the graph trainer. Review its configuration and resource needs before running.
It writes graph/model outputs, which must stay outside Git. Community labels use
Ollama through `OLLAMA_URL` and `OLLAMA_MODEL`.

The backend also refers to `SemanticGNNEmbedding` and `graph_embeddings_index`.
Create a graph-vector index only after verifying the trainer's actual output
property and dimension; do not assume sentence and graph embeddings are compatible.
A graph trained with a different model/dimension cannot reuse the sentence index.
GDS/APOC-dependent partner features require those Neo4j plugins and populated graph
relationships. Their end-to-end results have not been validated in this cleanup.
