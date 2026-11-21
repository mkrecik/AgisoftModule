import Metashape


def ActiveDocument():
    return Metashape.app.document


def ActiveChunk():
    return Metashape.app.document.chunk
