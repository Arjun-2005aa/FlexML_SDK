# Playbook: TensorFlow / Keras → FlexML

coremltools converts Keras models and SavedModels directly. TensorFlow is **NHWC**, so give the input shape as `(1, H, W, 3)`.

```bash
pip install tensorflow coremltools pillow numpy "flexml-companion[check] @ git+https://github.com/Arjun-2005aa/FlexML_SDK.git#subdirectory=python"
```

**TFLite (`.tflite`) can't be converted.** Ask the user for the original Keras model or SavedModel.

## Classification (Keras applications or your own)
```python
import tensorflow as tf, coremltools as ct
model = tf.keras.applications.MobileNetV3Small(weights="imagenet", include_preprocessing=True)
# With include_preprocessing=True the model expects 0–255 pixels: no scale/bias needed.
labels = [...]   # index-ordered class names
ml = ct.convert(model,
                inputs=[ct.ImageType(name="image", shape=(1, 224, 224, 3), color_layout=ct.colorlayout.RGB)],
                classifier_config=ct.ClassifierConfig(labels),
                minimum_deployment_target=ct.target.iOS17)
ml.save("flexml_export/MobileNetV3.mlpackage")
```

**Common preprocessing, as ImageType settings:**

| Model expects | `scale` | `bias` |
|---|---|---|
| 0–255 (layers inside the model) | 1 | `[0, 0, 0]` |
| 0–1 | `1/255` | `[0, 0, 0]` |
| −1..1 (`tf.keras.applications.mobilenet_v2.preprocess_input`) | `2/255` | `[-1, -1, -1]` |
| Caffe-style BGR minus mean (`resnet50.preprocess_input`) | 1 | `[-103.939, -116.779, -123.68]` with `color_layout=BGR` |

## Segmentation
Add an argmax at the end so the output is `[H, W]` Int32:
```python
inp = tf.keras.Input((512, 512, 3))
logits = seg_model(inp)                                        # [1, H, W, C]
classes = tf.cast(tf.argmax(logits, axis=-1)[0], tf.int32)     # [H, W]
wrapped = tf.keras.Model(inp, classes)
ml = ct.convert(wrapped, inputs=[ct.ImageType(name="image", shape=(1, 512, 512, 3), scale=1/255, bias=[0, 0, 0])],
                minimum_deployment_target=ct.target.iOS17)
ml.user_defined_metadata["names"] = str(dict(enumerate(LABELS)))
```

## Depth
Make the output `[1, H, W]` (squeeze the channel axis) and check that `flexml check-model` reports `depth`.

## Detection
For TF Object Detection API models, prefer exporting a YOLO-style head (`[1, 4+C, N]`, cx, cy, w, h in pixels) or retraining with Ultralytics. Post-processing with dynamic shapes doesn't convert. See the PyTorch playbook's detection section for the layout.

## Validate and compare
`flexml check-model flexml_export/<Name>.mlpackage --image samples/x.jpg`, then parity against `model.predict` on the same resized images (AGENTS.md §6).
