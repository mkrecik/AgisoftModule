import Metashape
import csv
import os
import math
import glob

doc = Metashape.app.document

def AddPhotosFromFolder(folder, chunk_name):
    photos = glob.glob(os.path.join(folder, "*.JPG")) if folder else []

    if not photos:
        print("Brak zdjęć")
        return False

    chunk = doc.addChunk()
    doc.chunk = chunk
    chunk.label = chunk_name or chunk.label
    chunk.addPhotos(photos)

    print("Wczytano zdjęcia z folderu")
    return True


def AlignCameras(downscale):
    chunk = doc.chunk
    chunk.matchPhotos(downscale=downscale, generic_preselection=False, reference_preselection=True, reset_matches = True)
    chunk.alignCameras(reset_alignment=True)
    print("Zdjęcia wyrównane")

def SetChunkCrs(crs):
    chunk = doc.chunk
    chunk.crs = crs
    print("Układ współrzędnych chunka ustawiony")


def _getMarker(chunk, Label):
    for marker in chunk.markers:
        if marker.label == Label:
            return marker
    return None

def _getCamera(chunk, Label):

    for camera in chunk.cameras:

        if camera.label == Label:
            return camera

    return None

CONTROL_POINTS = [201, 202, 204, 205, 207, 209, 210]

def ImportMarkers(src_crs, dst_crs, markers_file):
    chunk = doc.chunk
    src = src_crs
    dst = dst_crs

    markers = {}

    with open(
        markers_file, "r", encoding="utf-8"
    ) as f:
        reader = csv.reader(f, delimiter='\t')
        for row in reader:
            label, y, x, z = row
            marker = chunk
            marker = _getMarker(chunk, str(label))

            if marker is None:
                marker = chunk.addMarker()
                marker.label = label

            if (
                x != "" and y != "" and z != ""
            ):

                p = Metashape.CoordinateSystem.transform(Metashape.Vector([float(x), float(y), float(z)]), src, dst)    
                marker.reference.location = p
                marker.reference.enabled = True

            markers[label] = marker

    control_labels = {str(label) for label in CONTROL_POINTS}

    for marker in chunk.markers:
        marker.reference.enabled = marker.label in control_labels

    print("Punkty osnowy wczytane")

def GenerateSelectedProducts(downscale, do_pointcloud, do_model, do_dem, do_ortho):
    chunk = doc.chunk

    if do_pointcloud:
        chunk.buildDepthMaps(downscale=downscale, filter_mode = Metashape.AggressiveFiltering)
        chunk.buildPointCloud()

    if do_model:
        chunk.buildModel(surface_type=Metashape.Arbitrary, interpolation=Metashape.EnabledInterpolation)
        chunk.buildUV(mapping_mode=Metashape.GenericMapping)
        chunk.buildTexture(blending_mode=Metashape.MosaicBlending, texture_size=4096)

    if do_dem:
        chunk.buildDem()

    if do_ortho:
        chunk.buildOrthomosaic()

    print("Produkty wygenerowane")

def RunStage1(values):
    if not AddPhotosFromFolder(values["photos_dir"], values["chunk_name"]):
        return False
    SetChunkCrs(values["chunk_crs"])
    if values["gcp_file"] and values["gcp_crs"] is not None:
        ImportMarkers(values["gcp_crs"], values["chunk_crs"], values["gcp_file"])
    AlignCameras(values["align_downscale"])
    return True


def FilterMarkerProjections(threshold_px=1.0):
    chunk = doc.chunk
    removed = 0
    total = 0

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

    print("Filtracja osnowy: usunieto %d z %d rzutów (prog %.2f px)"
          % (removed, total, threshold_px))


def Realign():
    chunk = doc.chunk
    chunk.updateTransform()
    chunk.optimizeCameras()
    print("Wykonano ponowne wyrównanie")

def DetectMarkers(tolerance, max_residual):
    chunk = doc.chunk
    chunk.detectMarkers(target_type=Metashape.TargetType.CrossTarget, tolerance=tolerance, max_residual=max_residual)
    print("Wykryto punkty osnowy")


def RunStage2(values):
    FilterMarkerProjections(1.0)
    Realign()
    GenerateSelectedProducts(values["product_quality"], values["do_pointcloud"],
                             values["do_model"], values["do_dem"], values["do_ortho"])