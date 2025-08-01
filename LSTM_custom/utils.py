import os
import tensorflow as tf
import numpy as np


class Checkpoint(tf.keras.callbacks.Callback):
    def __init__(self, save_every: int):
        super().__init__()
        self.save_every = save_every
        self.save_dir   = 'checkpoint_saved'
        self.loss_log   = os.path.join(self.save_dir, "loss_log.csv")
        self.weight_dir = os.path.join(self.save_dir, "weight")

        os.makedirs(self.save_dir, exist_ok=True) 
        os.makedirs(self.weight_dir, exist_ok=True)  

        with open(self.loss_log, "w") as f:
            f.write("epoch,mean_loss,std_loss\n")

    def on_epoch_begin(self, epoch, logs=None):
        # 매 에포크 시작 시 배치 손실을 담을 리스트 초기화
        self._batch_losses = []

    def on_batch_end(self, batch, logs=None):
        # 배치가 끝날 때마다 logs["loss"]를 수집
        if logs is not None and "loss" in logs:
            self._batch_losses.append(logs["loss"])

    def on_epoch_end(self, epoch, logs=None):
        epoch_idx = epoch + 1
        mean_loss = float(np.mean(self._batch_losses))
        std_loss  = float(np.std(self._batch_losses))

        if epoch_idx % self.save_every == 0:
            fname = f"model_weights_epoch_{epoch_idx:03d}.h5"
            path  = os.path.join(self.weight_dir, fname)
            self.model.save_weights(path)
            print(f"[epochs : {epoch_idx}] Saved weights to {path}")

            with open(self.loss_log, "a") as f:
                f.write(f"{epoch_idx},{mean_loss:.4f},{std_loss:.4f}\n")