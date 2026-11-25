# AGENTS.md — Port a model to FlexML

You are helping a user turn their machine-learning model into a **Core ML model that runs well in the FlexML iOS app**. FlexML runs vision models on the live iPhone/iPad camera and streams results to robots. Follow this file exactly; it is self-contained.

> Users: copy this file (and `CLAUDE.md` if you use Claude Code) into the root of your model project, then ask your coding agent: *"Port my model to FlexML."* Detailed playbooks per framework live in the FlexML SDK repository (https://github.com/Arjun-2005aa/FlexML_SDK) under `docs/agents/playbooks/`.

---

## 1. Definition of done

1. A `.mlpackage` in `flexml_export/` that **passes** `flexml check-model` with the task the user expects.
2. A **parity check**: the Core ML model's outputs match the original model on at least 5 real images, within the tolerances in §6.
3. `flexml_export/PORT_REPORT.md` filled in (template in §9), with the exact commands used, the `check-model` output, parity numbers and any caveats.
4. The original model files and training code are **unchanged**.

## 2. FlexML's contract (hard requirements)

- **Input:** exactly **one image input** (`ct.ImageType`) with a **fixed size**, typically 224–640 px. FlexML renders the camera frame into this size (centre crop, letterbox or stretch, chosen per model in the app). The only other inputs allowed are detector thresholds named `iouThreshold` and `confidenceThreshold` (doubles), which FlexML drives from its sliders.
- **Normalisation lives in the model:** use `ImageType(scale=…, bias=…, color_layout=RGB|BGR)`. FlexML passes raw 0–255 pixels.
- **Format:** ML Program (`minimum_deployment_target=ct.target.iOS17`), FP16 compute precision (the default for ML Program), saved as `.mlpackage`.
- **Outputs:** use one of the layouts in §3, so FlexML recognises the task without manual setup.
- **Labels:** classifiers embed them through `ct.ClassifierConfig(labels)`. Every other task stores them in metadata:
  `model.user_defined_metadata["names"] = str({0: "person", 1: "robot", ...})`
  (or `"classes"` as a comma-separated string). Use the same order as the model's class indices.
- **Operators:** use static shapes and avoid ops the Neural Engine can't run where you have a choice. If an op is unsupported by coremltools, rewrite it in plain tensor ops before conversion; never drop it.

## 3. Output layouts FlexML recognises

| Task | Produce this | Notes |
|---|---|---|
| Classification | `ClassifierConfig` (preferred), or one vector of N scores | Softmax is applied by FlexML if the scores aren't probabilities |
| Detection (preferred) | Ultralytics export with `nms=True`, or any Core ML detector pipeline with outputs `confidence` [N,C] and `coordinates` [N,4] (normalised cx, cy, w, h; top-left origin) | Thresholds adjustable live |
| Detection (raw) | `[1, 4+C, N]` (YOLOv8/v11 style: cx, cy, w, h in input pixels, then C class scores), `[1, N, 5+C]` (YOLOv5: plus objectness), or `[1, N, 6]` (x1, y1, x2, y2, score, class) | FlexML decodes and runs NMS; N should be ≥ 1000 for the first two |
| Segmentation | `[H, W]` **Int32** class indices (argmax inside the model, preferred) or `[C, H, W]` scores | Label 0 named `background` is hidden by default |
| Depth | `[1, H, W]` Float, or a grayscale image output named `depth` | Relative depth is fine |
| Pose / keypoints | `[1, 5+3K, N]` (YOLO pose: box, score, K×(x, y, visibility)), or `[K, H, W]` heatmaps (name the output `heatmaps`) | 17 COCO keypoints get a skeleton |
| Image to image | Colour image output (`ct.ImageType` in `outputs=`) | Shown over the camera |

Anything else still runs, but FlexML only shows raw tensor statistics. Avoid that unless the user only needs the numbers streamed.

## 4. Workflow

1. **Inspect** the project: framework, checkpoint files, input size, preprocessing (mean/std, RGB or BGR), number of classes, label names, and output post-processing. Write down what you find before converting.
2. **Pick the path** (see §5): Ultralytics → `yolo export`; PyTorch → trace + `ct.convert`; TensorFlow/Keras → `ct.convert`; Hugging Face → load in PyTorch, then the PyTorch path; ONNX → re-export from the source framework (coremltools no longer converts ONNX).
3. **Set up an isolated environment:** `python -m venv .flexml-venv`, then `pip install coremltools pillow numpy` plus the source framework, and `pip install "flexml-companion[check] @ git+https://github.com/Arjun-2005aa/FlexML_SDK.git#subdirectory=python"` (or, from a local clone of the SDK, `pip install "./FlexML_SDK/python[check]"`).
4. **Wrap the model if needed**, so the graph outputs exactly one of the §3 layouts. Common fixes: return a tensor, not a dict; do argmax for segmentation; move preprocessing into `ImageType`.
5. **Convert** with `minimum_deployment_target=ct.target.iOS17`, add the label metadata, set the metadata (`model.author`, `model.short_description`, `model.version`, `model.license`), and save to `flexml_export/<Name>.mlpackage`.
6. **Validate:** run `flexml check-model flexml_export/<Name>.mlpackage --image <a real image> --json`. Fix every `errors` entry. Fix warnings unless the user agrees they're acceptable. Repeat until `"ok": true` and `"task"` is the expected one.
7. **Parity:** compare against the original model (§6).
8. **Optimise if asked, or if the model is over ~50 MB or the input over 640 px:** FP16 is already on; consider 8-bit palettisation (§7). Re-run steps 6–7 after any change.
9. **Report:** write `PORT_REPORT.md` and tell the user how to import the model on the phone (§8).

## 5. Recipes

**Ultralytics YOLO (v5u, v8, v9, v10, v11, 26):**
```bash
yolo export model=best.pt format=coreml nms=True imgsz=640 half=True    # detection (recommended)
yolo export model=best.pt format=coreml imgsz=640 half=True             # raw output alternative
yolo export model=best-pose.pt format=coreml imgsz=640                  # pose
yolo export model=best-cls.pt format=coreml imgsz=224                   # classification
```
Class names are embedded automatically. Move the result into `flexml_export/`.

**PyTorch:**
```python
import torch, coremltools as ct
model = load_user_model().eval()                      # however the project builds it
class Wrapped(torch.nn.Module):                       # make the output match §3
    def __init__(self, m): super().__init__(); self.m = m
    def forward(self, x): return self.m(x)            # e.g. ["out"].argmax(1).int() for segmentation
example = torch.rand(1, 3, H, W)
traced = torch.jit.trace(Wrapped(model), example)
mean, std = (0.485, 0.456, 0.406), (0.229, 0.224, 0.225)   # use the project's real values
mlmodel = ct.convert(
    traced,
    inputs=[ct.ImageType(name="image", shape=example.shape, color_layout=ct.colorlayout.RGB,
                         scale=1 / (255 * sum(std) / 3), bias=[-m / s for m, s in zip(mean, std)])],
    classifier_config=ct.ClassifierConfig(labels) if IS_CLASSIFIER else None,
    minimum_deployment_target=ct.target.iOS17,
)
```
Core ML's `scale` is one number for all channels, so use the mean of the stds and per-channel `bias`. That's an exact match when the stds are equal and a close approximation otherwise; mention it in the report. Models normalised to 0–1 use `scale=1/255, bias=[0,0,0]`; models expecting −1..1 use `scale=2/255, bias=[-1,-1,-1]`.

**TensorFlow / Keras:** `ct.convert(keras_model, inputs=[ct.ImageType(shape=(1, H, W, 3), scale=…, bias=…)], minimum_deployment_target=ct.target.iOS17)`. TensorFlow is NHWC, so give the input shape in that order.

**Hugging Face:** load the model with `transformers` in PyTorch (`torchscript=True` where supported), wrap it to return a plain tensor (e.g. `logits`, or `predicted_depth` for depth), then follow the PyTorch recipe. Take labels from `model.config.id2label`.

**ONNX only:** ask the user for the original framework's checkpoint and use that path. If none exists, try `onnx2torch` to get a PyTorch module, then trace it. Tell the user this route is less reliable.

## 6. Parity check

Run the original model and the Core ML model (`mlmodel.predict({"image": PIL_image})`, macOS) on 5–20 real images, using the **same resized input** for both. Pass when:
- **Classification:** top-1 agrees on all images, and top-5 overlaps on ≥ 80%.
- **Detection:** for each original box with confidence ≥ 0.3 there's a Core ML box of the same class with IoU ≥ 0.9, and the counts agree within ±1.
- **Segmentation:** ≥ 98% of pixels have the same class.
- **Depth / other dense outputs:** Pearson correlation ≥ 0.99, or relative L1 ≤ 2%.

FP16 explains small differences. If parity fails, check preprocessing (RGB vs BGR, mean/std, resize method) before anything else.

## 7. Optimisation (only with re-validation)

```python
import coremltools.optimize.coreml as cto
config = cto.OptimizationConfig(global_config=cto.OpPalettizerConfig(nbits=8))
small = cto.palettize_weights(mlmodel, config)       # about 4x smaller; re-run parity
```
Smaller inputs (e.g. 416 instead of 640) speed things up roughly quadratically. Recommend this only if the user's objects aren't tiny. Never change the architecture or retrain unless the user asks.

## 8. Getting it onto the phone (tell the user)

1. AirDrop `flexml_export/<Name>.mlpackage` to the iPhone, or save it to iCloud Drive.
2. In FlexML: **Change Model › Import a Core ML model**, then pick the file.
3. Tap ⓘ to check that the detected **Task** matches; under **Display › Model input**, use **Fit** for YOLO-style models and **Center crop** for classifiers.
4. **Start Inference**, then use **Benchmark** to measure speed on the device.

## 9. PORT_REPORT.md template

```markdown
# FlexML port report: <model name>
- Source: <framework, checkpoint path, commit/version>
- Output: flexml_export/<Name>.mlpackage (<size> MB), task: <task>, input <W×H>, labels: <count>
- Preprocessing baked in: color_layout=<RGB/BGR>, scale=<…>, bias=<…>
- Conversion command / script: <exact command or path to script>
- `flexml check-model` result: <PASS/FAIL, paste the summary lines>
- Parity on <N> images: <metric values vs thresholds>
- Optimisations: <none / FP16 / palettised 8-bit>, effect on parity: <…>
- Caveats: <approximations, unsupported parts, anything the user should know>
- Next step on the phone: import, check Task in ⓘ, set Model input to <Fit/Center crop>
```

## 10. Guardrails

- **Ask first** before downloading datasets or weights larger than ~500 MB, training or fine-tuning, or installing system packages.
- **Never** overwrite or modify the user's original checkpoints. Write only to `flexml_export/` and the virtual environment.
- **Never** invent metrics. Every number in the report must come from a command you ran; if you couldn't run something, write "not run" and why.
- **Licences:** note the model's licence in the report and metadata. Flag non-commercial licences if the user mentions selling the app or the model.
- **No uploads** of the user's model or data anywhere. Don't commit or push unless asked.
- If the model **can't** meet the contract (e.g. it needs two images, or text input), say so plainly and suggest the closest option.

## 11. Troubleshooting

| Problem | Fix |
|---|---|
| `check-model`: "No image input" | Pass `inputs=[ct.ImageType(...)]` to `ct.convert` |
| Task detected as `raw` | Reshape outputs to a §3 layout (e.g. add argmax, flatten detection heads to `[1, 4+C, N]`) |
| "Extra input … FlexML can't provide" | Bake constants into the graph; only `iouThreshold`/`confidenceThreshold` are allowed |
| Unsupported op during conversion | Rewrite with basic ops; check coremltools' supported-ops list; upgrade coremltools |
| Parity off on every image | Wrong channel order or normalisation |
| Parity off only on small objects | FP16 precision: try `compute_precision=ct.precision.FLOAT32` to confirm, then decide with the user |
| Model is huge or slow | Palettise (§7), reduce input size, prefer a smaller backbone |
