import Metashape
import numpy as np
import cv2



def _approxPosition(chunk, marker):
    if marker.position is not None:
        return marker.position
    if marker.reference.location is None:
        return None
    return chunk.transform.matrix.inv().mulp(chunk.crs.unproject(marker.reference.location))


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
    chunk = Metashape.app.document.chunk
    stats = {m.label: {"visible": 0, "found": 0} for m in chunk.markers}

    for camera in chunk.cameras:
        if camera.transform is None:
            continue
        gray = None
        for marker in chunk.markers:
            existing = marker.projections[camera]
            if existing is not None and existing.pinned:
                continue

            if existing is not None:
                uv = existing.coord
            else:
                pos = _approxPosition(chunk, marker)
                if pos is None:
                    continue
                if camera.transform.inv().mulp(pos).z <= 0:
                    continue  # punkt za kamerą
                uv = camera.project(pos)
            if uv is None or not (0 <= uv.x < camera.sensor.width
                                  and 0 <= uv.y < camera.sensor.height):
                continue
            stats[marker.label]["visible"] += 1

            if gray is None:
                gray = _loadGray(camera.photo.path)
                if gray is None:
                    print("Nie udało się wczytać zdjęcia %s" % camera.photo.path)
                    break
            res = _findCorner(gray, uv.x, uv.y, int(win), max_dist)
            if res is not None:
                marker.projections[camera] = Metashape.Marker.Projection(
                    Metashape.Vector(res), True)
                stats[marker.label]["found"] += 1

    added = sum(s["found"] for s in stats.values())
    print("Automatyczny pomiar: dodano %d rzutów (okno %d px, maks. odl. %.1f px)"
          % (added, win, max_dist))
    return stats
