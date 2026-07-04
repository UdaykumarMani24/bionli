"""
Structured Query Representation - Addresses Reviewer Concern #1
Provides a clean intermediate representation between NL and database queries.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Set
from enum import Enum, auto
import json
import hashlib
from datetime import datetime


class Intent(Enum):
    """Query intents for biological questions."""
    FUNCTION = auto()
    PATHWAY = auto()
    INTERACTION = auto()
    LOCATION = auto()
    DISEASE_ASSOCIATION = auto()
    EXPRESSION = auto()
    SEQUENCE = auto()
    STRUCTURE = auto()
    HOMOLOGY = auto()
    REGULATION = auto()
    
    @classmethod
    def from_string(cls, s: str) -> 'Intent':
        """Convert string to Intent with error handling."""
        mapping = {
            'function': cls.FUNCTION,
            'pathway': cls.PATHWAY,
            'interaction': cls.INTERACTION,
            'location': cls.LOCATION,
            'disease': cls.DISEASE_ASSOCIATION,
            'expression': cls.EXPRESSION,
            'sequence': cls.SEQUENCE,
            'structure': cls.STRUCTURE,
            'homology': cls.HOMOLOGY,
            'regulation': cls.REGULATION,
        }
        return mapping.get(s.lower(), cls.FUNCTION)
    
    def to_sparql_query_type(self) -> str:
        """Map intent to SPARQL query type for knowledge graph querying."""
        mapping = {
            Intent.FUNCTION: """
                SELECT DISTINCT ?function ?function_label
                WHERE {
                    ?gene rdfs:label ?gene_name .
                    ?gene obo:RO_0000087 ?function .
                    ?function rdfs:label ?function_label .
                }
            """,
            Intent.PATHWAY: """
                SELECT DISTINCT ?pathway ?pathway_label
                WHERE {
                    ?gene rdfs:label ?gene_name .
                    ?gene obo:RO_0002333 ?pathway .
                    ?pathway rdfs:label ?pathway_label .
                }
            """,
            Intent.INTERACTION: """
                SELECT DISTINCT ?interactor ?interactor_label
                WHERE {
                    ?gene rdfs:label ?gene_name .
                    ?gene obo:RO_0002436 ?interactor .
                    ?interactor rdfs:label ?interactor_label .
                }
            """,
            Intent.HOMOLOGY: """
                SELECT DISTINCT ?ortholog ?ortholog_label ?species
                WHERE {
                    ?gene rdfs:label ?gene_name .
                    ?gene obo:RO_0002326 ?ortholog .
                    ?ortholog rdfs:label ?ortholog_label .
                    ?ortholog obo:RO_0002162 ?species .
                    ?species rdfs:label ?species_label .
                }
            """,
        }
        return mapping.get(self, """
            SELECT DISTINCT ?result ?result_label
            WHERE {
                ?subject rdfs:label ?subject_label .
                ?subject ?predicate ?result .
                ?result rdfs:label ?result_label .
            }
        """)
    
    def to_natural_language(self) -> str:
        """Convert intent to natural language description."""
        mapping = {
            Intent.FUNCTION: "biological function",
            Intent.PATHWAY: "signaling pathway",
            Intent.INTERACTION: "protein-protein interaction",
            Intent.LOCATION: "subcellular localization",
            Intent.DISEASE_ASSOCIATION: "disease association",
            Intent.EXPRESSION: "gene expression pattern",
            Intent.SEQUENCE: "sequence information",
            Intent.STRUCTURE: "structural information",
            Intent.HOMOLOGY: "homologous genes",
            Intent.REGULATION: "regulatory relationships",
        }
        return mapping.get(self, "biological information")


class EntityType(Enum):
    """Types of biological entities with ontology mappings."""
    GENE = auto()
    PROTEIN = auto()
    DISEASE = auto()
    PATHWAY = auto()
    CHEMICAL = auto()
    ORGANISM = auto()
    CELL_TYPE = auto()
    TISSUE = auto()
    PHENOTYPE = auto()
    PROCESS = auto()
    
    def to_ontology_prefix(self) -> str:
        """Map entity type to ontology prefix for SPARQL queries."""
        prefixes = {
            EntityType.GENE: "ncbigene",
            EntityType.PROTEIN: "uniprot",
            EntityType.DISEASE: "doid",
            EntityType.PATHWAY: "reactome",
            EntityType.CHEMICAL: "chebi",
            EntityType.ORGANISM: "ncbitaxon",
            EntityType.CELL_TYPE: "cl",
            EntityType.TISSUE: "uberon",
            EntityType.PHENOTYPE: "hp",
            EntityType.PROCESS: "go",
        }
        return prefixes.get(self, "obo")
    
    def to_ols_url(self) -> str:
        """Get OLS search URL for this entity type."""
        base = "https://www.ebi.ac.uk/ols/api/ontologies"
        mapping = {
            EntityType.GENE: f"{base}/ncbigene",
            EntityType.PROTEIN: f"{base}/pr",
            EntityType.DISEASE: f"{base}/doid",
            EntityType.PATHWAY: f"{base}/reactome",
            EntityType.CHEMICAL: f"{base}/chebi",
            EntityType.ORGANISM: f"{base}/ncbitaxon",
            EntityType.PROCESS: f"{base}/go",
        }
        return mapping.get(self, f"{base}/go")


@dataclass
class Entity:
    """Represents a biological entity with full ontology linking."""
    text: str
    entity_type: EntityType
    ontology_id: Optional[str] = None
    ontology_iri: Optional[str] = None
    confidence: float = 1.0
    synonyms: List[str] = field(default_factory=list)
    expanded_terms: List[str] = field(default_factory=list)
    definitions: List[str] = field(default_factory=list)
    parents: List[str] = field(default_factory=list)
    children: List[str] = field(default_factory=list)
    start_char: int = 0
    end_char: int = 0
    source: str = "semantic_parser"
    
    def to_dict(self) -> dict:
        return {
            'text': self.text,
            'type': self.entity_type.name,
            'ontology_id': self.ontology_id,
            'ontology_iri': self.ontology_iri,
            'confidence': self.confidence,
            'synonyms': self.synonyms,
            'expanded_terms': self.expanded_terms,
            'definitions': self.definitions,
            'parents': self.parents,
            'children': self.children,
            'source': self.source
        }
    
    def to_sparql_term(self) -> str:
        """Convert entity to SPARQL term for querying."""
        if self.ontology_id:
            if ':' in self.ontology_id:
                return self.ontology_id
            return f"{self.entity_type.to_ontology_prefix()}:{self.ontology_id}"
        return f'"{self.text}"'
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2)
    
    def __hash__(self):
        return hash((self.text.lower(), self.entity_type, self.ontology_id))
    
    def __eq__(self, other):
        if not isinstance(other, Entity):
            return False
        return self.text.lower() == other.text.lower() and self.entity_type == other.entity_type


@dataclass
class StructuredQuery:
    """Complete intermediate representation with SPARQL generation."""
    original_question: str
    intent: Intent
    entities: List[Entity]
    constraints: Dict[str, Any] = field(default_factory=dict)
    relations: List[Dict[str, Any]] = field(default_factory=list)
    upper_ontology_types: List[str] = field(default_factory=list)
    query_hash: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    expanded_terms: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Generate query hash for caching."""
        self.query_hash = hashlib.md5(
            f"{self.intent.name}:{','.join(e.text for e in self.entities)}".encode()
        ).hexdigest()
    
    def to_dict(self) -> dict:
        return {
            'original_question': self.original_question,
            'intent': self.intent.name,
            'entities': [e.to_dict() for e in self.entities],
            'constraints': self.constraints,
            'relations': self.relations,
            'upper_ontology_types': self.upper_ontology_types,
            'query_hash': self.query_hash,
            'created_at': self.created_at,
            'expanded_terms': self.expanded_terms
        }
    
    def to_json(self) -> str:
        """Convert to formatted JSON string."""
        return json.dumps(self.to_dict(), indent=2)
    
    def to_sparql(self, knowledge_graph: str = "bio2rdf") -> str:
        """
        Generate SPARQL query from structured representation.
        
        Args:
            knowledge_graph: Target knowledge graph (bio2rdf, wikidata, etc.)
            
        Returns:
            Complete SPARQL query string
        """
        # Define common prefixes
        prefixes = {
            "bio2rdf": """
                PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                PREFIX owl: <http://www.w3.org/2002/07/owl#>
                PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
                PREFIX ncbigene: <http://identifiers.org/ncbigene/>
                PREFIX uniprot: <http://purl.uniprot.org/core/>
                PREFIX go: <http://purl.obolibrary.org/obo/GO_>
                PREFIX doid: <http://purl.obolibrary.org/obo/DOID_>
                PREFIX chebi: <http://purl.obolibrary.org/obo/CHEBI_>
                PREFIX reactome: <http://identifiers.org/reactome/>
                PREFIX obo: <http://purl.obolibrary.org/obo/>
                PREFIX oboInOwl: <http://www.geneontology.org/formats/oboInOwl#>
            """,
            "wikidata": """
                PREFIX wd: <http://www.wikidata.org/entity/>
                PREFIX wdt: <http://www.wikidata.org/prop/direct/>
                PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            """
        }
        
        prefix_str = prefixes.get(knowledge_graph, prefixes["bio2rdf"])
        
        if not self.entities:
            return prefix_str + "\nSELECT ?result WHERE { }"
        
        # Build WHERE clause
        where_clauses = []
        select_vars = set()
        
        for i, entity in enumerate(self.entities):
            var_name = f"?entity_{i}"
            where_clauses.append(f"  {var_name} rdfs:label \"{entity.text}\" .")
            
            if self.intent == Intent.FUNCTION:
                where_clauses.append(f"  {var_name} obo:RO_0000087 ?function .")
                select_vars.add("?function")
                where_clauses.append("  ?function rdfs:label ?function_label .")
                select_vars.add("?function_label")
                
            elif self.intent == Intent.PATHWAY:
                where_clauses.append(f"  {var_name} obo:RO_0002333 ?pathway .")
                select_vars.add("?pathway")
                where_clauses.append("  ?pathway rdfs:label ?pathway_label .")
                select_vars.add("?pathway_label")
                
            elif self.intent == Intent.INTERACTION:
                where_clauses.append(f"  {var_name} obo:RO_0002436 ?interactor .")
                select_vars.add("?interactor")
                where_clauses.append("  ?interactor rdfs:label ?interactor_label .")
                select_vars.add("?interactor_label")
                
            elif self.intent == Intent.HOMOLOGY:
                where_clauses.append(f"  {var_name} obo:RO_0002326 ?ortholog .")
                select_vars.add("?ortholog")
                where_clauses.append("  ?ortholog rdfs:label ?ortholog_label .")
                select_vars.add("?ortholog_label")
                where_clauses.append("  ?ortholog obo:RO_0002162 ?species .")
                select_vars.add("?species")
                where_clauses.append("  ?species rdfs:label ?species_label .")
                select_vars.add("?species_label")
        
        # Add constraints
        if 'organism' in self.constraints:
            organism = self.constraints['organism']
            where_clauses.append(f"  ?gene ncbitaxon:in_taxon ncbitaxon:{organism} .")
        
        # Add ontology expansion terms
        if self.expanded_terms:
            for term in self.expanded_terms[:5]:  # Limit to 5 expanded terms
                where_clauses.append(f"  OPTIONAL {{ ?subject rdfs:label \"{term}\" . }}")
        
        # Build SELECT clause
        if not select_vars:
            select_vars.add("?result")
        
        select_clause = "SELECT DISTINCT " + " ".join(sorted(select_vars))
        
        # Build final query
        query = f"""
        {prefix_str}
        
        {select_clause}
        WHERE {{
        {chr(10).join(where_clauses)}
        }}
        LIMIT 100
        """
        
        return query.strip()
    
    def to_sql(self, schema: str = "bioportal") -> str:
        """
        Generate SQL query for relational database schemas.
        
        Args:
            schema: Database schema (bioportal, uniprot, etc.)
            
        Returns:
            SQL query string
        """
        if schema == "bioportal":
            # BioPortal schema example
            return f"""
            SELECT * FROM concepts
            WHERE concept_name IN ({', '.join([f"'{e.text}'" for e in self.entities])})
            AND concept_type = '{self.intent.to_natural_language()}'
            LIMIT 100;
            """
        else:
            # Generic SQL
            conditions = []
            for entity in self.entities:
                conditions.append(f"entity_name LIKE '%{entity.text}%'")
            
            where_clause = " OR ".join(conditions) if conditions else "1=1"
            
            return f"""
            SELECT * FROM biological_entities
            WHERE {where_clause}
            LIMIT 100;
            """
    
    def to_elasticsearch(self) -> Dict[str, Any]:
        """
        Generate Elasticsearch query.
        
        Returns:
            Elasticsearch query dictionary
        """
        must_conditions = []
        
        for entity in self.entities:
            must_conditions.append({
                "match": {
                    "text": {
                        "query": entity.text,
                        "boost": 2.0
                    }
                }
            })
        
        if self.entities:
            must_conditions.append({
                "term": {
                    "intent": self.intent.name.lower()
                }
            })
        
        return {
            "query": {
                "bool": {
                    "must": must_conditions,
                    "filter": [
                        {"term": {"domain": "biology"}}
                    ]
                }
            },
            "size": 100,
            "sort": [{"relevance": {"order": "desc"}}]
        }


@dataclass
class QueryResult:
    """Unified result format from any data source with full provenance."""
    source: str
    data: Dict[str, Any]
    confidence: float
    evidence: List[Dict[str, Any]]
    structured_query: Optional[StructuredQuery] = None
    provenance: Dict[str, Any] = field(default_factory=dict)
    retrieval_time_ms: float = 0.0
    source_url: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            'source': self.source,
            'data': self.data,
            'confidence': self.confidence,
            'evidence': self.evidence,
            'provenance': self.provenance,
            'retrieval_time_ms': self.retrieval_time_ms,
            'source_url': self.source_url
        }
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2)