import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np

class RNNC(nn.Module):
	def __init__(self,token,args):
		super(RNNC,self).__init__()
		
		self.word_emb = nn.Embedding(len(token['tokens']),args.word_dim,padding_idx=0)
		self.edge_emb = nn.Embedding(3,args.word_dim,padding_idx=0)
		self.ner_emb = nn.Embedding(len(token['nodes']),args.word_dim)
	
		self.rnn = nn.LSTM(
			input_size=args.word_dim,
			hidden_size=args.hidden_dim,
			num_layers=args.num_layer,
			batch_first=args.batch_first,
			dropout=args.dropout,
			bidirectional=args.bidirectional
		)
		
		self.word_size = args.word_dim
		self.hidden_size = args.hidden_dim
		self.num_layer = args.num_layer
		self.batch_first = args.batch_first
		self.dropout = args.dropout
		self.bidirectional = args.bidirectional

			
		self.dense_1 = nn.Linear(4*args.hidden_dim,32)
		self.act_1 = nn.ReLU()
		self.dense_2 = nn.Linear(32,len(token['edges']))
		
		if(args.mode == 'pretrain'):
			self.load()
			self.word_emb.weight.requires_grad = False
			print("here",self.word_emb.weight.requires_grad)

	def load(self):
		with open('./data/embedding/glove.6B.100d.txt') as f:
			arr = np.zeros((self.word_emb.weight.shape[0],self.word_emb.weight.shape[1]),dtype=np.float32)
			for i,line in enumerate(f):
				for j,num in enumerate(line.strip().split()[1:]):
					arr[i+1,j] = float(num)
					
			self.word_emb.weight = nn.Parameter(torch.tensor(arr))


	def forward(self,data,data_len,data_ner,data_point):
		def pack(seq,seq_length):
			sorted_seq_lengths, indices = torch.sort(seq_length, descending=True)
			_, desorted_indices = torch.sort(indices, descending=False)

			if self.batch_first:
				seq = seq[indices]
			else:
				seq = seq[:, indices]
			packed_inputs = nn.utils.rnn.pack_padded_sequence(seq,
															sorted_seq_lengths.cpu().numpy(),
															batch_first=self.batch_first)

			return packed_inputs,desorted_indices

		def unpack(res, state,desorted_indices):
			padded_res,_ = nn.utils.rnn.pad_packed_sequence(res, batch_first=self.batch_first)

			state = [state[i][:,desorted_indices] for i in range(len(state)) ] 

			if(self.batch_first):
				desorted_res = padded_res[desorted_indices]
			else:
				desorted_res = padded_res[:, desorted_indices]

			return desorted_res,state

		def feat_extract(output,length,ner):
			"""
			answer_output: batch*sentence*feat_len
			query_output:  batch*sentence*feat_len
			for simple rnn, we just take the output from 
			"""
			if( self.batch_first == False ):
				output = output.transpose(0,1) 

			repre = []
			for j in range(2):
				temp = [torch.cat([ output[i][ length[i][j][1]-1 ][:self.hidden_size] , 
											output[i][ length[i][j][0] ][self.hidden_size:]] , dim=-1 ) for i in range(len(length))]
				repre.append(torch.stack(temp,dim=0))

			#temp = [torch.cat([ self.ner_emb(ner[i][ length[i][j][1]-1 ]) , self.ner_emb(ner[i][ length[i][j][0] ])] , dim=-1 ) for i in range(ner.shape[0])]
			#repre.append(torch.stack(temp,dim=0))
			
			repre = torch.cat(repre,dim=-1)

			return repre
		#first check for the mask ans the embedding
		mask =  data.eq(0)

		word = self.word_emb(data)
		#word = word + self.ner_emb(data_ner)
		#word = word + self.edge_emb(data_point)
		
		#query part
		packed_inputs,desorted_indices = pack(word,data_len)
		res, state = self.rnn(packed_inputs)
		query_res,_ = unpack(res, state,desorted_indices)

		#extract the representation of the sentence
		query_result = feat_extract(query_res,data_point,data_ner)

		output = self.dense_1(query_result)
		output = self.act_1(output)
		output = self.dense_2(output)

		return output
