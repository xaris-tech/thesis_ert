"""CSV export: one row per measurement, written atomically."""

import csv
import os

from . import paths
from .models import iter_all_measurements

CSV_COLUMNS = [
    "plantation_id",
    "plantation_name",
    "zone_id",
    "tree_id",
    "measurement_timestamp",
    "imp_ratio",
    "classification",
    "data_path",
    "image_path",
    "synced",
]


def export_measurements_csv(database, output_path):
    """Write one row per measurement. Atomic via tmp + os.replace."""
    tmp = output_path + ".tmp"
    rows = 0
    try:
        with open(tmp, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
            writer.writeheader()
            for p, z, t, m in iter_all_measurements(database):
                writer.writerow({
                    "plantation_id": p.plant_id,
                    "plantation_name": p.name,
                    "zone_id": z.zone_id,
                    "tree_id": t.tree_id,
                    "measurement_timestamp": m.timestamp.toString("yyyy-MM-dd HH:mm:ss"),
                    "imp_ratio": m.imp_ratio,
                    "classification": m.classification,
                    "data_path": m.data_path,
                    "image_path": m.image_path,
                    "synced": m.synced,
                })
                rows += 1
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, output_path)
    except Exception:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
        raise
    return rows
