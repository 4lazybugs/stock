import argparse

def get_training_args():
    parser = argparse.ArgumentParser(description='Train/Infer LSTM model.')
    parser.add_argument(
        '--mode',
        choices=['train','predict','all'],
        default='all',
        help='실행모드: train(학습만) / predict(예측+플롯+손실곡선) / all(학습→예측)'
    )
    parser.add_argument('--epochs',        type=int, default=10, help='훈련할 epoch 수')
    parser.add_argument('--batch_size',    type=int, default=32, help='배치 크기')
    parser.add_argument('--save_interval', type=int, default=5,  help='체크포인트 저장 주기')
    parser.add_argument('--sample_size',   type=int, required=True, help='입력 window size')
    return parser.parse_args()