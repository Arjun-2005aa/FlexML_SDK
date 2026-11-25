# Playbook: PyTorch (torchvision, timm, custom) → FlexML

Trace the model, wrap it so the output matches a FlexML layout, and put the preprocessing into `ct.ImageType`.

```bash
pip install torch torchvision coremltools pillow numpy "flexml-companion[check] @ git+https://github.com/Arjun-2005aa/FlexML_SDK.git#subdirectory=python"
```

## Shared helper
```python
import torch, coremltools as ct

def image_input(shape, mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225), bgr=False):
    """Core ML ImageType doing (pixel/255 - mean)/std. Core ML has one scale for all channels:
    exact when the stds are equal, otherwise a close approximation (state it in the report)."""
    s = sum(std) / 3
    return ct.ImageType(name="image", shape=shape, scale=1 / (255 * s), bias=[-m / s for m in mean],
                        color_layout=ct.colorlayout.BGR if bgr else ct.colorlayout.RGB)

def convert(module, shape, **kw):
    traced = torch.jit.trace(module.eval(), torch.rand(*shape))
    return ct.convert(traced, inputs=[image_input(shape, **kw.pop("norm", {}))],
                      minimum_deployment_target=ct.target.iOS17, **kw)
```

## Classification (torchvision / timm)
```python
import timm
model = timm.create_model("mobilenetv3_large_100", pretrained=True)
cfg = model.pretrained_cfg                       # mean/std/input size
labels = [...]                                    # e.g. ImageNet class names, in index order
ml = convert(model, (1, 3, 224, 224), norm={"mean": cfg["mean"], "std": cfg["std"]},
             classifier_config=ct.ClassifierConfig(labels))
ml.save("flexml_export/MobileNetV3.mlpackage")
```

## Semantic segmentation (argmax inside: small Int32 output, fast on the phone)
```python
import torchvision
class Seg(torch.nn.Module):
    def __init__(self, m): super().__init__(); self.m = m
    def forward(self, x): return self.m(x)["out"].argmax(1).squeeze(0).to(torch.int32)   # [H, W]
m = torchvision.models.segmentation.deeplabv3_mobilenet_v3_large(weights="DEFAULT")
ml = convert(Seg(m), (1, 3, 512, 512))
ml.user_defined_metadata["names"] = str(dict(enumerate(LABELS)))   # LABELS[0] = "background"
ml.save("flexml_export/Segmenter.mlpackage")
```

## Depth (e.g. MiDaS, Depth Anything)
```python
class Depth(torch.nn.Module):
    def __init__(self, m): super().__init__(); self.m = m
    def forward(self, x): return self.m(x).reshape(1, x.shape[2], x.shape[3])   # [1, H, W]
# check-model should report: task depth. Relative depth is fine.
```
If the network outputs a lower resolution, upsample inside `forward` with `torch.nn.functional.interpolate` to keep the layout `[1, H, W]`, or leave it smaller. FlexML scales the map to the frame.

## Object detection (custom heads)
FlexML needs a fixed-size output. Two-stage detectors with dynamic box counts (Faster R-CNN, Mask R-CNN) don't convert well; suggest a YOLO model instead. For single-stage detectors, decode boxes **inside** the wrapper and emit the raw YOLO layout:

```python
class Det(torch.nn.Module):
    """Emit [1, 4 + C, N]: cx, cy, w, h in input pixels, then per-class scores (0..1)."""
    def __init__(self, m): super().__init__(); self.m = m
    def forward(self, x):
        boxes, scores = self.m(x)            # adapt: decode anchors → boxes [1,N,4] (cx,cy,w,h px), scores [1,N,C]
        return torch.cat([boxes, scores], dim=2).permute(0, 2, 1)
```
FlexML applies the confidence threshold and class-aware NMS itself. N should be ≥ 1000; pad with zero-score rows if needed. Add `names` metadata.

## Pose (heatmaps)
Output `[K, H, W]` heatmaps and name the output `heatmaps` during conversion with `convert(..., outputs=[ct.TensorType(name="heatmaps")])`. FlexML takes each map's peak and draws a skeleton when K = 17 (COCO order).

## Parity (generic)
```python
import numpy as np, glob
from PIL import Image
def to_tensor(img, size, mean, std):
    a = np.asarray(img.resize(size), dtype=np.float32) / 255
    return torch.from_numpy(((a - mean) / std).transpose(2, 0, 1))[None]
for path in sorted(glob.glob("samples/*.jpg"))[:10]:
    img = Image.open(path).convert("RGB")
    ref = WRAPPED(to_tensor(img, (W, H), np.array(MEAN), np.array(STD))).detach().numpy()
    out = list(ml.predict({"image": img.resize((W, H))}).values())[0]
    # compare per AGENTS.md §6 (argmax equality, pixel agreement, correlation…)
```

Then run `flexml check-model flexml_export/<Name>.mlpackage --image samples/x.jpg`.
