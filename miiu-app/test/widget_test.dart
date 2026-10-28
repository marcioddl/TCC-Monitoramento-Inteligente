// Testes de unidade do app (rodam com: flutter test).
//
// As amostras JSON abaixo foram geradas pela API real do MIIU: o teste
// garante que o app entende exatamente o formato que o backend devolve.

import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:miiu_app/modelos.dart';
import 'package:miiu_app/rotulos.dart';

const _criada = '{"protocolo": "MIIU-2026-Y6TR6J", "status": "em_triagem", "classe_informada": "buraco", "classe_detectada": null, "confianca": null, "criado_em": "2026-10-28T06:32:24.130599Z", "mensagem": "Ocorrência registrada. Ela passará por uma análise da equipe de gestão."}';
const _publica = '{"protocolo": "MIIU-2026-Y6TR6J", "status": "validada", "classe_informada": "buraco", "classe_detectada": null, "classe_final": "buraco", "confianca": null, "latitude": -5.07, "longitude": -42.8, "descricao": "Ocorrência de exemplo", "criado_em": "2026-10-28T06:32:24.130599Z", "atualizado_em": "2026-10-28T06:32:24.245083Z", "historico": [{"status": "recebida", "em": "2026-10-28T06:32:24.219430Z"}, {"status": "em_triagem", "em": "2026-10-28T06:32:24.219506Z"}, {"status": "validada", "em": "2026-10-28T06:32:24.246370Z"}], "imagem_url": "/ocorrencias/MIIU-2026-Y6TR6J/imagem"}';
const _mapa = '[{"protocolo": "MIIU-2026-Y6TR6J", "classe": "buraco", "status": "validada", "latitude": -5.07, "longitude": -42.8, "raio_m": 100, "criado_em": "2026-10-28T06:32:24.130599Z"}]';
const _proximidade = '{"alertas": [{"protocolo": "MIIU-2026-Y6TR6J", "classe": "buraco", "status": "validada", "distancia_m": 33.2, "latitude": -5.07, "longitude": -42.8, "raio_m": 100, "mensagem": "Buraco na via a 33 m de você", "canal": "app"}], "ignorada": false, "motivo": null, "verificado_em": "2026-10-28T06:32:24.278545Z"}';

void main() {
  group('contrato com a API', () {
    test('ocorrencia criada', () {
      final o = OcorrenciaCriada.fromJson(jsonDecode(_criada) as Map<String, dynamic>);
      expect(o.protocolo, startsWith('MIIU-'));
      expect(o.status, 'em_triagem');
      expect(o.classeDetectada, isNull);
      expect(o.mensagem, contains('Ocorrência'));
    });

    test('consulta publica com historico', () {
      final o = OcorrenciaPublica.fromJson(jsonDecode(_publica) as Map<String, dynamic>);
      expect(o.status, 'validada');
      expect(o.historico.map((e) => e.status), ['recebida', 'em_triagem', 'validada']);
      expect(o.latitude, closeTo(-5.07, 1e-9));
      expect(o.imagemUrl, endsWith('/imagem'));
    });

    test('pontos do mapa', () {
      final pontos = (jsonDecode(_mapa) as List<dynamic>)
          .map((e) => PontoMapa.fromJson(e as Map<String, dynamic>))
          .toList();
      expect(pontos, hasLength(1));
      expect(pontos.first.raioM, 100);
    });

    test('resposta de proximidade com alerta', () {
      final r = RespostaProximidade.fromJson(jsonDecode(_proximidade) as Map<String, dynamic>);
      expect(r.ignorada, isFalse);
      expect(r.alertas.single.distanciaM, lessThan(100));
      expect(r.alertas.single.mensagem, contains('Buraco na via'));
    });

    test('numeros inteiros no JSON sao aceitos onde se espera double', () {
      final p = PontoMapa.fromJson({
        'protocolo': 'MIIU-2026-AAAAAA',
        'classe': 'buraco',
        'status': 'validada',
        'latitude': -5,
        'longitude': -42,
        'raio_m': 100,
        'criado_em': '2026-10-28T06:32:24Z',
      });
      expect(p.latitude, -5.0);
    });
  });

  group('rotulos e formatacao', () {
    test('protocolo digitado e normalizado', () {
      expect(normalizarProtocolo('miiu-2026-7k3qxa'), 'MIIU-2026-7K3QXA');
      expect(normalizarProtocolo(' miiu 2026 7k3qxa '), 'MIIU-2026-7K3QXA');
      expect(normalizarProtocolo('MIIU-2026-O1IL0A'), 'MIIU-2026-01110A');
    });

    test('distancias', () {
      expect(formatarDistancia(85.4), '85 m');
      expect(formatarDistancia(1520), '1,5 km');
    });

    test('classes e status', () {
      expect(rotuloClasse('calcada_danificada'), 'Calçada danificada');
      expect(rotuloClasse(null), '–');
      expect(rotuloStatus('em_triagem'), 'Em análise');
      expect(corDoStatus('validada'), corAtiva);
      expect(corDoStatus('resolvida'), corEncerrada);
      expect(corDoStatus('em_triagem'), corAguardando);
    });

    test('porcentagem', () {
      expect(formatarPorcentagem(0.874), '87%');
      expect(formatarPorcentagem(null), '–');
    });
  });
}
