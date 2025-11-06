
# <font size=12px> BioNLI: A Semantic Natural Language Interface for Bioinformatics Databases</font>

# <font colore=blue><b>Project Overview</font></b>

BioNLI (Bio-Natural Language Interface) is a robust, deterministic, and highly accurate semantic framework designed to bridge the gap between natural language queries and complex bioinformatics databases and APIs (such as NCBI Entrez and Ensembl REST).

In the life sciences, data retrieval is often constrained by complex database schemas and specialized query languages. BioNLI solves this by using advanced NLP, biological pattern matching, and integrated Bio-Ontologies (Gene Ontology, PRO, ChEBI, and NCBI Taxonomy) to accurately parse user questions and generate precise, executable API queries.

This repository contains the full source code, deployment files, and necessary test data for the BioNLI system.

# <b> Key Features</b>

Semantic Query Resolution: Translates complex queries like "find mouse homologs of TP53" or "show immune genes that interact with viruses" into structured database API calls.

Ontology-Driven Inference: Leverages a Bidirectional Transformer Layer 2 (BTL2) architecture integrated with Bio-Ontologies to manage semantic ambiguities and resolve inferential questions.

High Accuracy: Achieved 89% accuracy in entity recognition and successfully resolved 92% of all evaluation inquiries.

Deterministic and Traceable: Unlike general Large Language Models (LLMs), BioNLI provides traceable results directly verified against authoritative public APIs.



# <b>Architecture and Structure</b>

The BioNLI system is built on a modular Python architecture designed for maintainability and scalability.
<pre>
bio_nli/
├── app.py                      # Main entry point for the Flask web application
├── core/                       # Core NLP, query logic, and service connectors
│   ├── nlp_processor.py        # Handles spaCy models, entity recognition, and semantic parsing
│   ├── query_builder.py        # Constructs API payloads and database queries (e.g., Entrez, Ensembl)
│   ├── database_connector.py   # Interfaces with internal configuration (databases.yaml)
│   ├── bio_services.py         # Abstracts API calls to external services (NCBI, Ensembl)
│   └── ontology_manager.py     # Manages ontology loading and inference logic (GO, PRO, ChEBI, etc.)
├── config/                     # Configuration files and settings
│   ├── settings.py             # General application environment settings
│   └── databases.yaml          # Database connection strings and schemas
├── models/                     # Custom machine learning models and data
│   ├── entity_detector.py      # Custom models for biological entity detection
│   └── query_classifier.py     # Classification logic for query types (e.g., homology, interaction)
├── api/                        # REST API endpoint definitions
│   └── routes.py               # Defines all /api/ endpoints for the application
├── static/                     # Web assets (CSS/JS)
├── templates/                  # Jinja2 HTML templates for the web interface
├── requirements.txt            # Python dependencies
├── Dockerfile                  # Instructions for building the Docker image
└── README.md                   # This file
</pre>

# <b> Getting Started</b>

Follow these instructions to get a copy of the project up and running on your local machine.

<b>Prerequisites</b>

You need Docker and Docker Compose installed on your system.

# <b>1. Clone the Repository</b>
<pre>
git clone [https://github.com/YourGitHubOrg/bio_nli.git](https://github.com/YourGitHubOrg/bionli.git)
cd bionli
</pre>


# <b>2. Configure Environment</b>

Review and update the settings in config/settings.py and config/databases.yaml as needed, particularly for any private database connections or API keys (though the system primarily relies on public APIs).

# <b>3. Build and Run with Docker</b>

The easiest way to run BioNLI is using the provided Dockerfile.

# Build the Docker image (this may take a few minutes for dependency installation)
docker build -t bionli-app .

# Run the container (maps container port 5000 to host port 8000)
docker run -d -p 8000:5000 --name bionli-instance bionli-app


# <b>4. Access the Application</b>

Once the container is running, the BioNLI web interface will be available at:

http://localhost:8000

# <b> Contributing</b>

Contributions are welcome! If you have suggestions for improvements, new ontology integrations, or bug fixes, please open an issue or submit a pull request.


# <b> Contact</b>

For support or collaboration, please contact:

Arunachalam Jothi: arunachalam@bioinfo.sastra.edu

Udayakumar Mani: uthay@bioinfo.sastra.edu
