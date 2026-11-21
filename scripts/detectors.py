import Metashape
import numpy as np
import cv2

from scripts.utils import ActiveChunk
from scripts.gcp import PredictProjections, EmptyStats

METHODS = {
    "metashape": "Detektor Metashape (CrossTarget)",
    "corners": "Detektor narożników (OpenCV)",
}


# ---------------------------------------------------------------------------
# Metoda 1: detektor narożników OpenCV
# ---------------------------------------------------------------------------

def _loadGray(path):
    return cv2.imdecode(np.fromfile(path, np.uint8), cv2.IMREAD_GRAYSCALE)


def _findCorner(gray, u, v, win, max_dist):
    h, w = gray.shape
    x0, y0 = int(u) - win, int(v) - win
    if x0 < 0 or y0 < 0 or x0 + 2 * win >= w or y0 + 2 * win >= h:
        return None
    roi = gray[y0:y0 + 2 * win, x0:x0 + 2 * win]

    pts = cv2.goodFeaturesToTrack(roi, maxCorners=20, qualityLevel=0.1, minDistance=5)
    if pts is None:
        return None
    pts = pts.reshape(-1, 2)
    d = np.hypot(pts[:, 0] - (u - x0), pts[:, 1] - (v - y0))
    i = int(d.argmin())
    if d[i] > max_dist:
        return None

    p = pts[i:i + 1].astype(np.float32)
    cv2.cornerSubPix(roi, p, (5, 5), (-1, -1),
                     (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.01))
    return float(p[0, 0] + x0), float(p[0, 1] + y0)


def AutoMeasureMarkers(win, max_dist):
    chunk = ActiveChunk()
    markers = list(chunk.markers)
    predicted = PredictProjections(chunk, markers)
    stats = EmptyStats(markers, predicted)

    by_camera = {}
    for marker, camera, uv in predicted.values():
        by_camera.setdefault(camera, []).append((marker, uv))

    for camera, items in by_camera.items():
        gray = _loadGray(camera.photo.path)
        if gray is None:
            print("Nie udało się wczytać zdjęcia %s" % camera.photo.path)
            continue
        for marker, uv in items:
            res = _findCorner(gray, uv.x, uv.y, int(win), max_dist)
            if res is not None:
                marker.projections[camera] = Metashape.Marker.Projection(
                    Metashape.Vector(res), True)
                stats[marker.label]["found"] += 1

    added = sum(s["found"] for s in stats.values())
    print("Detektor narożników: dodano %d rzutów (okno %d px, maks. odl. %.1f px)"
          % (added, win, max_dist))
    return stats


# ---------------------------------------------------------------------------
# Metoda 2: wbudowany detektor Metashape (detectMarkers, CrossTarget)
# ---------------------------------------------------------------------------

def DetectMarkersMetashape(tolerance, max_residual, max_dist):
    chunk = ActiveChunk()
    markers = list(chunk.markers)
    original_keys = {m.key for m in markers}
    predicted = PredictProjections(chunk, markers)
    stats = EmptyStats(markers, predicted)

    chunk.detectMarkers(target_type=Metashape.TargetType.CrossTarget,
                        tolerance=int(tolerance),
                        maximum_residual=max_residual)
    detected = [m for m in chunk.markers if m.key not in original_keys]

    best = {}
    n_detections = 0
    for det in detected:
        for camera in det.projections.keys():
            c = det.projections[camera].coord
            n_detections += 1
            for marker in markers:
                key = (marker.key, camera.key)
                if key not in predicted:
                    continue
                uv = predicted[key][2]
                d = ((c.x - uv.x) ** 2 + (c.y - uv.y) ** 2) ** 0.5
                if d <= max_dist and (key not in best or d < best[key][0]):
                    best[key] = (d, c.x, c.y)

    for key, (_, x, y) in best.items():
        marker, camera, _ = predicted[key]
        marker.projections[camera] = Metashape.Marker.Projection(
            Metashape.Vector([x, y]), True)
        stats[marker.label]["found"] += 1

    if detected:
        chunk.remove(detected)

    print("Detektor Metashape: %d wykryć na zdjęciach, przypisano %d rzutów do osnowy "
          "(tolerancja %d, maks. odchyłka %.1f px, maks. odl. %.1f px)"
          % (n_detections, len(best), tolerance, max_residual, max_dist))
    return stats
