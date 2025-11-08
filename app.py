from flask import Flask, render_template, request, jsonify
from core.nlp_processor import EnhancedNLPProcessor
from core.database_connector import RealDatabaseConnector
from core.bio_services import BioServices
import json
import time
from typing import Dict, Any, List  # Critical import for type hints

app = Flask(__name__)

# Initialize components
nlp_processor = EnhancedNLPProcessor()
db_connector = RealDatabaseConnector()
bio_services = BioServices()

class BioNLIApplication:
    """Main application class for the BioNLI system"""
    
    def __init__(self):
        self.query_history = []
    
    def process_query(self, natural_language_query: str) -> Dict[str, Any]:
        """Process natural language query and return comprehensive results"""
        
        # Step 1: NLP Processing
        parsed_query = nlp_processor.parse_query(natural_language_query)
        
        # Step 2: Database Query Execution
        db_results = db_connector.execute_complex_query(parsed_query)
        
        # Step 3: Service Integration (if needed)
        service_results = self._integrate_services(parsed_query)
        
        # Step 4: Compile comprehensive response
        response = {
            'query_analysis': parsed_query,
            'database_results': db_results,
            'service_recommendations': service_results,
            'suggested_queries': self._generate_suggestions(parsed_query),
            'timestamp': time.time()
        }
        
        # Store in history
        self.query_history.append({
            'query': natural_language_query,
            'timestamp': time.time(),
            'results_count': len(db_results)
        })
        
        return response
    
    def _integrate_services(self, parsed_query: Dict) -> List[Dict]:
        """Integrate biological services based on query type"""
        services = []
        entities = parsed_query['entities']
        
        if parsed_query['query_type'] == 'homology' and 'gene' in entities:
            for gene_entity in entities['gene']:
                services.append(
                    bio_services.run_blast_search(gene_entity['text'])
                )
        
        elif parsed_query['query_type'] == 'function' and 'gene' in entities:
            for gene_entity in entities['gene']:
                services.extend(
                    bio_services.get_biological_pathways(gene_entity['text'])
                )
        
        return services
    
    def _generate_suggestions(self, parsed_query: Dict) -> List[str]:
        """Generate suggested follow-up queries"""
        suggestions = []
        entities = parsed_query['entities']
        
        if 'gene' in entities:
            gene_name = entities['gene'][0]['text']
            suggestions.extend([
                f"What is the function of {gene_name}?",
                f"Show me interactions for {gene_name}",
                f"Where is {gene_name} expressed?",
                f"Get the sequence of {gene_name}"
            ])
        
        return suggestions

# Initialize application
bio_nli_app = BioNLIApplication()

# Flask Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/query', methods=['POST'])
def process_nl_query():
    """API endpoint for natural language queries"""
    data = request.get_json()
    
    if not data or 'query' not in data:
        return jsonify({'error': 'No query provided'}), 400
    
    query = data['query']
    results = bio_nli_app.process_query(query)
    
    return jsonify(results)

@app.route('/api/history', methods=['GET'])
def get_history():
    """Get query history"""
    return jsonify({
        'history': bio_nli_app.query_history[-10:],  # Last 10 queries
        'total_queries': len(bio_nli_app.query_history)
    })

@app.route('/api/entities', methods=['POST'])
def extract_entities():
    """Extract entities from text"""
    data = request.get_json()
    
    if not data or 'text' not in data:
        return jsonify({'error': 'No text provided'}), 400
    
    parsed = nlp_processor.parse_query(data['text'])
    
    return jsonify({
        'entities': parsed['entities'],
        'query_type': parsed['query_type']
    })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)