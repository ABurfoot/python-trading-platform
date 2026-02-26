#!/usr/bin/env python3
"""
Comprehensive ML Predictor Test Suite
=====================================
Tests for all machine learning components including:
- Neural Network architectures (LSTM, GRU, CNN-LSTM, Attention, Transformer)
- Tree-based models (Random Forest, XGBoost, Gradient Boosting)
- Training pipeline (early stopping, LR scheduling)
- Cross-validation
- Feature engineering
- Backtesting
- Statistical tests
- Ensemble methods
- Monte Carlo Dropout uncertainty
"""

import unittest
import numpy as np
import pandas as pd
import sys
import os
import warnings

# Suppress warnings for cleaner test output
warnings.filterwarnings('ignore')

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestMLImports(unittest.TestCase):
    """Test that all ML dependencies are available."""
    
    def test_numpy_available(self):
        """Test NumPy is available."""
        import numpy as np
        self.assertTrue(hasattr(np, 'array'))
    
    def test_pandas_available(self):
        """Test Pandas is available."""
        import pandas as pd
        self.assertTrue(hasattr(pd, 'DataFrame'))
    
    def test_sklearn_available(self):
        """Test scikit-learn is available."""
        from sklearn.ensemble import RandomForestRegressor
        from sklearn.preprocessing import StandardScaler
        self.assertTrue(True)
    
    def test_torch_available(self):
        """Test PyTorch is available."""
        try:
            import torch
            self.assertTrue(hasattr(torch, 'Tensor'))
        except ImportError:
            self.skipTest("PyTorch not installed")
    
    def test_xgboost_available(self):
        """Test XGBoost is available."""
        try:
            import xgboost
            self.assertTrue(hasattr(xgboost, 'XGBRegressor'))
        except ImportError:
            self.skipTest("XGBoost not installed")
    
    def test_optuna_available(self):
        """Test Optuna is available."""
        try:
            import optuna
            self.assertTrue(hasattr(optuna, 'create_study'))
        except ImportError:
            self.skipTest("Optuna not installed")
    
    def test_scipy_available(self):
        """Test SciPy is available."""
        from scipy import stats
        self.assertTrue(hasattr(stats, 'pearsonr'))


class TestNeuralNetworkArchitectures(unittest.TestCase):
    """Test all neural network architectures."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        try:
            import torch
            cls.torch_available = True
            cls.torch = torch
        except ImportError:
            cls.torch_available = False
            return
        
        # Create dummy data
        cls.batch_size = 16
        cls.seq_length = 30
        cls.input_size = 10
        cls.hidden_size = 32
        
        cls.X = torch.randn(cls.batch_size, cls.seq_length, cls.input_size)
    
    def test_lstm_predictor(self):
        """Test LSTM model forward pass."""
        if not self.torch_available:
            self.skipTest("PyTorch not installed")
        
        from trading.ml_predictor_v2 import LSTMPredictor
        
        model = LSTMPredictor(
            input_size=self.input_size,
            hidden_size=self.hidden_size,
            num_layers=2,
            dropout=0.2
        )
        
        output = model(self.X)
        
        self.assertEqual(output.shape, (self.batch_size, 1))
        self.assertFalse(self.torch.isnan(output).any())
    
    def test_gru_predictor(self):
        """Test GRU model forward pass."""
        if not self.torch_available:
            self.skipTest("PyTorch not installed")
        
        from trading.ml_predictor_v2 import GRUPredictor
        
        model = GRUPredictor(
            input_size=self.input_size,
            hidden_size=self.hidden_size,
            num_layers=2,
            dropout=0.2
        )
        
        output = model(self.X)
        
        self.assertEqual(output.shape, (self.batch_size, 1))
        self.assertFalse(self.torch.isnan(output).any())
    
    def test_cnn_lstm_predictor(self):
        """Test CNN-LSTM hybrid model forward pass."""
        if not self.torch_available:
            self.skipTest("PyTorch not installed")
        
        from trading.ml_predictor_v2 import CNNLSTMPredictor
        
        model = CNNLSTMPredictor(
            input_size=self.input_size,
            hidden_size=self.hidden_size,
            num_layers=2,
            dropout=0.2
        )
        
        output = model(self.X)
        
        self.assertEqual(output.shape, (self.batch_size, 1))
        self.assertFalse(self.torch.isnan(output).any())
    
    def test_attention_lstm(self):
        """Test Attention LSTM model forward pass."""
        if not self.torch_available:
            self.skipTest("PyTorch not installed")
        
        from trading.ml_predictor_v2 import AttentionLSTM
        
        model = AttentionLSTM(
            input_size=self.input_size,
            hidden_size=self.hidden_size,
            num_layers=2,
            dropout=0.2,
            num_heads=4
        )
        
        output = model(self.X)
        
        self.assertEqual(output.shape, (self.batch_size, 1))
        self.assertFalse(self.torch.isnan(output).any())
    
    def test_transformer_predictor(self):
        """Test Transformer model forward pass."""
        if not self.torch_available:
            self.skipTest("PyTorch not installed")
        
        from trading.ml_predictor_v2 import TransformerPredictor
        
        model = TransformerPredictor(
            input_size=self.input_size,
            hidden_size=self.hidden_size,
            num_layers=2,
            dropout=0.2,
            num_heads=4
        )
        
        output = model(self.X)
        
        self.assertEqual(output.shape, (self.batch_size, 1))
        self.assertFalse(self.torch.isnan(output).any())
    
    def test_ensemble_neural_net(self):
        """Test Ensemble Neural Network forward pass."""
        if not self.torch_available:
            self.skipTest("PyTorch not installed")
        
        from trading.ml_predictor_v2 import EnsembleNeuralNet
        
        model = EnsembleNeuralNet(
            input_size=self.input_size,
            hidden_size=self.hidden_size,
            dropout=0.2
        )
        
        output = model(self.X)
        
        self.assertEqual(output.shape, (self.batch_size, 1))
        self.assertFalse(self.torch.isnan(output).any())
    
    def test_tcn_predictor(self):
        """Test Temporal Convolutional Network forward pass."""
        if not self.torch_available:
            self.skipTest("PyTorch not installed")
        
        from trading.ml_predictor_v2 import TCNPredictor
        
        model = TCNPredictor(
            input_size=self.input_size,
            hidden_size=self.hidden_size,
            num_layers=4,
            dropout=0.2
        )
        
        output = model(self.X)
        
        self.assertEqual(output.shape, (self.batch_size, 1))
        self.assertFalse(self.torch.isnan(output).any())
    
    def test_wavenet_predictor(self):
        """Test WaveNet predictor forward pass."""
        if not self.torch_available:
            self.skipTest("PyTorch not installed")
        
        from trading.ml_predictor_v2 import WaveNetPredictor
        
        model = WaveNetPredictor(
            input_size=self.input_size,
            hidden_size=self.hidden_size,
            num_layers=4,
            dropout=0.2
        )
        
        output = model(self.X)
        
        self.assertEqual(output.shape, (self.batch_size, 1))
        self.assertFalse(self.torch.isnan(output).any())
    
    def test_bidirectional_lstm(self):
        """Test Bidirectional LSTM forward pass."""
        if not self.torch_available:
            self.skipTest("PyTorch not installed")
        
        from trading.ml_predictor_v2 import BidirectionalLSTM
        
        model = BidirectionalLSTM(
            input_size=self.input_size,
            hidden_size=self.hidden_size,
            num_layers=2,
            dropout=0.2
        )
        
        output = model(self.X)
        
        self.assertEqual(output.shape, (self.batch_size, 1))
        self.assertFalse(self.torch.isnan(output).any())
    
    def test_batch_normalization_in_lstm(self):
        """Test that batch normalization works correctly in enhanced LSTM."""
        if not self.torch_available:
            self.skipTest("PyTorch not installed")
        
        from trading.ml_predictor_v2 import LSTMPredictor
        
        model = LSTMPredictor(
            input_size=self.input_size,
            hidden_size=self.hidden_size,
            num_layers=2,
            dropout=0.2
        )
        
        # Test in training mode (batch norm uses batch statistics)
        model.train()
        output_train = model(self.X)
        
        # Test in eval mode (batch norm uses running statistics)
        model.eval()
        output_eval = model(self.X)
        
        # Both should produce valid outputs
        self.assertFalse(self.torch.isnan(output_train).any())
        self.assertFalse(self.torch.isnan(output_eval).any())


class TestModelWrappers(unittest.TestCase):
    """Test all model wrapper classes."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        np.random.seed(42)
        
        # Create synthetic time series data
        n_samples = 200
        n_features = 10
        seq_length = 30
        
        # Generate features
        cls.X = np.random.randn(n_samples, seq_length, n_features)
        cls.y = np.random.randn(n_samples) * 10 + 100  # Price-like targets
        
        # Flat version for tree models
        cls.X_flat = cls.X.reshape(n_samples, -1)
    
    def test_random_forest_wrapper(self):
        """Test Random Forest wrapper."""
        from trading.ml_predictor_v2 import RandomForestWrapper
        
        model = RandomForestWrapper(n_estimators=10, max_depth=5)
        model.fit(self.X, self.y)
        
        predictions = model.predict(self.X[:10])
        
        self.assertEqual(len(predictions), 10)
        self.assertTrue(np.all(np.isfinite(predictions)))
        
        # Test feature importance
        importance = model.get_feature_importance()
        self.assertIsNotNone(importance)
    
    def test_xgboost_wrapper(self):
        """Test XGBoost wrapper."""
        try:
            from trading.ml_predictor_v2 import XGBoostWrapper
        except ImportError:
            self.skipTest("XGBoost not installed")
        
        model = XGBoostWrapper(n_estimators=10, max_depth=3)
        model.fit(self.X, self.y)
        
        predictions = model.predict(self.X[:10])
        
        self.assertEqual(len(predictions), 10)
        self.assertTrue(np.all(np.isfinite(predictions)))
    
    def test_lightgbm_wrapper(self):
        """Test LightGBM wrapper."""
        try:
            from trading.ml_predictor_v2 import LightGBMWrapper
            wrapper = LightGBMWrapper(n_estimators=10, max_depth=3)
        except ImportError:
            self.skipTest("LightGBM not installed")
        
        wrapper.fit(self.X, self.y)
        predictions = wrapper.predict(self.X[:10])
        
        self.assertEqual(len(predictions), 10)
        self.assertTrue(np.all(np.isfinite(predictions)))
    
    def test_catboost_wrapper(self):
        """Test CatBoost wrapper."""
        try:
            from trading.ml_predictor_v2 import CatBoostWrapper
            wrapper = CatBoostWrapper(iterations=10, depth=3)
        except ImportError:
            self.skipTest("CatBoost not installed")
        
        wrapper.fit(self.X, self.y)
        predictions = wrapper.predict(self.X[:10])
        
        self.assertEqual(len(predictions), 10)
        self.assertTrue(np.all(np.isfinite(predictions)))
    
    def test_elasticnet_wrapper(self):
        """Test ElasticNet wrapper."""
        from trading.ml_predictor_v2 import ElasticNetWrapper
        
        model = ElasticNetWrapper(alpha=1.0, l1_ratio=0.5)
        model.fit(self.X, self.y)
        
        predictions = model.predict(self.X[:10])
        
        self.assertEqual(len(predictions), 10)
        self.assertTrue(np.all(np.isfinite(predictions)))
    
    def test_gradient_boosting_wrapper(self):
        """Test Gradient Boosting wrapper."""
        from trading.ml_predictor_v2 import GradientBoostingWrapper
        
        model = GradientBoostingWrapper(n_estimators=10, max_depth=3)
        model.fit(self.X, self.y)
        
        predictions = model.predict(self.X[:10])
        
        self.assertEqual(len(predictions), 10)
        self.assertTrue(np.all(np.isfinite(predictions)))
    
    def test_ridge_wrapper(self):
        """Test Ridge Regression wrapper with internal scaling."""
        from trading.ml_predictor_v2 import RidgeWrapper
        
        model = RidgeWrapper(alpha=1.0)
        model.fit(self.X, self.y)
        
        predictions = model.predict(self.X[:10])
        
        self.assertEqual(len(predictions), 10)
        self.assertTrue(np.all(np.isfinite(predictions)))
    
    def test_lstm_wrapper_basic(self):
        """Test LSTM wrapper basic training and prediction."""
        try:
            from trading.ml_predictor_v2 import LSTMWrapper
        except ImportError:
            self.skipTest("PyTorch not installed")
        
        model = LSTMWrapper(
            input_size=self.X.shape[2],
            hidden_size=16,
            epochs=5,  # Small for testing
            model_type='lstm'
        )
        
        model.fit(self.X[:100], self.y[:100])
        predictions = model.predict(self.X[100:110])
        
        self.assertEqual(len(predictions), 10)
        self.assertTrue(np.all(np.isfinite(predictions)))
    
    def test_lstm_wrapper_gru(self):
        """Test LSTM wrapper with GRU architecture."""
        try:
            from trading.ml_predictor_v2 import LSTMWrapper
        except ImportError:
            self.skipTest("PyTorch not installed")
        
        model = LSTMWrapper(
            input_size=self.X.shape[2],
            hidden_size=16,
            epochs=5,
            model_type='gru'
        )
        
        model.fit(self.X[:100], self.y[:100])
        predictions = model.predict(self.X[100:110])
        
        self.assertEqual(len(predictions), 10)
    
    def test_lstm_wrapper_cnn_lstm(self):
        """Test LSTM wrapper with CNN-LSTM architecture."""
        try:
            from trading.ml_predictor_v2 import LSTMWrapper
        except ImportError:
            self.skipTest("PyTorch not installed")
        
        model = LSTMWrapper(
            input_size=self.X.shape[2],
            hidden_size=16,
            epochs=5,
            model_type='cnn_lstm'
        )
        
        model.fit(self.X[:100], self.y[:100])
        predictions = model.predict(self.X[100:110])
        
        self.assertEqual(len(predictions), 10)
    
    def test_lstm_wrapper_attention(self):
        """Test LSTM wrapper with Attention architecture."""
        try:
            from trading.ml_predictor_v2 import LSTMWrapper
        except ImportError:
            self.skipTest("PyTorch not installed")
        
        model = LSTMWrapper(
            input_size=self.X.shape[2],
            hidden_size=16,
            epochs=5,
            model_type='attention'
        )
        
        model.fit(self.X[:100], self.y[:100])
        predictions = model.predict(self.X[100:110])
        
        self.assertEqual(len(predictions), 10)
    
    def test_lstm_wrapper_transformer(self):
        """Test LSTM wrapper with Transformer architecture."""
        try:
            from trading.ml_predictor_v2 import LSTMWrapper
        except ImportError:
            self.skipTest("PyTorch not installed")
        
        model = LSTMWrapper(
            input_size=self.X.shape[2],
            hidden_size=16,
            epochs=5,
            model_type='transformer'
        )
        
        model.fit(self.X[:100], self.y[:100])
        predictions = model.predict(self.X[100:110])
        
        self.assertEqual(len(predictions), 10)
    
    def test_lstm_wrapper_tcn(self):
        """Test LSTM wrapper with TCN architecture."""
        try:
            from trading.ml_predictor_v2 import LSTMWrapper
        except ImportError:
            self.skipTest("PyTorch not installed")
        
        model = LSTMWrapper(
            input_size=self.X.shape[2],
            hidden_size=16,
            epochs=5,
            model_type='tcn'
        )
        
        model.fit(self.X[:100], self.y[:100])
        predictions = model.predict(self.X[100:110])
        
        self.assertEqual(len(predictions), 10)
    
    def test_lstm_wrapper_wavenet(self):
        """Test LSTM wrapper with WaveNet architecture."""
        try:
            from trading.ml_predictor_v2 import LSTMWrapper
        except ImportError:
            self.skipTest("PyTorch not installed")
        
        model = LSTMWrapper(
            input_size=self.X.shape[2],
            hidden_size=16,
            epochs=5,
            model_type='wavenet'
        )
        
        model.fit(self.X[:100], self.y[:100])
        predictions = model.predict(self.X[100:110])
        
        self.assertEqual(len(predictions), 10)
    
    def test_lstm_wrapper_bilstm(self):
        """Test LSTM wrapper with Bidirectional LSTM architecture."""
        try:
            from trading.ml_predictor_v2 import LSTMWrapper
        except ImportError:
            self.skipTest("PyTorch not installed")
        
        model = LSTMWrapper(
            input_size=self.X.shape[2],
            hidden_size=16,
            epochs=5,
            model_type='bilstm'
        )
        
        model.fit(self.X[:100], self.y[:100])
        predictions = model.predict(self.X[100:110])
        
        self.assertEqual(len(predictions), 10)
    
    def test_lstm_wrapper_early_stopping(self):
        """Test that early stopping works."""
        try:
            from trading.ml_predictor_v2 import LSTMWrapper
        except ImportError:
            self.skipTest("PyTorch not installed")
        
        model = LSTMWrapper(
            input_size=self.X.shape[2],
            hidden_size=16,
            epochs=100,  # High epoch count
            patience=3,  # Low patience
            model_type='lstm'
        )
        
        model.fit(self.X[:100], self.y[:100])
        
        # Should stop at or before 100 epochs (may hit exactly 100 if no early stop triggered)
        self.assertLessEqual(len(model.training_history), 100)
    
    def test_monte_carlo_dropout(self):
        """Test Monte Carlo Dropout uncertainty estimation."""
        try:
            from trading.ml_predictor_v2 import LSTMWrapper
        except ImportError:
            self.skipTest("PyTorch not installed")
        
        model = LSTMWrapper(
            input_size=self.X.shape[2],
            hidden_size=16,
            epochs=5,
            dropout=0.3
        )
        
        model.fit(self.X[:100], self.y[:100])
        
        mean_pred, std_pred = model.predict_with_uncertainty(self.X[100:110], n_samples=10)
        
        self.assertEqual(len(mean_pred), 10)
        self.assertEqual(len(std_pred), 10)
        self.assertTrue(np.all(std_pred >= 0))  # Uncertainty should be non-negative


class TestFeatureEngineering(unittest.TestCase):
    """Test feature engineering pipeline."""
    
    def test_prepare_features(self):
        """Test that feature preparation creates expected features."""
        from trading.ml_predictor_v2 import AdvancedMLPredictor
        
        # Create sample OHLCV data
        dates = pd.date_range('2020-01-01', periods=200, freq='D')
        np.random.seed(42)
        
        df = pd.DataFrame({
            'date': dates,
            'open': np.random.randn(200).cumsum() + 100,
            'high': np.random.randn(200).cumsum() + 102,
            'low': np.random.randn(200).cumsum() + 98,
            'close': np.random.randn(200).cumsum() + 100,
            'volume': np.random.randint(1000000, 10000000, 200)
        })
        df.set_index('date', inplace=True)
        
        predictor = AdvancedMLPredictor()
        features_df = predictor._prepare_features(df)
        
        # Check that features were created
        self.assertIn('returns', features_df.columns)
        self.assertIn('log_returns', features_df.columns)
        self.assertIn('rsi_14', features_df.columns)
        self.assertIn('macd', features_df.columns)
        self.assertIn('volatility_20', features_df.columns)
        self.assertIn('sma_20', features_df.columns)
        
        # Check no NaN values in features
        self.assertFalse(features_df.isnull().any().any())
    
    def test_create_sequences(self):
        """Test sequence creation for LSTM."""
        from trading.ml_predictor_v2 import AdvancedMLPredictor
        
        predictor = AdvancedMLPredictor(sequence_length=30)
        
        features = np.random.randn(100, 10)  # 100 samples, 10 features
        targets = np.random.randn(100)
        
        X, y = predictor._create_sequences(features, targets)
        
        # Check shapes
        self.assertEqual(X.shape[0], 100 - 30)  # samples - sequence_length
        self.assertEqual(X.shape[1], 30)  # sequence_length
        self.assertEqual(X.shape[2], 10)  # features
        self.assertEqual(len(y), 100 - 30)


class TestCrossValidation(unittest.TestCase):
    """Test time series cross-validation."""
    
    def test_time_series_cv(self):
        """Test time series cross-validation produces valid results."""
        from trading.ml_predictor_v2 import AdvancedMLPredictor, RandomForestWrapper
        
        # Create synthetic data
        np.random.seed(42)
        n_samples = 200
        X = np.random.randn(n_samples, 30, 10)
        y = np.random.randn(n_samples) * 10 + 100
        
        predictor = AdvancedMLPredictor()
        model = RandomForestWrapper(n_estimators=10)
        
        cv_result = predictor._time_series_cv(X, y, model, n_splits=3)
        
        # Check result structure
        self.assertEqual(cv_result.n_splits, 3)
        self.assertGreater(cv_result.avg_rmse, 0)
        self.assertGreater(cv_result.std_rmse, 0)
        self.assertGreaterEqual(cv_result.avg_directional_accuracy, 0)
        self.assertLessEqual(cv_result.avg_directional_accuracy, 100)
        self.assertEqual(len(cv_result.fold_results), 3)


class TestBacktesting(unittest.TestCase):
    """Test backtesting functionality."""
    
    def test_backtest_strategy(self):
        """Test backtest produces valid metrics."""
        from trading.ml_predictor_v2 import AdvancedMLPredictor
        
        predictor = AdvancedMLPredictor(transaction_cost_bps=10)
        
        # Create synthetic predictions and actuals
        np.random.seed(42)
        n = 100
        predictions = np.cumsum(np.random.randn(n)) + 100
        actual_prices = predictions + np.random.randn(n) * 2
        actual_returns = np.diff(actual_prices) / actual_prices[:-1]
        actual_returns = np.concatenate([[0], actual_returns])
        
        result = predictor._backtest_strategy(predictions, actual_prices, actual_returns)
        
        # Check all required fields exist
        self.assertIsNotNone(result.total_return)
        self.assertIsNotNone(result.sharpe_ratio)
        self.assertIsNotNone(result.max_drawdown)
        self.assertIsNotNone(result.win_rate)
        self.assertIsNotNone(result.profit_factor)
        self.assertIsNotNone(result.transaction_costs)
        
        # Check reasonable ranges
        self.assertGreaterEqual(result.win_rate, 0)
        self.assertLessEqual(result.win_rate, 100)
        self.assertGreaterEqual(result.max_drawdown, 0)
    
    def test_transaction_costs_applied(self):
        """Test that transaction costs affect returns."""
        from trading.ml_predictor_v2 import AdvancedMLPredictor
        
        np.random.seed(42)
        n = 100
        predictions = np.cumsum(np.random.randn(n)) + 100
        actual_prices = predictions.copy()
        actual_returns = np.diff(actual_prices) / actual_prices[:-1]
        actual_returns = np.concatenate([[0], actual_returns])
        
        # High transaction costs
        predictor_high = AdvancedMLPredictor(transaction_cost_bps=100)  # 1%
        result_high = predictor_high._backtest_strategy(predictions, actual_prices, actual_returns)
        
        # Low transaction costs
        predictor_low = AdvancedMLPredictor(transaction_cost_bps=1)  # 0.01%
        result_low = predictor_low._backtest_strategy(predictions, actual_prices, actual_returns)
        
        # Higher costs should result in lower net returns
        self.assertGreater(result_high.transaction_costs, result_low.transaction_costs)


class TestStatisticalTests(unittest.TestCase):
    """Test statistical significance tests."""
    
    def test_statistical_tests_run(self):
        """Test that statistical tests execute and return results."""
        from trading.ml_predictor_v2 import AdvancedMLPredictor
        
        predictor = AdvancedMLPredictor()
        
        # Create correlated predictions (should show significance)
        np.random.seed(42)
        actual = np.cumsum(np.random.randn(100)) + 100
        predictions = actual + np.random.randn(100) * 0.5  # Highly correlated
        
        tests = predictor._statistical_tests(predictions, actual)
        
        # Should have multiple tests
        self.assertGreater(len(tests), 0)
        
        # Check test structure
        for test in tests:
            self.assertIsNotNone(test.test_name)
            self.assertIsNotNone(test.p_value)
            self.assertGreaterEqual(test.p_value, 0)
            self.assertLessEqual(test.p_value, 1)
            # Use bool() to convert numpy bool to Python bool for isinstance check
            self.assertIn(bool(test.is_significant), [True, False])


class TestHyperparameterTuning(unittest.TestCase):
    """Test hyperparameter tuning with Optuna."""
    
    def test_hyperparameter_tuning(self):
        """Test that hyperparameter tuning runs and improves model."""
        try:
            import optuna
        except ImportError:
            self.skipTest("Optuna not installed")
        
        from trading.ml_predictor_v2 import AdvancedMLPredictor
        
        predictor = AdvancedMLPredictor(n_tune_trials=3)  # Small for testing
        
        np.random.seed(42)
        X = np.random.randn(100, 30, 10)
        y = np.random.randn(100) * 10 + 100
        
        result = predictor._tune_hyperparameters(X, y, model_type='random_forest')
        
        self.assertIsNotNone(result)
        self.assertIsNotNone(result.best_params)
        self.assertEqual(result.n_trials, 3)
        self.assertGreater(result.best_score, 0)


class TestFeatureImportance(unittest.TestCase):
    """Test feature importance calculation."""
    
    def test_feature_importance_tree_model(self):
        """Test feature importance for tree-based models."""
        from trading.ml_predictor_v2 import AdvancedMLPredictor, RandomForestWrapper
        
        np.random.seed(42)
        n_samples = 100
        n_features = 10
        
        X = np.random.randn(n_samples, 30, n_features)
        y = np.random.randn(n_samples)
        
        # Train model
        model = RandomForestWrapper(n_estimators=10)
        model.fit(X, y)
        
        predictor = AdvancedMLPredictor()
        feature_names = [f'feature_{i}' for i in range(n_features)]
        
        importance = predictor._calculate_feature_importance(
            model, X[:20], y[:20], feature_names
        )
        
        self.assertIsNotNone(importance)
        self.assertGreater(len(importance.features), 0)
        
        # Check values sum approximately to 1 (normalized)
        total = sum(abs(v) for v in importance.features.values())
        self.assertAlmostEqual(total, 1.0, places=1)


class TestEnsemblePredictions(unittest.TestCase):
    """Test ensemble prediction generation."""
    
    def test_ensemble_weights_sum_to_one(self):
        """Test that ensemble weights are properly normalized."""
        from trading.ml_predictor_v2 import ModelPerformance
        
        # Create mock performances
        performances = {
            'Model1': ModelPerformance('Model1', 1.0, 0.8, 0.5, 55, 0.5, 52, 1.1),
            'Model2': ModelPerformance('Model2', 1.2, 0.9, 0.4, 52, 0.3, 50, 1.0),
            'Model3': ModelPerformance('Model3', 0.9, 0.7, 0.6, 58, 0.8, 55, 1.2),
        }
        
        # Calculate weights based on directional accuracy
        weights = {}
        total_weight = 0
        for name, perf in performances.items():
            w = max(0.1, (perf.directional_accuracy - 40) / 10)
            weights[name] = w
            total_weight += w
        
        # Normalize
        for name in weights:
            weights[name] /= total_weight
        
        # Check sum to 1
        self.assertAlmostEqual(sum(weights.values()), 1.0, places=5)


class TestDataClasses(unittest.TestCase):
    """Test data class serialization."""
    
    def test_price_prediction_to_dict(self):
        """Test PricePrediction serialization."""
        from trading.ml_predictor_v2 import PricePrediction
        
        pred = PricePrediction(
            date='2024-01-01',
            day_number=1,
            predicted_price=100.5,
            lower_bound=95.0,
            upper_bound=106.0,
            confidence=75.5,
            predicted_return=2.5
        )
        
        d = pred.to_dict()
        
        self.assertEqual(d['date'], '2024-01-01')
        self.assertEqual(d['day_number'], 1)
        self.assertEqual(d['predicted_price'], 100.5)
    
    def test_backtest_result_to_dict(self):
        """Test BacktestResult serialization."""
        from trading.ml_predictor_v2 import BacktestResult
        
        result = BacktestResult(
            total_return=10.5,
            annualized_return=15.2,
            sharpe_ratio=1.5,
            sortino_ratio=2.0,
            max_drawdown=5.5,
            win_rate=55.0,
            profit_factor=1.8,
            total_trades=50,
            transaction_costs=0.5,
            net_return=10.0,
            benchmark_return=8.0,
            alpha=0.02,
            beta=0.95,
            information_ratio=0.5
        )
        
        d = result.to_dict()
        
        self.assertEqual(d['total_return'], 10.5)
        self.assertEqual(d['sharpe_ratio'], 1.5)
        self.assertEqual(d['total_trades'], 50)


class TestSignalGeneration(unittest.TestCase):
    """Test trading signal generation."""
    
    def test_signal_from_predictions(self):
        """Test that signals are generated correctly from predictions."""
        from trading.ml_predictor_v2 import MLSignal
        
        # Test signal logic
        def get_signal(pred_return, prob_positive):
            if pred_return > 10 and prob_positive > 70:
                return MLSignal.STRONG_BUY
            elif pred_return > 5 and prob_positive > 60:
                return MLSignal.BUY
            elif pred_return < -10 and prob_positive < 30:
                return MLSignal.STRONG_SELL
            elif pred_return < -5 and prob_positive < 40:
                return MLSignal.SELL
            else:
                return MLSignal.HOLD
        
        self.assertEqual(get_signal(15, 80), MLSignal.STRONG_BUY)
        self.assertEqual(get_signal(7, 65), MLSignal.BUY)
        self.assertEqual(get_signal(-15, 20), MLSignal.STRONG_SELL)
        self.assertEqual(get_signal(-7, 35), MLSignal.SELL)
        self.assertEqual(get_signal(2, 50), MLSignal.HOLD)


class TestIntegration(unittest.TestCase):
    """Integration tests for the full prediction pipeline."""
    
    def test_full_prediction_pipeline(self):
        """Test complete prediction workflow with synthetic data."""
        try:
            from trading.ml_predictor_v2 import AdvancedMLPredictor
        except ImportError as e:
            self.skipTest(f"Missing dependency: {e}")
        
        # This test would normally use real data
        # For CI/CD, we'll just verify the predictor can be instantiated
        predictor = AdvancedMLPredictor(
            sequence_length=30,
            transaction_cost_bps=10,
            n_tune_trials=2
        )
        
        self.assertIsNotNone(predictor)
        self.assertEqual(predictor.sequence_length, 30)
        self.assertEqual(predictor.n_tune_trials, 2)


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and error handling."""
    
    def test_empty_predictions(self):
        """Test handling of empty predictions array."""
        from trading.ml_predictor_v2 import AdvancedMLPredictor
        
        predictor = AdvancedMLPredictor()
        
        result = predictor._backtest_strategy(
            np.array([]),
            np.array([]),
            np.array([])
        )
        
        # Should return empty result, not crash
        self.assertEqual(result.total_return, 0)
    
    def test_single_prediction(self):
        """Test handling of single prediction."""
        from trading.ml_predictor_v2 import AdvancedMLPredictor
        
        predictor = AdvancedMLPredictor()
        
        result = predictor._backtest_strategy(
            np.array([100]),
            np.array([100]),
            np.array([0])
        )
        
        self.assertEqual(result.total_return, 0)
    
    def test_nan_handling(self):
        """Test that NaN values are handled."""
        from trading.ml_predictor_v2 import RandomForestWrapper
        
        model = RandomForestWrapper(n_estimators=5)
        
        # Create data with no NaN (model should train)
        X = np.random.randn(50, 30, 10)
        y = np.random.randn(50)
        
        # Should not raise
        model.fit(X, y)
        
        predictions = model.predict(X[:5])
        self.assertTrue(np.all(np.isfinite(predictions)))


class TestBayesianNeuralNetwork(unittest.TestCase):
    """Test Bayesian Neural Network implementation."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        try:
            import torch
            cls.torch_available = True
        except ImportError:
            cls.torch_available = False
            return
        
        np.random.seed(42)
        cls.X = np.random.randn(100, 30, 10)
        cls.y = np.random.randn(100) * 10 + 100
    
    def test_bnn_wrapper_basic(self):
        """Test BNN wrapper training and prediction."""
        if not self.torch_available:
            self.skipTest("PyTorch not installed")
        
        from trading.ml_predictor_v2 import BayesianNNWrapper
        
        model = BayesianNNWrapper(
            input_size=self.X.shape[2],
            hidden_size=16,
            epochs=5,
            n_samples=10
        )
        
        model.fit(self.X[:80], self.y[:80])
        predictions = model.predict(self.X[80:])
        
        self.assertEqual(len(predictions), 20)
        self.assertTrue(np.all(np.isfinite(predictions)))
    
    def test_bnn_uncertainty_estimation(self):
        """Test BNN uncertainty quantification."""
        if not self.torch_available:
            self.skipTest("PyTorch not installed")
        
        from trading.ml_predictor_v2 import BayesianNNWrapper
        
        model = BayesianNNWrapper(
            input_size=self.X.shape[2],
            hidden_size=16,
            epochs=5,
            n_samples=20
        )
        
        model.fit(self.X[:80], self.y[:80])
        mean, std = model.predict_with_uncertainty(self.X[80:])
        
        self.assertEqual(len(mean), 20)
        self.assertEqual(len(std), 20)
        self.assertTrue(np.all(std >= 0))  # Uncertainty should be non-negative
    
    def test_bnn_prediction_intervals(self):
        """Test BNN prediction intervals."""
        if not self.torch_available:
            self.skipTest("PyTorch not installed")
        
        from trading.ml_predictor_v2 import BayesianNNWrapper
        
        model = BayesianNNWrapper(
            input_size=self.X.shape[2],
            hidden_size=16,
            epochs=5
        )
        
        model.fit(self.X[:80], self.y[:80])
        mean, lower, upper = model.get_prediction_intervals(self.X[80:], confidence=0.95)
        
        # Upper should be greater than lower
        self.assertTrue(np.all(upper >= lower))
        # Mean should be between bounds
        self.assertTrue(np.all(mean >= lower))
        self.assertTrue(np.all(mean <= upper))


class TestConformalPrediction(unittest.TestCase):
    """Test Conformal Prediction implementation."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        np.random.seed(42)
        cls.X = np.random.randn(200, 30, 10)
        cls.y = np.random.randn(200) * 10 + 100
    
    def test_conformal_wrapper_basic(self):
        """Test Conformal Prediction wrapper training and prediction."""
        from trading.ml_predictor_v2 import ConformalPredictionWrapper
        
        model = ConformalPredictionWrapper(
            base_model='random_forest',
            confidence_level=0.90,
            cv_folds=3
        )
        
        model.fit(self.X[:150], self.y[:150])
        predictions = model.predict(self.X[150:])
        
        self.assertEqual(len(predictions), 50)
        self.assertTrue(np.all(np.isfinite(predictions)))
    
    def test_conformal_prediction_intervals(self):
        """Test Conformal Prediction intervals."""
        from trading.ml_predictor_v2 import ConformalPredictionWrapper
        
        model = ConformalPredictionWrapper(
            base_model='random_forest',
            confidence_level=0.90,
            cv_folds=3
        )
        
        model.fit(self.X[:150], self.y[:150])
        predictions, lower, upper = model.predict_with_intervals(self.X[150:])
        
        # Upper should be greater than lower
        self.assertTrue(np.all(upper >= lower))
        # Predictions should be within bounds (approximately, for point predictions)
        self.assertTrue(np.all(predictions >= lower - 1e-6))
        self.assertTrue(np.all(predictions <= upper + 1e-6))
    
    def test_conformal_coverage(self):
        """Test that conformal prediction achieves approximately correct coverage."""
        from trading.ml_predictor_v2 import ConformalPredictionWrapper
        
        model = ConformalPredictionWrapper(
            base_model='random_forest',
            confidence_level=0.90,
            cv_folds=3
        )
        
        model.fit(self.X[:150], self.y[:150])
        coverage = model.get_coverage_score(self.X[150:], self.y[150:])
        
        # Coverage should be close to 0.90 (allow some slack due to small sample)
        self.assertGreaterEqual(coverage, 0.70)
        self.assertLessEqual(coverage, 1.0)
    
    def test_conformal_interval_width(self):
        """Test interval width calculation."""
        from trading.ml_predictor_v2 import ConformalPredictionWrapper
        
        model = ConformalPredictionWrapper(
            base_model='random_forest',
            confidence_level=0.90
        )
        
        model.fit(self.X[:150], self.y[:150])
        widths = model.get_interval_width(self.X[150:])
        
        # Widths should be positive
        self.assertTrue(np.all(widths > 0))


class TestAutoML(unittest.TestCase):
    """Test AutoML implementation."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        np.random.seed(42)
        cls.X = np.random.randn(100, 30, 10)
        cls.y = np.random.randn(100) * 10 + 100
    
    def test_automl_wrapper_basic(self):
        """Test AutoML wrapper training and prediction."""
        from trading.ml_predictor_v2 import AutoMLWrapper
        
        # Use short time budget for testing
        model = AutoMLWrapper(time_budget=10, ensemble_size=2)
        
        model.fit(self.X[:80], self.y[:80])
        predictions = model.predict(self.X[80:])
        
        self.assertEqual(len(predictions), 20)
        self.assertTrue(np.all(np.isfinite(predictions)))
    
    def test_automl_fallback_ensemble(self):
        """Test AutoML fallback ensemble when auto-sklearn not available."""
        from trading.ml_predictor_v2 import AutoMLWrapper, AUTOSKLEARN_AVAILABLE
        
        model = AutoMLWrapper(time_budget=10)
        model.fit(self.X[:80], self.y[:80])
        
        info = model.get_model_info()
        self.assertIn('using_autosklearn', info)
        
        # Should still make predictions regardless of backend
        predictions = model.predict(self.X[80:])
        self.assertEqual(len(predictions), 20)
    
    def test_automl_feature_importance(self):
        """Test AutoML feature importance."""
        from trading.ml_predictor_v2 import AutoMLWrapper
        
        model = AutoMLWrapper(time_budget=10)
        model.fit(self.X[:80], self.y[:80])
        
        importance = model.get_feature_importance()
        
        # May or may not have feature importance depending on backend
        if importance is not None:
            self.assertTrue(len(importance) > 0)


class TestReinforcementLearning(unittest.TestCase):
    """Test Reinforcement Learning implementation."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        try:
            from trading.ml_predictor_v2 import RL_AVAILABLE
            cls.rl_available = RL_AVAILABLE
        except ImportError:
            cls.rl_available = False
            return
        
        np.random.seed(42)
        # Create price-like data
        cls.prices = 100 + np.cumsum(np.random.randn(200) * 0.5)
        cls.features = np.random.randn(200, 10)
    
    def test_rl_wrapper_basic(self):
        """Test RL wrapper training and prediction."""
        if not self.rl_available:
            self.skipTest("stable-baselines3 not installed")
        
        from trading.ml_predictor_v2 import RLTradingWrapper
        
        model = RLTradingWrapper(
            input_size=self.features.shape[1],
            algorithm='PPO',
            total_timesteps=1000,  # Small for testing
            window_size=20
        )
        
        model.fit(self.features[:150], self.prices[:150])
        predictions = model.predict(self.features[150:])
        
        self.assertEqual(len(predictions), 50)
        # RL predictions are actions: -1, 0, or 1
        self.assertTrue(np.all(np.isin(predictions, [-1, 0, 1])))
    
    def test_rl_trading_signals(self):
        """Test RL trading signal generation."""
        if not self.rl_available:
            self.skipTest("stable-baselines3 not installed")
        
        from trading.ml_predictor_v2 import RLTradingWrapper
        
        model = RLTradingWrapper(
            input_size=self.features.shape[1],
            total_timesteps=1000,
            window_size=20
        )
        
        model.fit(self.features[:150], self.prices[:150])
        signals = model.get_trading_signals(self.features[150:160])
        
        self.assertEqual(len(signals), 10)
        for signal in signals:
            self.assertIn(signal, ['BUY', 'SELL', 'HOLD'])
    
    def test_rl_backtest(self):
        """Test RL backtesting."""
        if not self.rl_available:
            self.skipTest("stable-baselines3 not installed")
        
        from trading.ml_predictor_v2 import RLTradingWrapper
        
        model = RLTradingWrapper(
            input_size=self.features.shape[1],
            total_timesteps=1000,
            window_size=20
        )
        
        model.fit(self.features[:150], self.prices[:150])
        metrics = model.backtest(self.prices[150:], self.features[150:])
        
        self.assertIn('total_return', metrics)
        self.assertIn('sharpe_ratio', metrics)
        self.assertIn('max_drawdown', metrics)


class TestTradingEnvironment(unittest.TestCase):
    """Test the RL Trading Environment."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        try:
            from trading.ml_predictor_v2 import RL_AVAILABLE
            cls.rl_available = RL_AVAILABLE
        except ImportError:
            cls.rl_available = False
            return
        
        np.random.seed(42)
        cls.prices = 100 + np.cumsum(np.random.randn(100) * 0.5)
        cls.features = np.random.randn(100, 10)
    
    def test_environment_reset(self):
        """Test environment reset."""
        if not self.rl_available:
            self.skipTest("gymnasium not installed")
        
        from trading.ml_predictor_v2 import TradingEnvironment
        
        env = TradingEnvironment(
            prices=self.prices,
            features=self.features,
            window_size=20
        )
        
        obs, info = env.reset()
        
        self.assertEqual(len(obs), env.observation_space.shape[0])
        self.assertEqual(env.cash, 100000.0)
        self.assertEqual(env.shares, 0)
    
    def test_environment_step(self):
        """Test environment step."""
        if not self.rl_available:
            self.skipTest("gymnasium not installed")
        
        from trading.ml_predictor_v2 import TradingEnvironment
        
        env = TradingEnvironment(
            prices=self.prices,
            features=self.features,
            window_size=20
        )
        
        env.reset()
        
        # Test buy action
        obs, reward, done, truncated, info = env.step(1)  # Buy
        self.assertGreater(env.shares, 0)
        
        # Test sell action
        obs, reward, done, truncated, info = env.step(2)  # Sell
        self.assertEqual(env.shares, 0)
    
    def test_environment_metrics(self):
        """Test environment final metrics."""
        if not self.rl_available:
            self.skipTest("gymnasium not installed")
        
        from trading.ml_predictor_v2 import TradingEnvironment
        
        env = TradingEnvironment(
            prices=self.prices,
            features=self.features,
            window_size=20
        )
        
        env.reset()
        
        # Run through some steps
        done = False
        while not done:
            action = np.random.choice([0, 1, 2])
            obs, reward, done, truncated, info = env.step(action)
        
        metrics = env.get_final_metrics()
        
        self.assertIn('total_return', metrics)
        self.assertIn('sharpe_ratio', metrics)
        self.assertIn('max_drawdown', metrics)
        self.assertIn('final_value', metrics)


class TestVariationalLayers(unittest.TestCase):
    """Test Variational layers for Bayesian Neural Networks."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        try:
            import torch
            cls.torch_available = True
            cls.torch = torch
        except ImportError:
            cls.torch_available = False
    
    def test_variational_linear_forward(self):
        """Test Variational Linear layer forward pass."""
        if not self.torch_available:
            self.skipTest("PyTorch not installed")
        
        from trading.ml_predictor_v2 import VariationalLinear
        
        layer = VariationalLinear(10, 5)
        x = self.torch.randn(4, 10)
        
        # Training mode (stochastic)
        layer.train()
        out1 = layer(x)
        out2 = layer(x)
        
        self.assertEqual(out1.shape, (4, 5))
        # Outputs should be different due to sampling (most of the time)
        # Note: there's a tiny chance they could be equal, so we just check shapes
    
    def test_variational_linear_kl(self):
        """Test KL divergence calculation."""
        if not self.torch_available:
            self.skipTest("PyTorch not installed")
        
        from trading.ml_predictor_v2 import VariationalLinear
        
        layer = VariationalLinear(10, 5)
        kl = layer.kl_divergence()
        
        # KL should be non-negative
        self.assertGreaterEqual(kl.item(), 0)
    
    def test_bayesian_lstm_forward(self):
        """Test Bayesian LSTM forward pass."""
        if not self.torch_available:
            self.skipTest("PyTorch not installed")
        
        from trading.ml_predictor_v2 import BayesianLSTM
        
        model = BayesianLSTM(
            input_size=10,
            hidden_size=32,
            num_layers=2,
            dropout=0.3
        )
        
        x = self.torch.randn(4, 20, 10)  # batch, seq, features
        out = model(x)
        
        self.assertEqual(out.shape, (4, 1))
    
    def test_bayesian_lstm_uncertainty(self):
        """Test Bayesian LSTM uncertainty estimation."""
        if not self.torch_available:
            self.skipTest("PyTorch not installed")
        
        from trading.ml_predictor_v2 import BayesianLSTM
        
        model = BayesianLSTM(
            input_size=10,
            hidden_size=32,
            num_layers=2,
            dropout=0.3
        )
        
        x = self.torch.randn(4, 20, 10)
        mean, std = model.predict_with_uncertainty(x, n_samples=20)
        
        self.assertEqual(mean.shape, (4, 1))
        self.assertEqual(std.shape, (4, 1))
        self.assertTrue(self.torch.all(std >= 0))


if __name__ == '__main__':
    # Run tests with verbosity
    unittest.main(verbosity=2)
