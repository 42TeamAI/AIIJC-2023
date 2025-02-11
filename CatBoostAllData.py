import os
import random
import json

import numpy as np
import pandas as pd
import torch
from catboost import CatBoostClassifier
from sklearn.metrics import f1_score



def seed_everything(seed):
    random.seed(seed)
    os.environ['PYTHONHASHSEED'] = str(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def load_npy_for_cb(df, path):
    data = []
    for name in df.record_name:
        with open(f"{path}{name}.npy", "rb") as f:
            y = np.load(f, allow_pickle=True)
            row = np.std(y, axis=1)
            data.append(row)
    data = np.stack(data)
    data = pd.DataFrame(np.stack(data), columns=list(range(data.shape[-1])))
    data["record_name"] = df["record_name"]
    return data


def processing(gts, meta, cat_f, path, is_train=True):
    gts = gts.merge(meta, on='record_name')

    gts = gts.fillna(0)
    gts.age = gts.age.astype(int)

    for c in cat_f:
        gts[c] = gts[c].astype(str)
    gts.age = gts.age.astype(int)
    gts.ecg_id = gts.ecg_id.astype(int)
    gts.patient_id = gts.patient_id.astype(int)
    gts.scp_codes = gts.scp_codes.astype(str)
    if is_train:
        data = load_npy_for_cb(gts, path)
    else:
        data = load_npy_for_cb(gts, path)
    gts = gts.merge(data, on='record_name')
    if is_train:
        return gts.drop(columns=['myocard', 'record_name', 'recording_date', 'filename_lr', 'filename_hr', 'ecg_id', 'patient_id']), gts[
            'myocard']
    return gts.drop(columns=['myocard', 'record_name', 'recording_date', 'filename_lr', 'filename_hr', 'ecg_id', 'patient_id'])


seed_everything(42)
with open('config.json', 'r') as f:
    config = json.load(f)
df = pd.read_csv(config['train_gts'])
df_test = pd.read_csv('catboost_std.csv')
meta_test = pd.read_csv(config['test_meta'])
meta = pd.read_csv(config['train_meta'])
cat_f = ['age', 'sex', 'height', 'weight', 'nurse', 'site', 'device', 'heart_axis',
         'infarction_stadium1', 'infarction_stadium2', 'validated_by', 'second_opinion',
         'initial_autogenerated_report', 'validated_by_human', 'baseline_drift', 'static_noise',
         'burst_noise', 'electrodes_problems', 'extra_beats', 'pacemaker', 'strat_fold', 'group']


X_train, y_train = processing(df, meta, cat_f, path=config['train_path'])
X_val, y_val = processing(df_test, meta_test, cat_f, path=config['test_path'])

with open('catboost_all_data.json', 'r') as f:
    best_params = json.load(f)

model = CatBoostClassifier(eval_metric='F1', **best_params)


model.fit(X_train, y_train, eval_set=(X_val, y_val), cat_features=cat_f,
              text_features=['report', 'scp_codes'],
              early_stopping_rounds=100)
print(f1_score(y_val, model.predict(X_val)))

meta_test = pd.read_csv(config['test_meta'])
gts_test = pd.read_csv(config['sample_submission'])
X = processing(gts_test, meta_test, cat_f, path=config['test_path'], is_train=False)
cb_pred = model.predict(X)
gts_test['myocard'] = cb_pred
gts_test.to_csv('predict.csv', index=None)
model.save_model("model.cb")