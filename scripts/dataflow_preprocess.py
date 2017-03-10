# Copyright 2016 Google Inc. All Rights Reserved.
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
"""Example dataflow pipeline for preparing image training data.
"""
import argparse
import csv
import datetime
import io
import logging
import os
import subprocess
import sys
import numpy as np

sys.setrecursionlimit(10000)

import apache_beam as beam
from apache_beam.metrics import Metrics
try:
  from apache_beam.utils.pipeline_options import PipelineOptions
except ImportError:
  from apache_beam.utils.options import PipelineOptions

from google.cloud.ml.io import SaveFeatures
import vgg16bn

def configure_pipeline(p, opt):
  """Specify PCollection and transformations in pipeline."""
  read_input_source = beam.io.ReadFromText(
      opt.input_path, strip_trailing_newlines=True)
  labels = (p | 'Read dictionary' >> read_input_source)
  vgg = build_vgg(size=(opt.size_y, opt.size_x))
  _ = (p
       | 'Read input' >> read_input_source
       | 'Process images' >> beam.ParDo(ProcessImages(), size=(opt.size_y, opt.size_x))
       | 'Compute features' >> beam.ParDo(ComputeFeatures(),
                                          vgg)
       #| 'save' >> beam.io.WriteToText('./test')) 
       | 'save' >> SaveFeatures(opt.output_path)) 


def build_vgg(size):
  "Loads pre-built VGG model up to last convolutional layer"""
  return vgg16bn.Vgg16BN(include_top=False, size=size)

        
class ProcessImages(beam.DoFn):
  from keras.preprocessing import image
  def process(self, element, size):
    x = image.img_to_array(image.load_img(element, target_size=size))
    x = self.image_data_generator.random_transform(x)
    x = self.image_data_generator.standardize(x)
                        
class ComputeFeatures(beam.DoFn):
  def process(self, element, vgg):
    yield vgg.predict(np.expand_dims(element, axis=0))

  
def save_features(data):
  features = data
  dl_utils.save_array("cnn_features.dat", features)


def run(in_args=None):
  """Runs the pre-processing pipeline."""
  pipeline_options = PipelineOptions.from_dictionary(vars(in_args))
  with beam.Pipeline(options=pipeline_options) as p:
    configure_pipeline(p, in_args)

  
def default_args(argv):
  """Provides default values for Workflow flags."""
  parser = argparse.ArgumentParser()

  parser.add_argument(
      '--input_path',
      required=True,
      help='Input specified as uri to CSV file. Each line of csv file '
      'contains colon-separated GCS uri to an image and labels.')
  parser.add_argument(
      '--output_path',
      required=True,
      help='Output directory to write results to.')
  parser.add_argument(
      '--size_x',
      dest='size_x',
      default=640,
      help='Target image X size in pixels')
  parser.add_argument(
      '--size_y',
      dest='size_y',
      default=360,
      help='Target image Y size in pixels')
  parser.add_argument(
      '--project',
      type=str,
      help='The cloud project name to be used for running this pipeline')

  parser.add_argument(
      '--job_name',
      type=str,
      default='flowers-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S'),
      help='A unique job identifier.')
  parser.add_argument(
      '--num_workers', default=20, type=int, help='The number of workers.')
  parser.add_argument('--cloud', default=False, action='store_true')
  parser.add_argument(
      '--runner',
      help='See Dataflow runners, may be blocking'
      ' or not, on cloud or not, etc.')

  parsed_args, _ = parser.parse_known_args(argv)

  if parsed_args.cloud:
    # Flags which need to be set for cloud runs.
    default_values = {
        'project':
            get_cloud_project(),
        'temp_location':
            os.path.join(os.path.dirname(parsed_args.output_path), 'temp'),
        'runner':
            'DataflowRunner',
        'extra_package':
            Default.CML_PACKAGE,
        'save_main_session':
            True,
    }
  else:
    # Flags which need to be set for local runs.
    default_values = {
        'runner': 'DirectRunner',
    }

  for kk, vv in default_values.iteritems():
    if kk not in parsed_args or not vars(parsed_args)[kk]:
      vars(parsed_args)[kk] = vv

  return parsed_args


def main(argv):
  arg_dict = default_args(argv)
  run(arg_dict)


if __name__ == '__main__':
  main(sys.argv[1:])