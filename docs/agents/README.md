# Port your model with an AI coding agent

These files let a coding agent (Claude Code, OpenAI Codex, Cursor, GitHub Copilot, Gemini CLI and others) convert **your** model into a Core ML model that runs well in FlexML. The agent checks its own work with `flexml check-model`.

## Use it

1. Copy the agent file into the **root of your model project** (where your training code or checkpoint lives):

   | Agent | Copy |
   |---|---|
   | Claude Code | `AGENTS.md` **and** `CLAUDE.md` (it imports AGENTS.md) |
   | Codex, Cursor, Copilot, Gemini CLI, Jules, Aider… | `AGENTS.md` |

2. Open the project in your agent and ask, for example:
   - "Port my model to FlexML."
   - "Port `runs/detect/train/weights/best.pt` to FlexML for object detection."
   - "Convert this Hugging Face depth model for FlexML and check parity on the images in `samples/`."

3. The agent writes `flexml_export/<Name>.mlpackage` and `flexml_export/PORT_REPORT.md`. Read the report, then AirDrop the `.mlpackage` to your phone and import it in **FlexML › Change Model**.

## What the agent does

1. **Works out** your framework, preprocessing, classes and outputs.
2. **Converts** with coremltools (or `yolo export` for Ultralytics), with the image preprocessing built in.
3. **Validates** with `flexml check-model`, the same rules the app uses, until it passes.
4. **Compares** the Core ML model with your original on real images (parity).
5. **Optionally shrinks** the model, re-checking afterwards.
6. **Reports** commands, results and caveats. It never edits your original checkpoint and never invents numbers.

## Check a model yourself

```bash
pip install "flexml-companion[check] @ git+https://github.com/Arjun-2005aa/FlexML_SDK.git#subdirectory=python"   # needs macOS for --image
flexml check-model MyModel.mlpackage --image photo.jpg
flexml check-model MyModel.mlpackage --json    # machine-readable
```

## Playbooks

Longer, framework-specific guides an agent (or you) can follow:
- [Ultralytics YOLO](playbooks/ultralytics.md)
- [PyTorch: torchvision, timm, custom](playbooks/pytorch.md)
- [Hugging Face Transformers](playbooks/huggingface.md)
- [TensorFlow / Keras](playbooks/tensorflow.md)

See also [Bring your own model](../bring-your-own-model.md) for the manual route.
