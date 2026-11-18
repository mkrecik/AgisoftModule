import Metashape
import importlib
import pipeline_functions
importlib.reload(pipeline_functions)
from pipeline_functions import RunStage1, RunStage2

try:
    from PySide2 import QtCore, QtWidgets
except ImportError:
    from PySide6 import QtCore, QtWidgets


def run_wizard():
    global _wizard_dlg
    dlg = QtWidgets.QDialog(QtWidgets.QApplication.activeWindow())
    dlg.setWindowTitle("Pomocnik przetwarzania BSL")
    dlg.setMinimumWidth(720)
    main_layout = QtWidgets.QVBoxLayout(dlg)

    crs = {"gcp": None, "chunk": None}

    # SEKCJA 1 - Wczytanie zdjęć i osnowy, wybranie układu współrzędnych
    box1 = QtWidgets.QGroupBox("Dane wejściowe")
    grid1 = QtWidgets.QGridLayout(box1)
    for c in range(2):
        grid1.setColumnStretch(c, 1)

    # Nazwa chunka - 0-1, 0 (przez obie kolumny)
    chunk_name_edit = QtWidgets.QLineEdit()
    chunk_name_edit.setPlaceholderText("Chunk 1")
    grid1.addWidget(QtWidgets.QLabel("Nazwa chunka"), 0, 0, 1, 2)
    grid1.addWidget(chunk_name_edit, 1, 0, 1, 2)

    # Katalog ze zdjęciami - 2-3, 0
    photos_edit = QtWidgets.QLineEdit()
    photos_btn = QtWidgets.QPushButton("...")
    photos_btn.setFixedWidth(32)
    photos_btn.clicked.connect(lambda: photos_edit.setText(
        Metashape.app.getExistingDirectory("Katalog ze zdjęciami")
        or photos_edit.text()))
    photos_row = QtWidgets.QHBoxLayout()
    photos_row.addWidget(photos_edit)
    photos_row.addWidget(photos_btn)
    grid1.addWidget(QtWidgets.QLabel("Katalog ze zdjęciami"), 2, 0)
    grid1.addLayout(photos_row, 3, 0)

    # Układ projektu - 2-3, 1
    chunk_crs_edit = QtWidgets.QLineEdit()
    chunk_crs_edit.setReadOnly(True)
    chunk_crs_edit.setPlaceholderText("Wybierz układ współrzędnych")
    chunk_crs_btn = QtWidgets.QPushButton("...")
    chunk_crs_btn.setFixedWidth(32)

    # Plik osnowy - 4-5, 0
    gcp_edit = QtWidgets.QLineEdit()
    gcp_btn = QtWidgets.QPushButton("...")
    gcp_btn.setFixedWidth(32)
    gcp_btn.clicked.connect(lambda: gcp_edit.setText(
        Metashape.app.getOpenFileName("Plik *.txt z osnową", filter="*.csv *.txt")
        or gcp_edit.text()))
    gcp_row = QtWidgets.QHBoxLayout()
    gcp_row.addWidget(gcp_edit)
    gcp_row.addWidget(gcp_btn)
    grid1.addWidget(QtWidgets.QLabel("Plik z punktami osnowy"), 4, 0)
    grid1.addLayout(gcp_row, 5, 0)

    # Układ osnowy - 4-5, 1
    gcp_crs_edit = QtWidgets.QLineEdit()
    gcp_crs_edit.setReadOnly(True)
    gcp_crs_edit.setPlaceholderText("Wybierz układ współrzędnych")
    gcp_crs_btn = QtWidgets.QPushButton("...")
    gcp_crs_btn.setFixedWidth(32)

    def pick_gcp_crs():
        selected = Metashape.app.getCoordinateSystem("Układ osnowy")
        if selected is not None:
            crs["gcp"] = selected
            gcp_crs_edit.setText(getattr(selected, "name", None) or str(selected))

    gcp_crs_btn.clicked.connect(pick_gcp_crs)
    gcp_crs_row = QtWidgets.QHBoxLayout()
    gcp_crs_row.addWidget(gcp_crs_edit)
    gcp_crs_row.addWidget(gcp_crs_btn)
    grid1.addWidget(QtWidgets.QLabel("Układ osnowy"), 4, 1)
    grid1.addLayout(gcp_crs_row, 5, 1)


    def pick_chunk_crs():
        selected = Metashape.app.getCoordinateSystem("Uklad projektu")
        if selected is not None:
            crs["chunk"] = selected
            chunk_crs_edit.setText(getattr(selected, "name", None) or str(selected))

    chunk_crs_btn.clicked.connect(pick_chunk_crs)
    chunk_crs_row = QtWidgets.QHBoxLayout()
    chunk_crs_row.addWidget(chunk_crs_edit)
    chunk_crs_row.addWidget(chunk_crs_btn)
    grid1.addWidget(QtWidgets.QLabel("Układ projektu"), 2, 1)
    grid1.addLayout(chunk_crs_row, 3, 1)

    # SEKCJA 2 - Dokładność orientacji (zakładka 1)
    box_align = QtWidgets.QGroupBox("Orientacja")
    grid_align = QtWidgets.QGridLayout(box_align)
    grid_align.setColumnStretch(0, 1)
    grid_align.setColumnStretch(1, 1)

    align_combo = QtWidgets.QComboBox()
    for text, downscale in (("Highest", 0), ("High", 1), ("Medium", 2),
                            ("Low", 4), ("Lowest", 8)):
        align_combo.addItem(text, downscale)
    align_combo.setCurrentText("Medium")
    grid_align.addWidget(QtWidgets.QLabel("Dokładność orientacji zdjęć"), 0, 0)
    grid_align.addWidget(align_combo, 1, 0)

    # ZAKŁADKI: 1 - dane wejściowe i orientacja, 2 - produkty
    tabs = QtWidgets.QTabWidget()

    tab1 = QtWidgets.QWidget()
    tab1_layout = QtWidgets.QVBoxLayout(tab1)
    tab1_layout.addWidget(box1)
    tab1_layout.addWidget(box_align)
    tab1_layout.addStretch(1)
    tabs.addTab(tab1, "Dane wejściowe i orientacja")

    # SEKCJA 3 - Parametry generowania produktów (zakładka 2)
    box2 = QtWidgets.QGroupBox("Produkty")
    grid2 = QtWidgets.QGridLayout(box2)
    for c in range(2):
        grid2.setColumnStretch(c, 1)

    product_combo = QtWidgets.QComboBox()
    for text, value in (("Ultra High", 1), ("High", 2), ("Medium", 4), ("Low", 8), ("Lowest", 16)):
        product_combo.addItem(text, value)
    product_combo.setCurrentText("Medium")
    grid2.addWidget(QtWidgets.QLabel("Dokładność wytworzenia produktów"), 0, 0)
    grid2.addWidget(product_combo, 1, 0)

    pointcloud_check = QtWidgets.QCheckBox("Chmura punktow")
    pointcloud_check.setChecked(True)
    model_check = QtWidgets.QCheckBox("Model siatkowy z tekstura")
    model_check.setChecked(True)
    dem_check = QtWidgets.QCheckBox("NMT")
    ortho_check = QtWidgets.QCheckBox("Ortomozaika")
    grid2.addWidget(pointcloud_check, 2, 0)
    grid2.addWidget(model_check, 3, 0)
    grid2.addWidget(dem_check, 4, 0)
    grid2.addWidget(ortho_check, 5, 0)

    tab2 = QtWidgets.QWidget()
    tab2_layout = QtWidgets.QVBoxLayout(tab2)
    tab2_layout.addWidget(box2)
    tab2_layout.addStretch(1)
    tabs.addTab(tab2, "Produkty")

    main_layout.addWidget(tabs)

    # # SEKCJA 3 - Automatyczny pomiar osnowy 
    # box3 = QtWidgets.QGroupBox("Automatyczny pomiar osnowy")
    # grid3 = QtWidgets.QGridLayout(box3)
    # for c in range(3):
    #     grid3.setColumnStretch(c, 1)

    # tolerance_label = QtWidgets.QLabel("Tolerancja [0-100]")
    # tolerance_spin = QtWidgets.QSpinBox()
    # tolerance_spin.setRange(0, 100)
    # tolerance_spin.setValue(50)
    # grid3.addWidget(tolerance_label, 0, 1)
    # grid3.addWidget(tolerance_spin, 1, 1)

    # radius_spin = QtWidgets.QDoubleSpinBox()
    # radius_spin.setRange(10, 2000)
    # radius_spin.setSingleStep(10)
    # radius_spin.setValue(100)
    # grid3.addWidget(QtWidgets.QLabel("Okno poszukiwan [px]"), 0, 2)
    # grid3.addWidget(radius_spin, 1, 2)

    # outlier_spin = QtWidgets.QDoubleSpinBox()
    # outlier_spin.setRange(1, 500)
    # outlier_spin.setValue(20)
    # grid3.addWidget(QtWidgets.QLabel("Maks. odleglosc od rzutu [px]"), 2, 0)
    # grid3.addWidget(outlier_spin, 3, 0)

    # opencv_label = QtWidgets.QLabel("Parametry OpenCV (np. 7x7)")
    # opencv_edit = QtWidgets.QLineEdit("7x7")
    # grid3.addWidget(opencv_label, 2, 1)
    # grid3.addWidget(opencv_edit, 3, 1)

    # main_layout.addWidget(box3)

    # def update_visibility():
    #     method = method_combo.currentText()
    #     metashape_method = method.startswith("Metashape")
    #     tolerance_label.setVisible(metashape_method)
    #     tolerance_spin.setVisible(metashape_method)
    #     opencv_label.setVisible(not metashape_method)
    #     opencv_edit.setVisible(not metashape_method)

    # method_combo.currentIndexChanged.connect(lambda *a: update_visibility())
    # update_visibility()


    # PRZYCISKI: zakładka 1 - etap 1, zakładka 2 - generowanie produktów
    stage1_btn = QtWidgets.QPushButton("Uruchom etap 1")
    tab1_layout.addWidget(stage1_btn)

    stage2_btn = QtWidgets.QPushButton("Uruchome etap 2")
    tab2_layout.addWidget(stage2_btn)

    close_btn = QtWidgets.QPushButton("Zamknij")
    main_layout.addWidget(close_btn)
    close_btn.clicked.connect(dlg.close)

    def on_stage1():
        if not photos_edit.text().strip():
            QtWidgets.QMessageBox.warning(dlg, "Brak danych",
                                          "Podaj katalog ze zdjęciami")
            return
        if crs["chunk"] is None:
            QtWidgets.QMessageBox.warning(dlg, "Brak danych",
                                          "Wybierz układ projektu")
            return

        values = get_values()
        dlg.setEnabled(False)
        QtWidgets.QApplication.processEvents()
        try:
            ok = RunStage1(values)
        finally:
            dlg.setEnabled(True)

        if ok:
            tabs.setCurrentIndex(1)
            QtWidgets.QMessageBox.information(
                dlg, "Etap 1 zakończony",
                "Orientacja zakończona.\nPomierz ręcznie osnowę w Metashape, "
                "a potem wygeneruj produkty w zakładce „Produkty”.")

    def on_stage2():
        values = get_values()
        print("Parametry z okna:")
        for key, value in values.items():
            print("  %s = %s" % (key, value))
        dlg.close()
        QtWidgets.QApplication.processEvents()
        RunStage2(values)

    stage1_btn.clicked.connect(on_stage1)
    stage2_btn.clicked.connect(on_stage2)

    # Pobór argumentów
    def get_values():

        return {
            "chunk_name": chunk_name_edit.text().strip(),
            "photos_dir": photos_edit.text().strip(),
            "gcp_file": gcp_edit.text().strip(),
            "gcp_crs": crs["gcp"],
            "chunk_crs": crs["chunk"],
            "align_downscale": align_combo.currentData(),
            "product_quality": product_combo.currentData(),
            "do_pointcloud": pointcloud_check.isChecked(),
            "do_model": model_check.isChecked(),
            "do_dem": dem_check.isChecked(),
            "do_ortho": ortho_check.isChecked(),
            # "gcp_method": method_combo.currentText(),
            # "tolerance": tolerance_spin.value(),
            # "search_radius": radius_spin.value(),
            # "outlier_px": outlier_spin.value(),
            # "opencv_params": opencv_edit.text().strip(),
        }

    dlg.setWindowModality(QtCore.Qt.NonModal)
    dlg.show()
    _wizard_dlg = dlg
    return dlg


_wizard_dlg = None


# run_wizard()

Metashape.app.removeMenuItem("Przetwórz BSL")
Metashape.app.addMenuItem("Przetwórz BSL", run_wizard)