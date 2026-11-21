import Metashape
import csv
import json
import os

from scripts.gcp import AutoMeasureMarkers

IMAGE_EXTENSIONS = {".jpg", ".jpeg"}


def _doc():
    return Metashape.app.document


def _chunk():
    return Metashape.app.document.chunk


def AddPhotosFromFolder(folder, chunk_name):
    photos = []
    if folder and os.path.isdir(folder):
        photos = sorted(
            os.path.join(folder, f) for f in os.listdir(folder)
            if os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS
        )

    if not photos:
        print("Brak zdjęć")
        return False

    doc = _doc()
    chunk = doc.addChunk()
    doc.chunk = chunk
    chunk.label = chunk_name or chunk.label
    chunk.addPhotos(photos)

    print("Wczytano %d zdjęć z folderu" % len(photos))
    return True


def AlignCameras(downscale):
    chunk = _chunk()
    chunk.matchPhotos(downscale=downscale, generic_preselection=True,
                      reference_preselection=True, reset_matches=True)
    chunk.alignCameras(reset_alignment=True)
    print("Zdjęcia wyrównane")


def SetChunkCrs(crs):
    chunk = _chunk()
    chunk.crs = crs
    print("Układ współrzędnych chunka ustawiony")


def _getMarker(chunk, label):
    for marker in chunk.markers:
        if marker.label == label:
            return marker
    return None


def _getCamera(chunk, label):
    for camera in chunk.cameras:
        if camera.label == label:
            return camera
    return None


def _parseFloat(value):
    try:
        return float(value.replace(",", "."))
    except (ValueError, AttributeError):
        return None


TYPE_COLUMN_NAME = "typ"


def _isControl(type_value):
    v = type_value.strip().lower()
    if v == "control":
        return True
    if v == "check":
        return False
    return None


def ImportMarkers(src_crs, dst_crs, markers_file):
    chunk = _chunk()

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


def GenerateSelectedProducts(downscale, do_pointcloud, do_model, do_dem, do_ortho):
    chunk = _chunk()

    if do_ortho:
        do_dem = True
    if do_dem:
        do_pointcloud = True

    if do_pointcloud or do_model:
        chunk.buildDepthMaps(downscale=downscale, filter_mode=Metashape.AggressiveFiltering)

    if do_pointcloud:
        chunk.buildPointCloud()

    if do_model:
        chunk.buildModel(surface_type=Metashape.Arbitrary,
                         interpolation=Metashape.EnabledInterpolation,
                         source_data=Metashape.DepthMapsData)
        chunk.buildUV(mapping_mode=Metashape.GenericMapping)
        chunk.buildTexture(blending_mode=Metashape.MosaicBlending, texture_size=4096)

    if do_dem:
        chunk.buildDem(source_data=Metashape.PointCloudData)

    if do_ortho:
        chunk.buildOrthomosaic(surface_data=Metashape.ElevationData)

    print("Produkty wygenerowane")


def RunStage1(values):
    # Dodanie zdjęć z folderu
    if not AddPhotosFromFolder(values["photos_dir"], values["chunk_name"]):
        return False
    SetChunkCrs(values["chunk_crs"])
    # Import osnowy
    if values["gcp_file"] and values["gcp_crs"] is not None:
        ImportMarkers(values["gcp_crs"], values["chunk_crs"], values["gcp_file"])
    # Wyrównanie zdjęć
    AlignCameras(values["align_downscale"])
    return True


def FilterMarkerProjections(threshold_px=1.0, protected=None):
    protected = protected or set()
    chunk = _chunk()
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


def Realign():
    chunk = _chunk()
    chunk.updateTransform()
    chunk.optimizeCameras()
    print("Wykonano ponowne wyrównanie")


def DetectMarkers(tolerance, max_residual):

    chunk = _chunk()
    chunk.detectMarkers(target_type=Metashape.TargetType.CrossTarget,
                        tolerance=tolerance,
                        maximum_residual=max_residual,
                        merge_markers=True)
    print("Wykryto punkty osnowy")


def RunStage2(values):

    chunk = _chunk()

    protected = set()
    manual = {}
    for m in chunk.markers:
        pinned = [c for c in m.projections.keys() if m.projections[c].pinned]
        manual[m.label] = len(pinned)
        protected.update((m.key, c.key) for c in pinned)

    measured = [m for m in chunk.markers if manual[m.label] >= 2]
    if len(measured) < 3:
        print("Pomierz ręcznie co najmniej 3 fotopunkty (każdy na co najmniej 2 zdjęciach, "
              "zielone flagi). Teraz: %d" % len(measured))
        return False

    # 1. orientacja na ręcznie pomierzonych punktach
    chunk.updateTransform()
    chunk.optimizeCameras()
    print("Orientacja na %d ręcznie pomierzonych punktach" % len(measured))

    # 2. automatyczny pomiar pozostałych rzutów
    auto = AutoMeasureMarkers(values["search_win"], values["max_dist"])

    # 3. wyrównanie z nowymi pomiarami, potem filtracja odstających
    Realign()
    removed = FilterMarkerProjections(values.get("filter_px", 1.0), protected)

    # 4. końcowa aerotriangulacja
    Realign()

    _saveStage2Info(chunk, protected, auto, removed)

    report = MarkerReport(manual, auto, removed)
    print(report)
    return report


STAGE2_META_KEY = "bsl_stage2"


def _saveStage2Info(chunk, protected, auto, removed):

    info = {"manual": sorted(list(p) for p in protected), "auto": auto, "removed": removed}
    try:
        chunk.meta[STAGE2_META_KEY] = json.dumps(info)
    except Exception as e:
        print("Nie udało się zapisać informacji o pomiarach w chunku: %s" % e)


def _loadStage2Info(chunk):
    try:
        raw = chunk.meta[STAGE2_META_KEY]
        return json.loads(raw) if raw else None
    except Exception:
        return None


def CurrentMarkerReport():
    chunk = _chunk()
    info = _loadStage2Info(chunk)
    manual_pairs = {tuple(p) for p in info["manual"]} if info else None

    manual, auto = {}, {}
    for m in chunk.markers:
        pinned = [c for c in m.projections.keys() if m.projections[c].pinned]
        if manual_pairs is None:
            manual[m.label] = len(pinned)
            continue
        n_manual = sum(1 for c in pinned if (m.key, c.key) in manual_pairs)
        manual[m.label] = n_manual
        visible = info["auto"].get(m.label, {}).get("visible", 0)
        auto[m.label] = {"found": len(pinned) - n_manual, "visible": visible}

    removed = info["removed"] if info else {}
    report = MarkerReport(manual, auto, removed)
    if info is None:
        report += ("\nUWAGA: etap 2 nie był uruchomiony na tym chunku (albo uruchomiono go "
                   "starszą wersją skryptu) - kolumna 'ręczne' zawiera wszystkie zielone flagi.")
    else:
        report += ("\n'auto' = obecne automatyczne / zdjęcia, na które punkt się rzutował "
                   "w etapie 2 (po filtracji)")
    return report


def MarkerReport(manual, auto, removed):
    chunk = _chunk()
    lines = [
        "%-6s %-8s %6s %10s %8s %8s %9s %8s %8s %8s"
        % ("punkt", "typ", "ręczne", "auto", "usunięte", "razem",
           "repr[px]", "dX[m]", "dY[m]", "dH[m]"),
        "-" * 92,
    ]
    sq = {"control": [], "check": []}

    for marker in chunk.markers:
        label = marker.label
        kind = "control" if marker.reference.enabled else "check"
        a = auto.get(label, {"visible": 0, "found": 0})
        n_total = len(marker.projections.keys())

        repr_txt = dx_txt = dy_txt = dh_txt = "-"
        if marker.position is not None:
            errs = []
            for camera in marker.projections.keys():
                if camera.transform is None:
                    continue
                proj = camera.project(marker.position)
                if proj is not None:
                    c = marker.projections[camera].coord
                    errs.append(((proj.x - c.x) ** 2 + (proj.y - c.y) ** 2) ** 0.5)
            if errs:
                repr_txt = "%.2f" % (sum(e * e for e in errs) / len(errs)) ** 0.5

            if marker.reference.location is not None:
                est = chunk.transform.matrix.mulp(marker.position)
                ref = chunk.crs.unproject(marker.reference.location)
                d = chunk.crs.localframe(ref).mulv(est - ref)
                dx_txt, dy_txt, dh_txt = ("%.3f" % d.y, "%.3f" % d.x, "%.3f" % d.z)
                sq[kind].append((d.x ** 2, d.y ** 2, d.z ** 2))

        lines.append("%-6s %-8s %6d %10s %8d %8d %9s %8s %8s %8s"
                     % (label, kind, manual.get(label, 0),
                        "%d/%d" % (a["found"], a["visible"]),
                        removed.get(label, 0), n_total,
                        repr_txt, dx_txt, dy_txt, dh_txt))

    lines.append("")
    for kind in ("control", "check"):
        if sq[kind]:
            n = len(sq[kind])
            rx, ry, rh = (sum(v[i] for v in sq[kind]) / n for i in range(3))
            lines.append("RMS %-7s (%d pkt): XY = %.3f m, H = %.3f m"
                         % (kind, n, (rx + ry) ** 0.5, rh ** 0.5))
    lines.append("")
    lines.append("auto = znalezione / zdjęcia, na które punkt się rzutuje")
    return "\n".join(lines)


def RunStage3(values):
    GenerateSelectedProducts(values["product_quality"], values["do_pointcloud"],
                             values["do_model"], values["do_dem"], values["do_ortho"])