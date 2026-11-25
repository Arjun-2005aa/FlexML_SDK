"""`flexml check-model`: does a Core ML model run well in FlexML?

Mirrors the app's own rules (FlexML/Models/ModelInspector.swift) so people, and the AI agents
described in docs/agents/AGENTS.md, can verify a converted model on a Mac before copying it to
the phone. Needs `coremltools` (`pip install "flexml-companion[check]"`).

Exit code: 0 = passes (warnings allowed), 1 = will not work in FlexML, 2 = could not read it.
"""
from __future__ import annotations

import ast
import json
import math
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

GRAYSCALE_SPACES = {10, 40}  # GRAYSCALE, GRAYSCALE_FLOAT16
DTYPES = {65552: "Float16", 65568: "Float32", 65600: "Float64", 131104: "Int32"}


@dataclass
class Report:
    path: str
    task: str = "raw"
    reason: str = ""
    input_size: Optional[Tuple[int, int]] = None
    labels: List[str] = field(default_factory=list)
    yolo_layout: Optional[str] = None
    outputs: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    prediction: Optional[Dict[str, Any]] = None

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_dict(self) -> Dict[str, Any]:
        return {"path": self.path, "ok": self.ok, "task": self.task, "reason": self.reason,
                "inputSize": self.input_size, "labels": len(self.labels), "yoloLayout": self.yolo_layout,
                "outputs": self.outputs, "errors": self.errors, "warnings": self.warnings, "notes": self.notes,
                "prediction": self.prediction}


def _shape(feature) -> List[int]:
    t = feature.type
    return list(t.multiArrayType.shape) if t.HasField("multiArrayType") else []


def _find_labels(message) -> List[str]:
    """Class labels anywhere in the spec (classifiers, NMS stages of detector pipelines)."""
    for desc, value in message.ListFields():
        if desc.name in ("stringClassLabels",) and value.vector:
            return list(value.vector)
        if desc.name == "int64ClassLabels" and value.vector:
            return [str(v) for v in value.vector]
        if desc.message_type is not None:
            repeated = getattr(desc, "is_repeated", None)
            if repeated is None:  # older protobuf
                repeated = desc.label == desc.LABEL_REPEATED
            items = value if repeated else [value]
            for item in items:
                if hasattr(item, "ListFields"):
                    found = _find_labels(item)
                    if found:
                        return found
    return []


def _mlprogram_classifier_labels(spec) -> List[str]:
    """ML Program classifiers keep their labels inline in the `classify` op's `classes` argument."""
    if spec.WhichOneof("Type") != "mlProgram":
        return []
    for fn in spec.mlProgram.functions.values():
        for block in fn.block_specializations.values():
            for op in block.operations:
                if op.type != "classify" or "classes" not in op.inputs:
                    continue
                for arg in op.inputs["classes"].arguments:
                    if arg.WhichOneof("binding") != "value":
                        continue
                    imm = arg.value.immediateValue
                    tensors = ([v.immediateValue.tensor for v in imm.list.values]
                               if imm.WhichOneof("value") == "list" else [imm.tensor])
                    labels: List[str] = []
                    for t in tensors:
                        labels += [str(v) for v in (t.strings.values or t.longInts.values or t.ints.values)]
                    if labels:
                        return labels
    return []


def _metadata_labels(meta: Dict[str, str]) -> List[str]:
    if "names" in meta:
        try:
            names = ast.literal_eval(meta["names"])
            if isinstance(names, dict):
                return [str(names[k]) for k in sorted(names)]
            if isinstance(names, (list, tuple)):
                return [str(n) for n in names]
        except (ValueError, SyntaxError):
            pass
    if "classes" in meta and "," in meta["classes"]:
        return [c.strip() for c in meta["classes"].split(",")]
    params = meta.get("com.apple.coreml.model.preview.params")
    if params:
        try:
            labels = json.loads(params).get("labels")
            if isinstance(labels, list):
                return [str(l) for l in labels]
        except (ValueError, AttributeError):
            pass
    return []


def _yolo_layout(arrays: List[Tuple[str, List[int]]]) -> Optional[Tuple[str, str]]:
    proto = next((s[1] for _, s in arrays if len(s) == 4 and s[0] == 1), 0)
    for _, shape in arrays:
        dims = shape[:]
        while dims and dims[0] == 1:
            dims.pop(0)
        if len(dims) != 2:
            continue
        a, b = dims
        if b == 6 and a <= 1000:
            return "end-to-end", "NMS-free YOLO output (x1, y1, x2, y2, score, class)"
        if b >= 1000 and 5 <= a <= 600:
            if a == 56 and proto == 0:
                return "pose", "Raw YOLO pose output with 17 keypoints"
            if a - 4 - proto >= 1:
                return "channels-first", f"Raw YOLOv8/v11-style output with {a - 4 - proto} classes"
        if a >= 1000 and 6 <= b <= 600:
            return "anchors-first", f"Raw YOLOv5-style output with {b - 5} classes"
    return None


def check(path: str, image: Optional[str] = None) -> Report:
    import coremltools as ct

    report = Report(path=path)
    spec = ct.utils.load_spec(path)
    desc = spec.description
    meta = dict(desc.metadata.userDefined)
    preview = meta.get("com.apple.coreml.model.preview.type", "").lower()

    # ---- inputs ----
    images = [f for f in desc.input if f.type.HasField("imageType")]
    others = [f for f in desc.input if not f.type.HasField("imageType")]
    if not images:
        report.errors.append("No image input. FlexML feeds camera frames, so the input must be an image: "
                             "convert with inputs=[ct.ImageType(...)].")
    elif len(images) > 1:
        report.warnings.append(f"{len(images)} image inputs; FlexML feeds the camera to '{images[0].name}' only.")
    if images:
        it = images[0].type.imageType
        report.input_size = (it.width, it.height)
        if it.HasField("imageSizeRange") or it.HasField("enumeratedSizes"):
            report.warnings.append(f"Flexible input size; FlexML uses the default {it.width}×{it.height}. Prefer a fixed size.")
        if it.width * it.height > 1024 * 1024:
            report.warnings.append(f"Large input ({it.width}×{it.height}); expect low frame rates. 320–640 px is typical.")
        if it.colorSpace in GRAYSCALE_SPACES:
            report.notes.append("Grayscale image input: FlexML converts camera frames to grayscale for you.")
    for f in others:
        n = f.name.lower()
        if "confidence" in n or "iou" in n:
            report.notes.append(f"Extra input '{f.name}' is driven by FlexML's threshold sliders.")
        else:
            report.errors.append(f"Extra input '{f.name}' that FlexML can't provide. Only an image (plus iou/confidence thresholds) is supported.")

    # ---- outputs / task (same order as the app) ----
    outputs = list(desc.output)
    names = {o.name.lower() for o in outputs}
    arrays = [(o.name, _shape(o)) for o in outputs if o.type.HasField("multiArrayType")]
    image_outputs = [o for o in outputs if o.type.HasField("imageType")]
    report.outputs = [
        f"{o.name}: image {o.type.imageType.width}×{o.type.imageType.height}" if o.type.HasField("imageType")
        else f"{o.name}: {o.type.WhichOneof('Type')} {_shape(o) or ''} {DTYPES.get(o.type.multiArrayType.dataType, '') if o.type.HasField('multiArrayType') else ''}".strip()
        for o in outputs
    ]
    report.labels = _find_labels(spec) or _mlprogram_classifier_labels(spec) or _metadata_labels(meta)

    def decide() -> Tuple[str, str]:
        if not images:
            return "raw", "No image input."
        if "confidence" in names and "coordinates" in names or preview == "objectdetector":
            return "detection", "Object-detector pipeline outputs (confidence + coordinates) with built-in NMS."
        if desc.predictedFeatureName:
            return "classification", "Core ML marks this model as a classifier."
        if preview == "imagesegmenter":
            return "segmentation", "Apple preview metadata declares an image segmenter."
        if "depth" in preview:
            return "depth", "Apple preview metadata declares a depth estimator."
        layout = _yolo_layout(arrays)
        if layout:
            report.yolo_layout = layout[0]
            return ("keypoints" if layout[0] == "pose" else "detection"), layout[1]
        if image_outputs:
            o = image_outputs[0]
            gray = o.type.imageType.colorSpace in GRAYSCALE_SPACES
            n = o.name.lower()
            if not gray:
                return "imageToImage", "Outputs a colour image."
            if "depth" in n or "disparity" in n:
                return "depth", f"Grayscale image output named '{o.name}'."
            if any(k in n for k in ("seg", "mask", "label", "class")) or report.labels:
                return "segmentation", "Grayscale image output that looks like a class map."
            return "depth", "Grayscale image output; treated as depth."
        if arrays:
            name, shape = max(arrays, key=lambda a: math.prod(a[1]) if a[1] else 0)
            dims = shape[:]
            while dims and dims[0] == 1:
                dims.pop(0)
            n = name.lower()
            out = next(o for o in outputs if o.name == name)
            is_int = out.type.multiArrayType.dataType == 131104
            if len(dims) == 2 and dims[0] >= 32 and dims[1] >= 32:
                if is_int or any(k in n for k in ("seg", "label", "class", "pred")):
                    return "segmentation", f"A {dims[0]}×{dims[1]} class map."
                return "depth", f"A {dims[0]}×{dims[1]} single-channel map; treated as depth."
            if len(dims) == 3 and dims[1] >= 16 and dims[2] >= 16:
                if any(k in n for k in ("heatmap", "keypoint", "pose")):
                    return "keypoints", f"{dims[0]} keypoint heatmaps."
                if dims[0] == 1:
                    return "depth", "A single-channel map; treated as depth."
                return "segmentation", f"{dims[0]} class score maps."
            if len(dims) == 1 and 2 <= dims[0] <= 30000:
                return "classification", f"A vector of {dims[0]} scores."
            if not shape:
                report.warnings.append(f"Output '{name}' has no fixed shape in the spec; FlexML may show it as raw tensors. "
                                       "Give outputs fixed shapes when converting.")
        if any(o.type.HasField("dictionaryType") or o.type.HasField("stringType") for o in outputs):
            return "classification", "Label or probability dictionary output."
        return "raw", "Outputs don't match a known layout; FlexML shows them as raw tensors."

    report.task, report.reason = decide()

    # ---- quality checks ----
    if report.task == "raw" and images:
        report.warnings.append("FlexML won't draw results for this model (raw tensors only). See the output layouts in "
                               "docs/bring-your-own-model.md, or pick the task by hand in the app.")
    if report.task in ("detection", "segmentation", "keypoints") and not report.labels:
        report.warnings.append("No class labels found; FlexML will show 'class N'. Add "
                               "model.user_defined_metadata['names'] = str({0: 'person', ...}).")
    if spec.WhichOneof("Type") == "mlProgram":
        report.notes.append("ML Program (recommended).")
    elif spec.specificationVersion < 4:
        report.notes.append(f"Older Core ML format (spec {spec.specificationVersion}); fine, but new conversions should target iOS 17.")
    if report.yolo_layout in ("channels-first", "anchors-first"):
        report.notes.append("Raw YOLO: FlexML decodes it and runs NMS itself. Use Display › Model input › Fit (default for these).")

    if image and images:
        report.prediction = _predict(path, images[0], image, ct)
    return report


def _predict(path: str, image_input, image_path: str, ct) -> Dict[str, Any]:
    """Runs the model once on a test image (macOS only) and summarises the outputs."""
    try:
        from PIL import Image
    except ImportError:
        return {"error": "pip install pillow to run a test prediction"}
    try:
        import numpy as np
        model = ct.models.MLModel(path)
        it = image_input.type.imageType
        img = Image.open(image_path).convert("L" if it.colorSpace in GRAYSCALE_SPACES else "RGB").resize((it.width, it.height))
        inputs: Dict[str, Any] = {image_input.name: img}
        for f in model.get_spec().description.input:
            if f.name != image_input.name and f.type.HasField("doubleType"):
                inputs[f.name] = 0.25 if "confidence" in f.name.lower() else 0.45
        out = model.predict(inputs)
        summary = {}
        for k, v in out.items():
            if hasattr(v, "shape"):
                a = np.asarray(v, dtype=np.float64)
                summary[k] = {"shape": list(a.shape), "min": float(a.min()) if a.size else None, "max": float(a.max()) if a.size else None}
            elif isinstance(v, dict):
                top = sorted(v.items(), key=lambda kv: -kv[1])[:3]
                summary[k] = {"top": [[str(a), round(float(b), 3)] for a, b in top]}
            elif hasattr(v, "size"):
                summary[k] = {"image": list(v.size)}
            else:
                summary[k] = str(v)[:80]
        return summary
    except Exception as e:  # noqa: BLE001 - report, don't crash the check
        return {"error": f"prediction failed: {e}"}


def main(args) -> int:
    try:
        report = check(args.model, args.image)
    except ImportError:
        print("coremltools is required: pip install \"flexml-companion[check]\"", file=sys.stderr)
        return 2
    except Exception as e:  # noqa: BLE001
        print(f"Couldn't read {args.model}: {e}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        mark = "PASS" if report.ok else "FAIL"
        print(f"{mark}  {report.path}")
        print(f"  FlexML will treat it as: {report.task}  ({report.reason})")
        if report.input_size:
            print(f"  Input: {report.input_size[0]}×{report.input_size[1]} image")
        print(f"  Labels: {len(report.labels)}" + (f" (e.g. {', '.join(report.labels[:5])})" if report.labels else ""))
        for o in report.outputs:
            print(f"  Output {o}")
        for e in report.errors:
            print(f"  ✗ {e}")
        for w in report.warnings:
            print(f"  ! {w}")
        for n in report.notes:
            print(f"  · {n}")
        if report.prediction is not None:
            print("  Test prediction: " + json.dumps(report.prediction))
    return 0 if report.ok else 1
