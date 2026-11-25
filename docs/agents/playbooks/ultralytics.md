# Playbook: Ultralytics YOLO → FlexML

Covers YOLOv5u, v8, v9, v10, v11 and YOLO26 for detection, pose and classification. This is the easiest path, because Ultralytics exports Core ML directly.

## 1. Environment
```bash
python -m venv .flexml-venv && source .flexml-venv/bin/activate
pip install ultralytics coremltools pillow
pip install "flexml-companion[check] @ git+https://github.com/Arjun-2005aa/FlexML_SDK.git#subdirectory=python"
```

## 2. Export
```bash
mkdir -p flexml_export
# Detection, with NMS inside the model (recommended: FlexML's sliders control the thresholds)
yolo export model=path/to/best.pt format=coreml nms=True imgsz=640 half=True
# Detection, raw output (FlexML decodes and runs NMS; slightly less CPU on the phone)
yolo export model=path/to/best.pt format=coreml imgsz=640 half=True
# Pose (17 keypoints) / classification
yolo export model=path/to/best-pose.pt format=coreml imgsz=640
yolo export model=path/to/best-cls.pt  format=coreml imgsz=224
mv path/to/best.mlpackage flexml_export/
```

**Choosing `imgsz`:** use the training size (usually 640). Use 416 or 320 only if the user wants speed over small-object accuracy; this needs a parity check against the `.pt` at the same size.

**Segmentation models (`-seg`):** FlexML currently draws the boxes only. Say so in the report.

## 3. Validate
```bash
flexml check-model flexml_export/best.mlpackage --image samples/example.jpg
```

What to expect:
- **`nms=True`:** task `detection`, "Object-detector pipeline outputs", labels = your classes.
- **Raw:** task `detection`, "Raw YOLOv8/v11-style output with C classes", labels from Ultralytics' `names` metadata.
- **Pose:** task `keypoints`, "Raw YOLO pose output with 17 keypoints".

## 4. Parity (macOS)
```python
from ultralytics import YOLO
import glob
pt, ml = YOLO("path/to/best.pt"), YOLO("flexml_export/best.mlpackage")
for img in sorted(glob.glob("samples/*.jpg"))[:10]:
    a = pt.predict(img, imgsz=640, conf=0.3, verbose=False)[0].boxes
    b = ml.predict(img, imgsz=640, conf=0.3, verbose=False)[0].boxes
    print(img, len(a), len(b))   # then match by class with IoU ≥ 0.9 (AGENTS.md §6)
```

## 5. On the phone
Import the model. Under **Display › Model input**, keep **Fit (letterbox)**, which matches YOLO training. Set the confidence threshold in **Display › Filter**.
