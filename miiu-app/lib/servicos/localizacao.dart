import 'package:geolocator/geolocator.dart';

/// Acesso ao GPS do aparelho.
class Localizacao {
  /// Garante GPS ligado e permissao concedida. Devolve null se estiver tudo
  /// certo, ou a mensagem a mostrar ao cidadao.
  static Future<String?> garantirPermissao() async {
    if (!await Geolocator.isLocationServiceEnabled()) {
      return 'Ative a localização (GPS) do aparelho.';
    }
    var permissao = await Geolocator.checkPermission();
    if (permissao == LocationPermission.denied) {
      permissao = await Geolocator.requestPermission();
    }
    if (permissao == LocationPermission.denied) {
      return 'O MIIU precisa da localização para registrar onde está o problema.';
    }
    if (permissao == LocationPermission.deniedForever) {
      return 'A permissão de localização foi negada. Libere-a nas configurações do aparelho.';
    }
    return null;
  }

  static Future<Position> posicaoAtual() => Geolocator.getCurrentPosition(
        locationSettings: const LocationSettings(
          accuracy: LocationAccuracy.best,
          timeLimit: Duration(seconds: 30),
        ),
      );

  static Future<Position?> ultimaConhecida() => Geolocator.getLastKnownPosition();

  static double distancia(double lat1, double lon1, double lat2, double lon2) =>
      Geolocator.distanceBetween(lat1, lon1, lat2, lon2);

  static Future<bool> abrirConfiguracoes() => Geolocator.openAppSettings();
}
