"""
Semantic Parser - Publication Quality
Primary: BioBERT NER with HGNC validation
Fallback: Pattern matching with official HGNC gene list
"""

import torch
import logging
import re
import numpy as np
from transformers import AutoTokenizer, AutoModelForTokenClassification
from typing import List, Tuple, Optional, Dict, Any
from datetime import datetime

# Import from structured_query
from .structured_query import Entity, EntityType, Intent, StructuredQuery

# Import HGNC loader
from .hgnc_loader import HGNCGeneLoader

logger = logging.getLogger(__name__)


class BioBERTEntityRecognizer:
    """
    Primary entity recognizer using BioBERT with HGNC validation.
    """
    
    # BioBERT entity label mapping (simplified for our purposes)
    ENTITY_LABELS = {
        'B-GENE': 'GENE', 'I-GENE': 'GENE',
        'B-PROTEIN': 'PROTEIN', 'I-PROTEIN': 'PROTEIN',
        'B-DISEASE': 'DISEASE', 'I-DISEASE': 'DISEASE',
        'B-CHEMICAL': 'CHEMICAL', 'I-CHEMICAL': 'CHEMICAL',
        'B-PROCESS': 'PROCESS', 'I-PROCESS': 'PROCESS',
        'B-PATHWAY': 'PATHWAY', 'I-PATHWAY': 'PATHWAY',
    }
    
    # Minimum confidence threshold
    MIN_CONFIDENCE = 0.60
    
    # Stop words to filter out
    STOP_WORDS = {
        'is', 'the', 'what', 'function', 'role', 'gene', 'protein', 
        'does', 'of', 'in', 'for', 'with', 'by', 'at', 'on', 'from',
        'to', 'and', 'or', 'but', 'not', 'are', 'was', 'were', 'be',
        'been', 'being', 'have', 'has', 'had', 'do', 'did', 'will',
        'would', 'could', 'should', 'may', 'might', 'can', 'shall',
        'describe', 'explain', 'tell', 'me', 'about', 'find', 'show'
    }
    
    def __init__(self, model_name: str = "dmis-lab/biobert-v1.1", 
                 cache_dir: str = "data/models/", 
                 hgnc_dir: str = "data/hgnc/",
                 use_gpu: bool = True):
        """Initialize entity recognizer with HGNC validation."""
        
        # Load official HGNC gene list
        logger.info("Loading HGNC gene list...")
        self.hgnc = HGNCGeneLoader(cache_dir=hgnc_dir)
        
        # Load BioBERT
        self.device = torch.device("cuda" if use_gpu and torch.cuda.is_available() else "cpu")
        self.biobert_available = False
        
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(model_name, cache_dir=cache_dir)
            self.model = AutoModelForTokenClassification.from_pretrained(
                model_name,
                cache_dir=cache_dir,
                num_labels=len(self.ENTITY_LABELS),
                ignore_mismatched_sizes=True
            )
            self.model.to(self.device)
            self.model.eval()
            self.softmax = torch.nn.Softmax(dim=2)
            self.biobert_available = True
            logger.info(f"✓ BioBERT loaded on {self.device}")
        except Exception as e:
            logger.warning(f"BioBERT loading failed: {e}")
        
        logger.info(f"✓ Entity recognizer initialized")
        logger.info(f"  - HGNC genes: {self.hgnc.total_genes:,}")
        logger.info(f"  - BioBERT: {'Available' if self.biobert_available else 'Fallback only'}")
    
    def extract_entities(self, text: str) -> List[Entity]:
        """Extract entities using HGNC validation first, BioBERT as supplement."""
        entities = []

        # Method 1: Direct HGNC matching — always run first.
        # If the query contains an official gene symbol, this is the most
        # reliable signal and should take priority over BioBERT.
        hgnc_entities = self._extract_hgnc_matches(text)
        if hgnc_entities:
            entities = hgnc_entities
            logger.info(f"HGNC direct match found {len(entities)} entities")

        # Method 2: Synonym matching (e.g. "p53" -> TP53)
        if not entities:
            entities = self._extract_synonyms(text)

        # Method 3: BioBERT — only run if HGNC found nothing.
        # Avoids BioBERT hallucinating random gene names like UQCC6.
        if not entities and self.biobert_available:
            biobert_entities = self._extract_with_biobert(text)
            for e in biobert_entities:
                if e.entity_type == EntityType.GENE:
                    canonical = self.hgnc.get_canonical(e.text)
                    if canonical:
                        e.text = canonical
                        e.confidence = min(e.confidence + 0.05, 0.98)
                        e.source = 'biobert_hgnc_validated'
                        entities.append(e)
                    elif e.confidence > self.MIN_CONFIDENCE:
                        entities.append(e)
                elif e.confidence > self.MIN_CONFIDENCE:
                    if e.text.lower() not in self.STOP_WORDS and len(e.text) > 1:
                        entities.append(e)

        # Method 4: Pattern-based fallback
        if not entities:
            entities = self._extract_pattern_matches(text)

        # Remove duplicates
        entities = self._deduplicate(entities)

        logger.info(f"Extracted {len(entities)} entities")
        return entities
    
    def _extract_with_biobert(self, text: str) -> List[Entity]:
        """Extract entities using BioBERT with proper token aggregation."""
        entities = []
        
        try:
            inputs = self.tokenizer(text, return_tensors="pt", truncation=True, max_length=128)
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            with torch.no_grad():
                outputs = self.model(**inputs)
                probabilities = self.softmax(outputs.logits)
                predictions = torch.argmax(probabilities, dim=2)
            
            tokens = self.tokenizer.convert_ids_to_tokens(inputs['input_ids'][0])
            predictions = predictions[0].cpu().numpy()
            
            current_entity = None
            current_tokens = []
            current_probs = []
            
            for i, (token, pred) in enumerate(zip(tokens, predictions)):
                # Get label name (handle out of range)
                label_idx = pred % len(self.ENTITY_LABELS)
                pred_label = list(self.ENTITY_LABELS.keys())[label_idx]
                prob = probabilities[0][i][pred].item()
                
                if pred_label.startswith('B-'):
                    # Save previous entity
                    if current_entity and current_tokens:
                        entity_text = self._merge_tokens(current_tokens)
                        if entity_text and len(entity_text) > 1:
                            entity_type_str = self.ENTITY_LABELS.get(current_entity, 'GENE')
                            try:
                                entity_type = EntityType[entity_type_str]
                            except KeyError:
                                entity_type = EntityType.GENE
                            entities.append(Entity(
                                text=entity_text,
                                entity_type=entity_type,
                                confidence=float(np.mean(current_probs)) if current_probs else prob,
                                source='biobert'
                            ))
                    
                    current_entity = pred_label
                    current_tokens = [token]
                    current_probs = [prob]
                    
                elif pred_label.startswith('I-') and current_entity:
                    # Handle word pieces
                    if token.startswith('##'):
                        current_tokens[-1] = current_tokens[-1] + token[2:]
                    else:
                        current_tokens.append(token)
                    current_probs.append(prob)
                else:
                    if current_entity and current_tokens:
                        entity_text = self._merge_tokens(current_tokens)
                        if entity_text and len(entity_text) > 1:
                            entity_type_str = self.ENTITY_LABELS.get(current_entity, 'GENE')
                            try:
                                entity_type = EntityType[entity_type_str]
                            except KeyError:
                                entity_type = EntityType.GENE
                            entities.append(Entity(
                                text=entity_text,
                                entity_type=entity_type,
                                confidence=float(np.mean(current_probs)) if current_probs else 0.7,
                                source='biobert'
                            ))
                        current_entity = None
                        current_tokens = []
                        current_probs = []
            
            # Handle last entity
            if current_entity and current_tokens:
                entity_text = self._merge_tokens(current_tokens)
                if entity_text and len(entity_text) > 1:
                    entity_type_str = self.ENTITY_LABELS.get(current_entity, 'GENE')
                    try:
                        entity_type = EntityType[entity_type_str]
                    except KeyError:
                        entity_type = EntityType.GENE
                    entities.append(Entity(
                        text=entity_text,
                        entity_type=entity_type,
                        confidence=float(np.mean(current_probs)) if current_probs else 0.7,
                        source='biobert'
                    ))
                    
        except Exception as e:
            logger.warning(f"BioBERT extraction failed: {e}")
        
        return entities
    
    def _extract_hgnc_matches(self, text: str) -> List[Entity]:
        """Direct HGNC symbol matching."""
        entities = []
        text_upper = text.upper()
        
        # Check against known genes
        for gene in self.hgnc.genes:
            pattern = r'\b' + re.escape(gene) + r'\b'
            if re.search(pattern, text_upper):
                entities.append(Entity(
                    text=gene,
                    entity_type=EntityType.GENE,
                    confidence=0.95,
                    source='hgnc_match'
                ))
                break  # Return first match
        
        return entities
    
    def _extract_synonyms(self, text: str) -> List[Entity]:
        """Synonym matching using HGNC synonyms."""
        entities = []
        text_lower = text.lower()
        
        # Check synonyms
        for synonym, canonical in self.hgnc.synonyms.items():
            pattern = r'\b' + re.escape(synonym) + r'\b'
            if re.search(pattern, text_lower):
                entities.append(Entity(
                    text=canonical,
                    entity_type=EntityType.GENE,
                    confidence=0.92,
                    source='hgnc_synonym'
                ))
                break
        
        # Check previous symbols
        if not entities:
            for prev, canonical in self.hgnc.previous_symbols.items():
                pattern = r'\b' + re.escape(prev) + r'\b'
                if re.search(pattern, text_lower):
                    entities.append(Entity(
                        text=canonical,
                        entity_type=EntityType.GENE,
                        confidence=0.90,
                        source='hgnc_previous'
                    ))
                    break
        
        return entities
    
    def _extract_pattern_matches(self, text: str) -> List[Entity]:
        """Fallback pattern matching for genes."""
        entities = []
        
        # Common gene patterns
        patterns = [
            r'\b(TP53|BRCA1|BRCA2|EGFR|INS|CFTR|APOE|APP|SNCA|HTT|DMD|MYC|KRAS|PTEN|RB1|VEGFA)\b',
            r'\b(p53|brca1|brca2|egfr|insulin|cftr|apoe|app|snca|htt|dmd|myc|kras|pten|rb1|vegf)\b'
        ]
        
        text_upper = text.upper()
        for pattern in patterns:
            matches = re.finditer(pattern, text_upper, re.IGNORECASE)
            for match in matches:
                gene_text = match.group()
                # Normalize to standard symbol
                normalized = self.hgnc.get_canonical(gene_text) or gene_text.upper()
                entities.append(Entity(
                    text=normalized,
                    entity_type=EntityType.GENE,
                    confidence=0.85,
                    source='pattern_match'
                ))
                break  # Return first match
        
        return entities
    
    def _merge_tokens(self, tokens: List[str]) -> str:
        """Merge token pieces into a single string."""
        merged = []
        for token in tokens:
            if token.startswith('##'):
                merged.append(token[2:])
            else:
                merged.append(token)
        return ''.join(merged).strip()
    
    def _deduplicate(self, entities: List[Entity]) -> List[Entity]:
        """Remove duplicate entities."""
        seen = set()
        unique = []
        for e in entities:
            key = f"{e.text}:{e.entity_type.name}"
            if key not in seen:
                seen.add(key)
                unique.append(e)
        return unique
    
    def get_stats(self) -> dict:
        """Get recognizer statistics."""
        return {
            'hgnc': self.hgnc.get_stats(),
            'biobert_available': self.biobert_available,
            'device': str(self.device)
        }


class IntentClassifier:
    """Intent classifier based on keywords."""
    
    INTENT_KEYWORDS = {
        Intent.FUNCTION: ['function', 'role', 'purpose', 'what does', 'what is', 'describe'],
        Intent.PATHWAY: ['pathway', 'signaling', 'cascade', 'involved in'],
        Intent.INTERACTION: ['interact', 'bind', 'complex', 'partner', 'interaction'],
        Intent.LOCATION: ['location', 'localize', 'where', 'expressed', 'localization'],
        Intent.DISEASE_ASSOCIATION: ['disease', 'cancer', 'disorder', 'associated', 'linked'],
        Intent.HOMOLOGY: ['homolog', 'ortholog', 'paralog', 'mouse', 'rat', 'version'],
        Intent.EXPRESSION: ['expression', 'expressed', 'upregulated', 'downregulated'],
        Intent.SEQUENCE: ['sequence', 'amino acid', 'nucleotide', 'dna', 'rna'],
        Intent.STRUCTURE: ['structure', 'domain', 'fold', 'conformation'],
        Intent.REGULATION: ['regulate', 'control', 'activate', 'inhibit'],
    }
    
    def classify(self, text: str) -> Tuple[Intent, float]:
        """Classify intent using keywords."""
        text_lower = text.lower()
        
        best_intent = Intent.FUNCTION
        best_score = 0.5
        
        for intent, keywords in self.INTENT_KEYWORDS.items():
            score = 0
            for kw in keywords:
                if kw in text_lower:
                    score += 1
            if score > best_score:
                best_score = min(score / 3, 0.95)
                best_intent = intent
        
        return best_intent, best_score


class SemanticParser:
    """Main semantic parser."""
    
    def __init__(self, use_gpu: bool = True, cache_dir: str = "data/models/",
                 hgnc_dir: str = "data/hgnc/"):
        """Initialize semantic parser."""
        logger.info("=" * 60)
        logger.info("Initializing Semantic Parser (Publication Version)")
        logger.info("=" * 60)
        
        self.entity_recognizer = BioBERTEntityRecognizer(
            use_gpu=use_gpu, 
            cache_dir=cache_dir,
            hgnc_dir=hgnc_dir
        )
        self.intent_classifier = IntentClassifier()
        
        logger.info("✓ Semantic parser initialized")
        logger.info(f"  - HGNC genes: {self.entity_recognizer.hgnc.total_genes:,}")
        logger.info(f"  - BioBERT: {'Available' if self.entity_recognizer.biobert_available else 'Fallback'}")
        logger.info("=" * 60)
    
    def parse(self, question: str) -> StructuredQuery:
        """Parse question into structured query."""
        logger.info(f"Parsing: {question[:100]}...")
        
        entities = self.entity_recognizer.extract_entities(question)
        intent, intent_confidence = self.intent_classifier.classify(question)
        
        structured_query = StructuredQuery(
            original_question=question,
            intent=intent,
            entities=entities,
            constraints={},
            relations=[]
        )
        
        logger.info(f"✓ Parsed: intent={intent.name}, entities={len(entities)}")
        return structured_query
    
    def get_stats(self) -> dict:
        """Get parser statistics."""
        return self.entity_recognizer.get_stats()
        
    # In semantic_parser.py, in _normalize_gene method
    def _normalize_gene(self, gene_text: str) -> Optional[str]:
        """Normalize gene name to official HGNC symbol."""
        
        # First, use HGNC loader (MOST IMPORTANT)
        if self.hgnc:
            canonical = self.hgnc.get_canonical(gene_text)
            if canonical:
                logger.info(f"HGNC mapping: {gene_text} → {canonical}")
                return canonical
        
        # Fallback to explicit mapping (in case HGNC fails)
        gene_lower = gene_text.lower()
        explicit_map = {
            'brca1': 'BRCA1',
            'brca2': 'BRCA2',
            'tp53': 'TP53',
            'p53': 'TP53',
            'egfr': 'EGFR',
            'insulin': 'INS',
            'cftr': 'CFTR',
            'apoe': 'APOE',
            'app': 'APP',
        }
        
        if gene_lower in explicit_map:
            return explicit_map[gene_lower]
        
        # If it's a valid pattern, return as-is
        if re.match(r'^[A-Z]{2,5}[0-9]{1,4}[A-Z]?$', gene_text.upper()):
            return gene_text.upper()
        
        return None