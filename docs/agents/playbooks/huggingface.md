# Playbook: Hugging Face Transformers → FlexML

Load the model in PyTorch, wrap it to return a plain tensor in a FlexML layout, and take preprocessing and labels from the model's config.

```bash
pip install torch transformers coremltools pillow numpy "flexml-companion[check] @ git+https://github.com/Arjun-2005aa/FlexML_SDK.git#subdirectory=python"
```

```python
import torch, coremltools as ct
from transformers import AutoImageProcessor

def image_input(proc, h, w):
    mean, std = proc.image_mean, proc.image_std
    s = sum(std) / 3   # Core ML has one scale; exact when stds are equal
    return ct.ImageType(name="image", shape=(1, 3, h, w), scale=1 / (255 * s), bias=[-m / s for m in mean],
                        color_layout=ct.colorlayout.RGB)

def to_coreml(wrapper, proc, h, w, **kw):
    traced = torch.jit.trace(wrapper.eval(), torch.rand(1, 3, h, w))
    return ct.convert(traced, inputs=[image_input(proc, h, w)], minimum_deployment_target=ct.target.iOS17, **kw)
```
Use the processor's crop or resize size for `h, w` (e.g. `proc.size["height"]`).

## Image classification (ViT, ConvNeXt, MobileViT…)
```python
from transformers import AutoModelForImageClassification
name = "apple/mobilevit-small"
model = AutoModelForImageClassification.from_pretrained(name, torchscript=True)
proc = AutoImageProcessor.from_pretrained(name)
class Cls(torch.nn.Module):
    def __init__(self, m): super().__init__(); self.m = m
    def forward(self, x): return self.m(pixel_values=x)[0].softmax(-1)
labels = [model.config.id2label[i] for i in range(model.config.num_labels)]
ml = to_coreml(Cls(model), proc, 256, 256, classifier_config=ct.ClassifierConfig(labels))
```
MobileViT expects BGR in 0–1 with no mean/std; check `proc.do_normalize` and channel order, and set `scale=1/255, bias=[0,0,0]` and BGR where needed.

## Semantic segmentation (SegFormer, DPT-seg…)
```python
from transformers import AutoModelForSemanticSegmentation
class Seg(torch.nn.Module):
    def __init__(self, m, h, w): super().__init__(); self.m, self.h, self.w = m, h, w
    def forward(self, x):
        logits = self.m(pixel_values=x)[0]                                   # [1, C, h/4, w/4]
        up = torch.nn.functional.interpolate(logits, size=(self.h, self.w), mode="bilinear", align_corners=False)
        return up.argmax(1).squeeze(0).to(torch.int32)                        # [H, W] class indices
ml.user_defined_metadata["names"] = str(model.config.id2label)              # FlexML reads {0: 'wall', …}
```

## Depth (DPT, Depth Anything)
```python
from transformers import AutoModelForDepthEstimation
class Depth(torch.nn.Module):
    def __init__(self, m): super().__init__(); self.m = m
    def forward(self, x): return self.m(pixel_values=x)[0]                   # predicted_depth [1, H, W]
```
Apple also publishes a ready-made Depth Anything V2 Core ML model, so suggest it if the user just needs depth.

## Object detection (DETR, YOLOS, RT-DETR)
Emit the **end-to-end** layout `[1, Q, 6]`: x1, y1, x2, y2 (normalised), score, class. FlexML needs no NMS for it.
```python
class E2E(torch.nn.Module):
    def __init__(self, m): super().__init__(); self.m = m
    def forward(self, x):
        out = self.m(pixel_values=x)
        prob = out.logits.softmax(-1)[..., :-1]          # drop the "no object" class
        score, cls = prob.max(-1)
        cx, cy, w, h = out.pred_boxes.unbind(-1)         # normalised centre format
        boxes = torch.stack([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2], -1)
        return torch.cat([boxes, score[..., None], cls[..., None].float()], -1)   # [1, Q, 6]
```
Q (queries) ≤ 1000 is required (DETR uses 100). Add `names` from `id2label`. RT-DETR has no "no object" class (sigmoid scores), so use `out.logits.sigmoid()` and skip the slice.

## Validate and compare
`flexml check-model flexml_export/<Name>.mlpackage --image samples/x.jpg`, then run parity against the original `transformers` pipeline on the same resized images (AGENTS.md §6).
