# Bring Your Own Model

FlexML runs Core ML models (`.mlmodel`, `.mlpackage` or `.mlmodelc`) that take an **image** as input. It works out what the model does from its outputs and draws the results. You can check and correct this in the model's details (the ⓘ button in **Change Model**).

## Supported tasks

| Task | What FlexML recognises | Shown as |
|---|---|---|
| Object detection | Core ML detector pipelines (`confidence` + `coordinates`, e.g. Create ML, Ultralytics with `nms=True`); raw YOLOv5/v7 `[1, N, 5+C]`, YOLOv8/v9/v11 `[1, 4+C, N]`, NMS-free YOLOv10/26 `[1, N, 6]` | Tracked boxes, labels, distances in AR |
| Classification | Core ML classifiers, or a vector of scores (softmax applied if needed) | Top-K list |
| Segmentation | Class-index image or `[H, W]` Int32 map, or `[C, H, W]` scores | Coloured mask |
| Depth | Single-channel image or `[1, H, W]` map | Colour depth map |
| Pose / keypoints | YOLOv8/11-pose `[1, 56, N]`, or `[K, H, W]` heatmaps | Skeleton |
| Image to image | Colour image output (style transfer, enhancement) | Output image |
| Anything else | Any outputs | Raw tensor summary (min/max/mean) and JSON |

## Converting models from other frameworks

Apple's official converter is **[coremltools](https://github.com/apple/coremltools)** (`pip install coremltools`, [documentation](https://apple.github.io/coremltools/docs-guides/)). It converts PyTorch (TorchScript or `torch.export`), TensorFlow/Keras, and scikit-learn/XGBoost models, and many Hugging Face models through their PyTorch weights, into `.mlpackage`. For ONNX models, convert from the original PyTorch or TensorFlow model instead (current coremltools no longer imports ONNX).

The two rules that matter most for FlexML:
1. Declare the input as an image: `ct.ImageType(shape=(1, 3, H, W), scale=1/255, color_layout=ct.colorlayout.RGB)`.
2. Store class names in metadata: `mlmodel.user_defined_metadata["names"] = str({0: "person", 1: "robot"})`.

Framework-specific recipes are in the playbooks: [PyTorch](agents/playbooks/pytorch.md), [TensorFlow](agents/playbooks/tensorflow.md), [Hugging Face](agents/playbooks/huggingface.md), [Ultralytics](agents/playbooks/ultralytics.md).

## Let an AI coding agent do it

Copy [`docs/agents/AGENTS.md`](agents/AGENTS.md) (plus [`CLAUDE.md`](https://github.com/Arjun-2005aa/FlexML_SDK/blob/main/docs/agents/CLAUDE.md) for Claude Code) into your model project and ask your agent to *"port my model to FlexML"*. It converts the model, validates it with `flexml check-model`, compares it against your original, and writes a report. See [docs/agents](agents/README.md).

## Check any model before copying it to the phone

```bash
pip install "flexml-companion[check] @ git+https://github.com/Arjun-2005aa/FlexML_SDK.git#subdirectory=python"   # needs macOS for --image
flexml check-model MyModel.mlpackage --image photo.jpg
```
This applies the same rules as the app: what task it will be treated as, input size, labels, problems and fixes.

## The fastest path: ready-made models

- **Apple's model gallery** ([developer.apple.com/machine-learning/models](https://developer.apple.com/machine-learning/models/)): YOLOv3, DeepLabV3, Depth Anything V2, ResNet50, MobileNetV2 and more. They work as downloaded.
- **Create ML** (on a Mac with Xcode): train an Image Classifier or Object Detector on your own photos and export the `.mlmodel`. Labels are included automatically.

## Ultralytics YOLO (recommended for custom detection)

```bash
pip install ultralytics
# Detection with built-in NMS (recommended): FlexML's threshold sliders control it live
yolo export model=yolo11n.pt format=coreml nms=True imgsz=640 half=True
# Or a raw export: FlexML decodes it and runs NMS itself
yolo export model=yolo11n.pt format=coreml imgsz=640 half=True
# Other tasks
yolo export model=yolo11n-pose.pt format=coreml imgsz=640   # keypoints
yolo export model=yolo11n-cls.pt  format=coreml imgsz=224   # classification
yolo export model=yolo11n-seg.pt  format=coreml imgsz=640   # boxes only (masks not drawn yet)
```

For your own data, train first with `yolo train data=your.yaml model=yolo11n.pt`, then export `runs/detect/train/weights/best.pt` the same way. Class names travel in the model's metadata and FlexML reads them.

**Tip:** Ultralytics models are trained on letterboxed images. FlexML defaults to **Fit (letterbox)** for raw YOLO models; check it under Display › Model input.

## PyTorch with coremltools

The important part is declaring the input as an **image** with the right normalisation.

```python
import torch, torchvision
import coremltools as ct

model = torchvision.models.mobilenet_v3_small(weights="DEFAULT").eval()
example = torch.rand(1, 3, 224, 224)
traced = torch.jit.trace(model, example)

# ImageNet normalisation: (pixel/255 - mean) / std  ->  scale = 1/(255*std), bias = -mean/std
mlmodel = ct.convert(
    traced,
    inputs=[ct.ImageType(name="image", shape=example.shape, color_layout=ct.colorlayout.RGB,
                         scale=1 / (255 * 0.226), bias=[-0.485 / 0.229, -0.456 / 0.224, -0.406 / 0.225])],
    classifier_config=ct.ClassifierConfig(class_labels),  # classifiers only: embeds labels
    minimum_deployment_target=ct.target.iOS17,
    compute_precision=ct.precision.FLOAT16,
)
mlmodel.save("MyClassifier.mlpackage")
```

**Labels for non-classifiers** (detection and segmentation) go in metadata, which FlexML reads:

```python
mlmodel.user_defined_metadata["names"] = str({0: "background", 1: "person", 2: "robot"})
# or: mlmodel.user_defined_metadata["classes"] = "background,person,robot"
```

**Rules that matter:**
- **Image input:** FlexML feeds camera frames, so models with a tensor input can't run on the camera. The inspector says so.
- **Fixed input size:** 224–640 px is typical. Flexible shapes run at the default size.
- **One image input:** extra inputs are supported only for detector thresholds (`iouThreshold` and `confidenceThreshold`).

## Getting the model onto the phone

1. Save the model to iCloud Drive or Files, or AirDrop it to the phone.
2. In FlexML: **Change Model › Import a Core ML model**, then pick the file. FlexML compiles it once (a few seconds) and keeps it.
3. Tap ⓘ next to the model to check the **detected task** and **why**, its input size, classes, and inputs/outputs. Change **Task** if the guess is wrong.
4. **Start Inference**, then use **Benchmark** (camera screen) to measure it on the device.

## Making it fast

| Tip | Typical effect |
|---|---|
| Use FP16 (`half=True` / `compute_precision=FLOAT16`) | Runs on the Neural Engine; roughly 2–4× faster than FP32 on CPU or GPU |
| Smaller input (320–416 instead of 640) | Roughly quadratic speed-up, less accuracy on small objects |
| 8-bit palettization: `ct.optimize.coreml.palettize_weights(model, ct.optimize.coreml.OptimizationConfig(global_config=ct.optimize.coreml.OpPalettizerConfig(nbits=8)))` | ~4× smaller file, similar speed, small accuracy cost |
| Keep "Run models on: Automatic" | Core ML picks the Neural Engine when it can |
| Raw YOLO exports | FlexML receives Float16 outputs directly (no conversion), so they cost less CPU than pipelines |

On an iPhone 13 Pro, YOLOv3 Tiny (416²) takes about 6 ms and DeepLabV3 (513²) about 10 ms per frame on the Neural Engine. See `Artifact/release-plan-2026-11/performance_report.md`.

## Troubleshooting

| Symptom | Fix |
|---|---|
| "This model takes numbers, not an image" | Re-export with `ct.ImageType` as the input |
| Wrong task detected | Model details (ⓘ) › Task, pick the right one |
| Boxes in the wrong place | Display › Model input: try **Fit** for YOLO, **Center crop** for classifiers |
| Labels show as "class 12" | Add `names` or `classes` metadata (see above) |
| Very slow | Check Benchmark; export FP16; reduce input size; avoid ops the Neural Engine doesn't support |
| Import fails | Make sure it's a `.mlmodel`, `.mlpackage` or `.mlmodelc`, built with coremltools 7 or newer |
