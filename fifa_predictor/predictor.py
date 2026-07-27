# File: fifa_predictor/predictor.py
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.preprocessing import MinMaxScaler, StandardScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout, Conv1D, MaxPooling1D, Flatten
from tensorflow.keras.optimizers import Adam
from tensorflow.keras.callbacks import EarlyStopping
import math

# ==========================================
# 1. SETUP & FEATURE ENGINEERING
# ==========================================

# CONFIGURATION
LOOK_BACK = 30       # Past 30 minutes
FORECAST_HORIZON = 3 # Predict next 3 minutes
EPOCHS = 100         # Increased, we use EarlyStopping
BATCH_SIZE = 16

# Load Data
df = pd.read_csv('wc_day6_1_bursts.csv')
df['datetime'] = pd.to_datetime(df['datetime'])
df.set_index('datetime', inplace=True)

# --- NEW: Feature Engineering ---
# 1. Log Transform (to handle scale)
df['log_count'] = np.log1p(df['request_count'])

# 2. Velocity (1st Derivative): How fast is traffic changing?
df['velocity'] = df['log_count'].diff()

# 3. Acceleration (2nd Derivative): Is the change speeding up?
df['acceleration'] = df['velocity'].diff()

# 4. Rolling Mean (Smooth trend): Context for the noise
df['rolling_mean'] = df['log_count'].rolling(window=5).mean()

# Drop NaNs created by diff/rolling
df.dropna(inplace=True)

# Select features to use
# We use [Log_Count, Velocity, Acceleration, Rolling_Mean]
features = ['log_count', 'velocity', 'acceleration', 'rolling_mean']
target_col = 'log_count' # We want to predict the log_count

data_values = df[features].values

print(f"Total Data Points after cleaning: {len(data_values)}")

# ==========================================
# 2. SCALING (Multivariate)
# ==========================================

# We need two scalers: one for inputs (X), one for target (Y) to inverse later
scaler_X = MinMaxScaler(feature_range=(0, 1))
scaled_data = scaler_X.fit_transform(data_values)

# Create a separate scaler just for the target column to make inverse transform easier
scaler_y = MinMaxScaler(feature_range=(0, 1))
scaler_y.fit(df[[target_col]]) 

# ==========================================
# 3. CREATE DATASET (Sliding Window)
# ==========================================

def create_multivariate_dataset(dataset, look_back=30, forecast_horizon=3):
    X, Y = [], []
    # dataset shape: [samples, features]
    # We only want to predict the 0th column (log_count)
    
    for i in range(len(dataset) - look_back - forecast_horizon + 1):
        # Gather input sequence (all features)
        a = dataset[i:(i + look_back), :] 
        X.append(a)
        
        # Gather target sequence (only log_count, which is column 0)
        # We take the actual future values from the dataset
        b = dataset[(i + look_back):(i + look_back + forecast_horizon), 0]
        Y.append(b)
        
    return np.array(X), np.array(Y)

X, y = create_multivariate_dataset(scaled_data, LOOK_BACK, FORECAST_HORIZON)

# Split Train/Test
train_size = int(len(X) * 0.8)
X_train, X_test = X[:train_size], X[train_size:]
y_train, y_test = y[:train_size], y[train_size:]

print(f"X_train shape: {X_train.shape} (Samples, Steps, Features)")
print(f"y_train shape: {y_train.shape} (Samples, Horizon)")

# ==========================================
# 4. BUILD HYBRID MODEL (Conv1D + LSTM)
# ==========================================
# Conv1D extracts local patterns (slope changes)
# LSTM captures long term dependencies

model = Sequential()

# Conv Layer: filters=32, kernel_size=3 (looks at 3 minutes at a time)
model.add(Conv1D(filters=32, kernel_size=3, activation='relu', input_shape=(LOOK_BACK, len(features))))
model.add(MaxPooling1D(pool_size=2)) # Downsample to highlight strongest features

# LSTM Layer
model.add(LSTM(64, activation='relu', return_sequences=False))
model.add(Dropout(0.2))

# Output
model.add(Dense(FORECAST_HORIZON))

model.compile(optimizer=Adam(learning_rate=0.001), loss='mse')

# Early Stopping: Stop training if validation loss doesn't improve for 10 epochs
es = EarlyStopping(monitor='val_loss', patience=10, restore_best_weights=True)

history = model.fit(X_train, y_train, 
                    epochs=EPOCHS, 
                    batch_size=BATCH_SIZE, 
                    validation_data=(X_test, y_test),
                    callbacks=[es],
                    verbose=1)

# ==========================================
# 5. EVALUATION
# ==========================================

train_predict = model.predict(X_train)
test_predict = model.predict(X_test)

# Inverse Transform
# We use scaler_y because y and predictions only contain the 'log_count' column
train_predict_inv = scaler_y.inverse_transform(train_predict)
y_train_inv = scaler_y.inverse_transform(y_train)
test_predict_inv = scaler_y.inverse_transform(test_predict)
y_test_inv = scaler_y.inverse_transform(y_test)

# Final Reverse Log Transform (expm1)
train_predict_final = np.expm1(train_predict_inv)
y_train_final = np.expm1(y_train_inv)
test_predict_final = np.expm1(test_predict_inv)
y_test_final = np.expm1(y_test_inv)

# Metrics for T+1
rmse = math.sqrt(mean_squared_error(y_test_final[:,0], test_predict_final[:,0]))
mae = mean_absolute_error(y_test_final[:,0], test_predict_final[:,0])

print(f"\n--- Improved Model Performance (T+1) ---")
print(f"RMSE: {rmse:.2f}")
print(f"MAE:  {mae:.2f}")

# ==========================================
# 6. VISUALIZATION
# ==========================================

plt.figure(figsize=(14, 6))
time_axis = range(len(y_test_final))

# Plot Actual vs Predicted for T+1
plt.plot(time_axis, y_test_final[:, 0], label='Actual (T+1)', color='blue', alpha=0.7)
plt.plot(time_axis, test_predict_final[:, 0], label='Conv1D-LSTM Prediction (T+1)', color='red', linestyle='--', linewidth=2)

plt.title(f'Improved Autoscaling Predictor (Multivariate) - RMSE: {rmse:.2f}')
plt.xlabel('Time Steps')
plt.ylabel('Requests')
plt.legend()
plt.grid(True, alpha=0.3)
plt.show()

# ==========================================
# 7. EXPORT CSV
# ==========================================
results_df = pd.DataFrame({
    'Actual_T+1': y_test_final[:, 0],
    'Pred_T+1':   test_predict_final[:, 0],
    'Actual_T+2': y_test_final[:, 1],
    'Pred_T+2':   test_predict_final[:, 1],
    'Actual_T+3': y_test_final[:, 2],
    'Pred_T+3':   test_predict_final[:, 2]
})

results_df.to_csv('improved_prediction_results.csv', index=False)
print("Saved to improved_prediction_results.csv")
