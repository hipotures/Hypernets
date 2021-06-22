import json

from hypernets.experiment import CompeteExperiment
from hypernets.experiment import Experiment
from hypernets.tabular import dask_ex as dex
from hypernets.tests.model.plain_model_test import create_plain_model
from hypernets.tests.tabular.dask_transofromer_test import setup_dask

from hypernets.tabular.datasets import dsutils

import numpy as np
import pandas as pd

from dask import dataframe as dd
from dask.distributed import LocalCluster, Client
from sklearn.preprocessing import LabelEncoder


class Test_Get_character:
	@classmethod
	def setup_class(cls):
		setup_dask(cls)

		columnNames = ["MPG","Cylinders","Displacement","Horsepower","Weight","Accleration","Model Year","Origin"]
		rawDataset = pd.read_csv('http://archive.ics.uci.edu/ml/machine-learning-databases/auto-mpg/auto-mpg.data', names=columnNames, na_values="?",comment="\t",sep=" ",skipinitialspace=True)
		rawDataset_copy = rawDataset.copy()

		cls.mpg_data_set = dd.from_pandas(rawDataset_copy, npartitions=1)
		cls.load_blood = dd.from_pandas(dsutils.load_blood(), npartitions=1)
		cls.bike_sharing = dd.from_pandas(dsutils.load_Bike_Sharing(), npartitions=1)

	# A test for multiclass task
	def experiment_with_bike_sharing(self, init_kwargs, run_kwargs, row_count=3000, with_dask=False):
		hyper_model = create_plain_model(with_encoder=True)
		X = dsutils.load_Bike_Sharing()
		if row_count is not None:
			X = X.head(row_count)
		X['count'] = LabelEncoder().fit_transform(X['count'])
		y = X.pop('count')

		if with_dask:
			X = self.bike_sharing.copy()
			y = X.pop('count')
			y = y.astype('str')

		X_train, X_test, y_train, y_test = \
			dex.train_test_split(X, y, test_size=0.3, random_state=9527)
		X_train, X_eval, y_train, y_eval = \
			dex.train_test_split(X_train, y_train, test_size=0.3, random_state=9527)

		init_kwargs = {
			'X_eval': X_eval, 'y_eval': y_eval, 'X_test': X_test,
			**init_kwargs
		}
		
		compete_experiment = CompeteExperiment(hyper_model, X_train, y_train, **init_kwargs)
		base_experiment = Experiment(hyper_model, X_train, y_train, **init_kwargs)

		mydict_compete = compete_experiment.get_data_character()
		mydict_base = base_experiment.get_data_character()

		assert mydict_base
		assert mydict_compete
		assert mydict_base['experimentType'] is 'base'
		assert mydict_compete['experimentType'] is 'compete'
		assert mydict_base['target']['taskType'] is 'multiclass'
		assert mydict_base['target']['freq'] is None
		assert mydict_base['target']['unique']
		assert mydict_base['target']['mean'] is None
		assert mydict_base['target']['max'] is None
		assert mydict_base['target']['min'] is None
		assert mydict_base['target']['stdev'] is None
		assert mydict_base['target']['dataType']
		assert len(mydict_base['targetDistribution']) <= 10
		assert mydict_base['datasetShape']['X_train']
		assert mydict_base['datasetShape']['y_train']
		assert mydict_base['datasetShape']['X_eval']
		assert mydict_base['datasetShape']['y_eval']
		assert mydict_base['datasetShape']['X_test']
		assert mydict_compete['featureDistribution']
	
	# A test for binary task
	def experiment_with_load_blood(self, init_kwargs, run_kwargs, row_count=3000, with_dask=False):
		hyper_model = create_plain_model(with_encoder=True)
		X = dsutils.load_blood()
		if row_count is not None:
			X = X.head(row_count)
		X['Class'] = LabelEncoder().fit_transform(X['Class'])
		y = X.pop('Class')

		if with_dask:
			X = self.load_blood.copy()
			y = X.pop('Class')

		X_train, X_test, y_train, y_test = \
		dex.train_test_split(X, y, test_size=0.3, random_state=9527)
		X_train, X_eval, y_train, y_eval = \
		dex.train_test_split(X_train, y_train, test_size=0.3, random_state=9527)

		init_kwargs = {
			'X_eval': X_eval, 'y_eval': y_eval, 'X_test': X_test,
			**init_kwargs
		}

		compete_experiment = CompeteExperiment(hyper_model, X_train, y_train, **init_kwargs)
		base_experiment = Experiment(hyper_model, X_train, y_train, **init_kwargs)

		mydict_compete = compete_experiment.get_data_character()
		mydict_base = base_experiment.get_data_character()

		assert mydict_base
		assert mydict_compete
		assert mydict_base['experimentType'] is 'base'
		assert mydict_compete['experimentType'] is 'compete'
		assert mydict_base['target']['taskType'] is 'binary'
		assert mydict_base['target']['freq'] is not None
		assert mydict_base['target']['unique'] is 2
		assert mydict_base['target']['mean'] is None
		assert mydict_base['target']['max'] is None
		assert mydict_base['target']['min'] is None
		assert mydict_base['target']['stdev'] is None
		assert mydict_base['target']['dataType']
		assert len(mydict_base['targetDistribution']) <= 10
		assert mydict_base['datasetShape']['X_train']
		assert mydict_base['datasetShape']['y_train']
		assert mydict_base['datasetShape']['X_eval']
		assert mydict_base['datasetShape']['y_eval']
		assert mydict_base['datasetShape']['X_test']
		assert mydict_compete['featureDistribution']

	# A test for regression task
	def experiment_with_mpg_data_set(self, init_kwargs, run_kwargs, row_count=3000, with_dask=False):
		hyper_model = create_plain_model(with_encoder=True)
		columnNames = ["MPG","Cylinders","Displacement","Horsepower","Weight","Accleration","Model Year","Origin"]
		rawDataset = pd.read_csv('http://archive.ics.uci.edu/ml/machine-learning-databases/auto-mpg/auto-mpg.data', names=columnNames, na_values="?",comment="\t",sep=" ",skipinitialspace=True)
		X = rawDataset.copy()
		if row_count is not None:
			X = X.head(row_count)
		X['MPG'] = LabelEncoder().fit_transform(X['MPG'])
		y = X.pop('MPG')
		y = y.astype('float64')
		
		if with_dask:
			X = self.mpg_data_set.copy()
			y = X.pop('MPG')
		
		X_train, X_test, y_train, y_test = \
		dex.train_test_split(X, y, test_size=0.3, random_state=9527)
		X_train, X_eval, y_train, y_eval = \
		dex.train_test_split(X_train, y_train, test_size=0.3, random_state=9527)

		init_kwargs = {
			'X_eval': X_eval, 'y_eval': y_eval, 'X_test': X_test,
			**init_kwargs
		}

		compete_experiment = CompeteExperiment(hyper_model, X_train, y_train, **init_kwargs)
		base_experiment = Experiment(hyper_model, X_train, y_train, **init_kwargs)

		mydict_compete = compete_experiment.get_data_character()
		mydict_base = base_experiment.get_data_character()

		assert mydict_base
		assert mydict_compete
		assert mydict_base['experimentType'] is 'base'
		assert mydict_compete['experimentType'] is 'compete'
		assert mydict_base['target']['taskType'] is 'regression'
		assert mydict_base['target']['freq'] is None
		assert mydict_base['target']['unique']
		assert mydict_base['target']['mean'] is not None
		assert mydict_base['target']['max'] is not None
		assert mydict_base['target']['min'] is not None
		assert mydict_base['target']['stdev'] is not None
		assert mydict_base['target']['dataType'] is 'float'
		assert len(mydict_base['targetDistribution']) <= 10
		assert mydict_base['datasetShape']['X_train']
		assert mydict_base['datasetShape']['y_train']
		assert mydict_base['datasetShape']['X_eval']
		assert mydict_base['datasetShape']['y_eval']
		assert mydict_base['datasetShape']['X_test']
		assert mydict_compete['featureDistribution']

	def test_multiclass_with_bike_sharing(self):
		self.experiment_with_bike_sharing({}, {})
		self.experiment_with_bike_sharing({}, {}, with_dask = True)
	
	def test_binary_with_load_blood(self):
		self.experiment_with_load_blood({}, {})
		self.experiment_with_load_blood({}, {}, with_dask = True)

	def test_regression_with_mpg_data_set(self):
		self.experiment_with_mpg_data_set({}, {})
		self.experiment_with_mpg_data_set({}, {}, with_dask = True)
