import Metashape

from scripts.utils import ActiveChunk


def _approxPosition(chunk, marker):
    if marker.position is not None:
        return marker.position
    if marker.reference.location is None:
        return None
    return chunk.transform.matrix.inv().mulp(chunk.crs.unproject(marker.reference.location))


def _predictedUV(chunk, marker, camera):

    existing = marker.projections[camera]
    if existing is not None and existing.pinned:
        return None

    if existing is not None:
        uv = existing.coord
    else:
        pos = _approxPosition(chunk, marker)
        if pos is None:
            return None
        if camera.transform.inv().mulp(pos).z <= 0:
            return None  # punkt za kamerą
        uv = camera.project(pos)
    if uv is None or not (0 <= uv.x < camera.sensor.width
                          and 0 <= uv.y < camera.sensor.height):
        return None
    return uv


def PredictProjections(chunk, markers):
    predicted = {}
    for camera in chunk.cameras:
        if camera.transform is None:
            continue
        for marker in markers:
            uv = _predictedUV(chunk, marker, camera)
            if uv is not None:
                predicted[(marker.key, camera.key)] = (marker, camera, uv)
    return predicted


def EmptyStats(markers, predicted):
    stats = {m.label: {"visible": 0, "found": 0} for m in markers}
    for marker, _, _ in predicted.values():
        stats[marker.label]["visible"] += 1
    return stats


def FilterMarkerProjections(threshold_px=1.0, protected=None):
    protected = protected or set()
    chunk = ActiveChunk()
    removed = 0
    total = 0
    removed_per_marker = {}

    for marker in chunk.markers:
        if marker.type != Metashape.Marker.Type.Regular:
            continue

        position = marker.position
        if position is None:
            continue

        to_remove = []
        for camera in chunk.cameras:
            projection = marker.projections[camera]
            if projection is None or camera.transform is None:
                continue
            if (marker.key, camera.key) in protected:
                continue

            projected = camera.project(position)
            if projected is None:
                continue

            dx = projected[0] - projection.coord[0]
            dy = projected[1] - projection.coord[1]
            total += 1

            if (dx * dx + dy * dy) ** 0.5 > threshold_px:
                to_remove.append(camera)

        for camera in to_remove:
            marker.projections[camera] = None
            removed += 1
        removed_per_marker[marker.label] = len(to_remove)

    print("Filtracja osnowy: usunięto %d z %d rzutów (próg %.2f px)"
          % (removed, total, threshold_px))
    return removed_per_marker
