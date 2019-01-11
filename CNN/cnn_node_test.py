#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IRIE Final Project - Edge Detection
CNN - Consider the info of nodes
Testing
"""

import numpy as np
import json

from gensim.models import Word2Vec

import keras

from keras.layers import Input

from keras.models import Model
from keras.layers import Dense, Dropout, Flatten, BatchNormalization, merge
from keras.layers.convolutional import Conv2D, MaxPooling2D

import sklearn.metrics

# 0. Load dataset
with open("data/train.json", 'r', encoding='utf-8') as f:
    train_data = [json.loads(line) for line in f]

with open("data/test.json", 'r', encoding='utf-8') as f:
    test_data = [json.loads(line) for line in f]
    
# len(train_data), training data size = 1000
# len(test_data), training data size = 97


# 1. Word2vec
# (a) Sentence (tokens) list

def build_sentence_list(dataset):
    sentence_list = []
    for data in dataset:
        token = data['tokens']
        sentence_list.append(token)
    return sentence_list

train_sentence_list = build_sentence_list(train_data)
test_sentence_list = build_sentence_list(test_data)
    

# (b) Word2vec model
word2vec_dim = 200

word2vec_tr_model = Word2Vec.load('savings/word2vec_model.model') 

num_words = len(word2vec_tr_model.wv.vocab) + 4 # 1533 words +  <PAD>, <SOS>, <EOS>, <UNK> => 1537

'''
<PAD>: padding
<SOS>: start of sentence
<EOS>: end of sentence
<UNK>: unknown words
'''

# (c) Create embedding matrix
emb_matrix = np.zeros([num_words, word2vec_dim]) # first row is the embedding, [0, 0, ..., 0], for <PAD>
emb_matrix[1] = np.zeros(word2vec_dim) + 0.2 # <SOS>
emb_matrix[2] = np.zeros(word2vec_dim) + 0.4 # <EOS>
emb_matrix[3] = np.zeros(word2vec_dim) + 0.6 # <UNK>
for i in range(num_words - 4):
    v = word2vec_tr_model.wv[word2vec_tr_model.wv.index2word[i]]
    emb_matrix[i + 4] = v   # Plus 1 to reserve index 0 for <PAD>
# emb_matrix.shape # (1537, 256)


# 2. Inputs of model
# (a) Data info. - Tokens & Edges & Nodes
def build_info(dataset):
    tokens_info = {}
    tokens_info['tokens'] = []
    
    edges_info = {}
    edges_info['num_relations'] = []
    edges_info['head_locs'] = []
    edges_info['tail_locs'] = []   
    edges_info['heads'] = []
    edges_info['tails'] = []    
    edges_info['edge_class'] = []
    
    nodes_info = {}
    nodes_info['node_class'] = []
    
    for data in dataset:
        tokens = data['tokens']
        tokens_info['tokens'].append(tokens)
        
        nodes = data['nodes']
        node_info = []
        for node in nodes:
            node_info.append(np.array([node[0][0]] + list(node[1].keys())))
        
        loc = np.array(node_info)[:, 0]
        node_class = np.array(node_info)[:, 1]
        
        edges = data['edges']
        edges_info['num_relations'].append(len(edges))
        for edge in edges:
            head_loc1, head_loc2 = edge[0]
            tail_loc1, tail_loc2 = edge[1]
            edges_info['head_locs'].append(head_loc1)
            edges_info['tail_locs'].append(tail_loc1)
            edges_info['heads'].append(tokens[head_loc1:head_loc2])
            edges_info['tails'].append(tokens[tail_loc1:tail_loc2])
            edges_info['edge_class'].extend(list(edge[2].keys()))
            
            head_class = node_class[np.where(loc == str(head_loc1))[0]]
            tail_class = node_class[np.where(loc == str(tail_loc1))[0]]
            nodes_info['node_class'].append(np.array([head_class] + [tail_class]).reshape([1, -1])[0])
        
    return tokens_info, edges_info, nodes_info

test_tokens_info,  test_edges_info,  test_nodes_info =  build_info(test_data)


# (b) Lexical Level Features
'''Lexical Level Features
Noun 1
Noun 2
Left and right tokens of noun 1
Left and right tokens of noun 2
(WordNet)
'''
test_data_size = len(test_edges_info['head_locs'])

#node_token_len = list(map(len, train_edges_info['heads'] + train_edges_info['tails']))
#np.unique(node_token_len)
#np.percentile(node_token_len, 99) = 9

def word2vec_seq(sequences, word2vec_dim = word2vec_dim):
    word2vec_seqs = []
    for seq in sequences:
        word2vec_seq = np.zeros([len(seq), word2vec_dim])
        for i, word in enumerate(seq):
            if word == '<SOS>':
                word2vec_seq[i] = emb_matrix[1] # <SOS>
            elif word == '<EOS>':
                word2vec_seq[i] = emb_matrix[2] # <EOS>
            elif word not in word2vec_tr_model:
                word2vec_seq[i] = emb_matrix[3] # <UKN>
            else:
                word2vec_seq[i] = word2vec_tr_model[word]
        word2vec_seqs.append(word2vec_seq)
    return word2vec_seqs
                
def pad_sequences(word2vec_seqs, max_len, word2vec_dim = word2vec_dim):
    pad_seqs = []
    for seq in word2vec_seqs:     
        if len(seq) < max_len:
            pad_seq = np.vstack((seq, np.zeros([max_len - len(seq), word2vec_dim])))
        else:
            pad_seq = seq[:max_len, :]
        pad_seqs.append(pad_seq)
        
    return pad_seqs
            
test_noun1 = word2vec_seq([[head_seq[0]] for head_seq in test_edges_info['heads']])
test_noun2 = word2vec_seq([[tail_seq[0]] for tail_seq in test_edges_info['tails']])

test_LH = []
test_RH = []
test_LT = []
test_RT = []
count = -1
for i, num_relation in enumerate(test_edges_info['num_relations']):    
    token = ['<SOS>'] + test_tokens_info['tokens'][i] + ['<EOS>']
    for _ in range(num_relation):
        count += 1
        head_loc = test_edges_info['head_locs'][count]
        test_LH.append(token[head_loc - 1])
        test_RH.append(token[head_loc + 1])
        tail_loc = test_edges_info['tail_locs'][count]
        test_LT.append(token[head_loc - 1])
        test_RT.append(token[head_loc + 1])
        
test_LH = word2vec_seq([[i] for i in test_LH])
test_RH = word2vec_seq([[i] for i in test_RH])
test_LT = word2vec_seq([[i] for i in test_LT])
test_RT = word2vec_seq([[i] for i in test_RT])

test_node_class = test_nodes_info['node_class']
node_class_category = np.load('savings/node_class_category.npy')
node_class_one_hot = np.zeros([test_data_size, len(node_class_category)*2])
fact_or_not = np.zeros(test_data_size)
for i in range(test_data_size):
    idx1 = np.where(node_class_category == test_node_class[i][0])[0]
    idx2 = np.where(node_class_category == test_node_class[i][1])[0] + len(node_class_category)
    node_class_one_hot[i, idx1] = 1.
    node_class_one_hot[i, idx2] = 1.
    if test_node_class[i][0] != test_node_class[i][1]:
        fact_or_not[i] = 1.

lexical_feat = [np.array(list(test_noun1[i][0]) + list(test_noun2[i][0]) + \
                         list(test_LH[i][0]) + list(test_RH[i][0]) + list(test_LT[i][0]) + \
                         list(test_RT[i][0]) + list(node_class_one_hot[i]) + [fact_or_not[i]]) for i in range(test_data_size)] # shape: 16959 x (200 * 6 + 15 * 2 + 1)

# (c) Sentence Level Features
# i. Word Features (WF) - the whole info. from tokens
rep_tokens = []
for i, num_relation in enumerate(test_edges_info['num_relations']):    
    token = ['<SOS>'] + test_tokens_info['tokens'][i] + ['<EOS>']
    three_word_unit = []
    for j in range(1, len(token)-1):
        three_word_unit.extend(token[j-1 : j+2])
    for _ in range(num_relation):  
        rep_tokens.append(three_word_unit)

#rep_token_len = list(map(len, rep_tokens))
#np.unique(rep_token_len)
#np.percentile(rep_token_len, 90) = 70

pad_rep_tokens = pad_sequences(word2vec_seq(rep_tokens), max_len = 100*3, word2vec_dim = word2vec_dim) # 16959 x 300 x 256

word_feat = [i.reshape([100, word2vec_dim*3]) for i in pad_rep_tokens] # 16959 x 100 x 768


# ii. Position Features (PF) - the relative distances far from the target nodes
position_feat = []
for i in range(test_data_size):
    head_loc = test_edges_info['head_locs'][i]
    tail_loc = test_edges_info['tail_locs'][i]
    relative_position = np.zeros([100, 2])
    for j in range(100):
        relative_position[j] = np.array([j-head_loc, tail_loc-j])
    position_feat.append(relative_position)


# iii. Concatenate WF and PF
word_position_feat = [np.hstack((word_feat[i], position_feat[i])).reshape([100, word2vec_dim*3+2, 1]) for i in range(test_data_size)]
    

# 3. Outputs of model - ground truth
test_edge_class = test_edges_info['edge_class']
class_category = np.unique(test_edge_class)

y_true = np.zeros(test_data_size)
for i in range(test_data_size):
    y_true[i] = np.where(class_category == test_edge_class[i])[0]


# 4. Load Model
model = keras.models.load_model('savings/edge_detection_cnn_node.h5')

pred_prob = model.predict([np.array(lexical_feat), np.array(word_position_feat)])

y_pred = [np.argmax(i) for i in pred_prob]

accuracy = sklearn.metrics.accuracy_score(y_true, y_pred)
precision = sklearn.metrics.precision_score(y_true, y_pred, average = 'macro')
recall = sklearn.metrics.recall_score(y_true, y_pred, average = 'macro')
macro_f1 = sklearn.metrics.f1_score(y_true, y_pred, average = 'macro')
micro_f1 = sklearn.metrics.f1_score(y_true, y_pred, average = 'micro')

print('Accuracy: ', accuracy, '\nPrecision: ', precision, '\nRecall: ', recall, '\nMacro-F1: ', macro_f1, '\nMicro-F1: ', micro_f1) 

# Accuracy:  0.9783263094521373 
# Precision:  0.9630994367531716 
# Recall:  0.9294201816598232 
# Macro-F1:  0.9444897354183651
# Micro-F1:  0.9783263094521373

# Training - loss: 0.0486 - acc: 0.9822 - val_loss: 0.0449 - val_acc: 0.9814
# Testing Accuracy = 0.9783
# Testing Precision = 0.9631
# Testing Recall = 0.9294
# Testing Macro-F1 = 0.9445
# Testing Micro-F1 = 0.9783