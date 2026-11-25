import Metashape
import numpy as np
import cv2

from scripts.utils import ActiveChunk
from scripts.gcp import PredictProjections, EmptyStats

METHODS = {
    "metashape": "Detektor Metashape (CrossTarget)",
    "corners": "Detektor narożników (OpenCV)",
    "template": "Template Matching (OpenCV)",
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

# ---------------------------------------------------------------------------
# Metoda 3: Template Matching OpenCV
# ---------------------------------------------------------------------------

def AutoMeasureMarkersTemplate(win, max_dist, template_size, min_score):
    chunk = ActiveChunk()
    markers = list(chunk.markers)
    predicted = PredictProjections(chunk, markers)
    stats = EmptyStats(markers, predicted)

    image_cache = {}

    def get_gray(camera):
        path = camera.photo.path
        if path not in image_cache:
            image_cache[path] = _loadGray(path)
        return image_cache[path]

    templates = []

    for marker in markers:
        for camera, projection in marker.projections.items():
            if not projection.valid or not projection.pinned:
                continue

            gray = get_gray(camera)
            if gray is None:
                continue

            x = int(round(projection.coord[0]))
            y = int(round(projection.coord[1]))
            half = int(template_size) // 2

            h, w = gray.shape
            if (x - half < 0 or y - half < 0 or
                    x + half >= w or y + half >= h):
                continue

            template = gray[
                y - half:y + half + 1,
                x - half:x + half + 1
            ]

            if template.shape[0] < 3 or template.shape[1] < 3:
                continue

            if float(np.std(template)) < 1.0:
                continue

            templates.append((camera, template.copy()))

    print("Liczba przygotowanych wzorców: %d" % len(templates))
    by_camera = {}
    for marker, camera, uv in predicted.values():
        existing_cameras = {c.key for c in marker.projections.keys()}

        if camera.key in existing_cameras:
            continue

        by_camera.setdefault(camera, []).append((marker, uv))

    for camera, items in by_camera.items():
        gray = get_gray(camera)

        if gray is None:
            print("Nie udało się wczytać zdjęcia %s" % camera.photo.path)
            continue

        h, w = gray.shape

        for marker, uv in items:
            marker_templates = templates

            if not marker_templates:
                continue

            u, v = float(uv.x), float(uv.y)
            best_score = -1.0
            best_position = None

            for source_camera, template in marker_templates:
                if source_camera.key == camera.key:
                    continue

                th, tw = template.shape
                half_x = tw // 2
                half_y = th // 2

                x0 = max(0, int(np.floor(u - win - half_x)))
                y0 = max(0, int(np.floor(v - win - half_y)))
                x1 = min(w, int(np.ceil(u + win + half_x + 1)))
                y1 = min(h, int(np.ceil(v + win + half_y + 1)))

                roi = gray[y0:y1, x0:x1]

                if roi.shape[0] < th or roi.shape[1] < tw:
                    continue

                result = cv2.matchTemplate(
                    roi,
                    template,
                    cv2.TM_CCOEFF_NORMED
                )

                for ry in range(result.shape[0]):
                    for rx in range(result.shape[1]):
                        px = x0 + rx + half_x
                        py = y0 + ry + half_y

                        distance = np.hypot(px - u, py - v)

                        if distance > max_dist:
                            result[ry, rx] = -1.0

                _, score, _, location = cv2.minMaxLoc(result)

                if score > best_score:
                    best_score = score
                    best_position = (
                        x0 + location[0] + half_x,
                        y0 + location[1] + half_y
                    )

            if best_position is None or best_score < min_score:
                continue

            marker.projections[camera] = Metashape.Marker.Projection(
                Metashape.Vector([
                    float(best_position[0]),
                    float(best_position[1])
                ]),
                True
            )

            stats[marker.label]["found"] += 1

    added = sum(s["found"] for s in stats.values())

    print(
        "Template Matching: dodano %d rzutów "
        "(okno %d px, maks. odl. %.1f px, "
        "rozmiar wzorca %d px, minimalne podobieństwo %.2f)"
        % (added, win, max_dist, template_size, min_score)
    )

    return stats

