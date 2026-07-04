"""
Intent Router - Routes any biological question to the appropriate data source
"""

import re
import logging
from typing import Dict, List, Tuple, Optional, Any
from enum import Enum

logger = logging.getLogger(__name__)


class QuestionType(Enum):
    """Types of biological questions."""
    GENE_FUNCTION = "gene_function"
    GENE_DESCRIPTION = "gene_description"
    PROTEIN_FUNCTION = "protein_function"
    HOMOLOGY = "homology"
    INTERACTION = "interaction"
    PATHWAY = "pathway"
    DISEASE_ASSOCIATION = "disease_association"
    LOCATION = "location"
    EXPRESSION = "expression"
    SEQUENCE = "sequence"
    STRUCTURE = "structure"
    REGULATION = "regulation"
    CONCEPT_DEFINITION = "concept_definition"
    COMPARISON = "comparison"
    LIST = "list"


class IntentRouter:
    """
    Routes any biological question to the appropriate data source(s).
    Uses comprehensive keyword patterns, entity types, and question structure.
    """
    
    # Comprehensive intent patterns - covers ANY biological question
    INTENT_PATTERNS = {
        # Gene Function
        QuestionType.GENE_FUNCTION: [
            r'function\s+of\s+(\w+)', r'what\s+does\s+(\w+)\s+do', r'role\s+of\s+(\w+)',
            r'purpose\s+of\s+(\w+)', r'what\s+is\s+the\s+function', r'what\s+is\s+(\w+)\s+gene',
            r'biological\s+function\s+of', r'molecular\s+function\s+of'
        ],
        
        # Gene Description
        QuestionType.GENE_DESCRIPTION: [
            r'tell\s+me\s+about\s+(\w+)', r'describe\s+(\w+)', r'what\s+is\s+(\w+)',
            r'information\s+about\s+(\w+)', r'explain\s+(\w+)', r'what\s+is\s+(\w+)\s+gene',
            r'overview\s+of\s+(\w+)', r'details\s+about\s+(\w+)'
        ],
        
        # Protein Function
        QuestionType.PROTEIN_FUNCTION: [
            r'protein\s+function', r'what\s+does\s+(\w+)\s+protein\s+do', r'role\s+of\s+(\w+)\s+protein',
            r'function\s+of\s+(\w+)\s+protein', r'what\s+is\s+(\w+)\s+protein',
            r'protein\s+encoded\s+by\s+(\w+)'
        ],
        
        # Homology / Orthologs
        QuestionType.HOMOLOGY: [
            r'homolog', r'ortholog', r'paralog', r'mouse\s+version', r'rat\s+version',
            r'zebrafish\s+homolog', r'fly\s+ortholog', r'worm\s+equivalent',
            r'find\s+(\w+)\s+homologs?', r'(\w+)\s+homologs?\s+in\s+(\w+)',
            r'what\s+is\s+the\s+(\w+)\s+homolog', r'equivalent\s+gene\s+in\s+(\w+)',
            r'orthologous\s+gene', r'homologous\s+gene'
        ],
        
        # Protein-Protein Interactions
        QuestionType.INTERACTION: [
            r'interact', r'binding', r'complex', r'partner', r'interaction',
            r'what\s+proteins\s+bind', r'protein-protein\s+interaction',
            r'find\s+proteins\s+that\s+bind', r'proteins\s+that\s+interact',
            r'binds\s+to', r'interacts\s+with', r'binding\s+partners',
            r'interaction\s+network', r'protein\s+complexes?\s+with',
            r'what\s+binds\s+to\s+(\w+)', r'(\w+)\s+interacting\s+proteins',
            r'show\s+interactions\s+for', r'interaction\s+partners\s+of'
        ],
        
        # Pathways
        QuestionType.PATHWAY: [
            r'pathway', r'signaling', r'cascade', r'involved\s+in', r'participates\s+in',
            r'genes\s+in\s+the\s+(\w+)\s+pathway', r'pathway\s+genes',
            r'what\s+pathways?\s+is\s+(\w+)\s+involved', r'(\w+)\s+signaling\s+pathway',
            r'metabolic\s+pathway', r'cell\s+signaling', r'signal\s+transduction',
            r'pathway\s+analysis', r'kegg\s+pathway', r'reactome\s+pathway'
        ],
        
        # Disease Associations
        QuestionType.DISEASE_ASSOCIATION: [
            r'disease', r'cancer', r'disorder', r'syndrome', r'associated\s+with',
            r'linked\s+to', r'causes\s+(\w+)', r'what\s+diseases', r'genes\s+linked\s+to',
            r'disease\s+association', r'(\w+)\s+disease', r'what\s+diseases?\s+does\s+(\w+)\s+cause',
            r'(\w+)\s+mutation\s+disease', r'pathogenic\s+variants', r'clinical\s+significance'
        ],
        
        # Location / Localization
        QuestionType.LOCATION: [
            r'location', r'localization', r'where\s+is', r'chromosome', r'cytogenetic',
            r'subcellular', r'nuclear', r'cytoplasmic', r'cellular\s+location',
            r'where\s+is\s+(\w+)\s+located', r'chromosomal\s+position',
            r'gene\s+location', r'expressed\s+where', r'tissue\s+distribution'
        ],
        
        # Expression
        QuestionType.EXPRESSION: [
            r'expression', r'expressed', r'upregulated', r'downregulated', r'levels',
            r'where\s+is\s+(\w+)\s+expressed', r'tissue\s+expression', r'expression\s+pattern',
            r'mRNA\s+expression', r'protein\s+expression', r'expression\s+profile',
            r'developmental\s+expression', r'cell-type\s+specific\s+expression'
        ],
        
        # Sequence
        QuestionType.SEQUENCE: [
            r'sequence', r'length', r'amino\s+acid', r'nucleotide', r'coding', r'dna',
            r'rna', r'protein\s+sequence', r'primary\s+structure', r'sequence\s+alignment',
            r'conserved\s+sequence', r'motif', r'domain\s+sequence'
        ],
        
        # Structure
        QuestionType.STRUCTURE: [
            r'structure', r'domain', r'fold', r'conformation', r'3d', r'crystal',
            r'pdb', r'structural', r'secondary\s+structure', r'tertiary\s+structure',
            r'protein\s+structure', r'structural\s+domain', r'alpha\s+helix', r'beta\+sheet'
        ],
        
        # Regulation
        QuestionType.REGULATION: [
            r'regulate', r'regulation', r'control', r'activate', r'inhibit', r'repress',
            r'modulate', r'what\s+regulates', r'what\s+does\s+(\w+)\s+regulate',
            r'transcriptional\s+regulation', r'post-translational\s+regulation',
            r'feedback\s+regulation', r'upstream\s+regulator', r'downstream\s+target'
        ],
        
        # Concept Definition
        QuestionType.CONCEPT_DEFINITION: [
            r'what\s+is\s+(\w+)', r'define\s+(\w+)', r'explain\s+(\w+)', r'meaning\s+of\s+(\w+)',
            r'apoptosis', r'autophagy', r'mitosis', r'meiosis', r'dna\s+repair', r'cell\s+cycle',
            r'signal\s+transduction', r'glycolysis', r'fermentation', r'oxidative\s+phosphorylation',
            r'definition\s+of\s+(\w+)', r'what\s+is\s+meant\s+by', r'describe\s+(\w+)\s+process'
        ],
        
        # Comparison
        QuestionType.COMPARISON: [
            r'compare', r'difference', r'versus', r'vs', r'between', r'similarities', r'contrast',
            r'different\s+from', r'similar\s+to', r'compare\s+and\s+contrast'
        ],
        
        # List / Enumeration
        QuestionType.LIST: [
            r'list', r'show\s+all', r'what\s+are\s+the', r'genes\s+that', r'proteins\s+that',
            r'enumerate', r'name\s+all', r'all\s+genes', r'complete\s+list'
        ]
    }
    
    # Data source mapping for each intent
    DATA_SOURCES = {
        QuestionType.GENE_FUNCTION: ['ncbi', 'uniprot'],
        QuestionType.GENE_DESCRIPTION: ['ncbi', 'uniprot'],
        QuestionType.PROTEIN_FUNCTION: ['uniprot', 'ncbi'],
        QuestionType.HOMOLOGY: ['ensembl'],
        QuestionType.INTERACTION: ['string'],
        QuestionType.PATHWAY: ['reactome'],
        QuestionType.DISEASE_ASSOCIATION: ['disgenet'],
        QuestionType.LOCATION: ['ncbi', 'ensembl'],
        QuestionType.EXPRESSION: ['ncbi'],
        QuestionType.SEQUENCE: ['uniprot', 'ensembl'],
        QuestionType.STRUCTURE: ['pdb', 'uniprot'],
        QuestionType.REGULATION: ['ncbi', 'string'],
        QuestionType.CONCEPT_DEFINITION: ['ols'],
        QuestionType.COMPARISON: ['ncbi', 'uniprot'],
        QuestionType.LIST: ['reactome', 'ncbi']
    }
    
    # Known human gene symbols (for entity extraction fallback)
    KNOWN_GENES = {
        'TP53', 'BRCA1', 'BRCA2', 'EGFR', 'INS', 'CFTR', 'APOE', 'APP',
        'SNCA', 'HTT', 'DMD', 'MYC', 'KRAS', 'PTEN', 'RB1', 'VEGFA',
        'ERBB2', 'MET', 'ALK', 'ROS1', 'RET', 'FGFR1', 'FGFR2', 'FGFR3',
        'PDGFRA', 'KIT', 'IDH1', 'IDH2', 'NTRK1', 'NTRK2', 'NTRK3',
        'CDKN2A', 'PIK3CA', 'AKT1', 'MTOR', 'MAPK1', 'MAPK3', 'JAK2',
        'STAT3', 'NOTCH1', 'NOTCH2', 'WNT1', 'CTNNB1', 'APC', 'SMAD4'
    }
    
    def __init__(self):
        """Initialize the intent router with compiled patterns."""
        # Compile all regex patterns for efficiency
        self.compiled_patterns = {}
        for qtype, patterns in self.INTENT_PATTERNS.items():
            self.compiled_patterns[qtype] = [re.compile(p, re.IGNORECASE) for p in patterns]
        
        logger.info(f"IntentRouter initialized with {len(self.INTENT_PATTERNS)} intent types")
    
    def route(self, question: str, entities: List = None) -> Dict:
        """
        Route question to appropriate data sources.
        
        Args:
            question: The user's question
            entities: Optional list of extracted entities (from BioBERT)
            
        Returns:
            Dict with: intent, entities, data_sources, confidence
        """
        question_lower = question.lower()
        
        # Step 1: Extract entities (genes, proteins, concepts)
        extracted_entities = self._extract_entities(question, entities)
        
        # Step 2: Classify intent
        intent, intent_confidence = self._classify_intent(question, extracted_entities)
        
        # Step 3: Determine data sources
        data_sources = self.DATA_SOURCES.get(intent, ['ncbi'])
        
        # Step 4: Determine if this is a concept question
        is_concept = intent == QuestionType.CONCEPT_DEFINITION
        
        logger.info(f"Routed to: {intent.value} (confidence: {intent_confidence:.2f})")
        logger.info(f"  Data sources: {data_sources}")
        logger.info(f"  Entities: {extracted_entities}")
        
        return {
            'intent': intent,
            'intent_confidence': intent_confidence,
            'entities': extracted_entities,
            'data_sources': data_sources,
            'is_concept': is_concept,
            'has_gene': any(e['type'] == 'GENE' for e in extracted_entities),
            'has_concept': any(e['type'] == 'CONCEPT' for e in extracted_entities)
        }
    
    def _extract_entities(self, question: str, biobert_entities: List = None) -> List[Dict]:
        """Extract biological entities from question."""
        entities = []
        
        # Use BioBERT entities if available
        if biobert_entities:
            for e in biobert_entities:
                entities.append({
                    'text': e.text if hasattr(e, 'text') else e.get('text', ''),
                    'type': e.entity_type.name if hasattr(e, 'entity_type') else e.get('type', 'UNKNOWN'),
                    'confidence': e.confidence if hasattr(e, 'confidence') else e.get('confidence', 0.8)
                })
        
        # Fallback: pattern-based extraction
        if not entities:
            question_upper = question.upper()
            question_lower = question.lower()
            
            # Look for gene symbols
            for gene in self.KNOWN_GENES:
                if gene in question_upper:
                    entities.append({
                        'text': gene,
                        'type': 'GENE',
                        'confidence': 0.85
                    })
                    break
            
            # Look for biological concepts
            concepts = [
                'apoptosis', 'autophagy', 'mitosis', 'meiosis', 'dna repair',
                'cell cycle', 'signal transduction', 'glycolysis', 'fermentation',
                'oxidative phosphorylation', 'angiogenesis', 'senescence'
            ]
            for concept in concepts:
                if concept in question_lower:
                    entities.append({
                        'text': concept.title(),
                        'type': 'CONCEPT',
                        'confidence': 0.80
                    })
                    break
        
        return entities
    
    def _classify_intent(self, question: str, entities: List[Dict]) -> Tuple[QuestionType, float]:
        """Classify question intent using patterns and entities."""
        question_lower = question.lower()
        
        # Score each intent based on pattern matches
        scores = {}
        for qtype, patterns in self.compiled_patterns.items():
            score = 0
            for pattern in patterns:
                match = pattern.search(question)
                if match:
                    score += 1
                    # Boost score if pattern captured a gene/concept
                    if match.groups() and len(match.groups()) > 0:
                        captured = match.group(1)
                        if captured.upper() in self.KNOWN_GENES:
                            score += 2
            if score > 0:
                scores[qtype] = score
        
        # Boost based on entities
        for entity in entities:
            if entity['type'] == 'GENE':
                # Gene-related questions — boost all gene intents equally
                for qtype in [QuestionType.GENE_FUNCTION, QuestionType.GENE_DESCRIPTION,
                              QuestionType.HOMOLOGY, QuestionType.INTERACTION,
                              QuestionType.PATHWAY, QuestionType.DISEASE_ASSOCIATION,
                              QuestionType.STRUCTURE, QuestionType.PROTEIN_FUNCTION,
                              QuestionType.SEQUENCE, QuestionType.LOCATION]:
                    scores[qtype] = scores.get(qtype, 0) + 2
            
            elif entity['type'] == 'CONCEPT':
                # Concept-related questions
                scores[QuestionType.CONCEPT_DEFINITION] = scores.get(QuestionType.CONCEPT_DEFINITION, 0) + 3
        
        # Special handling for structure questions
        if any(phrase in question_lower for phrase in
               ['structure', 'domain', 'fold', '3d', 'pdb', 'alphafold',
                'sequence length', 'amino acid', 'crystal', 'structural']):
            scores[QuestionType.STRUCTURE] = scores.get(QuestionType.STRUCTURE, 0) + 5

        # Special handling for interaction questions (common phrases)
        if any(phrase in question_lower for phrase in ['proteins that bind', 'interacts with', 'binding partners']):
            scores[QuestionType.INTERACTION] = scores.get(QuestionType.INTERACTION, 0) + 5
        
        # Special handling for homology questions
        homology_phrases = [
            'homolog', 'ortholog', 'mouse version', 'rat version',
            'zebrafish version', 'fly version', 'worm version',
            'rat equivalent', 'mouse equivalent', 'zebrafish equivalent',
            'equivalent of', 'equivalent gene', 'counterpart',
            'find the', 'find mouse', 'find rat', 'find zebrafish',
            'version of', 'in mouse', 'in rat', 'in zebrafish',
            'in drosophila', 'in c. elegans'
        ]
        if any(phrase in question_lower for phrase in homology_phrases):
            scores[QuestionType.HOMOLOGY] = scores.get(QuestionType.HOMOLOGY, 0) + 5
        
        # Special handling for pathway questions
        if any(phrase in question_lower for phrase in ['pathway', 'signaling']):
            scores[QuestionType.PATHWAY] = scores.get(QuestionType.PATHWAY, 0) + 3
        
        # Special handling for disease questions
        if any(phrase in question_lower for phrase in ['disease', 'cancer', 'disorder']):
            scores[QuestionType.DISEASE_ASSOCIATION] = scores.get(QuestionType.DISEASE_ASSOCIATION, 0) + 3
        
        # Get best intent
        if scores:
            best_intent = max(scores, key=scores.get)
            max_score = scores[best_intent]
            confidence = min(0.6 + (max_score / 10), 0.95)
            return best_intent, confidence
        
        # Default to gene description for "tell me about X" questions
        if re.search(r'tell\s+me\s+about', question_lower):
            return QuestionType.GENE_DESCRIPTION, 0.70
        
        # Default to concept definition for "what is X" questions
        if re.search(r'what\s+is\s+(\w+)', question_lower):
            return QuestionType.CONCEPT_DEFINITION, 0.65
        
        return QuestionType.GENE_DESCRIPTION, 0.60
    
    def get_supported_intents(self) -> List[str]:
        """Return list of supported intent types."""
        return [intent.value for intent in QuestionType]