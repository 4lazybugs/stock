import os
import sys
import glob
import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

from config import get_training_args
from model import LSTM
from utils import Checkpoint

if __name__ == "__main__":
    args = get_training_args()
    SAVE_DIR = 'checkpoint_saved'

    # ─── train 모드 ──────────────────────────────────────
    if args.mode == 'train':
        data = yf.download('006400.KS', '2012-01-01', '2017-02-02')

        lstm = LSTM(sample_size=args.sample_size, output_size=args.sample_size)
        lstm.pre_processor(data)
        lstm.build_model()

        checkpoint = Checkpoint(save_every=args.save_interval)
        lstm.model.fit(
            lstm.train_input,
            lstm.gt_output,
            epochs=args.epochs,
            batch_size=args.batch_size,
            callbacks=[checkpoint]
        )
        sys.exit(0)


    # ─── predict 모드 or all 모드 ────────────────────────
    data    = yf.download('006400.KS', '2012-01-01', '2017-02-02')
    data_gt = yf.download('006400.KS', '2017-02-03', '2017-08-14')

    lstm = LSTM(sample_size=args.sample_size, output_size=args.sample_size)
    lstm.pre_processor(data)
    lstm.build_model()

    if args.mode == 'all':
        checkpoint = Checkpoint(save_every=args.save_interval)
        lstm.model.fit(
            lstm.train_input,
            lstm.gt_output,
            epochs=args.epochs,
            batch_size=args.batch_size,
            callbacks=[checkpoint]
        )

    # ─── 최신 체크포인트 로드 ─────────────────────────────
    weight_dir = os.path.join(SAVE_DIR, 'weight')
    ckpts      = sorted(glob.glob(os.path.join(weight_dir, '*.h5')))
    if not ckpts:
        raise FileNotFoundError(f"No checkpoints found in {weight_dir}")
    latest_ckpt = ckpts[-1]
    print(f">>> Loading latest weights: {latest_ckpt}")
    lstm.model.load_weights(latest_ckpt)

    # ─── epoch 문자열 추출 (loss/predict 파일명에 공통 사용) ───
    basename, _ = os.path.splitext(os.path.basename(latest_ckpt))
    epoch_str   = basename[basename.find('epoch_'):]  # e.g. "epoch_020"

    # ─── 손실곡선 플롯 & 저장 ────────────────────────────
    loss_log = os.path.join(SAVE_DIR, 'loss_log.csv')
    df_loss  = pd.read_csv(loss_log)

    plt.figure(figsize=(8,4))
    plt.errorbar(
        df_loss['epoch'],
        df_loss['mean_loss'],
        yerr=df_loss['std_loss'],
        fmt='-o',
        capsize=4,
        label='Mean Loss'
    )
    plt.title("Training Loss Curve")
    plt.xlabel("Epoch"); plt.ylabel("Loss")
    plt.legend(); plt.grid(True)
    plt.tight_layout()

    # 저장
    loss_fig = f"loss_{epoch_str}.png"
    loss_out = os.path.join(SAVE_DIR, loss_fig)
    os.makedirs(os.path.dirname(loss_out), exist_ok=True)
    plt.savefig(loss_out, dpi=150)
    plt.show()


    # ─── 예측 & 시각화 ──────────────────────────────────
    target_idx   = 2
    predict_days = len(data_gt)
    predicted    = []

    inp   = data[-lstm.sample_size:].to_numpy()
    out_sz = lstm.output_size
    iters = predict_days // out_sz
    rem   = predict_days % out_sz

    for _ in range(iters):
        p = lstm.predict(inp)
        predicted.extend(p)
        inp = np.concatenate([inp[out_sz:], p], axis=0)
    if rem:
        p = lstm.predict(inp)
        predicted.extend(p[:rem])

    arr          = np.array(predicted)
    predict_seq  = arr[:, target_idx]
    history_seq  = data.to_numpy()[:, target_idx]
    ground_truth = data_gt.to_numpy()[:, target_idx]
    predict_seq += (history_seq[-1] - predict_seq[0])

    plt.figure(figsize=(14,5))
    plt.plot(data.index,    history_seq,   label='History',      marker='o')
    plt.plot(data_gt.index, predict_seq,   label='Forecast',     marker='x')
    plt.plot(data_gt.index, ground_truth,  label='Ground Truth', marker='s')
    plt.axvline(x=data_gt.index[0], linestyle='--', color='gray',
                label='Prediction Start')
    plt.title("Past True vs Future Predicted vs Ground Truth (3rd Feature)")
    plt.xlabel("Date"); plt.ylabel("Value")
    plt.legend(); plt.grid(True)
    plt.xticks(rotation=45); plt.tight_layout()

    # 저장
    predict_fig = f"predict_{epoch_str}.png"
    predict_out = os.path.join(SAVE_DIR, predict_fig)
    os.makedirs(os.path.dirname(predict_out), exist_ok=True)
    plt.savefig(predict_out, dpi=150)
    plt.show()
