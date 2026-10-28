import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

import '../modelos.dart';
import 'armazenamento.dart';

class ErroApi implements Exception {
  final int? status;
  final String mensagem;

  ErroApi(this.mensagem, {this.status});

  @override
  String toString() => mensagem;
}

/// Cliente HTTP da API do MIIU.
class Api {
  static const _tempoLimite = Duration(seconds: 30);

  /// Pula a pagina de aviso do ngrok (plano gratuito) quando o backend e
  /// acessado por um tunel; nos demais casos o servidor ignora o cabecalho.
  static const _cabecalhos = {'ngrok-skip-browser-warning': '1'};
  static const _cabecalhosJson = {..._cabecalhos, 'Content-Type': 'application/json'};

  static Uri _uri(String caminho, [Map<String, String>? parametros]) {
    final uri = Uri.parse('${Armazenamento.urlApi}$caminho');
    return parametros == null ? uri : uri.replace(queryParameters: parametros);
  }

  static String urlImagem(String caminhoRelativo) => '${Armazenamento.urlApi}$caminhoRelativo';

  /// O FastAPI responde JSON sem charset; decodificar os bytes como UTF-8
  /// evita acentos quebrados ("OcorrÃªncia").
  static dynamic _json(http.Response resposta) => jsonDecode(utf8.decode(resposta.bodyBytes));

  static Future<dynamic> _tratar(Future<http.Response> chamada) async {
    final http.Response resposta;
    try {
      resposta = await chamada.timeout(_tempoLimite);
    } on TimeoutException {
      throw ErroApi('O servidor demorou demais para responder.');
    } on http.ClientException {
      // falha de rede: no Android vem de um SocketException, na web do navegador
      throw ErroApi('Sem conexão com o servidor (${Armazenamento.urlApi}). '
          'Verifique a internet e o endereço em Ajustes.');
    }

    if (resposta.statusCode >= 200 && resposta.statusCode < 300) {
      return resposta.bodyBytes.isEmpty ? null : _json(resposta);
    }

    var mensagem = 'Erro ${resposta.statusCode} no servidor.';
    try {
      final corpo = _json(resposta);
      final detalhe = corpo is Map<String, dynamic> ? corpo['detail'] : null;
      if (detalhe is String) {
        mensagem = detalhe;
      } else if (detalhe is List && detalhe.isNotEmpty) {
        mensagem = detalhe
            .map((e) => e is Map<String, dynamic> ? '${e['msg']}' : '$e')
            .join('; ');
      }
    } catch (_) {
      // corpo sem JSON: mantem a mensagem generica
    }
    throw ErroApi(mensagem, status: resposta.statusCode);
  }

  static Future<Map<String, dynamic>> saude() async =>
      await _tratar(http.get(_uri('/health'), headers: _cabecalhos)) as Map<String, dynamic>;

  /// A foto vai como bytes (e nao pelo caminho do arquivo) para funcionar
  /// tambem na versao web, que nao tem acesso ao sistema de arquivos.
  static Future<OcorrenciaCriada> reportar({
    required List<int> imagem,
    required double latitude,
    required double longitude,
    required double? precisaoM,
    required String classe,
    String? descricao,
  }) async {
    final requisicao = http.MultipartRequest('POST', _uri('/ocorrencias'))
      ..headers.addAll(_cabecalhos)
      ..fields['latitude'] = latitude.toStringAsFixed(7)
      ..fields['longitude'] = longitude.toStringAsFixed(7)
      ..fields['classe_informada'] = classe
      ..fields['device_id'] = Armazenamento.deviceId
      ..files.add(http.MultipartFile.fromBytes('imagem', imagem, filename: 'foto.jpg'));
    if (precisaoM != null) {
      requisicao.fields['precisao_m'] = precisaoM.toStringAsFixed(1);
    }
    if (descricao != null && descricao.trim().isNotEmpty) {
      requisicao.fields['descricao'] = descricao.trim();
    }

    final corpo = await _tratar(
      requisicao.send().then((enviada) => http.Response.fromStream(enviada)),
    );
    return OcorrenciaCriada.fromJson(corpo as Map<String, dynamic>);
  }

  static Future<OcorrenciaPublica> consultar(String protocolo) async {
    final corpo = await _tratar(
      http.get(_uri('/ocorrencias/${Uri.encodeComponent(protocolo)}'), headers: _cabecalhos),
    );
    return OcorrenciaPublica.fromJson(corpo as Map<String, dynamic>);
  }

  static Future<List<PontoMapa>> mapa(double latitude, double longitude, {int raioM = 3000}) async {
    final corpo = await _tratar(http.get(
      _uri('/ocorrencias/mapa', {
        'latitude': latitude.toString(),
        'longitude': longitude.toString(),
        'raio_m': raioM.toString(),
      }),
      headers: _cabecalhos,
    ));
    return (corpo as List<dynamic>)
        .map((e) => PontoMapa.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  static Future<void> registrarDispositivo({String? tokenFcm, bool? notificacoes}) async {
    final dados = <String, dynamic>{};
    if (tokenFcm != null) dados['fcm_token'] = tokenFcm;
    if (notificacoes != null) dados['notificacoes_habilitadas'] = notificacoes;
    await _tratar(http.put(
      _uri('/dispositivos/${Armazenamento.deviceId}'),
      headers: _cabecalhosJson,
      body: jsonEncode(dados),
    ));
  }

  static Future<RespostaProximidade> checar(double latitude, double longitude, double? precisaoM) async {
    final corpo = await _tratar(http.post(
      _uri('/geofence/checar'),
      headers: _cabecalhosJson,
      body: jsonEncode({
        'device_id': Armazenamento.deviceId,
        'latitude': latitude,
        'longitude': longitude,
        'precisao_m': precisaoM,
      }),
    ));
    return RespostaProximidade.fromJson(corpo as Map<String, dynamic>);
  }
}
