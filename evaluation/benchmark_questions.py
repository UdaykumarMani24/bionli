import json
from typing import List, Dict, Any

class BioNLIBenchmark:
    """Standardized benchmark for evaluating BioNLI performance"""
    
    def __init__(self):
        self.test_questions = self._load_benchmark_questions()
    
    def _load_benchmark_questions(self) -> List[Dict[str, Any]]:
        """Comprehensive benchmark questions covering various biological query types"""
        return [
            # Gene Function Queries
            {
                'id': 'GF001',
                'question': 'What is the function of TP53 gene?',
                'category': 'gene_function',
                'expected_entities': ['TP53'],
                'expected_query_type': 'function',
                'difficulty': 'basic'
            },
            {
                'id': 'GF002', 
                'question': 'Tell me about the role of BRCA1 in DNA repair',
                'category': 'gene_function',
                'expected_entities': ['BRCA1'],
                'expected_query_type': 'function',
                'difficulty': 'intermediate'
            },
            
            # Sequence Queries
            {
                'id': 'SQ001',
                'question': 'Get the DNA sequence of insulin gene',
                'category': 'sequence',
                'expected_entities': ['INS'],
                'expected_query_type': 'sequence', 
                'difficulty': 'basic'
            },
            {
                'id': 'SQ002',
                'question': 'Show me the protein sequence of EGFR',
                'category': 'sequence',
                'expected_entities': ['EGFR'],
                'expected_query_type': 'sequence',
                'difficulty': 'basic'
            },
            
            # Homology Queries
            {
                'id': 'HM001',
                'question': 'Find homologs of TP53 in mice',
                'category': 'homology',
                'expected_entities': ['TP53'],
                'expected_query_type': 'homology',
                'difficulty': 'intermediate'
            },
            {
                'id': 'HM002',
                'question': 'What is the mouse version of BRCA1 gene?',
                'category': 'homology', 
                'expected_entities': ['BRCA1'],
                'expected_query_type': 'homology',
                'difficulty': 'intermediate'
            },
            
            # Expression Queries
            {
                'id': 'EX001',
                'question': 'Where is the insulin gene expressed?',
                'category': 'expression',
                'expected_entities': ['INS'],
                'expected_query_type': 'expression',
                'difficulty': 'intermediate'
            },
            
            # Interaction Queries
            {
                'id': 'IN001',
                'question': 'What proteins interact with TP53?',
                'category': 'interaction',
                'expected_entities': ['TP53'],
                'expected_query_type': 'interaction',
                'difficulty': 'advanced'
            },
            
            # Complex Multi-concept Queries
            {
                'id': 'CX001',
                'question': 'Which immune genes are targeted by viruses?',
                'category': 'complex_concept',
                'expected_entities': [],
                'expected_query_type': 'immune_virus_interaction',
                'difficulty': 'advanced'
            },
            {
                'id': 'CX002',
                'question': 'Find cancer-related genes on chromosome 17',
                'category': 'complex_concept',
                'expected_entities': [],
                'expected_query_type': 'cancer_gene',
                'difficulty': 'advanced'
            }
        ]
    
    def evaluate_system(self, nlp_processor, db_connector) -> Dict[str, Any]:
        """Comprehensive evaluation of BioNLI system"""
        results = {
            'overall_score': 0,
            'category_scores': {},
            'detailed_results': [],
            'metrics': {
                'entity_recognition_accuracy': 0,
                'query_classification_accuracy': 0,
                'response_success_rate': 0,
                'average_confidence': 0
            }
        }
        
        total_questions = len(self.test_questions)
        entity_correct = 0
        query_type_correct = 0
        response_success = 0
        total_confidence = 0
        
        for question_data in self.test_questions:
            question = question_data['question']
            
            try:
                # Process query through BioNLI
                parsed_query = nlp_processor.parse_query(question)
                db_results = db_connector.execute_complex_query(parsed_query)
                
                # Evaluate performance
                evaluation = self._evaluate_single_query(question_data, parsed_query, db_results)
                results['detailed_results'].append(evaluation)
                
                # Calculate metrics
                if evaluation['entity_recognition_correct']:
                    entity_correct += 1
                if evaluation['query_type_correct']:
                    query_type_correct += 1
                if evaluation['has_valid_response']:
                    response_success += 1
                
                total_confidence += parsed_query.get('confidence_score', 0)
                
            except Exception as e:
                print(f"Error evaluating question {question_data['id']}: {e}")
                results['detailed_results'].append({
                    'question_id': question_data['id'],
                    'question': question,
                    'error': str(e),
                    'entity_recognition_correct': False,
                    'query_type_correct': False,
                    'has_valid_response': False
                })
        
        # Calculate final metrics
        results['metrics']['entity_recognition_accuracy'] = entity_correct / total_questions
        results['metrics']['query_classification_accuracy'] = query_type_correct / total_questions
        results['metrics']['response_success_rate'] = response_success / total_questions
        results['metrics']['average_confidence'] = total_confidence / total_questions
        
        # Calculate overall score (weighted average)
        weights = {'entity': 0.3, 'query_type': 0.3, 'response': 0.4}
        results['overall_score'] = (
            results['metrics']['entity_recognition_accuracy'] * weights['entity'] +
            results['metrics']['query_classification_accuracy'] * weights['query_type'] +
            results['metrics']['response_success_rate'] * weights['response']
        )
        
        return results
    
    def _evaluate_single_query(self, question_data: Dict, parsed_query: Dict, db_results: List) -> Dict[str, Any]:
        """Evaluate a single query's performance"""
        # Check entity recognition
        extracted_entities = [e['text'] for e in parsed_query.get('entities', {}).get('gene', [])]
        expected_entities = question_data['expected_entities']
        entity_correct = all(entity in extracted_entities for entity in expected_entities)
        
        # Check query classification
        query_type_correct = parsed_query.get('query_type') == question_data['expected_query_type']
        
        # Check if we got valid responses
        has_valid_response = len(db_results) > 0 and not any(
            result.get('status') == 'not_found' for result in db_results
        )
        
        return {
            'question_id': question_data['id'],
            'question': question_data['question'],
            'category': question_data['category'],
            'difficulty': question_data['difficulty'],
            'extracted_entities': extracted_entities,
            'expected_entities': expected_entities,
            'detected_query_type': parsed_query.get('query_type'),
            'expected_query_type': question_data['expected_query_type'],
            'confidence_score': parsed_query.get('confidence_score', 0),
            'entity_recognition_correct': entity_correct,
            'query_type_correct': query_type_correct,
            'has_valid_response': has_valid_response,
            'response_count': len(db_results)
        }
    
    def generate_performance_report(self, results: Dict[str, Any]) -> str:
        """Generate a comprehensive performance report"""
        report = []
        report.append("=" * 60)
        report.append("BioNLI Performance Benchmark Report")
        report.append("=" * 60)
        
        # Overall scores
        report.append(f"\nOverall Performance Score: {results['overall_score']:.3f}")
        report.append(f"Entity Recognition Accuracy: {results['metrics']['entity_recognition_accuracy']:.3f}")
        report.append(f"Query Classification Accuracy: {results['metrics']['query_classification_accuracy']:.3f}")
        report.append(f"Response Success Rate: {results['metrics']['response_success_rate']:.3f}")
        report.append(f"Average Confidence Score: {results['metrics']['average_confidence']:.3f}")
        
        # Category-wise performance
        report.append("\nCategory-wise Performance:")
        report.append("-" * 40)
        
        categories = {}
        for detail in results['detailed_results']:
            if 'error' not in detail:
                cat = detail['category']
                if cat not in categories:
                    categories[cat] = {'total': 0, 'correct_entity': 0, 'correct_query': 0, 'valid_response': 0}
                
                categories[cat]['total'] += 1
                if detail['entity_recognition_correct']:
                    categories[cat]['correct_entity'] += 1
                if detail['query_type_correct']:
                    categories[cat]['correct_query'] += 1
                if detail['has_valid_response']:
                    categories[cat]['valid_response'] += 1
        
        for cat, stats in categories.items():
            report.append(f"{cat.upper():<20} | Entities: {stats['correct_entity']}/{stats['total']} "
                         f"| Query Types: {stats['correct_query']}/{stats['total']} "
                         f"| Responses: {stats['valid_response']}/{stats['total']}")
        
        # Detailed results
        report.append("\nDetailed Question Results:")
        report.append("-" * 60)
        
        for detail in results['detailed_results']:
            if 'error' in detail:
                report.append(f"❌ {detail['question_id']}: {detail['question']} - ERROR: {detail['error']}")
            else:
                status = "✅" if all([
                    detail['entity_recognition_correct'],
                    detail['query_type_correct'], 
                    detail['has_valid_response']
                ]) else "⚠️"
                
                report.append(f"{status} {detail['question_id']}: {detail['question']}")
                report.append(f"   Entities: {detail['extracted_entities']} (expected: {detail['expected_entities']})")
                report.append(f"   Query Type: {detail['detected_query_type']} (expected: {detail['expected_query_type']})")
                report.append(f"   Confidence: {detail['confidence_score']:.3f}, Responses: {detail['response_count']}")
        
        return "\n".join(report)