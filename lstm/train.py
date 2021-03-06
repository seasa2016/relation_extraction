import torch
from data.dataloader import itemDataset,ToTensor,collate_fn,collate_fn1
from torch.utils.data import Dataset,DataLoader

import os
import argparse
import torch.optim as optim
import torch.nn as nn
from sklearn.metrics import f1_score,precision_score,recall_score

from torchvision import transforms, utils
from model.birnn import RNN
from model.birnn_co import RNNC

def train(args,model,train_data,test_data,criterion,optimizer,device):
	def convert(data,device):
		for name in data:
			if(isinstance(data[name],torch.Tensor)):
				data[name] = data[name].to(device)
		return data

	print("start training")
	for now in range(args.epoch):
		print(now)

		loss_sum = {'ner':0,'relate':0}
		count = {'ner':0,'relate':0,'total':0}
		model.train()
		model.zero_grad()
		
		for i,data in enumerate(train_data):
			#first convert the data into cuda
			data = convert(data,device)
			
			out = model(data['sent'],data['sent_len'],data['node'],data['edge'])
			if(isinstance(out,tuple)):
				"""
				temp = out[1].view(-1,out[1].shape[-1])
				
				loss = criterion(temp,data['node'].view(-1)) 
				_,pred = torch.topk(temp,1)
				pred = pred.view(-1)
				count['ner'] += torch.sum( data['node'].view(-1) == pred ).item()	
				loss_sum['ner'] += loss.detach().item()
			
				count['total'] += torch.sum(data['sent_len']).item()

				loss.backward(retain_graph=True)
				"""
				out = out[0]

			loss = criterion(out,data['label']) 
			_,pred = torch.topk(out,1)
			pred = pred.view(-1)
			count['relate'] += torch.sum( data['label'] == pred ).item()
			
			loss.backward()
			optimizer.step()
			model.zero_grad()
			loss_sum['relate'] += loss.detach().item()

		print('*'*10)
		print('training loss:{0} acc_relate:{1}/{2} acc_ner:{3}/{4}'.format(loss_sum,count['relate'],len(train_data)*args.batch_size,
																		count['ner'],count['total']))
		loss_sum = 0
		count = 0
		model.eval()
		
		ans={'label':[],'output':[]}

		for i,data in enumerate(test_data):
			#first convert the data into cuda
			data = convert(data,device)
			
			with torch.no_grad():
				out = model(data['sent'],data['sent_len'],data['node'],data['edge'])
				if(isinstance(out,tuple)):
					out = out[0]
				loss = criterion(out,data['label']) 
				_,pred = torch.topk(out,1)
				pred = pred.view(-1)
				count += torch.sum( data['label'] == pred ).item()
				loss_sum += loss.detach().item()

				ans['label'].extend(data['label'].view(-1).cpu().tolist())
				ans['output'].extend(pred.view(-1).cpu().tolist())

		print('testing loss:{0} acc:{1}/{2}'.format(loss_sum,count,len(test_data)*args.batch_size))
		print('F1 macro:{0}'.format( f1_score(ans['label'], ans['output'], average='macro') ))
		print('F1 micro:{0}'.format( f1_score(ans['label'], ans['output'], average='micro') ))
		print('macro precision:{0}'.format( precision_score(ans['label'], ans['output'], average='macro') ))
		print('macro recall:{0}'.format( recall_score(ans['label'], ans['output'], average='macro') ))
		checkpoint={'model':model.state_dict(),'args':args}
		torch.save(checkpoint, './save_model/{1}/step_{0}.pkl'.format(now,args.model))

def main():
	parser = argparse.ArgumentParser()

	parser.add_argument('--batch_size', default=256, type=int)
	parser.add_argument('--dropout', default=0, type=float)
	parser.add_argument('--epoch', default=20, type=int)
	parser.add_argument('--gpu', default=0, type=int)

	parser.add_argument('--word_dim', default=100, type=int)
	parser.add_argument('--hidden_dim', default=128, type=int)
	parser.add_argument('--batch_first', default=True, type=bool)
	parser.add_argument('--bidirectional', default=True, type=bool)
	parser.add_argument('--num_layer', default=2, type=int)

	parser.add_argument('--learning_rate', default=0.001, type=float)
	parser.add_argument('--mode', required=True, type=str)
	parser.add_argument('--model', required=True, type=str)

	args = parser.parse_args()

	if(torch.cuda.is_available()):
		device = torch.device('cuda')
	else:
		device = torch.device('cpu')

	print("loading data")
	train_data = itemDataset('./data/train.json',mode=args.mode,transform=transforms.Compose([ToTensor()]))
	test_data = itemDataset('./data/test.json',mode='test',transform=transforms.Compose([ToTensor()]))
	
	if(args.model == 'birnn'):
		train_loader = DataLoader(train_data, batch_size=args.batch_size,shuffle=True, num_workers=12,collate_fn=collate_fn)
		test_loader = DataLoader(test_data, batch_size=args.batch_size,shuffle=True, num_workers=12,collate_fn=collate_fn)
	elif(args.model == 'birnn_co'):
		train_loader = DataLoader(train_data, batch_size=args.batch_size,shuffle=True, num_workers=12,collate_fn=collate_fn1)
		test_loader = DataLoader(test_data, batch_size=args.batch_size,shuffle=True, num_workers=12,collate_fn=collate_fn1)
		
	print("setting model")
	if(args.model == 'birnn'):
		model = RNN(train_data.token,args)
	elif(args.model == 'birnn_co'):
		model = RNNC(train_data.token,args)
	args.model+='neer'	
	model = model.to(device)
	print(model)
	if(not os.path.isdir('./save_model/{0}'.format(args.model))):
		os.mkdir('./save_model/{0}'.format(args.model))
	#for name,d in model.named_parameters():
	#	print(name,d.requires_grad)
	
	optimizer = optim.Adam(filter(lambda p: p.requires_grad, model.parameters()),lr=args.learning_rate)
	
	criterion = nn.CrossEntropyLoss(reduction='sum',ignore_index=0)

	train(args,model,train_loader,test_loader,criterion,optimizer,device)
	


if(__name__ == '__main__'):
	main()
