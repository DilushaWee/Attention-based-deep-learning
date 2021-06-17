import random
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
import pickle as pkl
import keras
from keras.models import Sequential, Model, load_model
from keras.layers import LSTM, Dense, RepeatVector, TimeDistributed, Input, BatchNormalization, multiply, concatenate, Flatten, Activation, dot
from keras.optimizers import Adam
from keras.utils import plot_model
from keras.callbacks import EarlyStopping
import pydot as pyd
from keras.utils.vis_utils import plot_model, model_to_dot

keras.utils.vis_utils.pydot = pyd


n_ = 1000
train_window=480
predict_window=48

df_training_entity = pd.read_csv('sample_data/Ausgrid_Sydney_2011-07-01_2012-06-30.csv',usecols=['Total_consumption'])
train_len=len(df_training_entity)
df_testing_entity = pd.read_csv('sample_data/Ausgrid_Sydney_2012-07-01_2013-06-30.csv',usecols=['Total_consumption'])
test_len=len(df_testing_entity)

df_full=pd.concat([df_training_entity, df_testing_entity], ignore_index=True)

print(df_full.head())

x1 = df_full['Total_consumption'].tolist()
t=list(df_full.index.values)

plt.figure(figsize=(15, 4))
plt.plot(range(len(x1)), x1, label='x1')
plt.legend(loc='upper center', bbox_to_anchor=(0.5, -0.15), fancybox=True, shadow=False, ncol=2)
plt.show()

x_index = np.array(range(len(t)))

x1_trend_param = np.polyfit(x_index[:train_len], x1[:train_len], 1)
print(x1_trend_param)

x1_trend = x_index*x1_trend_param[0]+x1_trend_param[1]


plt.figure(figsize=(15, 4))
plt.plot(range(len(x1)), x1, label='x1')
plt.plot(range(len(x1_trend)), x1_trend, linestyle='--', label='x1_trend')
plt.legend(loc='upper center', bbox_to_anchor=(0.5, -0.15), fancybox=True, shadow=False, ncol=2)
plt.show()

x1_detrend = x1 - x1_trend
plt.figure(figsize=(15, 4))
plt.plot(range(len(x1_detrend)), x1_detrend, label='x1_detrend')
plt.legend(loc='upper center', bbox_to_anchor=(0.5, -0.15), fancybox=True, shadow=False, ncol=2)
plt.show()

x_lbl = np.column_stack([x1_detrend, x_index, [1]*train_len+[0]*(len(x_index)-train_len)])
print(x_lbl.shape)
print(x_lbl)

x_train_max = x_lbl[x_lbl[:, 2]==1, :1].max(axis=0)
x_train_max = x_train_max.tolist()+[1]*2  # only normalize for the first 2 columns
print(x_train_max)

x_normalize = np.divide(x_lbl, x_train_max)
print(x_normalize)

plt.figure(figsize=(15, 4))
plt.plot(range(train_len), x_normalize[:train_len, 0], label='x1_train_normalized')
plt.plot(range(train_len, len(x_normalize)), x_normalize[train_len:, 0], label='x1_test_normalized')
plt.legend(loc='upper center', bbox_to_anchor=(0.5, -0.15), fancybox=True, shadow=False, ncol=2)
plt.show()

def truncate(x, feature_cols=range(2), target_cols=range(2), label_col=2, train_len=100, test_len=20):
    in_, out_,peaks, lbl = [], [],[], []
    for i in range(len(x)-train_len-test_len+1):
        in_.append(x[i:(i+train_len), feature_cols].tolist())
        out_.append(x[(i+train_len):(i+train_len+test_len), target_cols].tolist())
        lbl.append(x[i+train_len, label_col])
    return np.array(in_), np.array(out_), np.array(peaks), np.array(lbl)
X_in, X_out, Peaks, lbl = truncate(x_normalize, feature_cols=range(2), target_cols=range(2), 
                            label_col=2, train_len=train_window, test_len=predict_window)
print(X_in.shape, X_out.shape, lbl.shape)


X_input_train = X_in[np.where(lbl==1)]
X_output_train = X_out[np.wher(lbl==1)]
X_input_test = X_in[np.where(lbl==0)]
X_output_test = X_out[np.where(lbl==0)]
print(X_input_train.shape, X_output_train.shape)
print(X_input_test.shape, X_output_test.shape)

#####################################

n_hidden = 100

input_train = Input(shape=(X_input_train.shape[1], X_input_train.shape[2]-1))
output_train = Input(shape=(X_output_train.shape[1], X_output_train.shape[2]-1))
print(input_train)
print(output_train)

#encoder_stack_h, encoder_last_h, encoder_last_c = LSTM(n_hidden, activation='elu', dropout=0.2, recurrent_dropout=0.2,return_state=True, return_sequences=True)(input_train)
encoder_stack_h, encoder_last_h, encoder_last_c = LSTM(n_hidden, activation='tanh', dropout=0.2, recurrent_dropout=0, return_state=True, return_sequences=True)(input_train)
print(encoder_stack_h)
print(encoder_last_h)
print(encoder_last_c)


encoder_last_h = BatchNormalization(momentum=0.6)(encoder_last_h)
encoder_last_c = BatchNormalization(momentum=0.6)(encoder_last_c)

decoder_input = RepeatVector(output_train.shape[1])(encoder_last_h)
print(decoder_input)


#decoder_stack_h = LSTM(n_hidden, activation='elu', dropout=0.2, recurrent_dropout=0.2, return_state=False, return_sequences=True)(decoder_input, initial_state=[encoder_last_h, encoder_last_c])
decoder_stack_h = LSTM(n_hidden, activation='tanh', dropout=0.2, recurrent_dropout=0, return_state=False, return_sequences=True)(decoder_input, initial_state=[encoder_last_h, encoder_last_c])
print(decoder_stack_h)

print("HEre")
print((encoder_stack_h))
encoder_stack_h=Dense(100)(encoder_stack_h)
print((encoder_stack_h))
attention = dot([decoder_stack_h, encoder_stack_h], axes=[2, 2])
#attention= Dense(480)(attention)
attention = Activation('softmax')(attention)
print(attention)

context = dot([attention, encoder_stack_h], axes=[2,1])
context = BatchNormalization(momentum=0.6)(context)
print(context)

decoder_combined_context = concatenate([context, decoder_stack_h])
print(decoder_combined_context)

#############################

out = TimeDistributed(Dense(output_train.shape[2]))(decoder_combined_context)
print(out)

model = Model(inputs=input_train, outputs=out)
opt = Adam(lr=0.01, clipnorm=1)
model.compile(loss='mean_squared_error', optimizer=opt, metrics=['mae'])
model.summary()

plot_model(model, to_file='model_plot.png', show_shapes=True, show_layer_names=True)


epc = 10
es = EarlyStopping(monitor='val_loss', mode='min', patience=50)
history = model.fit(X_input_train[:, :, :1], X_output_train[:, :, :1], validation_split=0.2, epochs=epc, verbose=1, callbacks=[es], batch_size=100)
train_mae = history.history['mae']
valid_mae = history.history['val_mae']
 
model.save('model_forecasting_seq2seq.h5')



plt.plot(train_mae, label='train mae'), 
plt.plot(valid_mae, label='validation mae')
plt.ylabel('mae')
plt.xlabel('epoch')
plt.title('train vs. validation accuracy (mae)')
plt.legend(loc='upper center', bbox_to_anchor=(0.5, -0.15), fancybox=True, shadow=False, ncol=2)
plt.show()

train_pred_detrend = model.predict(X_input_train[:, :, :1])*x_train_max[:1]
test_pred_detrend = model.predict(X_input_test[:, :, :1])*x_train_max[:1]
print(train_pred_detrend.shape, test_pred_detrend.shape)
train_true_detrend = X_output_train[:, :, :1]*x_train_max[:1]
test_true_detrend = X_output_test[:, :, :1]*x_train_max[:1]
print(train_true_detrend.shape, test_true_detrend.shape)


train_pred_detrend = np.concatenate([train_pred_detrend, np.expand_dims(X_output_train[:, :, 1], axis=2)], axis=2)
test_pred_detrend = np.concatenate([test_pred_detrend, np.expand_dims(X_output_test[:, :, 1], axis=2)], axis=2)
print(train_pred_detrend.shape, test_pred_detrend.shape)
train_true_detrend = np.concatenate([train_true_detrend, np.expand_dims(X_output_train[:, :, 1], axis=2)], axis=2)
test_true_detrend = np.concatenate([test_true_detrend, np.expand_dims(X_output_test[:, :, 1], axis=2)], axis=2)
print(train_pred_detrend.shape, test_pred_detrend.shape)


data_final = dict()
for dt, lb in zip([train_pred_detrend, train_true_detrend, test_pred_detrend, test_true_detrend],['train_pred', 'train_true', 'test_pred', 'test_true']):
    dt_x1 = dt[:, :, 0] + dt[:, :, 1]*x1_trend_param[0] + x1_trend_param[1]    
    data_final[lb] = dt_x1
    print(lb+': {}'.format(data_final[lb].shape))


for lb in ['train', 'test']:
    plt.figure(figsize=(15, 4))
    plt.hist(data_final[lb+'_pred'].flatten(), bins=100, color='orange', alpha=0.5, label=lb+' pred')
    plt.hist(data_final[lb+'_true'].flatten(), bins=100, color='green', alpha=0.5, label=lb+' true')
    plt.legend()
    plt.title('value distribution: '+lb)
    plt.show()


for lb in ['train', 'test']:
    MAE_overall = abs(data_final[lb+'_pred'] - data_final[lb+'_true']).mean()
    MAE_ = abs(data_final[lb+'_pred'] - data_final[lb+'_true']).mean(axis=1)
    plt.figure(figsize=(15, 3))
    plt.plot(MAE_)
    plt.title('MAE '+lb+': overall MAE = '+str(MAE_overall))
    plt.show()


ith_timestep = random.choice(range(data_final[lb+'_pred'].shape[1]))
plt.figure(figsize=(15, 5))
train_start_t = 0
test_start_t = data_final['train_pred'].shape[0]
for lb, tm, clrs in zip(['train', 'test'], [train_start_t, test_start_t], [['green', 'red'], ['blue', 'orange']]):
    for i, x_lbl in zip([0], ['x1']):
        plt.plot(range(tm, tm+data_final[lb+'_pred'].shape[0]), 
                 data_final[lb+'_pred'][:, ith_timestep], 
                 linestyle='--', linewidth=1, color=clrs[0], label='pred '+x_lbl)
        plt.plot(range(tm, tm+data_final[lb+'_pred'].shape[0]), 
                 data_final[lb+'_true'][:, ith_timestep], 
                 linestyle='-', linewidth=1, color=clrs[1], label='true '+x_lbl)
    
plt.title('{}th time step in all samples'.format(ith_timestep))
plt.legend(loc='upper center', bbox_to_anchor=(0.5, -0.15), fancybox=True, shadow=False, ncol=8)
plt.show()


lb = 'test'
plt.figure(figsize=(15, 5))
for i, x_lbl, clr in zip([0], ['x1'], ['green']):
    plt.plot(data_final[lb+'_pred'][:, ith_timestep], linestyle='--', color=clr, label='pred '+x_lbl)
    plt.plot(data_final[lb+'_true'][:, ith_timestep], linestyle='-', color=clr, label='true '+x_lbl)
plt.title('({}): {}th time step in all samples'.format(lb, ith_timestep))
plt.legend(loc='upper center', bbox_to_anchor=(0.5, -0.15), fancybox=True, shadow=False, ncol=2)
plt.show()
e
