# Copyright 2022 The KerasCV Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import tensorflow as tf

import keras_cv
from keras_cv.layers.preprocessing.mosaic import Mosaic

classes = 10


class MosaicTest(tf.test.TestCase):
    def DISABLED_test_integration_retina_net(self):
        train_ds, train_dataset_info = keras_cv.datasets.pascal_voc.load(
            bounding_box_format="xywh", split="train", batch_size=9
        )
        mosaic = keras_cv.layers.Mosaic(bounding_box_format="xywh")
        train_ds = train_ds.map(mosaic, num_parallel_calls=tf.data.AUTOTUNE)
        train_ds = train_ds.map(
            lambda inputs: (inputs["images"], inputs["bounding_boxes"]),
            num_parallel_calls=tf.data.AUTOTUNE,
        )
        model = keras_cv.models.RetinaNet(
            classes=20,
            bounding_box_format="xywh",
            backbone="resnet50",
            backbone_weights="imagenet",
            include_rescaling=True,
            evaluate_train_time_metrics=False,
        )
        model.backbone.trainable = False
        optimizer = tf.optimizers.SGD(global_clipnorm=10.0)
        model.compile(
            run_eagerly=True,
            classification_loss=keras_cv.losses.FocalLoss(
                from_logits=True, reduction="none"
            ),
            box_loss=keras_cv.losses.SmoothL1Loss(l1_cutoff=1.0, reduction="none"),
            optimizer=optimizer,
        )
        callbacks = [
            tf.keras.callbacks.ReduceLROnPlateau(patience=5),
            tf.keras.callbacks.TerminateOnNaN(),
        ]
        history = model.fit(train_ds, epochs=20, callbacks=callbacks)

        for loss in history.history["loss"]:
            self.assertFalse(tf.math.is_nan(loss))

    def test_return_shapes(self):
        xs = tf.ones((2, 512, 512, 3))
        # randomly sample labels
        ys_labels = tf.random.categorical(tf.math.log([[0.5, 0.5]]), 2)
        ys_labels = tf.squeeze(ys_labels)
        ys_labels = tf.one_hot(ys_labels, classes)

        # randomly sample bounding boxes
        ys_bounding_boxes = tf.random.uniform((2, 3, 5), 0, 1)

        layer = Mosaic(bounding_box_format="xywh")
        # mosaic on labels
        outputs = layer(
            {"images": xs, "labels": ys_labels, "bounding_boxes": ys_bounding_boxes}
        )
        xs, ys_labels, ys_bounding_boxes = (
            outputs["images"],
            outputs["labels"],
            outputs["bounding_boxes"],
        )

        self.assertEqual(xs.shape, [2, 512, 512, 3])
        self.assertEqual(ys_labels.shape, [2, 10])
        self.assertEqual(ys_bounding_boxes.shape, [2, 12, 5])

    def test_in_tf_function(self):
        xs = tf.cast(
            tf.stack(
                [2 * tf.ones((4, 4, 3)), tf.ones((4, 4, 3))],
                axis=0,
            ),
            tf.float32,
        )
        ys = tf.one_hot(tf.constant([0, 1]), 2)

        layer = Mosaic()

        @tf.function
        def augment(x, y):
            return layer({"images": x, "labels": y})

        outputs = augment(xs, ys)
        xs, ys = outputs["images"], outputs["labels"]

        self.assertEqual(xs.shape, [2, 4, 4, 3])
        self.assertEqual(ys.shape, [2, 2])

    def test_image_input_only(self):
        xs = tf.cast(
            tf.stack([2 * tf.ones((100, 100, 1)), tf.ones((100, 100, 1))], axis=0),
            tf.float32,
        )
        layer = Mosaic()
        with self.assertRaisesRegexp(ValueError, "expects inputs in a dictionary"):
            _ = layer(xs)

    def test_single_image_input(self):
        xs = tf.ones((512, 512, 3))
        ys = tf.one_hot(tf.constant([1]), 2)
        inputs = {"images": xs, "labels": ys}
        layer = Mosaic()
        with self.assertRaisesRegexp(
            ValueError, "Mosaic received a single image to `call`"
        ):
            _ = layer(inputs)

    def test_int_labels(self):
        xs = tf.ones((2, 512, 512, 3))
        ys = tf.one_hot(tf.constant([1, 0]), 2, dtype=tf.int32)
        inputs = {"images": xs, "labels": ys}
        layer = Mosaic()
        with self.assertRaisesRegexp(ValueError, "Mosaic received labels with type"):
            _ = layer(inputs)

    def test_image_input(self):
        xs = tf.ones((2, 512, 512, 3))
        layer = Mosaic()
        with self.assertRaisesRegexp(
            ValueError, "Mosaic expects inputs in a dictionary with format"
        ):
            _ = layer(xs)
