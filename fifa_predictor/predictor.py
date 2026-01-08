# File: fifa_predictor/predictor.py
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout
from tensorflow.keras.optimizers import Adam
import math

# ==========================================
# 1. SETUP & DATA PREPARATION
# ==========================================

# CONFIGURATION
LOOK_BACK = 30      # How many past minutes to look at
FORECAST_HORIZON = 3 # Predict next 3 minutes
EPOCHS = 50
BATCH_SIZE = 16

# ---------------------------------------------------------
# OPTION A: Load your real CSV file
df = pd.read_csv('wc_day6_1_bursts.csv')
df['datetime'] = pd.to_datetime(df['datetime'])
df.set_index('datetime', inplace=True)
# ---------------------------------------------------------

# (Simulating more data to make LSTM trainable for this demo)
# Replicating the pattern to create enough data points for training
raw_values = df['request_count'].values.reshape(-1, 1)

print(f"Total Data Points: {len(raw_values)}")

# ==========================================
# 2. PRE-PROCESSING (Crucial for Bursts)
# ==========================================

# A. Log Transform (Handles the jump from 2 to 676 better)
log_values = np.log1p(raw_values)

# B. MinMax Scaling (0 to 1)
scaler = MinMaxScaler(feature_range=(0, 1))
scaled_values = scaler.fit_transform(log_values)

# C. Create Sequences (Sliding Window)
def create_dataset(dataset, look_back=30, forecast_horizon=3):
    X, Y = [], []
    for i in range(len(dataset) - look_back - forecast_horizon + 1):
        a = dataset[i:(i + look_back), 0]
        X.append(a)
        # The target is the NEXT 3 minutes
        Y.append(dataset[(i + look_back):(i + look_back + forecast_horizon), 0])
    return np.array(X), np.array(Y)

X, y = create_dataset(scaled_values, LOOK_BACK, FORECAST_HORIZON)

# Reshape input to be [samples, time steps, features]
X = np.reshape(X, (X.shape[0], X.shape[1], 1))

# Split into Train/Test
train_size = int(len(X) * 0.8)
test_size = len(X) - train_size
X_train, X_test = X[0:train_size], X[train_size:len(X)]
y_train, y_test = y[0:train_size], y[train_size:len(y)]

print(f"Training Shape: {X_train.shape}, Testing Shape: {X_test.shape}")

# ==========================================
# 3. BUILD & TRAIN LSTM
# ==========================================

model = Sequential()
# Input layer
model.add(LSTM(64, activation='relu', input_shape=(LOOK_BACK, 1)))
model.add(Dropout(0.2))
# Output layer (3 neurons for next 3 minutes)
model.add(Dense(FORECAST_HORIZON))

model.compile(optimizer=Adam(learning_rate=0.001), loss='mse')

# Train
history = model.fit(X_train, y_train, epochs=EPOCHS, batch_size=BATCH_SIZE, validation_data=(X_test, y_test), verbose=1)

# ==========================================
# 4. EVALUATION & INVERSE TRANSFORM
# ==========================================

# Make predictions
train_predict = model.predict(X_train)
test_predict = model.predict(X_test)

# Function to inverse scale AND inverse log
def inverse_transform_data(prediction_scaled):
    # 1. Inverse MinMax
    inv_scaled = scaler.inverse_transform(prediction_scaled)
    # 2. Inverse Log (expm1)
    inv_log = np.expm1(inv_scaled)
    return inv_log

# Inverse transform everything
y_train_inv = inverse_transform_data(y_train)
y_test_inv = inverse_transform_data(y_test)
train_predict_inv = inverse_transform_data(train_predict)
test_predict_inv = inverse_transform_data(test_predict)

# Calculate RMSE for the first minute (t+1)
rmse_t1 = math.sqrt(mean_squared_error(y_test_inv[:,0], test_predict_inv[:,0]))
mae_t1 = mean_absolute_error(y_test_inv[:,0], test_predict_inv[:,0])

print(f"\nModel Performance (Test Set - T+1 minute):")
print(f"RMSE: {rmse_t1:.2f} requests")
print(f"MAE:  {mae_t1:.2f} requests")

# ==========================================
# 5. VISUALIZATION
# ==========================================

plt.figure(figsize=(14, 6))

# We will plot the "Next Minute" (T+1) prediction vs Actual
# The test data starts after train_size + look_back
time_axis = range(len(y_test_inv))

plt.plot(time_axis, y_test_inv[:, 0], label='Actual Request Count (T+1)', color='blue', linewidth=2)
plt.plot(time_axis, test_predict_inv[:, 0], label='LSTM Prediction (T+1)', color='red', linestyle='--', linewidth=2)

plt.title(f'FIFA98 Load Prediction (Next Minute) - RMSE: {rmse_t1:.2f}', fontsize=14)
plt.xlabel('Time Steps (Minutes)', fontsize=12)
plt.ylabel('Request Count', fontsize=12)
plt.legend()
plt.grid(True, alpha=0.3)
plt.show()

# ==========================================
# 6. EXPORT TO CSV
# ==========================================

# We create a DataFrame comparing Actual vs Predicted for all 3 minutes
results_df = pd.DataFrame({
    'Actual_T+1': y_test_inv[:, 0].flatten(),
    'Pred_T+1':   test_predict_inv[:, 0].flatten(),
    'Actual_T+2': y_test_inv[:, 1].flatten(),
    'Pred_T+2':   test_predict_inv[:, 1].flatten(),
    'Actual_T+3': y_test_inv[:, 2].flatten(),
    'Pred_T+3':   test_predict_inv[:, 2].flatten()
})

# Add a simple diff column for analysis
results_df['Error_T+1'] = results_df['Actual_T+1'] - results_df['Pred_T+1']

print("\n--- Saving comparison to 'prediction_results.csv' ---")
print(results_df.head())
results_df.to_csv('prediction_results.csv', index=False)
