import csv

import Metashape

from scripts.utils import ActiveChunk

TYPE_COLUMN_NAME = "typ"


def _getMarker(chunk, label):
    for marker in chunk.markers:
        if marker.label == label:
            return marker
    return None


def _parseFloat(value):
    try:
        return float(value.replace(",", "."))
    except (ValueError, AttributeError):
        return None


def _isControl(type_value):
    v = type_value.strip().lower()
    if v == "control":
        return True
    if v == "check":
        return False
    return None


def ImportMarkers(src_crs, dst_crs, markers_file):
    chunk = ActiveChunk()

    with open(markers_file, "r", encoding="utf-8-sig") as f:
        sample = f.read(4096)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters="\t;,")
        except csv.Error:
            dialect = csv.excel_tab
        rows = list(csv.reader(f, dialect))

    type_col = 4
    control, check = [], []

    for row in rows:
        row = [c.strip() for c in row]
        if len(row) < 4:
            continue

        label = row[0]
        y, x, z = (_parseFloat(v) for v in row[1:4])
        if y is None or x is None or z is None:
            for i, name in enumerate(c.lower() for c in row):
                if name == TYPE_COLUMN_NAME:
                    type_col = i
                    break
            continue

        marker = _getMarker(chunk, label)
        if marker is None:
            marker = chunk.addMarker()
            marker.label = label

        p = Metashape.CoordinateSystem.transform(
            Metashape.Vector([x, y, z]), src_crs, dst_crs)
        marker.reference.location = p

        type_value = row[type_col] if len(row) > type_col else ""
        is_control = _isControl(type_value)
        if is_control is None:
            print("Uwaga: punkt %s ma typ '%s' (oczekiwano control/check) - traktuję jako check"
                  % (label, type_value))
            is_control = False

        marker.reference.enabled = is_control
        (control if is_control else check).append(label)

    print("Punkty osnowy wczytane: %d" % (len(control) + len(check)))
    print("  control (%d): %s" % (len(control), ", ".join(control)))
    print("  check   (%d): %s" % (len(check), ", ".join(check)))
