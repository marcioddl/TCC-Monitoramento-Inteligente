import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:uuid/uuid.dart';

const String _urlCompilada = String.fromEnvironment('API_URL');

/// Endereco padrao do backend, na ordem:
/// 1. o definido na compilacao:
///    flutter build apk --release --dart-define=API_URL=https://SEU-DOMINIO.ngrok-free.dev
/// 2. na versao web servida pelo backend (/app/), o endereco da propria pagina;
/// 3. 10.0.2.2, o "localhost" do computador visto de dentro do emulador Android.
/// O endereco tambem pode ser trocado em Ajustes.
String get urlPadrao {
  if (_urlCompilada.isNotEmpty) return _urlCompilada;
  if (kIsWeb) return Uri.base.origin;
  return 'http://10.0.2.2:8000';
}

/// Preferencias locais. O app nao tem login: o aparelho e identificado por
/// um UUID gerado na primeira execucao, e o cidadao acompanha os reportes
/// pelos numeros de protocolo guardados aqui.
class Armazenamento {
  static late SharedPreferences _prefs;

  static const _chaveDispositivo = 'device_id';
  static const _chaveUrl = 'url_api';
  static const _chaveAlertas = 'alertas_ativos';
  static const _chaveProtocolos = 'protocolos';

  static Future<void> iniciar() async {
    _prefs = await SharedPreferences.getInstance();
    if (_prefs.getString(_chaveDispositivo) == null) {
      await _prefs.setString(_chaveDispositivo, const Uuid().v4());
    }
  }

  static String get deviceId => _prefs.getString(_chaveDispositivo)!;

  static String get urlApi => _prefs.getString(_chaveUrl) ?? urlPadrao;

  static Future<void> definirUrlApi(String url) async {
    var limpa = url.trim();
    while (limpa.endsWith('/')) {
      limpa = limpa.substring(0, limpa.length - 1);
    }
    if (!limpa.startsWith('http://') && !limpa.startsWith('https://')) {
      // IP da rede local usa http; um dominio (ngrok, nuvem) usa https
      final local = RegExp(r'^(localhost|\d{1,3}(\.\d{1,3}){3})(:\d+)?$').hasMatch(limpa);
      limpa = '${local ? 'http' : 'https'}://$limpa';
    }
    await _prefs.setString(_chaveUrl, limpa);
  }

  static bool get alertasAtivos => _prefs.getBool(_chaveAlertas) ?? false;

  static Future<void> definirAlertas(bool ativos) => _prefs.setBool(_chaveAlertas, ativos);

  static List<String> get protocolos => _prefs.getStringList(_chaveProtocolos) ?? <String>[];

  static Future<void> adicionarProtocolo(String protocolo) async {
    final lista = protocolos.where((p) => p != protocolo).toList();
    lista.insert(0, protocolo);
    await _prefs.setStringList(_chaveProtocolos, lista);
  }

  static Future<void> removerProtocolo(String protocolo) async {
    final lista = protocolos.where((p) => p != protocolo).toList();
    await _prefs.setStringList(_chaveProtocolos, lista);
  }
}
