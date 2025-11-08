from typing import Dict, List, Any, Optional
from dataclasses import dataclass

@dataclass
class QueryPayload:
    """Standardized query payload structure"""
    query_type: str
    entities: List[Dict[str, Any]]
    concepts: Dict[str, List[str]]
    parameters: Dict[str, Any]
    source_priority: List[str]
    max_results: int = 10

class BioQueryBuilder:
    """Builds standardized query payloads for biological databases"""
    
    def __init__(self):
        self.source_endpoints = {
            'ncbi': {
                'gene': 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi',
                'summary': 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi',
                'homologene': 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi'
            },
            'ensembl': {
                'base': 'https://rest.ensembl.org/',
                'lookup': 'lookup/id/',
                'homology': 'homology/id/'
            },
            'uniprot': {
                'search': 'https://rest.uniprot.org/uniprotkb/search'
            }
        }
    
    def build_gene_query(self, gene_name: str, organism: str = "human") -> QueryPayload:
        """Build query for gene information"""
        return QueryPayload(
            query_type='gene_info',
            entities=[{'type': 'gene', 'text': gene_name, 'normalized': gene_name.upper()}],
            concepts={'gene_function': ['function', 'expression']},
            parameters={
                'organism': organism,
                'databases': ['ncbi', 'ensembl'],
                'fields': ['symbol', 'name', 'summary', 'function', 'location']
            },
            source_priority=['ncbi', 'ensembl']
        )
    
    def build_homology_query(self, gene_name: str, target_species: str, source_species: str = "human") -> QueryPayload:
        """Build query for homology search"""
        return QueryPayload(
            query_type='homology',
            entities=[
                {'type': 'gene', 'text': gene_name, 'normalized': gene_name.upper()},
                {'type': 'species', 'text': target_species, 'normalized': self._normalize_species(target_species)}
            ],
            concepts={'homology': ['ortholog', 'homolog', 'equivalent']},
            parameters={
                'source_species': source_species,
                'target_species': target_species,
                'homology_type': 'ortholog',
                'databases': ['ncbi', 'ensembl']
            },
            source_priority=['ensembl', 'ncbi']
        )
    
    def build_sequence_query(self, gene_name: str, sequence_type: str = "genomic") -> QueryPayload:
        """Build query for sequence retrieval"""
        return QueryPayload(
            query_type='sequence',
            entities=[{'type': 'gene', 'text': gene_name, 'normalized': gene_name.upper()}],
            concepts={'sequence': ['dna', 'protein', 'nucleotide']},
            parameters={
                'sequence_type': sequence_type,
                'formats': ['fasta', 'genbank'],
                'databases': ['ncbi', 'ensembl']
            },
            source_priority=['ncbi', 'ensembl']
        )
    
    def build_pathway_query(self, gene_name: str) -> QueryPayload:
        """Build query for pathway information"""
        return QueryPayload(
            query_type='pathway',
            entities=[{'type': 'gene', 'text': gene_name, 'normalized': gene_name.upper()}],
            concepts={'pathway': ['signaling', 'metabolic', 'regulatory']},
            parameters={
                'pathway_sources': ['KEGG', 'Reactome', 'WikiPathways'],
                'include_interactions': True,
                'include_compounds': True
            },
            source_priority=['internal']  # Using internal BioServices
        )
    
    def build_interaction_query(self, gene_name: str, interaction_type: str = "protein-protein") -> QueryPayload:
        """Build query for molecular interactions"""
        return QueryPayload(
            query_type='interaction',
            entities=[{'type': 'gene', 'text': gene_name, 'normalized': gene_name.upper()}],
            concepts={'interaction': ['binding', 'complex', 'association']},
            parameters={
                'interaction_type': interaction_type,
                'sources': ['STRING', 'BioGRID', 'IntAct'],
                'confidence_threshold': 0.7
            },
            source_priority=['internal']  # Using internal services
        )
    
    def build_concept_query(self, parsed_query: Dict[str, Any]) -> QueryPayload:
        """Build query based on NLP parsing results"""
        query_type = parsed_query['query_type']
        entities = parsed_query['entities']
        concepts = parsed_query['concepts']
        
        # Extract primary gene entity
        primary_gene = None
        if 'gene' in entities and entities['gene']:
            primary_gene = entities['gene'][0]['text']
        
        # Extract species if present
        target_species = "human"
        if 'species' in entities and entities['species']:
            target_species = self._normalize_species(entities['species'][0]['text'])
        
        # Route based on query type
        if query_type == 'homology' and primary_gene:
            return self.build_homology_query(primary_gene, target_species)
        elif query_type == 'sequence' and primary_gene:
            return self.build_sequence_query(primary_gene)
        elif query_type == 'function' and primary_gene:
            return self.build_gene_query(primary_gene)
        elif 'pathway' in concepts and primary_gene:
            return self.build_pathway_query(primary_gene)
        elif 'interaction' in concepts and primary_gene:
            return self.build_interaction_query(primary_gene)
        else:
            # Default to gene query
            return self.build_gene_query(primary_gene or 'TP53')  # Fallback
    
    def build_ncbi_payload(self, payload: QueryPayload) -> Dict[str, Any]:
        """Convert to NCBI API payload"""
        if payload.query_type == 'gene_info':
            gene_entity = payload.entities[0]['text']
            return {
                'db': 'gene',
                'term': f"{gene_entity}[Gene Name] AND {payload.parameters['organism']}[Organism]",
                'retmode': 'json',
                'retmax': payload.max_results
            }
        elif payload.query_type == 'homology':
            gene_entity = payload.entities[0]['text']
            return {
                'dbfrom': 'gene',
                'db': 'gene',
                'term': f"{gene_entity}[Gene Name] AND {payload.parameters['target_species']}[Organism]",
                'retmode': 'json'
            }
        
        return {}
    
    def build_ensembl_payload(self, payload: QueryPayload) -> Dict[str, Any]:
        """Convert to Ensembl API payload"""
        # Ensembl typically uses REST endpoints rather than parameter payloads
        return {
            'content-type': 'application/json',
            'headers': {'Accept': 'application/json'}
        }
    
    def _normalize_species(self, species_name: str) -> str:
        """Normalize species names"""
        species_map = {
            'human': 'homo sapiens',
            'mouse': 'mus musculus', 
            'rat': 'rattus norvegicus',
            'mus': 'mus musculus',
            'rattus': 'rattus norvegicus',
            'yeast': 'saccharomyces cerevisiae',
            'ecoli': 'escherichia coli'
        }
        return species_map.get(species_name.lower(), species_name.lower())
    
    def validate_payload(self, payload: QueryPayload) -> bool:
        """Validate query payload before execution"""
        if not payload.entities:
            return False
        
        if payload.query_type in ['gene_info', 'homology', 'sequence']:
            if not any(entity['type'] == 'gene' for entity in payload.entities):
                return False
        
        if payload.max_results > 50:  # Safety limit
            payload.max_results = 50
            
        return True
