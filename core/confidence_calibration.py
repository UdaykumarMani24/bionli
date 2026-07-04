"""
Confidence Calibration Module - Publication Quality
Implements temperature scaling and bin-based calibration.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass, field
import json
import os
import logging

logger = logging.getLogger(__name__)


@dataclass
class CalibrationBin:
    """Represents a confidence bin for calibration."""
    lower: float
    upper: float
    expected_accuracy: float
    count: int = 0
    correct: int = 0


@dataclass
class CalibrationResults:
    """Results of confidence calibration."""
    temperature: float
    ece: float  # Expected Calibration Error
    mce: float  # Maximum Calibration Error
    bins: List[CalibrationBin]
    calibration_curve: Dict[str, List[float]]
    
    def to_dict(self) -> dict:
        return {
            'temperature': self.temperature,
            'ece': self.ece,
            'mce': self.mce,
            'bins': [{'lower': b.lower, 'upper': b.upper, 
                      'expected_accuracy': b.expected_accuracy,
                      'count': b.count, 'correct': b.correct} for b in self.bins],
            'calibration_curve': self.calibration_curve
        }
    
    def save(self, path: str):
        """Save calibration results to file."""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
        logger.info(f"Calibration results saved to {path}")
    
    @classmethod
    def load(cls, path: str) -> 'CalibrationResults':
        """Load calibration results from file."""
        with open(path, 'r') as f:
            data = json.load(f)
        
        bins = [CalibrationBin(
            lower=b['lower'],
            upper=b['upper'],
            expected_accuracy=b['expected_accuracy'],
            count=b.get('count', 0),
            correct=b.get('correct', 0)
        ) for b in data['bins']]
        
        return cls(
            temperature=data['temperature'],
            ece=data['ece'],
            mce=data['mce'],
            bins=bins,
            calibration_curve=data['calibration_curve']
        )


class TemperatureScaler(nn.Module):
    """
    Temperature scaling for confidence calibration.
    Learns a single temperature parameter to calibrate confidence scores.
    """
    
    def __init__(self, init_temp: float = 1.0):
        super().__init__()
        self.temperature = nn.Parameter(torch.ones(1) * init_temp)
    
    def forward(self, logits: torch.Tensor) -> torch.Tensor:
        """Apply temperature scaling to logits."""
        return logits / self.temperature
    
    def calibrate_probabilities(self, logits: torch.Tensor) -> torch.Tensor:
        """Convert logits to calibrated probabilities."""
        scaled_logits = self.forward(logits)
        return F.softmax(scaled_logits, dim=-1)


class ConfidenceCalibrator:
    """
    Confidence calibration using temperature scaling and bin-based adjustment.
    """
    
    def __init__(self, n_bins: int = 10, min_samples_per_bin: int = 10):
        """
        Initialize calibrator.
        
        Args:
            n_bins: Number of bins for calibration
            min_samples_per_bin: Minimum samples required per bin
        """
        self.n_bins = n_bins
        self.min_samples_per_bin = min_samples_per_bin
        self.temperature_scaler = TemperatureScaler()
        self.calibration_bins = []
        self.is_fitted = False
        
        logger.info(f"ConfidenceCalibrator initialized with {n_bins} bins")
    
    def fit(self, logits: List[torch.Tensor], 
            labels: List[int],
            val_logits: List[torch.Tensor] = None,
            val_labels: List[int] = None) -> CalibrationResults:
        """
        Fit temperature scaling and bin calibration.
        
        Args:
            logits: Model logits for training
            labels: True labels
            val_logits: Validation logits (optional)
            val_labels: Validation labels (optional)
            
        Returns:
            CalibrationResults with fitted parameters
        """
        logger.info("Fitting confidence calibration...")
        
        # Use validation data if provided, otherwise use training data
        calib_logits = val_logits if val_logits else logits
        calib_labels = val_labels if val_labels else labels
        
        # Convert to tensors
        logits_tensor = torch.stack(calib_logits) if isinstance(calib_logits[0], torch.Tensor) else torch.tensor(calib_logits)
        labels_tensor = torch.tensor(calib_labels)
        
        # Optimize temperature
        temperature = self._optimize_temperature(logits_tensor, labels_tensor)
        self.temperature_scaler.temperature.data = torch.tensor([temperature])
        
        # Apply temperature scaling
        scaled_logits = self.temperature_scaler(logits_tensor)
        probabilities = F.softmax(scaled_logits, dim=-1)
        predicted_probs, predicted_labels = torch.max(probabilities, dim=-1)
        
        # Compute bin calibration
        bins = self._compute_bins(predicted_probs.numpy(), predicted_labels.numpy(), 
                                   calib_labels, n_bins=self.n_bins)
        
        # Compute calibration errors
        ece = self._compute_ece(bins)
        mce = self._compute_mce(bins)
        
        self.calibration_bins = bins
        self.is_fitted = True
        
        results = CalibrationResults(
            temperature=float(temperature),
            ece=ece,
            mce=mce,
            bins=bins,
            calibration_curve={
                'confidence': [b.expected_accuracy for b in bins],
                'accuracy': [b.expected_accuracy for b in bins],  # Will be refined
                'counts': [b.count for b in bins]
            }
        )
        
        logger.info(f"Calibration complete: temperature={temperature:.3f}, ECE={ece:.4f}")
        return results
    
    def _optimize_temperature(self, logits: torch.Tensor, labels: torch.Tensor) -> float:
        """
        Optimize temperature using negative log-likelihood.
        
        Args:
            logits: Model logits
            labels: True labels
            
        Returns:
            Optimal temperature
        """
        # Use L-BFGS for optimization
        nll_criterion = nn.CrossEntropyLoss()
        
        def compute_nll(temp):
            scaled_logits = logits / temp
            return nll_criterion(scaled_logits, labels)
        
        # Search over temperature values
        best_temp = 1.0
        best_nll = compute_nll(torch.tensor(1.0))
        
        for temp in np.linspace(0.5, 2.0, 30):
            nll = compute_nll(torch.tensor(temp))
            if nll < best_nll:
                best_nll = nll
                best_temp = temp
        
        return best_temp
    
    def _compute_bins(self, probs: np.ndarray, preds: np.ndarray, 
                      labels: List[int], n_bins: int = 10) -> List[CalibrationBin]:
        """
        Compute bin-based calibration.
        
        Args:
            probs: Predicted probabilities
            preds: Predicted labels
            labels: True labels
            n_bins: Number of bins
            
        Returns:
            List of calibration bins
        """
        bins = []
        bin_edges = np.linspace(0, 1, n_bins + 1)
        
        for i in range(n_bins):
            lower = bin_edges[i]
            upper = bin_edges[i + 1]
            
            # Find samples in this bin
            mask = (probs >= lower) & (probs < upper)
            bin_probs = probs[mask]
            bin_preds = preds[mask]
            bin_labels = np.array(labels)[mask] if isinstance(labels, list) else labels[mask]
            
            if len(bin_probs) < self.min_samples_per_bin:
                # Use neighboring bins if too few samples
                continue
            
            # Compute accuracy in this bin
            correct = np.sum(bin_preds == bin_labels)
            accuracy = correct / len(bin_probs) if len(bin_probs) > 0 else 0
            
            # Expected confidence is average probability in bin
            expected_confidence = np.mean(bin_probs) if len(bin_probs) > 0 else 0
            
            bins.append(CalibrationBin(
                lower=float(lower),
                upper=float(upper),
                expected_accuracy=float(accuracy),
                count=len(bin_probs),
                correct=int(correct)
            ))
        
        return bins
    
    def _compute_ece(self, bins: List[CalibrationBin]) -> float:
        """Compute Expected Calibration Error."""
        total_samples = sum(b.count for b in bins)
        if total_samples == 0:
            return 0.0
        
        ece = 0.0
        for bin_info in bins:
            if bin_info.count > 0:
                confidence = (bin_info.lower + bin_info.upper) / 2
                accuracy = bin_info.expected_accuracy
                weight = bin_info.count / total_samples
                ece += weight * abs(confidence - accuracy)
        
        return ece
    
    def _compute_mce(self, bins: List[CalibrationBin]) -> float:
        """Compute Maximum Calibration Error."""
        max_error = 0.0
        for bin_info in bins:
            if bin_info.count > 0:
                confidence = (bin_info.lower + bin_info.upper) / 2
                accuracy = bin_info.expected_accuracy
                error = abs(confidence - accuracy)
                max_error = max(max_error, error)
        
        return max_error
    
    def calibrate_confidence(self, raw_confidence: float, entity_type: str = None) -> float:
        """
        Calibrate raw confidence score using fitted bins.
        
        Args:
            raw_confidence: Raw model confidence (0-1)
            entity_type: Entity type for type-specific calibration
            
        Returns:
            Calibrated confidence score
        """
        if not self.is_fitted:
            logger.warning("Calibrator not fitted, returning raw confidence")
            return raw_confidence
        
        # Find appropriate bin
        for bin_info in self.calibration_bins:
            if bin_info.lower <= raw_confidence <= bin_info.upper:
                return bin_info.expected_accuracy
        
        # If outside all bins, return raw confidence scaled
        if raw_confidence > self.calibration_bins[-1].upper:
            return min(raw_confidence * 0.95, 0.95)
        else:
            return raw_confidence * 0.9
    
    def get_calibration_curve(self) -> Dict[str, List[float]]:
        """Get calibration curve data."""
        if not self.is_fitted:
            return {'confidence': [], 'accuracy': [], 'counts': []}
        
        return {
            'confidence': [(b.lower + b.upper) / 2 for b in self.calibration_bins],
            'accuracy': [b.expected_accuracy for b in self.calibration_bins],
            'counts': [b.count for b in self.calibration_bins]
        }


class EntityConfidenceCalibrator:
    """
    Entity-specific confidence calibration.
    """
    
    def __init__(self, entity_types: List[str]):
        self.calibrators = {
            entity_type: ConfidenceCalibrator() 
            for entity_type in entity_types
        }
        self.entity_types = entity_types
        self.global_calibrator = ConfidenceCalibrator()
        self.is_fitted = False
        
        logger.info(f"EntityConfidenceCalibrator initialized for {len(entity_types)} entity types")
    
    def fit(self, entity_data: Dict[str, List[Tuple[float, bool]]]):
        """
        Fit calibrators for each entity type.
        
        Args:
            entity_data: Dictionary mapping entity type to list of (confidence, is_correct) pairs
        """
        for entity_type, data in entity_data.items():
            if entity_type in self.calibrators:
                # Convert to bin format
                bins = self._create_bins_from_data(data)
                self.calibrators[entity_type].calibration_bins = bins
                self.calibrators[entity_type].is_fitted = True
        
        # Fit global calibrator
        all_data = []
        for data in entity_data.values():
            all_data.extend(data)
        global_bins = self._create_bins_from_data(all_data)
        self.global_calibrator.calibration_bins = global_bins
        self.global_calibrator.is_fitted = True
        self.is_fitted = True
        
        logger.info("Entity confidence calibration complete")
    
    def _create_bins_from_data(self, data: List[Tuple[float, bool]]) -> List[CalibrationBin]:
        """Create calibration bins from confidence data."""
        bins = []
        bin_edges = np.linspace(0, 1, 11)
        
        for i in range(10):
            lower = bin_edges[i]
            upper = bin_edges[i + 1]
            
            bin_data = [(c, corr) for c, corr in data if lower <= c <= upper]
            
            if bin_data:
                avg_confidence = np.mean([c for c, _ in bin_data])
                accuracy = np.mean([1 if corr else 0 for _, corr in bin_data])
                
                bins.append(CalibrationBin(
                    lower=float(lower),
                    upper=float(upper),
                    expected_accuracy=float(accuracy),
                    count=len(bin_data),
                    correct=int(sum(1 for _, corr in bin_data if corr))
                ))
        
        return bins
    
    def calibrate_entity_confidence(self, raw_confidence: float, entity_type: str) -> float:
        """
        Calibrate confidence for specific entity type.
        
        Args:
            raw_confidence: Raw model confidence
            entity_type: Type of entity
            
        Returns:
            Calibrated confidence
        """
        if not self.is_fitted:
            return raw_confidence
        
        if entity_type in self.calibrators:
            return self.calibrators[entity_type].calibrate_confidence(raw_confidence, entity_type)
        
        return self.global_calibrator.calibrate_confidence(raw_confidence, entity_type)
    
    def save(self, path: str):
        """Save calibrator to disk."""
        data = {
            'entity_types': self.entity_types,
            'calibration_data': {}
        }
        
        for entity_type, calibrator in self.calibrators.items():
            if calibrator.is_fitted:
                data['calibration_data'][entity_type] = {
                    'bins': [(b.lower, b.upper, b.expected_accuracy, b.count) 
                            for b in calibrator.calibration_bins]
                }
        
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Calibrator saved to {path}")
    
    @classmethod
    def load(cls, path: str) -> 'EntityConfidenceCalibrator':
        """Load calibrator from disk."""
        with open(path, 'r') as f:
            data = json.load(f)
        
        calibrator = cls(data['entity_types'])
        
        for entity_type, calib_data in data.get('calibration_data', {}).items():
            if entity_type in calibrator.calibrators:
                bins = []
                for lower, upper, accuracy, count in calib_data['bins']:
                    bins.append(CalibrationBin(
                        lower=lower,
                        upper=upper,
                        expected_accuracy=accuracy,
                        count=count,
                        correct=int(accuracy * count) if count > 0 else 0
                    ))
                calibrator.calibrators[entity_type].calibration_bins = bins
                calibrator.calibrators[entity_type].is_fitted = True
        
        calibrator.is_fitted = True
        return calibrator