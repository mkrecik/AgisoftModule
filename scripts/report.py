import json

from scripts.utils import ActiveChunk
from scripts.detectors import METHODS

STAGE2_META_KEY = "bsl_stage2"


def MethodHeader(method):
    return "Metoda wykrywania: %s\n\n" % METHODS.get(method, method)


def _reprojErrors(marker):
    out = []
    if marker.position is None:
        return out
    for camera in marker.projections.keys():
        if camera.transform is None:
            continue
        proj = camera.project(marker.position)
        if proj is not None:
            c = marker.projections[camera].coord
            out.append((camera, ((proj.x - c.x) ** 2 + (proj.y - c.y) ** 2) ** 0.5))
    return out


def AllReprojErrors(chunk, protected):
    out = []
    for marker in chunk.markers:
        kind = "control" if marker.reference.enabled else "check"
        for camera, err in _reprojErrors(marker):
            src = "manual" if (marker.key, camera.key) in protected else "auto"
            out.append((kind, src, err))
    return out


def _coordError(chunk, marker):
    if marker.position is None or marker.reference.location is None:
        return None
    if len(marker.projections.keys()) < 2:
        return None
    est = chunk.transform.matrix.mulp(marker.position)
    ref = chunk.crs.unproject(marker.reference.location)
    return chunk.crs.localframe(ref).mulv(est - ref)


def CoordRms(chunk):
    sq = {"control": [], "check": []}
    for marker in chunk.markers:
        d = _coordError(chunk, marker)
        if d is not None:
            kind = "control" if marker.reference.enabled else "check"
            sq[kind].append((d.x ** 2 + d.y ** 2, d.z ** 2))
    out = {}
    for kind, vals in sq.items():
        if vals:
            n = len(vals)
            out[kind] = [(sum(v[0] for v in vals) / n) ** 0.5,
                         (sum(v[1] for v in vals) / n) ** 0.5, n]
    return out


def _errStats(errs):
    if not errs:
        return "brak rzutów"
    n = len(errs)
    return ("średni %.3f px, RMS %.3f px, maks. %.3f px (n = %d)"
            % (sum(errs) / n, (sum(e * e for e in errs) / n) ** 0.5, max(errs), n))


def SaveStage2Info(chunk, protected, auto, removed, before, method):
    info = {"manual": sorted(list(p) for p in protected), "auto": auto,
            "removed": removed, "before": before, "method": method}
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
    chunk = ActiveChunk()
    info = _loadStage2Info(chunk)
    manual_pairs = {tuple(p) for p in info["manual"]} if info else None

    if info is None:
        manual = {m.label: sum(1 for c in m.projections.keys() if m.projections[c].pinned)
                  for m in chunk.markers}
        report = MarkerReport(manual, {}, {})
        report += ("\nUWAGA: etap 2 nie był uruchomiony na tym chunku.")
        return report

    manual = {m.label: sum(1 for c in m.projections.keys()
                           if (m.key, c.key) in manual_pairs)
              for m in chunk.markers}
    return MethodHeader(info.get("method", "corners")) + MarkerReport(
        manual, info["auto"], info["removed"], manual_pairs, info.get("before"))


def MarkerReport(manual, auto, removed, protected=None, before=None):
    chunk = ActiveChunk()
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
        errs = [e for _, e in _reprojErrors(marker)]
        if errs:
            repr_txt = "%.2f" % (sum(e * e for e in errs) / len(errs)) ** 0.5

        d = _coordError(chunk, marker)
        if d is not None:
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

    if protected is not None and auto:
        lines.append("")
        lines.extend(_qualitySummary(chunk, auto, removed, protected, before))
    return "\n".join(lines)


def _qualitySummary(chunk, auto, removed, protected, before):
    errs = AllReprojErrors(chunk, protected)
    auto_errs = [e for _, src, e in errs if src == "auto"]
    out = ["=" * 92, "OCENA JAKOŚCI WYKRYWANIA", "=" * 92, ""]

    # 1. średni błąd reprojekcji (po filtracji i końcowym wyrównaniu)
    out.append("1. Średni błąd reprojekcji fotopunktów")
    out.append("   wykrycia automatyczne:  " + _errStats(auto_errs))
    out.append("   pomiary ręczne:         "
               + _errStats([e for _, src, e in errs if src == "manual"]))
    out.append("   wszystkie - control:    "
               + _errStats([e for kind, _, e in errs if kind == "control"]))
    out.append("   wszystkie - check:      "
               + _errStats([e for kind, _, e in errs if kind == "check"]))
    out.append("")

    # 2. kompletność wykryć
    visible = sum(a["visible"] for a in auto.values())
    found = sum(a["found"] for a in auto.values())
    rejected = sum(removed.values())
    kept = found - rejected
    pts_visible = [l for l, a in auto.items() if a["visible"] > 0]
    pts_found = [l for l in pts_visible if auto[l]["found"] - removed.get(l, 0) > 0]

    def pct(a, b):
        return 100.0 * a / b if b else 0.0

    out.append("2. Kompletność wykryć")
    out.append("   wykryto:                %d / %d możliwych rzutów (%.1f %%)"
               % (found, visible, pct(found, visible)))
    out.append("   po filtracji:           %d / %d (%.1f %%)"
               % (kept, visible, pct(kept, visible)))
    out.append("   punkty z wykryciem:     %d / %d punktów"
               % (len(pts_found), len(pts_visible)))
    weak = sorted(l for l in pts_visible
                  if pct(auto[l]["found"] - removed.get(l, 0), auto[l]["visible"]) < 50)
    if weak:
        out.append("   < 50 %% po filtracji:    %s" % ", ".join(weak))
    out.append("")

    # 3. odporność na obserwacje odstające
    out.append("3. Odporność na obserwacje odstające")
    out.append("   odrzucone jako odstające: %d / %d wykryć (%.1f %%)"
               % (rejected, found, pct(rejected, found)))
    if before:
        out.append("   błąd reprojekcji wykryć przed filtracją: " + _errStats(before["auto_errs"]))
        out.append("   błąd reprojekcji wykryć po filtracji:    " + _errStats(auto_errs))
        rms_after = CoordRms(chunk)
        for kind in ("control", "check"):
            b, a = before["rms"].get(kind), rms_after.get(kind)
            if b and a:
                out.append("   RMS %-7s przed / po filtracji:  XY %.3f / %.3f m,  H %.3f / %.3f m"
                           % (kind, b[0], a[0], b[1], a[1]))
    return out
