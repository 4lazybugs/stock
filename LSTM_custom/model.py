import numpy as np
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM as KerasLSTM
from sklearn.preprocessing import MinMaxScaler
from sklearn.preprocessing import StandardScaler 
from sklearn.preprocessing import RobustScaler
from tensorflow.keras.layers import RepeatVector, TimeDistributed, Dense

class LSTM:
    def __init__(self, sample_size, output_size):
        self.sample_size = sample_size
        self.output_size = output_size
        self.feature_size = None
        self.train_input = None
        self.gt_output = None
        self.model = None
        self.scaler = RobustScaler()

    def pre_processor(self, data):
        scaled_data = self.scaler.fit_transform(data.to_numpy())

        data_reshaped = []  
        gt_output = []
        data_size = data.shape[0] - (self.sample_size + self.output_size) + 1

        for current_idx in range(data_size):
            next_idx = current_idx + self.sample_size
            data_reshaped.append(scaled_data[current_idx : next_idx])
            gt_output.append(scaled_data[next_idx : next_idx + self.output_size])
            
        self.train_input = np.array(data_reshaped)
        self.gt_output = np.array(gt_output)

        return self.train_input

    def build_model(self):
        if self.train_input is None:
            raise ValueError("train_data가 없습니다. 먼저 pre_processor를 실행하세요.")

        input_shape = (self.train_input.shape[1], self.train_input.shape[2])
        self.feature_size = self.train_input.shape[2]

        model = Sequential()
        model.add(KerasLSTM(128, input_shape=(self.sample_size, self.feature_size), return_sequences=True))    # return_sequences=False
        model.add(KerasLSTM(64, return_sequences=True))
        model.add(TimeDistributed(Dense(self.feature_size)))

        model.compile(optimizer='adam', loss='mae')
        
        self.model = model

    def predict(self, model_input):
        if self.model is None:
            raise ValueError("model이 정의되지 않았습니다. 먼저 build_model() 실행하세요.")

        # 정규화
        scaled_input = self.scaler.transform(model_input)
        if len(scaled_input.shape) == 2:
            scaled_input = np.expand_dims(scaled_input, axis=0)

        # 예측
        predicted = self.model.predict(scaled_input)

        # 역정규화
        output_reshaped = predicted.reshape(-1, self.feature_size)
        output_inversed = self.scaler.inverse_transform(output_reshaped)

        return output_inversed.reshape(self.output_size, self.feature_size)

    
