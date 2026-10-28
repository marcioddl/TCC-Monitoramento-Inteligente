import 'package:flutter/foundation.dart';
import 'package:latlong2/latlong.dart';

/// Sinais compartilhados entre as telas, sem pacote de gerencia de estado.
class Estado {
  /// Incrementado a cada novo reporte, para a lista "Minhas" recarregar.
  static final ValueNotifier<int> versaoReportes = ValueNotifier<int>(0);

  /// Ponto que o mapa deve centralizar (ex.: ao tocar em "Ver no mapa").
  static final ValueNotifier<LatLng?> focoNoMapa = ValueNotifier<LatLng?>(null);
}
