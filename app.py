"""
BioNLI - Complete Publication-Ready Flask Application
Answers ANY biological question
"""

import os
import logging
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from dotenv import load_dotenv
import time
import uuid

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Initialize QA engine
from core.qa_engine import BioQuestionAnsweringEngine

EMAIL = os.getenv('NCBI_EMAIL', 'udaybioinfo@gmail.com')
USE_GPU = os.getenv('USE_GPU', 'False').lower() == 'true'

qa_engine = BioQuestionAnsweringEngine(email=EMAIL, use_gpu=USE_GPU)


@app.route('/')
def index():
    """Render main interface."""
    return render_template('index.html')


@app.route('/api/ask', methods=['POST'])
def ask():
    """Answer any biological question."""
    start_time = time.time()
    request_id = str(uuid.uuid4())
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        question = data.get('question', '').strip()
        
        if not question:
            return jsonify({'error': 'No question provided'}), 400
        
        logger.info(f"Request {request_id}: {question[:100]}...")
        
        answer = qa_engine.answer(question)
        answer['request_id'] = request_id
        answer['response_time'] = time.time() - start_time
        
        return jsonify(answer)
        
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        return jsonify({'error': str(e), 'request_id': request_id}), 500


@app.route('/api/stats', methods=['GET'])
def stats():
    """Get system statistics."""
    return jsonify(qa_engine.get_stats())


@app.route('/api/health', methods=['GET'])
def health():
    """Health check."""
    return jsonify({
        'status': 'healthy',
        'version': '2.0',
        'timestamp': time.time()
    })


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
    
    print("\n" + "=" * 70)
    print("🔬 BioNLI - Publication-Ready System")
    print("=" * 70)
    print(f"📍 Server: http://localhost:{port}")
    print(f"📊 System Stats:")
    stats = qa_engine.get_stats()
    print(f"   - HGNC Genes: {stats['hgnc_genes']:,}")
    print(f"   - GO Terms: {stats['go_terms']:,}")
    print(f"   - Data Sources: {len(stats['source_stats'])}")
    print("=" * 70)
    print("\n✅ Ready to answer ANY biological question!")
    print("💡 Try: http://localhost:5000")
    print("=" * 70 + "\n")
    
    app.run(host='0.0.0.0', port=port, debug=debug)