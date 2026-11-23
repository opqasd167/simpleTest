# "real" corpus

Three public Hang Seng Bank PDFs: credit card minimum payment terms, a privacy notice, and a bilingual
(Traditional Chinese / English) maintenance schedule. They test what synthetic documents cannot:
real layouts (tables flattened by text extraction), bilingual text, and Chinese questions about English
documents (cross-lingual retrieval needs a multilingual embedding model).

Questions and expected answers in dataset.jsonl were written by reading the documents. The CN* cases
check cross-lingual retrieval; with the default English-only embedding model they are expected to fail
retrieval.
