import importlib
import Metashape
from PySide2 import QtCore, QtWidgets


for _name in ("scripts.utils", "scripts.gcp", "scripts.detectors",
              "scripts.markers", "scripts.report", "scripts.processing"):
    importlib.reload(importlib.import_module(_name))

from scripts.processing import RunStage1, RunStage2, RunStage3
from scripts.report import CurrentMarkerReport
from scripts.detectors import METHODS



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

    # Nazwa chunka - 0-1, 0 
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
        Metashape.app.getOpenFileName("Plik z osnową (*.csv, *.txt)", filter="*.csv *.txt")
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

    # SEKCJA 2b - Automatyczny pomiar osnowy
    box_gcp = QtWidgets.QGroupBox("Automatyczny pomiar osnowy")
    grid_gcp = QtWidgets.QGridLayout(box_gcp)
    grid_gcp.setColumnStretch(0, 1)
    grid_gcp.setColumnStretch(1, 1)

    # Metoda wykrywania - 0-1, 0-1
    method_combo = QtWidgets.QComboBox()
    for key, text in METHODS.items():
        method_combo.addItem(text, key)
    grid_gcp.addWidget(QtWidgets.QLabel("Metoda wykrywania fotopunktów"), 0, 0, 1, 2)
    grid_gcp.addWidget(method_combo, 1, 0, 1, 2)

    # Parametry wspólne - 2-3
    max_dist_spin = QtWidgets.QDoubleSpinBox()
    max_dist_spin.setRange(1, 200)
    max_dist_spin.setValue(15)
    grid_gcp.addWidget(QtWidgets.QLabel("Maks. odległość od przybliżenia [px]"), 2, 0)
    grid_gcp.addWidget(max_dist_spin, 3, 0)

    # Parametry detektora narożników - 4-5
    search_win_label = QtWidgets.QLabel("Okno wyszukiwania wokół rzutu [px]")
    search_win_spin = QtWidgets.QSpinBox()
    search_win_spin.setRange(10, 500)
    search_win_spin.setSingleStep(10)
    search_win_spin.setValue(50)
    grid_gcp.addWidget(search_win_label, 4, 0)
    grid_gcp.addWidget(search_win_spin, 5, 0)

    # Parametry detektora Metashape - 4-5
    tolerance_label = QtWidgets.QLabel("Tolerancja detektora [0-100]")
    tolerance_spin = QtWidgets.QSpinBox()
    tolerance_spin.setRange(0, 100)
    tolerance_spin.setValue(50)
    grid_gcp.addWidget(tolerance_label, 4, 0)
    grid_gcp.addWidget(tolerance_spin, 5, 0)

    max_residual_label = QtWidgets.QLabel("Maks. odchyłka detektora [px]")
    max_residual_spin = QtWidgets.QDoubleSpinBox()
    max_residual_spin.setRange(0.1, 100)
    max_residual_spin.setValue(5)
    grid_gcp.addWidget(max_residual_label, 4, 1)
    grid_gcp.addWidget(max_residual_spin, 5, 1)

    method_widgets = {
        "metashape": [tolerance_label, tolerance_spin, max_residual_label, max_residual_spin],
        "corners": [search_win_label, search_win_spin],
    }

    def update_method_params():
        current = method_combo.currentData()
        for key, widgets in method_widgets.items():
            for w in widgets:
                w.setVisible(key == current)

    method_combo.currentIndexChanged.connect(lambda *a: update_method_params())
    update_method_params()

    gcp_info = QtWidgets.QLabel(
        "Przed uruchomieniem pomierz ręcznie w Metashape co najmniej 3 fotopunkty "
        "(każdy na co najmniej 2 zdjęciach).")
    gcp_info.setWordWrap(True)

    # Filtracja osnowy
    box_filter = QtWidgets.QGroupBox("Filtracja osnowy")
    grid_filter = QtWidgets.QGridLayout(box_filter)
    grid_filter.setColumnStretch(0, 1)
    grid_filter.setColumnStretch(1, 1)

    filter_spin = QtWidgets.QDoubleSpinBox()
    filter_spin.setRange(0.1, 20)
    filter_spin.setSingleStep(0.1)
    filter_spin.setDecimals(2)
    filter_spin.setValue(1.0)
    grid_filter.addWidget(QtWidgets.QLabel("Próg filtracji (błąd reprojekcji) [px]"), 0, 0)
    grid_filter.addWidget(filter_spin, 1, 0)

    tab_gcp = QtWidgets.QWidget()
    tab_gcp_layout = QtWidgets.QVBoxLayout(tab_gcp)
    tab_gcp_layout.addWidget(gcp_info)
    tab_gcp_layout.addWidget(box_gcp)
    tab_gcp_layout.addWidget(box_filter)
    tab_gcp_layout.addStretch(1)
    tabs.addTab(tab_gcp, "Pomiar osnowy")

    # SEKCJA 3 - Parametry generowania produktów
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
    model_check = QtWidgets.QCheckBox("Model siatkowy z teksturą")
    model_check.setChecked(True)
    dem_check = QtWidgets.QCheckBox("NMT")
    ortho_check = QtWidgets.QCheckBox("Ortomozaika")
    grid2.addWidget(pointcloud_check, 2, 0)
    grid2.addWidget(model_check, 3, 0)
    grid2.addWidget(dem_check, 4, 0)
    grid2.addWidget(ortho_check, 5, 0)

    # Zależności produktów: ortofotomapa wymaga NMT, NMT wymaga chmury punktów
    def on_ortho(checked):
        if checked:
            dem_check.setChecked(True)

    def on_dem(checked):
        if checked:
            pointcloud_check.setChecked(True)
        else:
            ortho_check.setChecked(False)

    def on_pointcloud(checked):
        if not checked:
            dem_check.setChecked(False)

    ortho_check.toggled.connect(on_ortho)
    dem_check.toggled.connect(on_dem)
    pointcloud_check.toggled.connect(on_pointcloud)

    tab2 = QtWidgets.QWidget()
    tab2_layout = QtWidgets.QVBoxLayout(tab2)
    tab2_layout.addWidget(box2)
    tab2_layout.addStretch(1)
    tabs.addTab(tab2, "Produkty")

    main_layout.addWidget(tabs)

    # PRZYCISKI: zakładka 1 - etap 1, zakładka 2 - generowanie produktów
    stage1_btn = QtWidgets.QPushButton("Uruchom etap 1")
    tab1_layout.addWidget(stage1_btn)

    stage2_btn = QtWidgets.QPushButton("Uruchom etap 2")
    tab_gcp_layout.addWidget(stage2_btn)

    report_btn = QtWidgets.QPushButton("Pokaż raport osnowy")
    tab_gcp_layout.addWidget(report_btn)
    report_btn.clicked.connect(
        lambda: show_report("Raport osnowy", CurrentMarkerReport()))

    stage3_btn = QtWidgets.QPushButton("Uruchom etap 3")
    tab2_layout.addWidget(stage3_btn)

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
            box = QtWidgets.QMessageBox(dlg)
            box.setIcon(QtWidgets.QMessageBox.Information)
            box.setWindowTitle("Etap 1 zakończony")
            box.setText("Orientacja zakończona.\nPomierz ręcznie co najmniej 3 fotopunkty "
                        "w Metashape, a potem uruchom etap 2 w zakładce „Pomiar osnowy”.")
            box.setStyleSheet("QLabel#qt_msgbox_label { min-width: 420px; font-size: 10pt; }")
            box.exec_()

    def on_stage2():
        values = get_values()
        dlg.setEnabled(False)
        QtWidgets.QApplication.processEvents()
        try:
            report = RunStage2(values)
        except Exception as e:
            report = False
            QtWidgets.QMessageBox.warning(dlg, "Błąd", str(e))
        finally:
            dlg.setEnabled(True)

        if report:
            tabs.setCurrentIndex(2)
            show_report("Etap 2 zakończony – raport osnowy", report)
        else:
            QtWidgets.QMessageBox.warning(
                dlg, "Etap 2 przerwany",
                "Pomierz ręcznie co najmniej 3 fotopunkty (każdy na co najmniej "
                "2 zdjęciach). Szczegóły w konsoli Metashape.")

    def show_report(title, text):
        rep = QtWidgets.QDialog(dlg)
        rep.setWindowTitle(title)
        rep.resize(860, 680)
        lay = QtWidgets.QVBoxLayout(rep)
        view = QtWidgets.QPlainTextEdit(text)
        view.setReadOnly(True)
        view.setLineWrapMode(QtWidgets.QPlainTextEdit.NoWrap)
        font = view.font()
        font.setFamily("Consolas")
        font.setStyleHint(font.Monospace)
        view.setFont(font)
        lay.addWidget(view)
        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok)
        btns.accepted.connect(rep.accept)
        lay.addWidget(btns)
        rep.exec_()

    def on_stage3():
        values = get_values()
        print("Parametry z okna:")
        for key, value in values.items():
            print("  %s = %s" % (key, value))
        dlg.close()
        QtWidgets.QApplication.processEvents()
        RunStage3(values)

    stage1_btn.clicked.connect(on_stage1)
    stage2_btn.clicked.connect(on_stage2)
    stage3_btn.clicked.connect(on_stage3)

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
            "search_win": search_win_spin.value(),
            "max_dist": max_dist_spin.value(),
            "filter_px": filter_spin.value(),
            "gcp_method": method_combo.currentData(),
            "tolerance": tolerance_spin.value(),
            "max_residual": max_residual_spin.value(),
        }

    dlg.setWindowModality(QtCore.Qt.NonModal)
    dlg.show()
    _wizard_dlg = dlg
    return dlg


_wizard_dlg = None


# run_wizard()

Metashape.app.removeMenuItem("Przetwórz BSL")
Metashape.app.addMenuItem("Przetwórz BSL", run_wizard)