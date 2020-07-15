# -*- coding:utf-8 -*-
"""

"""

from hypernets.core.search_space import *
from hypernets.core.ops import *
from hypernets.frameworks.ml.preprocessing import Pipeline, SimpleImputer, StandardScaler, ColumnTransformer
import pytest
from sklearn import pipeline
from sklearn import preprocessing

ids = []


def get_id(m):
    ids.append(m.id)
    return True


def tow_inputs():
    s1 = SimpleImputer()
    s2 = SimpleImputer()
    s3 = StandardScaler()([s1, s2])
    return s3


def tow_outputs():
    s1 = SimpleImputer()
    s2 = SimpleImputer()(s1)
    s3 = StandardScaler()(s1)
    return s2


def get_space():
    space = HyperSpace()
    with space.as_default():
        Pipeline([SimpleImputer(), StandardScaler()])
    return space


def get_space_2inputs():
    space = HyperSpace()
    with space.as_default():
        Pipeline([tow_inputs(), StandardScaler()])
    return space


def get_space_2outputs():
    space = HyperSpace()
    with space.as_default():
        Pipeline([tow_outputs()])
    return space


def get_space_p_in_p():
    space = HyperSpace()
    with space.as_default():
        p1 = Pipeline([SimpleImputer(name='imputer1'), StandardScaler(name='scaler1')], name='p1')
        p2 = Pipeline([SimpleImputer(name='imputer2'), StandardScaler(name='scaler2')], name='p2')
        input = HyperInput(name='input1')
        p3 = Pipeline([p1, p2], name='p3')(input)
        space.set_inputs(input)
    return space


def get_space_column_transformer():
    space = HyperSpace()
    with space.as_default():
        input = HyperInput(name='input1')
        p1 = Pipeline([SimpleImputer(name='imputer1'), StandardScaler(name='scaler1')], columns=['a', 'b', 'c'],
                      name='p1')(input)
        p2 = Pipeline([SimpleImputer(name='imputer2'), StandardScaler(name='scaler2')], columns=['c', 'd'], name='p2')(
            input)
        p3 = ColumnTransformer()([p1, p2])
        space.set_inputs(input)
    return space


class Test_HyperGBM:

    def test_pipeline(self):
        global ids
        space = get_space()
        space.random_sample()

        ids = []
        space.traverse(get_id)
        assert ids == ['ID_Module_Pipeline_1_input', 'Module_SimpleImputer_1', 'Module_StandardScaler_1',
                       'ID_Module_Pipeline_1_output']
        assert space.ID_Module_Pipeline_1_input.output_id == 'ID_Module_Pipeline_1_output'
        assert space.ID_Module_Pipeline_1_output.input_id == 'ID_Module_Pipeline_1_input'

        with pytest.raises(AssertionError) as e:
            space = get_space_2inputs()
            space.random_sample()
            ids = []
            space.traverse(get_id)

        with pytest.raises(AssertionError) as e:
            space = get_space_2outputs()
            space.random_sample()
            ids = []
            space.traverse(get_id)

    def test_pipeline_compose(self):
        space = get_space_p_in_p()
        space.random_sample()
        space = space.compile_space()
        global ids
        ids = []
        space.traverse(get_id)
        assert ids == ['ID_input1', 'ID_p3_input', 'ID_p1_input', 'ID_imputer1', 'ID_scaler1', 'ID_p1_output',
                       'ID_p2_input', 'ID_imputer2', 'ID_scaler2', 'ID_p2_output', 'ID_p3_output']

        _, (_, p) = space.ID_p3_output.compose()
        assert len(p.steps) == 2
        assert p.steps[0][1].__class__ == pipeline.Pipeline
        assert len(p.steps[0][1].steps) == 2
        assert p.steps[0][1].steps[1][1].__class__ == preprocessing.StandardScaler

    def test_column_transformer_compose(self):
        space = get_space_column_transformer()
        space.random_sample()
        space = space.compile_space()
        global ids
        ids = []
        space.traverse(get_id)
        assert ids == ['ID_input1', 'ID_p1_input', 'ID_p2_input', 'ID_imputer1', 'ID_imputer2', 'ID_scaler1',
                       'ID_scaler2', 'ID_p1_output', 'ID_p2_output', 'Module_ColumnTransformer_1']

        next, (name, p) = space.Module_ColumnTransformer_1.compose()
        assert len(p.transformers) == 2
        assert p.transformers[0][0] == 'p1'
        assert p.transformers[0][1].__class__ == pipeline.Pipeline
        assert p.transformers[0][2] == ['a', 'b', 'c']

        assert p.transformers[1][0] == 'p2'
        assert p.transformers[1][1].__class__ == pipeline.Pipeline
        assert p.transformers[1][2] == ['c', 'd']

        assert len(p.transformers[0][1].steps) == 2
        assert p.transformers[0][1].steps[1][1].__class__ == preprocessing.StandardScaler
