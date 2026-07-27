import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error, mean_absolute_percentage_error
import warnings
warnings.filterwarnings('ignore')

# Load and prepare data
df = pd.read_csv('wc_day6_1_bursts.csv')
df['datetime'] = pd.to_datetime(df['datetime'])
df = df.set_index('datetime')

print("Dataset Shape:", df.shape)
print("\nBasic Statistics:")
print(df.describe())

# Visualize the data
plt.figure(figsize=(14, 5))
plt.plot(df['request_count'], linewidth=0.8)
plt.title('FIFA98 Web Server Load - Minute-by-Minute Requests')
plt.xlabel('Time')
plt.ylabel('Request Count')
plt.tight_layout()
plt.savefig('load_pattern.png', dpi=150)
plt.show()

def create_features(df, target_col='request_count', lags=[1, 2, 3, 5, 10, 15, 30, 60], 
                    prediction_horizon=3):
    """
    Create features for time series prediction
    """
    data = df.copy()
    
    # Lag features (past values)
    for lag in lags:
        data[f'lag_{lag}'] = data[target_col].shift(lag)
    
    # Rolling statistics
    for window in [5, 10, 15, 30, 60]:
        data[f'rolling_mean_{window}'] = data[target_col].shift(1).rolling(window=window).mean()
        data[f'rolling_std_{window}'] = data[target_col].shift(1).rolling(window=window).std()
        data[f'rolling_max_{window}'] = data[target_col].shift(1).rolling(window=window).max()
        data[f'rolling_min_{window}'] = data[target_col].shift(1).rolling(window=window).min()
    
    # Rate of change features
    data['diff_1'] = data[target_col].shift(1).diff()
    data['diff_2'] = data[target_col].shift(1).diff(2)
    data['pct_change'] = data[target_col].shift(1).pct_change()
    
    # Time-based features
    data['hour'] = data.index.hour
    data['minute'] = data.index.minute
    data['hour_sin'] = np.sin(2 * np.pi * data['hour'] / 24)
    data['hour_cos'] = np.cos(2 * np.pi * data['hour'] / 24)
    data['minute_sin'] = np.sin(2 * np.pi * data['minute'] / 60)
    data['minute_cos'] = np.cos(2 * np.pi * data['minute'] / 60)
    
    # Target: average of next 3 minutes (for your auto-scaling use case)
    data['target_next_1'] = data[target_col].shift(-1)
    data['target_next_2'] = data[target_col].shift(-2)
    data['target_next_3'] = data[target_col].shift(-3)
    data['target_avg_3min'] = (data['target_next_1'] + data['target_next_2'] + data['target_next_3']) / 3
    data['target_max_3min'] = data[[f'target_next_{i}' for i in range(1, 4)]].max(axis=1)
    
    return data

# Create features
df_features = create_features(df)
df_features = df_features.dropna()

print(f"Features created. Shape: {df_features.shape}")
print(f"Feature columns: {len([c for c in df_features.columns if 'target' not in c])}")

from sklearn.model_selection import TimeSeriesSplit
from xgboost import XGBRegressor
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.linear_model import Ridge

def evaluate_model(y_true, y_pred, model_name="Model"):
    """Calculate and display metrics"""
    mae = mean_absolute_error(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    mape = mean_absolute_percentage_error(y_true, y_pred) * 100
    
    return {
        'Model': model_name,
        'MAE': mae,
        'RMSE': rmse,
        'MAPE (%)': mape
    }

def prepare_data_ml(df_features, target_col='target_max_3min'):
    """Prepare data for ML models"""
    feature_cols = [c for c in df_features.columns if 'target' not in c and c != 'request_count']
    
    X = df_features[feature_cols].values
    y = df_features[target_col].values
    
    # Time series split (80% train, 20% test)
    split_idx = int(len(X) * 0.8)
    X_train, X_test = X[:split_idx], X[split_idx:]
    y_train, y_test = y[:split_idx], y[split_idx:]
    
    return X_train, X_test, y_train, y_test, feature_cols

# Prepare data
X_train, X_test, y_train, y_test, feature_cols = prepare_data_ml(df_features)

print(f"Training samples: {len(X_train)}")
print(f"Test samples: {len(X_test)}")

# XGBoost - Often best for tabular time series
xgb_model = XGBRegressor(
    n_estimators=200,
    max_depth=6,
    learning_rate=0.05,
    subsample=0.8,
    colsample_bytree=0.8,
    random_state=42,
    early_stopping_rounds=20
)

xgb_model.fit(
    X_train, y_train,
    eval_set=[(X_test, y_test)],
    verbose=False
)

y_pred_xgb = xgb_model.predict(X_test)
results = [evaluate_model(y_test, y_pred_xgb, "XGBoost")]

# Feature importance
importance_df = pd.DataFrame({
    'feature': feature_cols,
    'importance': xgb_model.feature_importances_
}).sort_values('importance', ascending=False).head(15)

plt.figure(figsize=(10, 6))
plt.barh(importance_df['feature'], importance_df['importance'])
plt.xlabel('Importance')
plt.title('Top 15 Feature Importances (XGBoost)')
plt.gca().invert_yaxis()
plt.tight_layout()
plt.savefig('feature_importance.png', dpi=150)
plt.show()

import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, GRU, Dense, Dropout, Bidirectional
from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau
from tensorflow.keras.optimizers import Adam

def create_sequences(data, seq_length, prediction_horizon=3):
    """Create sequences for LSTM"""
    X, y = [], []
    for i in range(seq_length, len(data) - prediction_horizon + 1):
        X.append(data[i-seq_length:i])
        # Target: next 3 values (for multi-step prediction)
        y.append(data[i:i+prediction_horizon])
    return np.array(X), np.array(y)

# Prepare data for LSTM
scaler = MinMaxScaler()
scaled_data = scaler.fit_transform(df['request_count'].values.reshape(-1, 1))

SEQ_LENGTH = 60  # Use last 60 minutes to predict next 3
PREDICTION_HORIZON = 3

X_seq, y_seq = create_sequences(scaled_data, SEQ_LENGTH, PREDICTION_HORIZON)

# Split data
split_idx = int(len(X_seq) * 0.8)
X_train_lstm = X_seq[:split_idx]
X_test_lstm = X_seq[split_idx:]
y_train_lstm = y_seq[:split_idx]
y_test_lstm = y_seq[split_idx:]

print(f"LSTM Training shape: {X_train_lstm.shape}")
print(f"LSTM Test shape: {X_test_lstm.shape}")

# Build LSTM Model
def build_lstm_model(seq_length, n_features=1, prediction_horizon=3):
    model = Sequential([
        LSTM(64, return_sequences=True, input_shape=(seq_length, n_features)),
        Dropout(0.2),
        LSTM(32, return_sequences=False),
        Dropout(0.2),
        Dense(32, activation='relu'),
        Dense(prediction_horizon)  # Output: next 3 minutes
    ])
    
    model.compile(
        optimizer=Adam(learning_rate=0.001),
        loss='mse',
        metrics=['mae']
    )
    return model

# Build and train
lstm_model = build_lstm_model(SEQ_LENGTH, prediction_horizon=PREDICTION_HORIZON)
lstm_model.summary()

callbacks = [
    EarlyStopping(monitor='val_loss', patience=15, restore_best_weights=True),
    ReduceLROnPlateau(monitor='val_loss', factor=0.5, patience=5, min_lr=1e-6)
]

history = lstm_model.fit(
    X_train_lstm, y_train_lstm,
    epochs=100,
    batch_size=32,
    validation_split=0.15,
    callbacks=callbacks,
    verbose=1
)

# Evaluate LSTM
y_pred_lstm_scaled = lstm_model.predict(X_test_lstm)

# Inverse transform predictions
y_pred_lstm = scaler.inverse_transform(y_pred_lstm_scaled.reshape(-1, 1)).reshape(-1, PREDICTION_HORIZON)
y_test_lstm_inv = scaler.inverse_transform(y_test_lstm.reshape(-1, 1)).reshape(-1, PREDICTION_HORIZON)

# Calculate metrics for average of 3 minutes
y_test_avg = y_test_lstm_inv.mean(axis=1)
y_pred_avg = y_pred_lstm.mean(axis=1)

results.append(evaluate_model(y_test_avg, y_pred_avg, "LSTM"))

def build_gru_model(seq_length, n_features=1, prediction_horizon=3):
    model = Sequential([
        GRU(64, return_sequences=True, input_shape=(seq_length, n_features)),
        Dropout(0.2),
        GRU(32, return_sequences=False),
        Dropout(0.2),
        Dense(32, activation='relu'),
        Dense(prediction_horizon)
    ])
    
    model.compile(
        optimizer=Adam(learning_rate=0.001),
        loss='mse',
        metrics=['mae']
    )
    return model

gru_model = build_gru_model(SEQ_LENGTH, prediction_horizon=PREDICTION_HORIZON)

gru_model.fit(
    X_train_lstm, y_train_lstm,
    epochs=100,
    batch_size=32,
    validation_split=0.15,
    callbacks=callbacks,
    verbose=0
)

y_pred_gru_scaled = gru_model.predict(X_test_lstm)
y_pred_gru = scaler.inverse_transform(y_pred_gru_scaled.reshape(-1, 1)).reshape(-1, PREDICTION_HORIZON)
y_pred_gru_avg = y_pred_gru.mean(axis=1)

results.append(evaluate_model(y_test_avg, y_pred_gru_avg, "GRU"))

# Baseline: Simple Moving Average
sma_pred = df['request_count'].rolling(window=10).mean().shift(1).iloc[split_idx+60:split_idx+60+len(y_test_avg)].values
results.append(evaluate_model(y_test_avg[:len(sma_pred)], sma_pred[:len(y_test_avg)], "SMA (Baseline)"))

# Display results
results_df = pd.DataFrame(results)
print("\n" + "="*60)
print("MODEL COMPARISON RESULTS")
print("="*60)
print(results_df.to_string(index=False))

# Visualization
fig, axes = plt.subplots(2, 2, figsize=(14, 10))

# Plot 1: Predictions comparison
ax1 = axes[0, 0]
time_range = range(len(y_test_avg[:200]))
ax1.plot(time_range, y_test_avg[:200], label='Actual', linewidth=1.5, alpha=0.8)
ax1.plot(time_range, y_pred_avg[:200], label='LSTM', linewidth=1, alpha=0.7)
ax1.plot(time_range, y_pred_xgb[:200], label='XGBoost', linewidth=1, alpha=0.7)
ax1.set_xlabel('Time (minutes)')
ax1.set_ylabel('Request Count')
ax1.set_title('Prediction Comparison (First 200 Test Points)')
ax1.legend()
ax1.grid(True, alpha=0.3)

# Plot 2: Training history
ax2 = axes[0, 1]
ax2.plot(history.history['loss'], label='Training Loss')
ax2.plot(history.history['val_loss'], label='Validation Loss')
ax2.set_xlabel('Epoch')
ax2.set_ylabel('Loss (MSE)')
ax2.set_title('LSTM Training History')
ax2.legend()
ax2.grid(True, alpha=0.3)

# Plot 3: Error distribution
ax3 = axes[1, 0]
errors_lstm = y_test_avg - y_pred_avg
errors_xgb = y_test[:len(y_pred_xgb)] - y_pred_xgb
ax3.hist(errors_lstm, bins=50, alpha=0.5, label='LSTM', density=True)
ax3.hist(errors_xgb, bins=50, alpha=0.5, label='XGBoost', density=True)
ax3.set_xlabel('Prediction Error')
ax3.set_ylabel('Density')
ax3.set_title('Error Distribution')
ax3.legend()
ax3.grid(True, alpha=0.3)

# Plot 4: Metrics comparison
ax4 = axes[1, 1]
x_pos = range(len(results_df))
ax4.bar(x_pos, results_df['MAPE (%)'])
ax4.set_xticks(x_pos)
ax4.set_xticklabels(results_df['Model'], rotation=45)
ax4.set_ylabel('MAPE (%)')
ax4.set_title('Model Performance (Lower is Better)')
ax4.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig('model_comparison.png', dpi=150)
plt.show()
