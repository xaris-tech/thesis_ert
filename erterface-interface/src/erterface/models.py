"""Data model: Plantation > Zone > Tree > Measurement.

Each class has to_dict / from_dict for JSON round-tripping. The persisted
format is intentionally identical to the original based-3.py so existing
plantation_data.json files load without migration (unknown keys from
older files are ignored on load and dropped on the next save).
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
        self.name = f"Tree {tree_id}"
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


class Zone:
    def __init__(self, zone_id):
        self.zone_id = zone_id
        self.name = f"Zone {zone_id}"
        self.trees = []

    def to_dict(self):
        return {
            "zone_id": self.zone_id,
            "trees": [t.to_dict() for t in self.trees],
        }

    @classmethod
    def from_dict(cls, data):
        zone = cls(data["zone_id"])
        zone.trees = [Tree.from_dict(t) for t in data.get("trees", [])]
        return zone


class Plantation:
    def __init__(self, name, plant_id):
        self.name = name
        self.plant_id = plant_id
        self.zones = []

    def to_dict(self):
        return {
            "name": self.name,
            "plant_id": self.plant_id,
            "zones": [z.to_dict() for z in self.zones],
        }

    @classmethod
    def from_dict(cls, data):
        plantation = cls(data["name"], data["plant_id"])
        plantation.zones = [Zone.from_dict(z) for z in data.get("zones", [])]
        return plantation


def iter_all_measurements(database):
    """Walk the whole tree, yielding (plantation, zone, tree, measurement) tuples."""
    for p in database:
        for z in p.zones:
            for t in z.trees:
                for m in t.measurements:
                    yield p, z, t, m
