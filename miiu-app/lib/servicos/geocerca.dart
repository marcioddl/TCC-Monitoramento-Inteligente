import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:geolocator/geolocator.dart';

import '../modelos.dart';
import '../rotulos.dart';
import 'api.dart';
import 'armazenamento.dart';
import 'localizacao.dart';

/// Alertas de proximidade (geofencing).
///
/// Acompanha a posicao do aparelho e, a cada deslocamento relevante, pergunta
/// ao backend se ele entrou na geocerca de alguma ocorrencia validada. A
/// verificacao e feita no servidor, com o PostGIS; o aparelho nao precisa
/// conhecer as ocorrencias. Cada alerta chega uma unica vez (o backend
/// deduplica), por push do Firebase e tambem na propria resposta, que o app
/// exibe quando esta aberto.
///
/// No Android a leitura continua com o app em segundo plano gracas a um
/// servico em primeiro plano, que mostra uma notificacao fixa enquanto os
/// alertas estiverem ligados.
class ServicoGeocerca {
  ServicoGeocerca._();

  static final ServicoGeocerca instancia = ServicoGeocerca._();

  // Consulta o backend no maximo a cada intervalo, salvo deslocamento maior
  static const _intervaloMinimo = Duration(seconds: 10);
  static const _deslocamentoMinimoM = 25.0;

  final StreamController<Alerta> _alertas = StreamController<Alerta>.broadcast();
  final ValueNotifier<bool> ativo = ValueNotifier<bool>(false);
  final ValueNotifier<Position?> ultimaPosicao = ValueNotifier<Position?>(null);
  final ValueNotifier<String?> situacao = ValueNotifier<String?>(null);

  StreamSubscription<Position>? _assinatura;
  DateTime? _ultimaConsulta;
  Position? _posicaoConsultada;
  bool _consultando = false;

  Stream<Alerta> get alertas => _alertas.stream;

  /// Liga o monitoramento. Devolve null em caso de sucesso ou a mensagem de erro.
  Future<String?> ligar() async {
    final erro = await Localizacao.garantirPermissao();
    if (erro != null) return erro;

    await _assinatura?.cancel();
    final LocationSettings ajustes;
    // na web (inclusive no navegador do celular) nao ha servico em segundo plano
    if (!kIsWeb && defaultTargetPlatform == TargetPlatform.android) {
      ajustes = AndroidSettings(
        accuracy: LocationAccuracy.high,
        distanceFilter: 15,
        intervalDuration: const Duration(seconds: 5),
        foregroundNotificationConfig: ForegroundNotificationConfig(
          notificationTitle: 'MIIU: alertas de proximidade ligados',
          notificationText: 'Você será avisado ao se aproximar de um problema na via.',
          enableWakeLock: true,
        ),
      );
    } else {
      ajustes = const LocationSettings(accuracy: LocationAccuracy.high, distanceFilter: 15);
    }

    _assinatura = Geolocator.getPositionStream(locationSettings: ajustes).listen(
      _aoMover,
      onError: (Object e) {
        situacao.value = 'Erro ao ler o GPS: $e';
      },
    );
    _ultimaConsulta = null;
    _posicaoConsultada = null;
    ativo.value = true;
    situacao.value = 'Aguardando a primeira localização…';
    await Armazenamento.definirAlertas(true);
    return null;
  }

  Future<void> desligar() async {
    await _assinatura?.cancel();
    _assinatura = null;
    ativo.value = false;
    situacao.value = null;
    await Armazenamento.definirAlertas(false);
  }

  Future<void> _aoMover(Position posicao) async {
    ultimaPosicao.value = posicao;
    if (_consultando) return;

    final agora = DateTime.now();
    final anterior = _posicaoConsultada;
    final ultima = _ultimaConsulta;
    if (anterior != null && ultima != null) {
      final andou = Localizacao.distancia(
        anterior.latitude, anterior.longitude, posicao.latitude, posicao.longitude,
      );
      if (agora.difference(ultima) < _intervaloMinimo && andou < _deslocamentoMinimoM) {
        return;
      }
    }

    _consultando = true;
    try {
      final resposta = await Api.checar(posicao.latitude, posicao.longitude, posicao.accuracy);
      _ultimaConsulta = agora;
      _posicaoConsultada = posicao;
      situacao.value = resposta.ignorada ? motivoIgnorada(resposta.motivo) : null;
      for (final alerta in resposta.alertas) {
        _alertas.add(alerta);
      }
    } on ErroApi catch (e) {
      situacao.value = e.mensagem;
    } catch (e) {
      situacao.value = 'Falha na verificação de proximidade: $e';
    } finally {
      _consultando = false;
    }
  }
}
