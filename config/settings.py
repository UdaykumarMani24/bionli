import os
from typing import Dict, Any

class Settings:
    """Application settings with real database configurations"""
    
    # Database configurations
    DATABASES = {
        'uniprot': {
            'type': 'sparql',
            'endpoint': 'https://sparql.uniprot.org/sparql',
            'timeout': 30
        },
        'ncbi': {
            'type': 'api',
            'base_url': 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/',
            'api_key': os.getenv('NCBI_API_KEY', '')
        },
        'ensembl': {
            'type': 'api',
            'base_url': 'https://rest.ensembl.org/',
            'timeout': 30
        },
        'biomodels': {
            'type': 'api',
            'base_url': 'https://www.ebi.ac.uk/biomodels/',
            'timeout': 30
        }
    }
    
    # NLP Settings
    NLP_MODEL = "en_core_sci_sm"  # Scientific model
    SPACY_MODEL_SIZE = "sm"
    
    # Application Settings
    MAX_RESULTS = 50
    QUERY_TIMEOUT = 60
    CACHE_DURATION = 3600  # 1 hour
    
    # BioTools Integration
    BLAST_ENDPOINT = "https://blast.ncbi.nlm.nih.gov/Blast.cgi"
    EBI_TOOLS_ENDPOINT = "https://www.ebi.ac.uk/Tools/services/rest/"
    
    # Logging
    LOG_LEVEL = "INFO"

settings = Settings()