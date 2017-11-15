"""
Copyright 2017-2018 Fizyr (https://fizyr.com)

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import argparse
import os

import keras
import keras.preprocessing.image

import tensorflow as tf

from keras_retinanet.models import ResNet50RetinaNet, MobilenetRetinaNet
from keras_retinanet.preprocessing.coco import CocoGenerator
import keras_retinanet


def get_session():
    config = tf.ConfigProto()
    config.gpu_options.allow_growth = True
    return tf.Session(config=config)


def create_model(architecture, weights='imagenet'):
    image = keras.layers.Input((None, None, 3))
    if architecture == 'mobilenet':
        return MobilenetRetinaNet(image, num_classes=80, weights=weights)
    elif architecture == 'resnet50':
        return ResNet50RetinaNet(image, num_classes=80, weights=weights)
    else:
        raise ValueError('Unknown architecture')

def parse_args():
    parser = argparse.ArgumentParser(description='Simple training script for COCO object detection.')
    parser.add_argument('coco_path', help='Path to COCO directory (ie. /tmp/COCO).')
    parser.add_argument('--weights', help='Weights to use for initialization (defaults to ImageNet).', default='imagenet')
    parser.add_argument('--batch-size', help='Size of the batches.', default=1, type=int)
    parser.add_argument('--gpu', help='Id of the GPU to use (as reported by nvidia-smi).')
    parser.add_argument('--arch', help='Architecture to use (currently supports mobilenet or resnet50).', default='resnet50')


    return parser.parse_args()

if __name__ == '__main__':
    # parse arguments
    args = parse_args()

    # optionally choose specific GPU
    if args.gpu:
        os.environ['CUDA_VISIBLE_DEVICES'] = args.gpu
    keras.backend.tensorflow_backend.set_session(get_session())

    # create the model
    print('Creating model, this may take a second...')
    model = create_model(architecture=args.arch, weights=args.weights)

    # compile model (note: set loss to None since loss is added inside layer)
    model.compile(
        loss={
            'regression'    : keras_retinanet.losses.smooth_l1(),
            'classification': keras_retinanet.losses.focal()
        },
        optimizer=keras.optimizers.adam(lr=1e-5, clipnorm=0.001)
    )

    # print model summary
    print(model.summary())

    # create image data generator objects
    train_image_data_generator = keras.preprocessing.image.ImageDataGenerator(
        horizontal_flip=True,
    )
    test_image_data_generator = keras.preprocessing.image.ImageDataGenerator()

    # create a generator for training data
    train_generator = CocoGenerator(
        args.coco_path,
        'train2017',
        filter_empty_images=True,
        group_method='random',
        image_data_generator=train_image_data_generator,
        batch_size=args.batch_size,
    )

    # create a generator for testing data
    test_generator = CocoGenerator(
        args.coco_path,
        'val2017',
        filter_empty_images=True,
        image_data_generator=test_image_data_generator,
        batch_size=args.batch_size,
    )


    # start training
    model.fit_generator(
        generator=train_generator,
        steps_per_epoch=len(train_generator.image_ids) // args.batch_size,
        epochs=20,
        verbose=1,
        max_queue_size=20,
        validation_data=test_generator,
        validation_steps=len(test_generator.image_ids) // args.batch_size,
        callbacks=[
            keras.callbacks.ModelCheckpoint('snapshots/resnet50_coco_best.h5', monitor='loss', verbose=1, save_best_only=True),
            keras.callbacks.ReduceLROnPlateau(monitor='loss', factor=0.1, patience=2, verbose=1, mode='auto', epsilon=0.0001, cooldown=0, min_lr=0),
        ],
    )

    # store final result too
    model.save('snapshots/resnet50_coco_final.h5')
