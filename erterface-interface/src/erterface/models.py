"""Data model: Plantation > Tree > Measurement.

Each class has to_dict / from_dict for JSON round-tripping. The persisted
format follows the original based-3.py; files that still have the removed
Zone level load with each zone's trees lifted into the plantation, and
unknown keys are dropped on the next save.
"""

from PyQt6.QtCore import QDateTime, Qt


class Measurement:
    def __init__(self, imp_ratio, classification, timestamp, data_path="", image_path="",
                 synced=False, pattern=""):
        self.imp_ratio = imp_ratio
        # Drive pattern the ratio was measured with; ratios compare only within
        # one pattern (ADR-0075). "" for measurements from before it was kept.
        self.pattern = pattern
        self.classification = classification
        self.timestamp = timestamp
        self.data_path = data_path
        self.image_path = image_path
        self.synced = synced
        self.name = f"{timestamp.toString('yyyy-MM-dd')}\n{timestamp.toString('HH:mm')}\n{classification}"

    def to_dict(self):
        return {
            "imp_ratio": self.imp_ratio,
            "classification": self.classification,
            "timestamp": self.timestamp.toString(Qt.DateFormat.ISODate),
            "data_path": self.data_path,
            "image_path": self.image_path,
            "synced": self.synced,
            "pattern": self.pattern,
        }

    @classmethod
    def from_dict(cls, data):
        ts_raw = data["timestamp"]
        timestamp = QDateTime.fromString(ts_raw, Qt.DateFormat.ISODate)
        if not timestamp.isValid():
            timestamp = QDateTime.currentDateTime()
        return cls(
            data["imp_ratio"],
            data["classification"],
            timestamp,
            data.get("data_path", ""),
            data.get("image_path", ""),
            data.get("synced", False),
            data.get("pattern", ""),
        )


class Tree:
    def __init__(self, tree_id):
        self.tree_id = tree_id
        self.name = tree_id  # "disc-01", "e1", "T003": the label is the name
        self.measurements = []

    def to_dict(self):
        return {
            "tree_id": self.tree_id,
            "measurements": [m.to_dict() for m in self.measurements],
        }

    @classmethod
    def from_dict(cls, data):
        tree = cls(data["tree_id"])
        tree.measurements = [Measurement.from_dict(m) for m in data.get("measurements", [])]
        return tree


class Plantation:
    """Top level. Holds trees directly: the Zone level was removed (2026-10-26)."""

    def __init__(self, name, plant_id):
        self.name = name
        self.plant_id = plant_id
        self.trees = []

    def to_dict(self):
        return {
            "name": self.name,
            "plant_id": self.plant_id,
            "trees": [t.to_dict() for t in self.trees],
        }

    @classmethod
    def from_dict(cls, data):
        plantation = cls(data["name"], data["plant_id"])
        trees = list(data.get("trees", []))
        # Files from before the Zone level was removed: lift each zone's trees
        # up to the plantation, so nothing saved is lost.
        for zone in data.get("zones", []):
            trees.extend(zone.get("trees", []))
        plantation.trees = [Tree.from_dict(t) for t in trees]
        return plantation


def iter_all_measurements(database):
    """Walk everything, yielding (plantation, tree, measurement) tuples."""
    for p in database:
        for t in p.trees:
            for m in t.measurements:
                yield p, t, m
