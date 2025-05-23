import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, LSTM, Dropout
from tensorflow.keras.callbacks import EarlyStopping
from sklearn.preprocessing import MinMaxScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error


# Define a class for HVAC neural network models
class HVACNeuralNetwork:
    def __init__(self, model_type='MLP'):
        self.model_type = model_type
        self.model = None
        self.scaler_X = MinMaxScaler()
        self.scaler_y = MinMaxScaler()

    def preprocess_data(self, X, y, sequence_length=None):
        """Preprocess data for neural network training"""
        # Scale features and targets
        X_scaled = self.scaler_X.fit_transform(X)
        y_scaled = self.scaler_y.fit_transform(y.reshape(-1, 1)).flatten()

        # For LSTM, reshape data into sequences
        if self.model_type == 'LSTM' and sequence_length:
            X_seq = []
            y_seq = []
            for i in range(len(X_scaled) - sequence_length):
                X_seq.append(X_scaled[i:i + sequence_length])
                y_seq.append(y_scaled[i + sequence_length])
            return np.array(X_seq), np.array(y_seq)

        return X_scaled, y_scaled

    def build_model(self, input_shape, output_shape=1):
        """Build neural network model"""
        if self.model_type == 'MLP':
            self.model = Sequential([
                Dense(64, activation='relu', input_shape=(input_shape,)),
                Dropout(0.2),
                Dense(32, activation='relu'),
                Dropout(0.2),
                Dense(16, activation='relu'),
                Dense(output_shape)
            ])
        elif self.model_type == 'LSTM':
            self.model = Sequential([
                LSTM(50, return_sequences=True, input_shape=input_shape),
                Dropout(0.2),
                LSTM(50),
                Dropout(0.2),
                Dense(25, activation='relu'),
                Dense(output_shape)
            ])

        self.model.compile(optimizer='adam', loss='mse', metrics=['mae'])
        return self.model

    def train(self, X, y, epochs=100, batch_size=32, validation_split=0.2, sequence_length=None):
        """Train the neural network model"""
        # Preprocess data
        if self.model_type == 'LSTM':
            X_processed, y_processed = self.preprocess_data(X, y, sequence_length)
            input_shape = (X_processed.shape[1], X_processed.shape[2])
        else:
            X_processed, y_processed = self.preprocess_data(X, y)
            input_shape = X_processed.shape[1]

        # Split data into training and validation sets
        X_train, X_val, y_train, y_val = train_test_split(
            X_processed, y_processed, test_size=validation_split, random_state=42
        )

        # Build model if not already built
        if self.model is None:
            self.build_model(input_shape)

        # Set up early stopping
        early_stopping = EarlyStopping(
            monitor='val_loss',
            patience=10,
            restore_best_weights=True
        )

        # Train model
        history = self.model.fit(
            X_train, y_train,
            epochs=epochs,
            batch_size=batch_size,
            validation_data=(X_val, y_val),
            callbacks=[early_stopping]
        )

        return history

    def predict(self, X, sequence_length=None):
        """Generate predictions using the trained model"""
        if self.model_type == 'LSTM':
            # For LSTM, reshape into sequences
            X_scaled = self.scaler_X.transform(X)
            X_seq = []
            for i in range(len(X_scaled) - sequence_length + 1):
                X_seq.append(X_scaled[i:i + sequence_length])
            X_processed = np.array(X_seq)
        else:
            X_processed = self.scaler_X.transform(X)

        # Generate predictions
        y_pred_scaled = self.model.predict(X_processed)

        # Inverse transform to get actual values
        if y_pred_scaled.ndim > 1 and y_pred_scaled.shape[1] == 1:
            y_pred = self.scaler_y.inverse_transform(y_pred_scaled).flatten()
        else:
            y_pred = self.scaler_y.inverse_transform(y_pred_scaled)

        return y_pred

    def evaluate(self, X_test, y_test, sequence_length=None):
        """Evaluate model performance on test data"""
        y_pred = self.predict(X_test, sequence_length)

        # For LSTM, adjust y_test to match prediction length
        if self.model_type == 'LSTM':
            y_test = y_test[sequence_length - 1:]
            if len(y_pred) < len(y_test):
                y_test = y_test[:len(y_pred)]

        # Calculate metrics
        mae = mean_absolute_error(y_test, y_pred)
        mse = mean_squared_error(y_test, y_pred)
        rmse = np.sqrt(mse)

        return {
            'MAE': mae,
            'MSE': mse,
            'RMSE': rmse,
            'predictions': y_pred,
            'actual': y_test
        }

    def save_model(self, filepath):
        """Save the trained model"""
        self.model.save(filepath)

    def load_model(self, filepath):
        """Load a trained model"""
        self.model = tf.keras.models.load_model(filepath)


# Main implementation for HVAC control
class HVACController:
    def __init__(self, data_path):
        self.data_path = data_path
        self.data = None
        self.mlp_model = HVACNeuralNetwork(model_type='MLP')
        self.lstm_model = HVACNeuralNetwork(model_type='LSTM')

    def load_data(self):
        """Load and prepare dataset"""
        # In a real implementation, this would load from files
        # For demonstration, we'll generate synthetic data

        # Generate timestamps for one year at 1-hour intervals
        timestamps = pd.date_range(
            start='2024-01-01',
            end='2024-12-31 23:00:00',
            freq='H'
        )

        n_samples = len(timestamps)

        # Generate synthetic features
        outdoor_temp = 15 + 15 * np.sin(np.linspace(0, 2 * np.pi, n_samples)) + 5 * np.random.randn(n_samples)
        humidity = 50 + 20 * np.sin(np.linspace(0, 4 * np.pi, n_samples)) + 10 * np.random.randn(n_samples)

        # Create time-based features
        hour_of_day = timestamps.hour
        day_of_week = timestamps.dayofweek
        month = timestamps.month

        # Generate occupancy patterns (higher during working hours on weekdays)
        occupancy = np.zeros(n_samples)
        for i, timestamp in enumerate(timestamps):
            if timestamp.dayofweek < 5:  # Weekday
                if 8 <= timestamp.hour < 18:  # Working hours
                    occupancy[i] = 0.7 + 0.3 * np.random.random()
                elif 7 <= timestamp.hour < 8 or 18 <= timestamp.hour < 19:
                    occupancy[i] = 0.3 + 0.3 * np.random.random()
                else:
                    occupancy[i] = 0.1 * np.random.random()
            else:  # Weekend
                occupancy[i] = 0.2 * np.random.random()

        # Generate optimal setpoint temperatures based on inputs (with some noise)
        optimal_setpoint = 21.0 + 0.01 * (outdoor_temp - 20.0) - 0.5 * occupancy + 0.2 * np.random.randn(n_samples)

        # Create dataframe
        self.data = pd.DataFrame({
            'timestamp': timestamps,
            'outdoor_temp': outdoor_temp,
            'humidity': humidity,
            'hour_of_day': hour_of_day,
            'day_of_week': day_of_week,
            'month': month,
            'occupancy': occupancy,
            'optimal_setpoint': optimal_setpoint
        })

        return self.data

    def prepare_features(self):
        """Prepare features for model training"""
        # One-hot encode categorical features
        hour_encoded = pd.get_dummies(self.data['hour_of_day'], prefix='hour')
        day_encoded = pd.get_dummies(self.data['day_of_week'], prefix='day')
        month_encoded = pd.get_dummies(self.data['month'], prefix='month')

        # Combine features
        features = pd.concat([
            self.data[['outdoor_temp', 'humidity', 'occupancy']],
            hour_encoded, day_encoded, month_encoded
        ], axis=1)

        # Target variable
        target = self.data['optimal_setpoint'].values

        return features.values, target

    def train_models(self, epochs=50):
        """Train both MLP and LSTM models"""
        if self.data is None:
            self.load_data()

        X, y = self.prepare_features()

        # Train MLP model
        print("Training MLP model...")
        mlp_history = self.mlp_model.train(X, y, epochs=epochs)

        # Train LSTM model with sequence length of 24 (one day)
        print("Training LSTM model...")
        sequence_length = 24
        lstm_history = self.lstm_model.train(X, y, epochs=epochs, sequence_length=sequence_length)

        return {
            'mlp_history': mlp_history,
            'lstm_history': lstm_history
        }

    def evaluate_models(self):
        """Evaluate both models on test data"""
        if self.data is None:
            self.load_data()

        # Prepare data
        X, y = self.prepare_features()

        # Split data into train/test
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        # Evaluate MLP model
        mlp_results = self.mlp_model.evaluate(X_test, y_test)

        # Evaluate LSTM model
        lstm_results = self.lstm_model.evaluate(X_test, y_test, sequence_length=24)

        return {
            'mlp_results': mlp_results,
            'lstm_results': lstm_results
        }

    def simulate_control(self, days=7):
        """Simulate HVAC control using the trained models"""
        if self.data is None:
            self.load_data()

        # Select a random week from the data
        start_idx = np.random.randint(0, len(self.data) - 24 * days)
        simulation_data = self.data.iloc[start_idx:start_idx + 24 * days].copy()

        # Prepare features
        X, _ = self.prepare_features()
        X_sim = X[start_idx:start_idx + 24 * days]

        # Get predictions from both models
        mlp_predictions = self.mlp_model.predict(X_sim)
        lstm_predictions = self.lstm_model.predict(X_sim, sequence_length=24)

        # Add predictions to simulation data
        simulation_data['mlp_setpoint'] = mlp_predictions

        # Adjust LSTM predictions length to match simulation data
        if len(lstm_predictions) < len(simulation_data):
            # Pad with the first prediction
            padding = np.full(len(simulation_data) - len(lstm_predictions), lstm_predictions[0])
            lstm_padded = np.concatenate([padding, lstm_predictions])
            simulation_data['lstm_setpoint'] = lstm_padded
        else:
            simulation_data['lstm_setpoint'] = lstm_predictions[:len(simulation_data)]

        # Calculate energy consumption (simplified model)
        # Assume energy is proportional to the difference between setpoint and outdoor temperature
        simulation_data['mlp_energy'] = np.abs(simulation_data['mlp_setpoint'] - simulation_data['outdoor_temp']) * 0.1
        simulation_data['lstm_energy'] = np.abs(
            simulation_data['lstm_setpoint'] - simulation_data['outdoor_temp']) * 0.1
        simulation_data['baseline_energy'] = np.abs(
            22 - simulation_data['outdoor_temp']) * 0.1  # Constant setpoint of 22°C

        return simulation_data

    def plot_results(self, simulation_data):
        """Plot simulation results"""
        # Plot setpoints
        plt.figure(figsize=(12, 10))

        plt.subplot(3, 1, 1)
        plt.plot(simulation_data['timestamp'], simulation_data['outdoor_temp'], label='Outdoor Temperature')
        plt.plot(simulation_data['timestamp'], simulation_data['optimal_setpoint'], label='Optimal Setpoint')
        plt.plot(simulation_data['timestamp'], simulation_data['mlp_setpoint'], label='MLP Prediction')
        plt.plot(simulation_data['timestamp'], simulation_data['lstm_setpoint'], label='LSTM Prediction')
        plt.plot(simulation_data['timestamp'], np.full(len(simulation_data), 22), label='Baseline (Constant 22°C)')
        plt.legend()
        plt.title('Temperature Setpoints')
        plt.ylabel('Temperature (°C)')

        # Plot occupancy
        plt.subplot(3, 1, 2)
        plt.plot(simulation_data['timestamp'], simulation_data['occupancy'])
        plt.title('Occupancy Levels')
        plt.ylabel('Occupancy Rate')

        # Plot energy consumption
        plt.subplot(3, 1, 3)
        plt.plot(simulation_data['timestamp'], simulation_data['mlp_energy'], label='MLP Energy')
        plt.plot(simulation_data['timestamp'], simulation_data['lstm_energy'], label='LSTM Energy')
        plt.plot(simulation_data['timestamp'], simulation_data['baseline_energy'], label='Baseline Energy')
        plt.legend()
        plt.title('Energy Consumption')
        plt.ylabel('Energy (kWh)')
        plt.xlabel('Time')

        plt.tight_layout()
        plt.savefig('hvac_simulation_results.png')

        # Calculate total energy consumption
        mlp_total = simulation_data['mlp_energy'].sum()
        lstm_total = simulation_data['lstm_energy'].sum()
        baseline_total = simulation_data['baseline_energy'].sum()

        print(f"Total Energy Consumption:")
        print(f"MLP Model: {mlp_total:.2f} kWh ({(1 - mlp_total / baseline_total) * 100:.2f}% savings)")
        print(f"LSTM Model: {lstm_total:.2f} kWh ({(1 - lstm_total / baseline_total) * 100:.2f}% savings)")
        print(f"Baseline: {baseline_total:.2f} kWh")

        return {
            'mlp_energy': mlp_total,
            'lstm_energy': lstm_total,
            'baseline_energy': baseline_total
        }


# Execute a simple demonstration
if __name__ == "__main__":
    controller = HVACController(data_path="synthetic")
    data = controller.load_data()
    print(f"Generated synthetic data with {len(data)} samples")

    # Train models
    training_history = controller.train_models(epochs=30)

    # Evaluate models
    evaluation_results = controller.evaluate_models()
    print("\nModel Evaluation Results:")
    print(
        f"MLP - MAE: {evaluation_results['mlp_results']['MAE']:.4f}, RMSE: {evaluation_results['mlp_results']['RMSE']:.4f}")
    print(
        f"LSTM - MAE: {evaluation_results['lstm_results']['MAE']:.4f}, RMSE: {evaluation_results['lstm_results']['RMSE']:.4f}")

    # Simulate HVAC control
    simulation_data = controller.simulate_control(days=7)
    energy_results = controller.plot_results(simulation_data)


def calculate_energy_consumption(setpoints, outdoor_temps, building_params):
    """
    Calculate energy consumption based on setpoints and outdoor temperatures

    Args:
        setpoints: Array of temperature setpoints (°C)
        outdoor_temps: Array of outdoor temperatures (°C)
        building_params: Dictionary of building thermal parameters

    Returns:
        Array of energy consumption values (kWh)
    """
    # Extract building parameters
    heat_capacity = building_params['heat_capacity']  # kWh/°C
    heat_loss_coefficient = building_params['heat_loss_coefficient']  # kW/°C
    cop_heating = building_params['cop_heating']  # Coefficient of Performance (heating)
    cop_cooling = building_params['cop_cooling']  # Coefficient of Performance (cooling)
    time_step = building_params['time_step']  # hours

    # Initialize arrays
    energy = np.zeros_like(setpoints)
    indoor_temp = np.full_like(setpoints, setpoints[0])

    # Simulate thermal behavior for each time step
    for i in range(1, len(setpoints)):
        # Calculate natural temperature change due to heat loss/gain
        temp_change_natural = (outdoor_temps[i - 1] - indoor_temp[
            i - 1]) * heat_loss_coefficient / heat_capacity * time_step

        # Calculate new indoor temperature without HVAC
        indoor_temp_natural = indoor_temp[i - 1] + temp_change_natural

        # Calculate required temperature change to reach setpoint
        temp_change_required = setpoints[i] - indoor_temp_natural

        # Calculate energy required for temperature change
        if temp_change_required > 0:  # Heating required
            energy[i] = heat_capacity * temp_change_required / cop_heating
        else:  # Cooling required
            energy[i] = heat_capacity * abs(temp_change_required) / cop_cooling

        # Update indoor temperature
        indoor_temp[i] = setpoints[i]

    return energy



def visualize_performance(dates, actual_temps, predicted_temps, energy_consumption, comfort_violations):
    """
    Visualize temperature control performance and energy consumption

    Args:
        dates: Array of timestamps
        actual_temps: Array of actual indoor temperatures
        predicted_temps: Array of predicted optimal temperatures
        energy_consumption: Array of energy consumption values
        comfort_violations: Array indicating comfort violations
    """
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 10), sharex=True)

    # Plot temperatures
    ax1.plot(dates, actual_temps, 'b-', label='Actual Temperature')
    ax1.plot(dates, predicted_temps, 'r--', label='Predicted Optimal Temperature')
    ax1.fill_between(dates, 20, 24, color='g', alpha=0.1, label='Comfort Zone')
    ax1.set_ylabel('Temperature (°C)')
    ax1.set_title('Temperature Control Performance')
    ax1.legend()

    # Plot energy consumption
    ax2.bar(dates, energy_consumption, width=0.02, color='orange')
    ax2.set_ylabel('Energy (kWh)')
    ax2.set_title('Energy Consumption')

    # Plot comfort violations
    ax3.scatter(dates, comfort_violations, color='red', s=20, alpha=0.5)
    ax3.set_ylim(-0.1, 1.1)
    ax3.set_ylabel('Comfort Violation')
    ax3.set_title('Comfort Violations (1 = Outside Comfort Range)')
    ax3.set_xlabel('Date')

    plt.tight_layout()
    plt.savefig('hvac_performance.png', dpi=300)
    plt.close()