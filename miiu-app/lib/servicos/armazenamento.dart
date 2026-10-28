import 'package:shared_preferences/shared_preferences.dart';
import 'package:uuid/uuid.dart';

/// Endereco padrao do backend. 10.0.2.2 e o "localhost" do computador visto
/// de dentro do emulador Android. Num celular fisico, use o IP do computador
/// na rede Wi-Fi (ex.: http://192.168.0.10:8000), ajustavel em Ajustes.
const String urlPadrao = 'http://10.0.2.2:8000';

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
      limpa = 'http://$limpa';
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
