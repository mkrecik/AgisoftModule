### **Okno dialogowe - parametry GUI**

**na 3**

- [x] Wybór katalogu ze zdjęciami
- [x] Wybór dokładności orientacji
- [x] Wybór poziomu szczegółowości produktów
- [x] Wybór produktów do wygenerowania: mapy głębi, gęsta chmura punktów, model siatkowy, tekstura, opcjonalnie DEM / ortofotomapa
- [x] Wybór układu współrzędnych Chunka

**na 4**

- [x] Pole do wyboru pliku CSV z punktami osnowy
- [x] Wybór układu współrzędnych pliku z osnową
- [x] Parametry metody wyszukiwania szachownic (jeśli są potrzebne)
  - [x] Okno wyszukiwania szachownicy wokół rzutu
  - [x] Maksymalna odległość wyszukiwania od przybliżenia

**na 5**

- [ ] Lista rozwijana z wyborem jednej z 3 metod wykrywania GCP
- [ ] Dynamiczna zmiana wyświetlanych parametrów po zmianie metody



### **Przetwarzanie**

**na 3**

- [x] Import zdjęć do nowego chunka `addPhotos`
- [x] Orientacja z samokalibracją `matchPhotos`  z wybranym downscale i `alignCameras`
- [x] Podział fotopunktów na wpasowania i kontolne
- [x] Generowanie wybranych produktów
- [x] Filtracja pomierzonej osnowy
- [x] Ponowne wyrównanie `optimizeCameras`

**na 4**

- [x] Import osnowy z CSV
- [x] Przeliczenie osnowy do układu docelowego chunka
- [x] Podział punktów na control i check według dodatkowej kolumny

— Ręczny pomiar 3 fotopunktów —

- [x] Orientacja zdjęć w oparciu o 3 ręcznie pomierzone punkty osnowy
- [x] Automatyczny pomiar osnowy na zdjęciach
- [x] Końcowa aeorotriangulacja `optimizeCameras`

— Automatyczny pomiar GCP —

- [x] Rzutowanie GCP na zdjęcia jako pierwsze przybliżenie `camera.project`
- [x] Wyszukiwanie szachownicy w oknie wokół rzutu

**na 5**

- [x] Wykrywanie fotopunktów dodatkowymi metodami
  - [x] Detektor narożników (Open CV
  - [x] Detektor szachownic `detectMarkers`
  - [x] Detektor ze wzoru (OpenCV, `matchTemplate`)
- [x] Obliczenie
  - [x] średni błąd reprojekcji dla fotopunktów
  - [x] kompletność wykryć
  - [x] odporność na obserwacje odstające