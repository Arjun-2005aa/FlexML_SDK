"""Tests for `flexml check-model` (skipped when coremltools isn't installed)."""
import os
import tempfile
import unittest

try:
    import coremltools as ct
    from coremltools.converters.mil import Builder as mb
except ImportError:  # pragma: no cover
    ct = None

from flexml_companion.modelcheck import check


@unittest.skipUnless(ct, "coremltools not installed")
class ModelCheckTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.TemporaryDirectory()

        @mb.program(input_specs=[mb.TensorSpec(shape=(1, 3, 64, 64))])
        def yolo(image):
            m = mb.reduce_mean(x=image, axes=[1, 2, 3], keep_dims=True)
            return mb.reshape(x=mb.tile(x=m, reps=[1, 84, 8400, 1]), shape=[1, 84, 8400], name="out")

        @mb.program(input_specs=[mb.TensorSpec(shape=(1, 10))])
        def tensor_in(x):
            return mb.relu(x=x, name="y")

        cls.yolo = os.path.join(cls.dir.name, "yolo.mlpackage")
        model = ct.convert(yolo, inputs=[ct.ImageType(name="image", shape=(1, 3, 64, 64))],
                           minimum_deployment_target=ct.target.iOS17)
        model.user_defined_metadata["names"] = str({i: f"c{i}" for i in range(80)})
        model.save(cls.yolo)
        cls.tensor = os.path.join(cls.dir.name, "tensor.mlpackage")
        ct.convert(tensor_in, minimum_deployment_target=ct.target.iOS17).save(cls.tensor)

    @classmethod
    def tearDownClass(cls):
        cls.dir.cleanup()

    def test_raw_yolo_passes_with_labels(self):
        r = check(self.yolo)
        self.assertTrue(r.ok)
        self.assertEqual((r.task, r.yolo_layout), ("detection", "channels-first"))
        self.assertEqual(len(r.labels), 80)
        self.assertEqual(r.input_size, (64, 64))

    def test_tensor_input_fails(self):
        r = check(self.tensor)
        self.assertFalse(r.ok)
        self.assertTrue(any("image input" in e for e in r.errors))


if __name__ == "__main__":
    unittest.main()
