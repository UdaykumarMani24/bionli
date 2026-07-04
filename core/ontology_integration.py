"""
Ontology Integration - Publication Quality
Real OWL parsing with no fake data fallback.
"""

import logging
import os
import urllib.request
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class OntologyConcept:
    """Represents a concept from a real ontology."""
    id: str
    label: str
    definition: Optional[str] = None
    parents: List[str] = field(default_factory=list)
    children: List[str] = field(default_factory=list)
    synonyms: List[str] = field(default_factory=list)
    xrefs: List[str] = field(default_factory=list)
    is_obsolete: bool = False


class RealOWLParser:
    """
    Real OWL file parser that actually parses OWL files.
    No fake data - requires owlready2.
    """
    
    ONTOLOGY_URLS = {
        'go': 'http://purl.obolibrary.org/obo/go.owl',
        'go-basic': 'http://purl.obolibrary.org/obo/go/go-basic.owl',
        'ncbitaxon': 'http://purl.obolibrary.org/obo/ncbitaxon.owl',
        'doid': 'http://purl.obolibrary.org/obo/doid.owl',
    }
    
    def __init__(self, cache_dir: str = "data/ontologies/"):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        
        # Check for owlready2 - REQUIRE IT
        try:
            import owlready2
            self.owlready2 = owlready2
            self.owlready_available = True
            logger.info("owlready2 available - will use full OWL parsing")
        except ImportError:
            self.owlready_available = False
            raise ImportError(
                "owlready2 is required for ontology parsing.\n"
                "Install with: pip install owlready2"
            )
    
    def download_ontology(self, ontology_name: str, force: bool = False) -> str:
        """Download ontology file - raises error if fails."""
        if ontology_name not in self.ONTOLOGY_URLS:
            raise ValueError(f"Unknown ontology: {ontology_name}")
        
        url = self.ONTOLOGY_URLS[ontology_name]
        cache_path = os.path.join(self.cache_dir, f"{ontology_name}.owl")
        
        if os.path.exists(cache_path) and not force:
            logger.info(f"Using cached ontology: {cache_path}")
            return cache_path
        
        logger.info(f"Downloading ontology from {url}...")
        
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'BioNLI/2.0'})
            with urllib.request.urlopen(req, timeout=120) as response:
                with open(cache_path, 'wb') as f:
                    f.write(response.read())
            logger.info(f"✓ Downloaded to {cache_path}")
            return cache_path
        except Exception as e:
            raise RuntimeError(f"Failed to download ontology {ontology_name}: {e}")
    
    def parse_go_owl(self, file_path: str) -> Dict[str, OntologyConcept]:
        """
        Parse REAL Gene Ontology OWL file using owlready2.
        Raises error if parsing fails.
        """
        if not self.owlready_available:
            raise RuntimeError("owlready2 required for OWL parsing")
        
        logger.info(f"Parsing GO OWL file: {file_path}")
        
        try:
            onto = self.owlready2.get_ontology(file_path).load()
        except Exception as e:
            raise RuntimeError(f"Failed to load GO OWL file: {e}")
        
        concepts = {}
        term_count = 0
        
        for cls in onto.classes():
            # Skip BFO and other upper ontology classes
            if cls.name.startswith('BFO:'):
                continue
            
            # Get label
            label = getattr(cls, 'label', None)
            if not label:
                continue
            label = str(label[0]) if isinstance(label, list) else str(label)
            
            # Get definition
            definition = None
            if hasattr(cls, 'definition'):
                def_list = getattr(cls, 'definition', [])
                if def_list:
                    definition = str(def_list[0])
            
            # Get synonyms
            synonyms = []
            if hasattr(cls, 'hasExactSynonym'):
                for syn in getattr(cls, 'hasExactSynonym', []):
                    synonyms.append(str(syn))
            
            # Get parents
            parents = []
            for parent in cls.is_a:
                if isinstance(parent, self.owlready2.ThingClass):
                    parents.append(parent.name)
            
            concepts[cls.name] = OntologyConcept(
                id=cls.name,
                label=label,
                definition=definition,
                parents=parents,
                synonyms=synonyms
            )
            
            term_count += 1
            if term_count % 10000 == 0:
                logger.info(f"   Parsed {term_count:,} terms...")
        
        logger.info(f"Parsed {len(concepts):,} concepts from GO")
        
        if len(concepts) < 1000:
            raise RuntimeError(f"Only parsed {len(concepts)} concepts - likely parsing error")
        
        return concepts
    
    def load_ontology(self, ontology_name: str) -> Dict[str, OntologyConcept]:
        """Load ontology - raises error if fails."""
        file_path = self.download_ontology(ontology_name)
        
        if ontology_name == 'go' or ontology_name == 'go-basic':
            return self.parse_go_owl(file_path)
        else:
            raise NotImplementedError(f"Parser for {ontology_name} not implemented")


class OntologyReasoner:
    """
    Ontology reasoner that loads REAL ontologies.
    No fake data - raises error if ontologies can't be loaded.
    """
    
    def __init__(self, cache_dir: str = "data/ontologies/", 
                 require_real: bool = True):
        """
        Initialize ontology reasoner.
        
        Args:
            cache_dir: Directory for cached ontology files
            require_real: If True, raise error if ontologies can't be loaded
        """
        self.cache_dir = cache_dir
        self.require_real = require_real
        self.ontologies: Dict[str, Dict[str, OntologyConcept]] = {}
        
        try:
            self.parser = RealOWLParser(cache_dir=cache_dir)
            self._load_ontologies()
        except Exception as e:
            if require_real:
                raise RuntimeError(
                    f"Cannot initialize ontology reasoner: {e}\n"
                    f"Please ensure:\n"
                    f"1. Internet connection\n"
                    f"2. owlready2 installed\n"
                    f"3. Sufficient disk space"
                )
            else:
                logger.warning(f"Running without ontologies: {e}")
        
        logger.info(f"✓ OntologyReasoner initialized")
        logger.info(f"  - GO terms loaded: {len(self.ontologies.get('go', {})):,}")
    
    def _load_ontologies(self):
        """Load essential ontologies."""
        logger.info("Loading Gene Ontology...")
        go_path = os.path.join(self.cache_dir, "go.owl")
        self.ontologies['go'] = self.parser.parse_go_owl(go_path)
    
    @property
    def go_concepts(self) -> Dict[str, OntologyConcept]:
        """Property to access GO concepts (backward compatibility)."""
        return self.ontologies.get('go', {})
    
    def get_concept(self, term: str) -> Optional[OntologyConcept]:
        """Get concept from GO by label."""
        go = self.ontologies.get('go', {})
        term_lower = term.lower()
        
        for concept in go.values():
            if concept.label.lower() == term_lower:
                return concept
            for syn in concept.synonyms:
                if syn.lower() == term_lower:
                    return concept
        return None
    
    def expand_entities(self, entities: List) -> List:
        """Expand entities with ontology synonyms."""
        expanded = []
        for entity in entities:
            concept = self.get_concept(entity.text)
            if concept:
                entity.synonyms = concept.synonyms
                entity.expanded_terms = concept.synonyms + concept.parents
                if concept.definition:
                    entity.definition = concept.definition
            expanded.append(entity)
        return expanded
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics."""
        return {
            'ontologies_loaded': list(self.ontologies.keys()),
            'total_concepts': sum(len(o) for o in self.ontologies.values())
        }