import spacy
import re
from typing import Dict, List, Any, Tuple
from collections import defaultdict

class EnhancedNLPProcessor:
    """Enhanced NLP processor with biological concept recognition"""
    
    def __init__(self):
        self.scientific_nlp = self._load_scientific_model()
        self.biological_patterns = self._init_biological_patterns()
        self.concept_keywords = self._init_concept_keywords()
        self.stop_words = self._init_stop_words()
        
    def _load_scientific_model(self):
        """Load scientific NLP model"""
        try:
            return spacy.load("en_core_sci_sm")
        except OSError:
            try:
                return spacy.load("en_ner_bionlp13cg_md")
            except OSError:
                print("Scientific models not found. Using general model...")
                return spacy.load("en_core_web_sm")
    
    def _init_biological_patterns(self) -> Dict[str, re.Pattern]:
        """Initialize biological entity recognition patterns"""
        return {
            'gene': re.compile(r'\b([A-Z][A-Z0-9]+[0-9]*|[A-Z]{1,4}[0-9]{1,5}[A-Z]?|p53|p21|p16|p27)\b', re.IGNORECASE),
            'protein': re.compile(r'\b([A-Z][a-z]{2,}[0-9]*[A-Z]?|[A-Z]{1,6}[0-9]{1,6})\b', re.IGNORECASE),
            'species': re.compile(r'\b(human|mouse|rat|mus musculus|drosophila|yeast|saccharomyces|cerevisiae|ecoli|escherichia coli|homo sapiens|mus|rattus)\b', re.IGNORECASE),
            'uniprot_id': re.compile(r'\b([OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9]([A-Z][A-Z0-9]{2}[0-9]){1,2})\b'),
            'gene_id': re.compile(r'\b(\d{1,10})\b'),
        }
    
    def _init_concept_keywords(self) -> Dict[str, List[str]]:
        """Initialize biological concept keywords"""
        return {
            'homology': ['homolog', 'homologs', 'homologous', 'ortholog', 'orthologs', 'orthologous', 'paralog', 'paralogs', 
                        'equivalent', 'counterpart', 'version', 'equivalent gene', 'similar gene', 'related gene'],
            'immune': ['immune', 'immunity', 'immunological', 'lymphocyte', 't-cell', 'b-cell', 'antibody', 'antigen'],
            'virus': ['virus', 'viral', 'virion', 'bacteriophage', 'retrovirus', 'hiv', 'influenza', 'coronavirus'],
            'cancer': ['cancer', 'tumor', 'oncogene', 'tumor suppressor', 'carcinoma', 'sarcoma', 'leukemia'],
            'expression': ['expression', 'expressed', 'transcription', 'translation', 'mrna', 'rna', 'transcript'],
            'interaction': ['interaction', 'interact', 'binding', 'complex', 'dimer', 'multimer', 'association'],
            'pathway': ['pathway', 'signaling', 'cascade', 'network', 'circuit', 'regulation'],
            'structure': ['structure', 'domain', 'motif', 'fold', 'conformation', 'tertiary', 'secondary'],
            'function': ['function', 'role', 'purpose', 'activity', 'mechanism', 'effect', 'action'],
            'sequence': ['sequence', 'dna sequence', 'protein sequence', 'nucleotide sequence', 'amino acid sequence']
        }
    
    def _init_stop_words(self) -> set:
        """Initialize stop words to ignore"""
        return {
            'find', 'search', 'show', 'tell', 'get', 'what', 'which', 'where', 'when', 'how', 'why',
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by',
            'are', 'is', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did',
            'can', 'could', 'will', 'would', 'should', 'may', 'might', 'must', 'me', 'my', 'your', 'our',
            'their', 'its', 'this', 'that', 'these', 'those', 'here', 'there', 'very', 'quite', 'rather',
            'some', 'any', 'all', 'both', 'each', 'every', 'either', 'neither', 'version', 'equivalent',
            'sequence', 'sequences', 'gene', 'genes', 'protein', 'proteins'  # Added biological terms that shouldn't be entities
        }
    
    def parse_query(self, query: str) -> Dict[str, Any]:
        """Enhanced query parsing with concept recognition"""
        doc = self.scientific_nlp(query.lower())
        
        # Extract entities and concepts
        entities = self._extract_entities_advanced(query, doc)
        concepts = self._extract_concepts(query)
        query_type = self._classify_query_type_advanced(query, doc, concepts, entities)
        relationships = self._extract_relationships(doc)
        
        return {
            'original_query': query,
            'normalized_query': self._normalize_query(query),
            'entities': entities,
            'concepts': concepts,
            'query_type': query_type,
            'relationships': relationships,
            'keywords': self._extract_scientific_keywords(doc),
            'confidence_score': self._calculate_confidence(entities, query_type, concepts)
        }
    
    def _extract_concepts(self, query: str) -> Dict[str, List[str]]:
        """Extract biological concepts from query"""
        concepts = defaultdict(list)
        query_lower = query.lower()
        
        for concept_type, keywords in self.concept_keywords.items():
            for keyword in keywords:
                if re.search(r'\b' + re.escape(keyword) + r'\b', query_lower):
                    concepts[concept_type].append(keyword)
        
        return dict(concepts)
    
    def _extract_entities_advanced(self, query: str, doc) -> Dict[str, List[Dict]]:
        """Advanced entity extraction with better filtering"""
        entities = defaultdict(list)
        
        # First, use spaCy NER extraction (more reliable)
        for ent in doc.ents:
            if ent.label_ in ['GENE', 'PROTEIN', 'ORGANISM', 'CELL_TYPE']:
                if self._is_valid_biological_entity(ent.label_.lower(), ent.text):
                    entity_info = {
                        'text': ent.text,
                        'start': ent.start_char,
                        'end': ent.end_char,
                        'label': ent.label_,
                        'confidence': 0.9,  # Higher confidence for NER
                        'source': 'spacy_ner'
                    }
                    entities[ent.label_.lower()].append(entity_info)
        
        # Then pattern-based extraction (as fallback)
        for entity_type, pattern in self.biological_patterns.items():
            matches = pattern.finditer(query)
            for match in matches:
                entity_text = match.group()
                if (self._is_valid_biological_entity(entity_type, entity_text) and 
                    not self._is_already_extracted(entities, entity_text)):
                    entity_info = {
                        'text': entity_text,
                        'start': match.start(),
                        'end': match.end(),
                        'normalized': self._normalize_entity(entity_type, entity_text),
                        'confidence': 0.7,  # Lower confidence for patterns
                        'source': 'pattern_match'
                    }
                    entities[entity_type].append(entity_info)
        
        # Sort entities by confidence and remove duplicates
        for entity_type in entities:
            # Remove duplicates based on text
            seen = set()
            unique_entities = []
            for entity in entities[entity_type]:
                if entity['text'] not in seen:
                    seen.add(entity['text'])
                    unique_entities.append(entity)
            # Sort by confidence (highest first)
            entities[entity_type] = sorted(unique_entities, key=lambda x: x.get('confidence', 0), reverse=True)
        
        return dict(entities)
    
    def _is_already_extracted(self, entities: Dict, entity_text: str) -> bool:
        """Check if entity has already been extracted by another method"""
        for entity_list in entities.values():
            for entity in entity_list:
                if entity['text'] == entity_text:
                    return True
        return False
    
    def _is_valid_biological_entity(self, entity_type: str, text: str) -> bool:
        """Validate if text is likely a biological entity"""
        text_lower = text.lower()
        
        # Filter out stop words
        if text_lower in self.stop_words:
            return False
        
        # Gene-specific validation
        if entity_type == 'gene':
            # Common biological terms that might match gene patterns
            common_biological_terms = {'genes', 'proteins', 'homologs', 'orthologs', 'paralogs', 
                                     'mutations', 'variants', 'alleles', 'loci', 'chromosomes',
                                     'sequence', 'sequences', 'gene', 'protein'}
            
            # Must look like a real gene name (mix of letters and numbers, or common gene names)
            valid_gene_pattern = (
                (text.upper() != text.lower()) and  # Has uppercase letters
                (len(text) >= 2) and 
                (text_lower not in common_biological_terms) and
                (not text.isdigit()) and
                (not text_lower in ['which', 'what', 'where', 'when', 'how', 'get', 'show']) and
                # Must be either: all caps with numbers, or common gene names like p53
                (re.match(r'^[A-Z0-9]+$', text) or text.lower() in ['p53', 'p21', 'p16', 'p27'])
            )
            return valid_gene_pattern
        
        return True
    
    def _classify_query_type_advanced(self, query: str, doc, concepts: Dict, entities: Dict) -> str:
        """Advanced query type classification with concept awareness"""
        query_lower = query.lower()
        
        # Check for sequence queries first (very specific)
        if concepts.get('sequence') or 'sequence' in query_lower:
            return 'sequence'
        
        # Check for homology queries 
        if concepts.get('homology'):
            return 'homology'
        
        # Check for complex concept-based queries
        if concepts.get('immune') and concepts.get('virus'):
            return 'immune_virus_interaction'
        elif concepts.get('cancer') and entities.get('gene'):
            return 'cancer_gene'
        
        # Check for species-specific queries
        if entities.get('species') and entities.get('gene'):
            if 'homolog' in query_lower or 'ortholog' in query_lower or 'equivalent' in query_lower:
                return 'homology'
        
        # Basic query patterns
        query_patterns = {
            'function': {
                'patterns': [r'function of', r'role of', r'what does', r'biological function', r'purpose of'],
                'keywords': ['function', 'role', 'purpose']
            },
            'expression': {
                'patterns': [r'expression in', r'expressed in', r'tissue expression', r'where is.*expressed'],
                'keywords': ['expression', 'expressed', 'tissue', 'cell type']
            },
            'interaction': {
                'patterns': [r'interacts with', r'interaction.*between', r'protein.*interaction', r'binds to'],
                'keywords': ['interact', 'interaction', 'bind', 'complex', 'partner']
            },
            'sequence': {
                'patterns': [r'sequence of', r'get sequence', r'dna sequence', r'protein sequence', r'nucleotide sequence'],
                'keywords': ['sequence', 'dna', 'rna', 'amino acid', 'nucleotide']
            },
            'homology': {
                'patterns': [r'homolog of', r'ortholog of', r'equivalent.*in', r'counterpart in', r'mouse version of'],
                'keywords': ['homolog', 'ortholog', 'equivalent', 'counterpart', 'version']
            }
        }
        
        best_match = 'general'
        highest_score = 0
        
        for q_type, patterns in query_patterns.items():
            score = 0
            
            # Pattern matching
            for pattern in patterns['patterns']:
                if re.search(pattern, query_lower):
                    score += 3  # Higher weight for patterns
            
            # Keyword matching
            for keyword in patterns['keywords']:
                if keyword in query_lower:
                    score += 1
            
            if score > highest_score:
                highest_score = score
                best_match = q_type
        
        return best_match
    
    def _extract_relationships(self, doc) -> List[Dict]:
        """Extract semantic relationships using dependency parsing"""
        relationships = []
        
        for token in doc:
            if token.dep_ in ['dobj', 'nsubj', 'attr', 'prep']:
                relationship = {
                    'head': token.head.lemma_,
                    'relation': token.dep_,
                    'dependent': token.lemma_,
                    'head_pos': token.head.pos_,
                    'dependent_pos': token.pos_
                }
                relationships.append(relationship)
        
        return relationships
    
    def _extract_scientific_keywords(self, doc) -> List[str]:
        """Extract scientific keywords"""
        keywords = []
        
        for token in doc:
            if (token.pos_ in ['NOUN', 'VERB', 'ADJ'] and 
                not token.is_stop and 
                len(token.lemma_) > 2 and
                token.lemma_ not in ['gene', 'protein', 'sequence']):
                keywords.append(token.lemma_)
        
        return list(set(keywords))
    
    def _normalize_query(self, query: str) -> str:
        """Normalize query for better processing"""
        # Remove extra whitespace
        query = ' '.join(query.split())
        
        # Common biological term normalization
        normalizations = {
            'dna': 'DNA',
            'rna': 'RNA',
            'mrna': 'mRNA',
            'trna': 'tRNA',
            'protein': 'protein',
            'gene': 'gene',
            'insulin': 'INS'  # Normalize insulin to gene symbol
        }
        
        for term, normalized in normalizations.items():
            query = re.sub(r'\b' + term + r'\b', normalized, query, flags=re.IGNORECASE)
        
        return query
    
    def _normalize_entity(self, entity_type: str, entity_text: str) -> str:
        """Normalize entity text"""
        if entity_type == 'species':
            species_map = {
                'human': 'Homo sapiens',
                'mouse': 'Mus musculus',
                'mice': 'Mus musculus',
                'rat': 'Rattus norvegicus',
                'mus': 'Mus musculus',
                'rattus': 'Rattus norvegicus',
                'yeast': 'Saccharomyces cerevisiae',
                'ecoli': 'Escherichia coli'
            }
            return species_map.get(entity_text.lower(), entity_text)
        
        # Normalize common gene names to symbols
        gene_normalizations = {
            'insulin': 'INS',
            'p53': 'TP53',
            'brca': 'BRCA1',
            'egf': 'EGFR'
        }
        return gene_normalizations.get(entity_text.lower(), entity_text.upper())
    
    def _calculate_confidence(self, entities: Dict, query_type: str, concepts: Dict) -> float:
        """Calculate confidence score for query parsing"""
        base_confidence = 0.5
        
        # Boost confidence if valid entities found
        if entities and any(len(entities[etype]) > 0 for etype in ['gene', 'protein']):
            base_confidence += 0.3
        
        # Boost confidence if specific query type identified
        if query_type != 'general':
            base_confidence += 0.2
        
        # Boost confidence if biological concepts detected
        if concepts:
            base_confidence += 0.1
        
        return min(base_confidence, 1.0)