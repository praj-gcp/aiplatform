# Copyright 2019 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""KFP pipeline orchestrating BigQuery and Cloud AI Platform services."""

import os

from helper_components import evaluate_model
from helper_components import retrieve_best_run
from jinja2 import Template
import kfp
from kfp.components import func_to_container_op
from kfp.dsl.types import Dict
from kfp.dsl.types import GCPProjectID
from kfp.dsl.types import GCPRegion
from kfp.dsl.types import GCSPath
from kfp.dsl.types import String
from kfp.gcp import use_gcp_secret

# Defaults and environment settings
BASE_IMAGE = os.getenv('BASE_IMAGE')
TRAINER_IMAGE = os.getenv('TRAINER_IMAGE')
RUNTIME_VERSION = os.getenv('RUNTIME_VERSION')
PYTHON_VERSION = os.getenv('PYTHON_VERSION')
COMPONENT_URL_SEARCH_PREFIX = os.getenv('COMPONENT_URL_SEARCH_PREFIX')
USE_KFP_SA = os.getenv('USE_KFP_SA')
TRAINING_FILE_PATH = 'gs://input_data_amy_bkt1/Anonymized_Fermentation_Data_final.xlsx'
INPUT_FILE = 'gs://input_data_amy_bkt1/Anonymized_Fermentation_Data_final.xlsx'
TRAINING_FILE_DIR = 'gs://workshop_trial_artifact_store_pp/data/training'
TESTING_FILE_DIR = 'gs://workshop_trial_artifact_store_pp/data/testing'
VALIDATION_FILE_DIR = 'gs://workshop_trial_artifact_store_pp/data/validation'


TESTING_FILE_PATH = 'gs://workshop_trial_artifact_store_pp/data/testing/X_test.csv'
# VALIDATION_FILE_PATH = 'datasets/validation/data.csv'
# TESTING_FILE_PATH = 'datasets/testing/data.csv'

# Parameter defaults
# SPLITS_DATASET_ID = 'splits'
HYPERTUNE_SETTINGS = """
{
    "hyperparameters":  {
        "goal": "MAXIMIZE",
        "maxTrials": 3,
        "maxParallelTrials": 3,
        "hyperparameterMetricTag": "accuracy",
        "enableTrialEarlyStopping": True,
        "algorithm": "RANDOM_SEARCH",
        "params": [
            {
                "parameterName": "n_estimators",
                "type": "INTEGER",
                "minValue": 10,
                "maxValue": 200,
                "scaleType": "UNIT_LINEAR_SCALE"
            },
            {
                "parameterName": "max_leaf_nodes",
                "type": "INTEGER",
                "minValue": 10,
                "maxValue": 500,
                "scaleType": "UNIT_LINEAR_SCALE"
            },
            {
                "parameterName": "max_depth",
                "type": "INTEGER",
                "minValue": 3,
                "maxValue": 20,
                "scaleType": "UNIT_LINEAR_SCALE"
            },
            {
                "parameterName": "min_samples_split",
                "type": "DISCRETE",
                "discreteValues": [2,5,10]
            },
            {
                "parameterName": "min_samples_leaf",
                "type": "INTEGER",
                "minValue": 10,
                "maxValue": 500,
                "scaleType": "UNIT_LINEAR_SCALE"
            },
            {
                "parameterName": "max_features",
                "type": "DOUBLE",
                "minValue": 0.5,
                "maxValue": 1.0,
                "scaleType": "UNIT_LINEAR_SCALE"
            },    
            {
                "parameterName": "class_weight",
                "type": "CATEGORICAL",
                "categoricalValues": [
                              "balanced",
                              "balanced_subsample"
                          ]
            },  

             {
                "parameterName": "random_state",
                "type": "INTEGER",
                "minValue": 35,
                "maxValue": 75,
                "scaleType": "UNIT_LINEAR_SCALE"
            },
            {
                "parameterName": "bootstrap",
                "type": "CATEGORICAL",
                "categoricalValues": [
                              "TRUE",
                              "FALSE"
                          ]
            } 
        ]
    }
}
"""

# # Helper functions
# def generate_sampling_query(source_table_name, num_lots, lots):
#     """Prepares the data sampling query."""

#     sampling_query_template = """
#          SELECT *
#          FROM 
#              `{{ source_table }}` AS cover
#          WHERE 
#          MOD(ABS(FARM_FINGERPRINT(TO_JSON_STRING(cover))), {{ num_lots }}) IN ({{ lots }})
#          """
#     query = Template(sampling_query_template).render(
#         source_table=source_table_name, num_lots=num_lots, lots=str(lots)[1:-1])

#     return query


# Create component factories
component_store = kfp.components.ComponentStore(
    local_search_paths=None, url_search_prefixes=[COMPONENT_URL_SEARCH_PREFIX])

# bigquery_query_op = component_store.load_component('bigquery/query')
mlengine_train_op = component_store.load_component('ml_engine/train')
mlengine_deploy_op = component_store.load_component('ml_engine/deploy')
retrieve_best_run_op = func_to_container_op(
    retrieve_best_run, base_image=BASE_IMAGE)
evaluate_model_op = func_to_container_op(evaluate_model, base_image=BASE_IMAGE)


@kfp.dsl.pipeline(
    name='Amyris Classifier Training',
    description='The pipeline training and deploying the Amyris classifierpipeline_yaml'
)
def amyris_train(project_id,
                    region,
                    gcs_root,
                    evaluation_metric_name,
                    evaluation_metric_threshold,
                    model_id,
                    version_id,
                    replace_existing_version,
                    hypertune_settings=HYPERTUNE_SETTINGS,
                    dataset_location='US'):
    """Orchestrates training and deployment of an sklearn model."""

    # Create the training split
#     query = generate_sampling_query(
#         source_table_name=source_table_name, num_lots=10, lots=[1, 2, 3, 4])

#     training_file_path = '{}/{}'.format(gcs_root, TRAINING_FILE_PATH)

#     create_training_split = bigquery_query_op(
#         query=query,
#         project_id=project_id,
#         dataset_id=dataset_id,
#         table_id='',
#         output_gcs_path=training_file_path,
#         dataset_location=dataset_location)

#     # Create the validation split
#     query = generate_sampling_query(
#         source_table_name=source_table_name, num_lots=10, lots=[8])

#     validation_file_path = '{}/{}'.format(gcs_root, VALIDATION_FILE_PATH)

#     create_validation_split = bigquery_query_op(
#         query=query,
#         project_id=project_id,
#         dataset_id=dataset_id,
#         table_id='',
#         output_gcs_path=validation_file_path,
#         dataset_location=dataset_location)

    # Create the testing split
#     query = generate_sampling_query(
#         source_table_name=source_table_name, num_lots=10, lots=[9])

#     testing_file_path = '{}/{}'.format(gcs_root, TESTING_FILE_PATH)

#     create_testing_split = bigquery_query_op(
#         query=query,
#         project_id=project_id,
#         dataset_id=dataset_id,
#         table_id='',
#         output_gcs_path=testing_file_path,
#         dataset_location=dataset_location)

    # Tune hyperparameters
    tune_args = [
        #'--training_dataset_path',
       # TRAINING_FILE_PATH,
        '--training_dataset', TRAINING_FILE_DIR,
        '--validation_dataset', VALIDATION_FILE_DIR,
        '--testing_dataset', TESTING_FILE_DIR, 
        '--input_file', INPUT_FILE, 
        '--hptune', 'True'
    ]

    job_dir = '{}/{}/{}'.format(gcs_root, 'jobdir/hypertune',
                                kfp.dsl.RUN_ID_PLACEHOLDER)

    hypertune = mlengine_train_op(
        project_id=project_id,
        region=region,
        master_image_uri='gcr.io/etl-project-datahub/trainer_image:latest',
        job_dir=job_dir,
        args=tune_args,
        training_input=hypertune_settings)

    # Retrieve the best trial
    get_best_trial = retrieve_best_run_op(
            project_id, hypertune.outputs['job_id'])

    # Train the model on a combined training and validation datasets
    job_dir = '{}/{}/{}'.format(gcs_root, 'jobdir', kfp.dsl.RUN_ID_PLACEHOLDER)

    train_args = [
       # '--training_dataset_path',
       #TRAINING_FILE_PATH,
        '--training_dataset', TRAINING_FILE_DIR,
        '--validation_dataset', VALIDATION_FILE_DIR,
        '--testing_dataset',  TESTING_FILE_DIR, 
        '--input_file', INPUT_FILE, 
        '--n_estimators',get_best_trial.outputs['n_estimators'], 
        '--max_leaf_nodes',get_best_trial.outputs['max_leaf_nodes'], 
        '--max_depth',get_best_trial.outputs['max_depth'],
        '--min_samples_split',get_best_trial.outputs['min_samples_split'],
        '--bootstrap' ,get_best_trial.outputs['bootstrap'],
        '--random_state' ,get_best_trial.outputs['random_state'],
        '--max_features' ,get_best_trial.outputs['max_features'],
        '--class_weight' ,get_best_trial.outputs['class_weight'],
        '--min_samples_leaf',get_best_trial.outputs['min_samples_leaf'],
        '--hptune', 'False'
    ]

    train_model = mlengine_train_op(
        project_id=project_id,
        region=region,
        master_image_uri='gcr.io/etl-project-datahub/trainer_image:latest',
        job_dir=job_dir,
        args=train_args)

    # Evaluate the model on the testing split
    eval_model = evaluate_model_op(
        dataset_path=TESTING_FILE_PATH,
        model_path=str(train_model.outputs['job_dir']),
        metric_name=evaluation_metric_name)

    # Deploy the model if the primary metric is better than threshold
    with kfp.dsl.Condition(eval_model.outputs['metric_value'] > evaluation_metric_threshold):
        deploy_model = mlengine_deploy_op(
        model_uri=train_model.outputs['job_dir'],
        project_id=project_id,
        model_id=model_id,
        version_id=version_id,
        runtime_version=RUNTIME_VERSION,
        python_version=PYTHON_VERSION,
        replace_existing_version=replace_existing_version)

    # Configure the pipeline to run using the service account defined
      # in the user-gcp-sa k8s secret
    if USE_KFP_SA == 'True':
        kfp.dsl.get_pipeline_conf().add_op_transformer(
              use_gcp_secret('user-gcp-sa'))
