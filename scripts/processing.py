import os

import Metashape

from scripts.utils import ActiveDocument, ActiveChunk
from scripts.markers import ImportMarkers
from scripts.gcp import FilterMarkerProjections
from scripts.detectors import AutoMeasureMarkers, DetectMarkersMetashape
from scripts.report import (AllReprojErrors, CoordRms, MarkerReport,
                            MethodHeader, SaveStage2Info)

IMAGE_EXTENSIONS = {".jpg", ".jpeg"}



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

    doc = ActiveDocument()
    chunk = doc.addChunk()
    doc.chunk = chunk
    chunk.label = chunk_name or chunk.label
    chunk.addPhotos(photos)

    print("Wczytano %d zdjęć z folderu" % len(photos))
    return True


def AlignCameras(downscale):
    chunk = ActiveChunk()
    chunk.matchPhotos(downscale=downscale, generic_preselection=True,
                      reference_preselection=True, reset_matches=True)
    chunk.alignCameras(reset_alignment=True)
    print("Zdjęcia wyrównane")


def SetChunkCrs(crs):
    chunk = ActiveChunk()
    chunk.crs = crs
    print("Układ współrzędnych chunka ustawiony")


def Realign():
    chunk = ActiveChunk()
    chunk.updateTransform()
    chunk.optimizeCameras()
    print("Wykonano ponowne wyrównanie")


def GenerateSelectedProducts(downscale, do_pointcloud, do_model, do_dem, do_ortho):
    chunk = ActiveChunk()

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


def RunStage2(values):

    chunk = ActiveChunk()

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
    method = values.get("gcp_method", "corners")
    if method == "metashape":
        auto = DetectMarkersMetashape(values["tolerance"], values["max_residual"],
                                      values["max_dist"])
    else:
        auto = AutoMeasureMarkers(values["search_win"], values["max_dist"])

    # 3. wyrównanie z nowymi pomiarami, potem filtracja odstających
    Realign()
    before = {
        "auto_errs": [e for kind, src, e in AllReprojErrors(chunk, protected) if src == "auto"],
        "rms": CoordRms(chunk),
    }
    removed = FilterMarkerProjections(values.get("filter_px", 1.0), protected)

    # 4. końcowa aerotriangulacja
    Realign()

    SaveStage2Info(chunk, protected, auto, removed, before, method)

    report = MethodHeader(method) + MarkerReport(manual, auto, removed, protected, before)
    print(report)
    return report


def RunStage3(values):
    GenerateSelectedProducts(values["product_quality"], values["do_pointcloud"],
                             values["do_model"], values["do_dem"], values["do_ortho"])
