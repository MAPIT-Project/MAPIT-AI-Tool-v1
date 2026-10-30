// Run on the new research graph after ingestion and author extraction.
MATCH (n)
WHERE any(label IN labels(n) WHERE label IN [
  'Project', 'Organization', 'Publication', 'Deliverable', 'PubAuthor', 'Call',
  'ReportSummary', 'Topic', 'LegalBasis', 'EuroSciVoc', 'PolicyPriority', 'WebItem', 'WebLink'
])
SET n.NodeType = head([label IN labels(n) WHERE label <> 'SemanticNode']),
    n:SemanticNode,
    n.EmbeddingText = trim(
      coalesce(toString(n.title), '') + ' ' + coalesce(toString(n.acronym), '') + ' ' +
      coalesce(toString(n.objective), '') + ' ' + coalesce(toString(n.description), '') + ' ' +
      coalesce(toString(n.name), '') + ' ' + coalesce(toString(n.country), '') + ' ' +
      coalesce(toString(n.shortName), '') + ' ' + coalesce(toString(n.affiliation), '') + ' ' +
      coalesce(toString(n.topic_destination), '') + ' ' + coalesce(toString(n.topic_description), '')
    );

CREATE FULLTEXT INDEX semanticNodeTextIndex IF NOT EXISTS
FOR (n:SemanticNode) ON EACH [n.EmbeddingText];

CREATE VECTOR INDEX text_embeddings_index IF NOT EXISTS
FOR (n:SemanticNode) ON (n.SentenceTransformerEmbedding)
OPTIONS {indexConfig: {`vector.dimensions`: 384, `vector.similarity_function`: 'cosine'}};

SHOW INDEXES;
