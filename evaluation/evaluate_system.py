#!/usr/bin/env python3
"""
Performance evaluation script for BioNLI system
Generates quantifiable metrics for journal submission
"""

import sys
import os
import json
from datetime import datetime

# Add parent directory to path to import core modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.nlp_processor import EnhancedNLPProcessor
from core.database_connector import RealDatabaseConnector
from benchmark_questions import BioNLIBenchmark

def main():
    print("🧬 BioNLI Comprehensive Performance Evaluation")
    print("=" * 50)
    
    # Initialize system components
    print("Initializing BioNLI system components...")
    nlp_processor = EnhancedNLPProcessor()
    db_connector = RealDatabaseConnector()
    benchmark = BioNLIBenchmark()
    
    # Run comprehensive evaluation
    print("Running benchmark evaluation...")
    results = benchmark.evaluate_system(nlp_processor, db_connector)
    
    # Generate report
    report = benchmark.generate_performance_report(results)
    print(report)
    
    # Save results to file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_filename = f"evaluation_results_{timestamp}.json"
    report_filename = f"performance_report_{timestamp}.txt"
    
    # Save detailed results
    with open(results_filename, 'w') as f:
        json.dump(results, f, indent=2)
    
    # Save human-readable report
    with open(report_filename, 'w') as f:
        f.write(report)
    
    print(f"\n📊 Results saved to:")
    print(f"   - Detailed data: {results_filename}")
    print(f"   - Human-readable: {report_filename}")
    
    # Print summary for quick assessment
    print(f"\n🎯 QUICK SUMMARY FOR PUBLICATION:")
    print(f"   Overall Score: {results['overall_score']:.3f}")
    print(f"   Entity Recognition: {results['metrics']['entity_recognition_accuracy']:.3f}")
    print(f"   Query Classification: {results['metrics']['query_classification_accuracy']:.3f}")
    print(f"   Response Success: {results['metrics']['response_success_rate']:.3f}")
    
    # Interpretation for publication
    if results['overall_score'] >= 0.8:
        print("✅ EXCELLENT - Ready for high-impact journal submission")
    elif results['overall_score'] >= 0.6:
        print("⚠️ GOOD - Solid results, consider improvements before Nature submission")  
    else:
        print("🔧 NEEDS IMPROVEMENT - Focus on core components before submission")

if __name__ == "__main__":
    main()