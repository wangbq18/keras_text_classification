# coding=utf-8

# @Author  : zhzhx2008
# @Time    : 18-10-9

import os
import warnings

import jieba
import numpy as np
from keras import Input
from keras import Model
from keras.callbacks import EarlyStopping, ModelCheckpoint
from keras.layers import Embedding, Dense, GlobalMaxPooling1D, SpatialDropout1D
from keras.preprocessing.sequence import pad_sequences
from keras.preprocessing.text import Tokenizer
from keras.utils import to_categorical
from sklearn.model_selection import train_test_split

warnings.filterwarnings("ignore")

seed = 2019
np.random.seed(seed)


def get_labels_datas(input_dir):
    datas_word = []
    datas_char = []
    labels = []
    label_dirs = os.listdir(input_dir)
    for label_dir in label_dirs:
        txt_names = os.listdir(os.path.join(input_dir, label_dir))
        for txt_name in txt_names:
            with open(os.path.join(input_dir, label_dir, txt_name), 'r') as fin:
                content = fin.readline()  # 只取第一行
                content = content.strip().replace(' ', '')
                datas_word.append(' '.join(jieba.cut(content)))
                datas_char.append(' '.join(list(content)))
                labels.append(label_dir)
    return labels, datas_word, datas_char


def get_label_id_map(labels):
    labels = set(labels)
    id_label_map = {}
    label_id_map = {}
    for index, label in enumerate(labels):
        id_label_map[index] = label
        label_id_map[label] = index
    return id_label_map, label_id_map


input_dir = './data/THUCNews'
labels, datas_word, datas_char = get_labels_datas(input_dir)
id_label_map, label_id_map = get_label_id_map(labels)

labels, labels_test, datas_word, datas_word_test, datas_char, datas_char_test = train_test_split(labels, datas_word, datas_char, test_size=0.3, shuffle=True, stratify=labels)
labels_train, labels_dev, datas_word_train, datas_word_dev, datas_char_train, datas_char_dev = train_test_split(labels, datas_word, datas_char, test_size=0.1, shuffle=True, stratify=labels)

y_train = [label_id_map.get(x) for x in labels_train]
y_dev = [label_id_map.get(x) for x in labels_dev]
y_test = [label_id_map.get(x) for x in labels_test]

num_classes = len(set(y_train))
y_train_index = to_categorical(y_train, num_classes)
y_dev_index = to_categorical(y_dev, num_classes)
y_test_index = to_categorical(y_test, num_classes)

# keras extract feature
tokenizer = Tokenizer()
tokenizer.fit_on_texts(datas_word_train)
# feature5: word index for deep learning
x_train_word_index = tokenizer.texts_to_sequences(datas_word_train)
x_dev_word_index = tokenizer.texts_to_sequences(datas_word_dev)
x_test_word_index = tokenizer.texts_to_sequences(datas_word_test)

# FastText（模型很简单，比较复杂的是构造输入数据）
ngram = 2


def create_ngram(sent, ngram_value):
    return set(zip(*[sent[i:] for i in range(ngram_value)]))


ngram_set = set()
for sentence in x_train_word_index:
    for i in range(2, ngram + 1):
        set_of_ngram = create_ngram(sentence, i)
        ngram_set.update(set_of_ngram)
start_index = len(tokenizer.word_index) + 1
# start_index = 9 + 1
token_indice = {v: k + start_index for k, v in enumerate(ngram_set)}
indice_token = {token_indice[k]: k for k in token_indice}
max_feature = np.max(list(indice_token.keys()))


def add_ngram(sequences, token_indice, ngram_range):
    new_sequences = []
    for sent in sequences:
        new_list = sent[:]
        new_list_origin_len = len(new_list)
        for ngram_value in range(2, ngram_range + 1):
            for i in range(new_list_origin_len - ngram_value + 1):
                ngram = tuple(new_list[i:i + ngram_value])
                if ngram in token_indice:
                    new_list.append(token_indice[ngram])
        new_sequences.append(new_list)
    return new_sequences


x_train_word_index_ngram = add_ngram(x_train_word_index, token_indice, ngram)
x_dev_word_index_ngram = add_ngram(x_dev_word_index, token_indice, ngram)
x_test_word_index_ngram = add_ngram(x_test_word_index, token_indice, ngram)
max_word_length = max([len(x) for x in x_train_word_index_ngram])
x_train_index = pad_sequences(x_train_word_index_ngram, maxlen=max_word_length)
x_dev_index = pad_sequences(x_dev_word_index_ngram, maxlen=max_word_length)
x_test_index = pad_sequences(x_test_word_index_ngram, maxlen=max_word_length)

input = Input(shape=(max_word_length,))
embedding = Embedding(max_feature + 1, 128)(input)
embedding = SpatialDropout1D(0.2)(embedding)
pooling = GlobalMaxPooling1D()(embedding)
output = Dense(num_classes, activation='softmax')(pooling)
model = Model(inputs=input, outputs=output)
model.compile(loss='categorical_crossentropy', optimizer='adam', metrics=['accuracy'])
print(model.summary())

model_weight_file = './model_fast_text.h5'
model_file = './model_fast_text.model'
early_stopping = EarlyStopping(monitor='val_loss', patience=5)
model_checkpoint = ModelCheckpoint(model_weight_file, save_best_only=True, save_weights_only=True)
model.fit(x_train_index,
          y_train_index,
          batch_size=8,
          epochs=1000,
          verbose=2,
          callbacks=[early_stopping, model_checkpoint],
          validation_data=(x_dev_index, y_dev_index),
          shuffle=True)

model.load_weights(model_weight_file)
model.save(model_file)
evaluate = model.evaluate(x_test_index, y_test_index, batch_size=8, verbose=2)
print('loss value=' + str(evaluate[0]))
print('metrics value=' + str(evaluate[1]))

# loss value=0.705208887183477
# metrics value=0.7619047609586564
